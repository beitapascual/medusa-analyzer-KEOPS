import re
import scipy
import h5py
from pathlib import Path
from typing import Dict, List, Union, Tuple, Any, Callable
import json
import warnings

VALID_BIDS_ENTITIES = ['sub', 'ses', 'task', 'acq', 'run', 'recording']
accepted_suffix = '_rec'

def inspect_converter_source(files: Path|List[Path], validation_type: str,
                             path: Path | None = None,
                             progress_callback: Callable[[int], None] | None = None,
                             log_callback: Callable[[str], None] | None = None) -> Dict[str, Union[bool, List[str]]]:
    """
    Valida un árbol de directorios para asegurar que los archivos .mat
    y sus carpetas contenedoras siguen la convención estándar de BIDS.
    """

    # Expresión regular para validar el formato de una entidad BIDS (ej. sub-01, task-rest)
    bids_entity_pattern = re.compile(r'^[a-zA-Z0-9]+-[a-zA-Z0-9]+$')

    idx_callback = 95 / len(files)

    for file in files:

        progress_callback(int(idx_callback*(files.index(file)+1) - 0.5*idx_callback))

        # Ignorar archivos o carpetas ocultas (que empiezan por .)
        if any(part.startswith('.') for part in file.parts):
            continue

        if validation_type == 'files':
            is_valid = False

            if file.suffix == '.mat':
                # Cargar fichero .mat
                data = scipy.io.loadmat(file)
                is_valid = 'bids' in data
            elif file.suffix in ['.h5','.hdf5']:
                # Cargar fichero HDF5
                with h5py.File(file, 'r') as hf:
                    is_valid = 'bids' in hf
            elif file.suffix == '.json':
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    is_valid = 'bids' in data

            # Comprobar si 'BIDS' es una de las claves en el diccionario cargado
            if not is_valid:
                log_callback(
                    f"[{file}] File does not contain a 'BIDS' field. Please, verify you have recorded it with the proper MEDUSA version (≥2026).",
                    "warning")
                continue
        else:
            relative_path = file.relative_to(path)
            relative_path_parts = relative_path.parts

            filename = file.stem # Remove the extension from the filename
            filename_parts = filename.split('_')

            entities_file = {}

            # 1. Validar que el nombre del archivo contiene entidades correctas y en orden
            if filename_parts[-1] != accepted_suffix:
                log_callback(
                    f"[{filename}] Suffix {filename_parts[-1]} is not valid. MEDUSA Studio files must end with {accepted_suffix}.",
                    "warning")
                continue

            last_entity_index = -1
            for part in filename_parts[:-1]: # El último elemento en BIDS suele ser el sufijo (ej. 'eeg', 'meg', 'bold'), no una entidad
                if not bids_entity_pattern.match(part):
                    log_callback(
                        f"[{filename}] Entity {part} is not valid. It should follow the format 'key-value'."
                        "warning")
                    continue

                key, value = part.split('-', 1)
                if key not in VALID_BIDS_ENTITIES:
                    log_callback(
                        f"[{filename}] Entity key '{key}' is not a valid or recognized BIDS entity.",
                        "warning")
                    continue
                else:
                    current_entity_index = VALID_BIDS_ENTITIES.index(key)
                    if current_entity_index < last_entity_index:
                        log_callback(
                            f"[{filename}] Entity '{key}' is out of order. Entities must follow the established BIDS sequence.",
                            "warning")
                        continue
                    last_entity_index = current_entity_index

                entities_file[key] = value

            # 2. Comprobar que existe la entidad obligatoria 'sub'
            if 'sub' not in entities_file:
                log_callback(f"[{filename}] Mandatory entity 'sub' is missing in the file name.",
                             "warning")
                continue

            # 3. Validar coherencia entre el nombre del archivo y el árbol de carpetas
            expected_sub = f"sub-{entities_file['sub']}"
            if expected_sub not in relative_path_parts:
                log_callback.append(
                    f"[{filename}] Incorrect folder structure. There is no folder named 'sub-{expected_sub}'.",
                    "warning")
                continue

            if 'ses' in entities_file:
                expected_ses = f"ses-{entities_file['ses']}"
                if expected_ses not in relative_path_parts:
                    log_callback(
                        f"[{filename}] Incorrect folder structure. There is no folder named 'ses-{expected_ses}'.",
                        "warning")
                elif expected_sub in relative_path_parts:
                    # Validar que 'sub' sea una carpeta padre o anterior a 'ses' en la ruta
                    sub_index = relative_path_parts.index(expected_sub)
                    ses_index = relative_path_parts.index(expected_ses)
                    if sub_index > ses_index:
                        log_callback(
                            f"[{filename}] Incorrect folder hierarchy. Folder '{expected_sub}' must appear before '{expected_ses}'.",
                            "warning")

            # 4. Validar que los nombres de las carpetas padre sigan nomenclatura compatible con BIDS
            # Las carpetas permitidas suelen ser de tipo sub-X, ses-Y.
            # Antes hemos validado que sub y ses existan y estén en su orden, pero esto evalúa que no haya carpetas
            # inválidas ente medias
            for folder in relative_path_parts:
                is_sub = (folder == expected_sub)
                is_ses = ('ses' in entities_file and folder == expected_ses)

                if not (is_sub or is_ses):
                    log_callback(
                        f"[{relative_path}] Folder '{folder}' does not follow a recognized MEDUSA Studio naming convention.",
                        "warning")

    return

