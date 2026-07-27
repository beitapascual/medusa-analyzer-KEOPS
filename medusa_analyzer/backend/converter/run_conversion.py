from pathlib import Path
from typing import Dict, List, Union, Tuple, Callable
import json
import pandas as pd
import shutil
import time
from medusa_analyzer.backend.converter.prune_output import prune_output

SENSOR_NAMES = {'eeg': 'electrodes',
                'fnirs': 'optodes'}

def to_pascal_case(snake_str):
    """Convierte una cadena de snake_case a camelCase."""
    components = snake_str.split('_')
    return ''.join(x.title() for x in components)

def keys_to_pascal_case(data):
    """
    Recorre recursivamente diccionarios y listas para aplicar
    la conversión a camelCase exclusivamente a las claves.
    """
    if isinstance(data, dict):
        # Si es un diccionario, convierte la clave y llama recursivamente para el valor
        return {to_pascal_case(key): keys_to_pascal_case(value) for key, value in data.items()}
    elif isinstance(data, list):
        # Si es una lista, llama recursivamente sobre sus elementos por si contienen diccionarios
        return [keys_to_pascal_case(item) for item in data]
    else:
        # Caso base: devuelve el valor tal cual (int, float, str, booleanos)
        return data

def _remove_nulls(obj):
    if isinstance(obj, dict):
        return {k: _remove_nulls(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [_remove_nulls(item) for item in obj if item is not None]
    return obj

def file_to_bids(input_path: Path, output_path: Path):
    """
    Lee un archivo JSON estructurado y lo exporta en un formato compatible con BIDS.
    """

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. Extracción de entidades BIDS
    subject = data['bids'].get('subject')
    session = data['bids'].get('session')
    task = data['bids'].get('task')
    acq = data['bids'].get('acquisition')
    run = data['bids'].get('run')

    entities = []
    entities.append(f"sub-{subject}")
    if session is not None: entities.append(f"ses-{session}")
    if task is not None: entities.append(f"task-{task}")
    if acq is not None: entities.append(f"acq-{acq}")
    if run is not None: entities.append(f"run-{run}")

    base_name = "_".join(entities)

    # Construcción de la ruta del sujeto y sesión (ej. dataset/sub-01/ses-01/)
    subject_output_path = output_path / f"sub-{subject}"
    if session is not None:
        subject_output_path = subject_output_path / f"ses-{session}"

    # Get experiment info
    experiment = keys_to_pascal_case(data.get('experiment'))
    experiment['TaskInformation'] = experiment.pop('ComponentData')

    # 2. Datos de Participant guardados en el participants.tsv raíz
    sociodemographics = data['bids'].get('participant')
    if sociodemographics is not None:
        sociodemographics_file = output_path / "participants.tsv"
        row = {"participant_id": f"sub-{subject}"}
        row.update(sociodemographics)
        df_part = pd.DataFrame([row])

        # Si el TSV existe, se añade la fila al final sin rescribir el encabezado
        if sociodemographics_file.exists():
            df_part.to_csv(sociodemographics_file, mode='a', sep='\t', index=False, header=False)
        else:
            df_part.to_csv(sociodemographics_file, sep='\t', index=False)

    # 3. Carpetas de data_type (eeg, emg, etc.) y Sidecars asociados
    for data_type, content in data.get('data').items():
        full_output_path = subject_output_path / data_type
        full_output_path.mkdir(parents=True, exist_ok=True)

        # Guardado de metadata tabular como electrodes, channels o sensors en formato TSV
        chann_data = content['component_data']['channel_set']
        for key_tsv in ['channels', 'sensors']:
            current_key = chann_data.get(key_tsv)
            if current_key:
                df_tsv = pd.DataFrame(current_key).fillna('n/a')
                df_tsv = df_tsv.rename(columns={
                    'uid': 'name',
                    'ch_type': 'type',
                    'sensor_type': 'type',
                    'unit': 'units'
                })
                if key_tsv == 'sensors':
                    key_tsv = SENSOR_NAMES.get(data_type,'sensors')

                    df_tsv['x'] = df_tsv['coordinates'].str[0]
                    df_tsv['y'] = df_tsv['coordinates'].str[1]
                    df_tsv['z'] = df_tsv['coordinates'].str[2]

                    # 2. Eliminar la columna original
                    df_tsv = df_tsv.drop(columns=['coordinates'])

                df_tsv.to_csv(full_output_path / f"{base_name}_{key_tsv}.tsv", sep='\t', index=False)

        # Se genera el sidecar del datatype omitiendo el bloque pesado de la señal cruda
        sidecar = {k: v for k, v in data['sidecars'][data_type].items()}
        if experiment is not None:
            sidecar.update(experiment)

        sidecar = _remove_nulls(sidecar)  # Eliminación de campos null
        with open(full_output_path / f"{base_name}_{data_type}.json", 'w', encoding='utf-8') as f:
            json.dump(sidecar, f, indent=4)

        # 3.5 Exportación de la señal cruda a formato EDF
        component_data = content.get('component_data', {})
        # Extracción de nombres de canales
        ch_names = [str(ch.get('uid')) for ch in component_data.get('channel_set', {}).get('channels', [])]
        # Estructuración del diccionario de salida
        signal_export = {
            "fs": component_data['fs'],
            "channels": ch_names,
            "times": component_data['times'],
            "signal": component_data['signal']
        }

        # Se omite el parámetro 'indent' para evitar que el tamaño del archivo
        # crezca desproporcionadamente debido a la matriz de la señal.
        with open(full_output_path / f"{base_name}_{data_type}.mpl", 'w', encoding='utf-8') as f:
            json.dump(signal_export, f)

    # 4. Exportación de Eventos en TSV dentro de la misma jerarquía de la señal
    events = data.get('events')
    if events and 'data' in events:
        df_events = pd.DataFrame(events['data'])
        # Apply dtypes to the DataFrame
        if 'dtypes' in events:
            df_events = df_events.astype(events['dtypes'])
        # Export to TSV (BIDS uses 'n/a' for missing values)
        df_events.to_csv( subject_output_path / f"{base_name}_events.tsv", sep='\t', index=False, na_rep='n/a')

        # Generate and export JSON sidecar according to BIDS dictionary structure
        events_sidecar = {}
        for col_name, desc_text in events['descriptions'].items():
            events_sidecar[to_pascal_case(col_name)] = desc_text
        events_sidecar = _remove_nulls(events_sidecar)  # Eliminación de campos null
        with open(subject_output_path / f"{base_name}_events.json", 'w', encoding='utf-8') as f:
            json.dump(events_sidecar, f, indent=4)


def run_conversion(input_data: List[str], output_path: str, extensions: Tuple[str, ...] = ('.mat', '.h5py'),
                   progress_callback: Callable[[int], None] | None = None,
                   log_callback: Callable[[str, str], None] | None = None) -> None:
    """
    Ejecuta el proceso de conversión para la ruta especificada.

    Args:
        path: La ruta al directorio o archivo que se va a convertir.

    Returns:
        bool: Devuelve True si la conversión fue exitosa, False en caso contrario.
    """
    progress_callback(0)
    log_callback(f"MEDUSA file converter started", "")
    log_callback(f"Reading input data...", "")
    time.sleep(1)

    output_path = Path(output_path)
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        error_msg = rf"Cannot create output folder: {e}."
        log_callback(error_msg, "error")
        raise Exception(error_msg)

    if not len(input_data) == 1 and Path(*input_data).is_dir():
        root_path = Path(*input_data)
        # Iterar de forma recursiva buscando solo archivos con las extensiones indicadas
        files = []
        for ext in extensions:
            files.extend(root_path.rglob(f"*{ext}"))

        if not files:
            # 4. Crear un mensaje de error más informativo
            extension_list_str = ", ".join([f"{ext}" for ext in extensions])
            error_msg = f"No files with the following extensions were found: {extension_list_str}."
            log_callback(error_msg, "error")
            raise Exception(error_msg)
    else:
        files = [Path(file) for file in input_data]
        root_path = files[0].parent

    # Gestión de dataset_description.json en la raíz del output
    dataset_desc_src = root_path / "dataset_description.json"
    # Se evalúa solo si no existe ya en el destino para evitar sobreescrituras en bucles
    try:
        if dataset_desc_src.exists():
            shutil.copy(dataset_desc_src, output_path / "dataset_description.json")
        else:
            default_dataset_desc = {
                "Name": output_path.name,
                "BIDSVersion": "MEDUSA-derived BIDS"
            }
            with open(output_path / "dataset_description.json", 'w', encoding='utf-8') as f:
                json.dump(default_dataset_desc, f, indent=4)
    except Exception as e:
        error_msg = f"Unable to create dataset_description.json. Verify permissions."
        log_callback(error_msg, "error")
        raise Exception(error_msg)

    progress_callback(5)
    log_callback(rf"Successfully read input data","")
    log_callback(rf"{len(files)} files detected","")
    log_callback(rf"Starting conversion...","")
    time.sleep(1)

    idx_callback = 90 / len(files)

    valid_files = files.copy()
    for file in files:
        try:
            file_to_bids(file, output_path)

            progress_callback(int(idx_callback * (files.index(file) + 1) - 0.5 * idx_callback + 5))
            log_callback(f"[{file.name}] Successfully converted", "")
            time.sleep(1)
        except Exception as e:
            error_msg = f"[{file.name}] Exception {e} during conversion"
            log_callback(error_msg, "error")
            valid_files.remove(file)

    progress_callback(95)
    log_callback(rf"Successfully converted {len(valid_files)} files","")
    log_callback(rf"Starting inheritance-based file pruning...","")
    time.sleep(1)

    try:
        prune_output(output_path)
    except Exception as e:
        error_msg = f"Exception during dataset inheritance-based file pruning: {e}"
        log_callback(error_msg, "error")
        raise Exception(error_msg)

    progress_callback(100)
    log_callback(rf"Inheritance-based file pruning successfully run","")
    log_callback(rf"Conversion completed: {len(valid_files)} of {len(files)} files converted successfully","")


    return