def summarize_source_dataset(files: List[Path]) -> Dict[str, int|List[Any]]:

    subs = set()
    tasks = set()
    sess = set()

    # 1. Recorrer cada fichero para extraer la información
    for file in files:
        # .stem coge el nombre del fichero sin la extensión final (ej: .nii.gz)
        base_name = file.stem

        # Partimos el nombre por las _ para obtener las entidades BIDS
        parts = base_name.split('_')

        for part in parts:
            # Separamos la clave del valor (ej: 'sub-01' -> ['sub', '01'])
            if '-' in part:
                key, value = part.split('-', 1)

                if key == 'sub':
                    subs.add(value)
                elif key == 'ses':
                    sess.add(value)
                elif key == 'task':
                    tasks.add(value)

    # 2. Calcular el resumen a partir de la información recolectada
    total_files = len(files)
    n_subs = len(subs)
    n_tasks = len(tasks)

    # 3. Crear el diccionario final con el resumen
    return {
        "Total files": total_files,
        "Number of subjects": n_subs,
        "Number of tasks": n_tasks,
        "Task list": list(tasks)
    }

def load_converter_source(input_data: Path|List[Path], validation_type: str, extensions: Tuple[str, ...] | None = None,
                         progress_callback: Callable[[int], None] | None = None,
                         log_callback: Callable[[str], None] | None = None):

    progress_callback(0)

    if validation_type == 'studio':
        # Iterar de forma recursiva buscando solo archivos con las extensiones indicadas
        files = []
        for ext in extensions:
            files.extend(input_data.rglob(f"*{ext}"))
        if not files:
            # 4. Crear un mensaje de error más informativo
            extension_list_str = ", ".join([f"{ext}" for ext in extensions])
            log_callback(f"No files with the following extensions were found: {extension_list_str}.","error")
            return {}
        if not isinstance(files, list):
            files = [files]
        inspect_converter_source(files, validation_type, input_data, progress_callback, log_callback)
    else:
        files = input_data
        if not isinstance(files, list):
            files = [files]
        inspect_converter_source(files, validation_type, None, progress_callback, log_callback)

    progress_callback(95)
    summary = summarize_source_dataset(files)
    progress_callback(100)

    return summary

# # --- Ejemplo de Uso ---
# if __name__ == "__main__":
#     results = read_converter_input(rf'D:\MEDUSA\medusa-analyzer-KEOPS\sample_data\medusa_files_new_model', 'files', ('.json',))
#     print(results)