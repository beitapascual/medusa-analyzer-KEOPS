import re
import scipy
import h5py
from pathlib import Path
from typing import Dict, List, Union, Tuple

VALID_BIDS_ENTITIES = ['sub', 'ses', 'task', 'acq', 'run', 'recording']
accepted_suffix = '_rec'

def validate_input(path: str, validation_type: str, extensions: Tuple[str, ...] = ('.mat', '.h5py')) -> Dict[str, Union[bool, List[str]]]:
    """
    Valida un árbol de directorios para asegurar que los archivos .mat
    y sus carpetas contenedoras siguen la convención estándar de BIDS.
    """

    path = Path(path)
    errors: List[str] = []

    if type not in ('studio', 'files'):
        return {"valid": False, "errors": [f"Unknown input validation type: {validation_type}"]}

    if not path.is_dir():
        return {"valid": False, "errors": [f"Selected path does not exist or is not a directory: {path}"]}

    # Expresión regular para validar el formato de una entidad BIDS (ej. sub-01, task-rest)
    bids_entity_pattern = re.compile(r'^[a-zA-Z0-9]+-[a-zA-Z0-9]+$')

    # Iterar de forma recursiva buscando solo archivos con las extensiones indicadas
    files = []
    for ext in extensions:
        files.extend(path.rglob(f"*.{ext}"))

    if not files:
        # 4. Crear un mensaje de error más informativo
        extension_list_str = ", ".join([f".{ext}" for ext in extensions])
        errors.append(f"No files with the following extensions were found: {extension_list_str}.")

    for file in files:
        # Ignorar archivos o carpetas ocultas (que empiezan por .)
        if any(part.startswith('.') for part in file.parts):
            continue

        is_valid = False
        if validation_type == 'files':
            if file.endswith('.mat'):
                # Cargar fichero .mat
                data = scipy.io.loadmat(file)
                is_valid = 'BIDS' in data
            elif file.endswith('.h5') or file.endswith('.hdf5'):
                # Cargar fichero HDF5
                with h5py.File(file, 'r') as hf:
                    is_valid = 'BIDS' in hf

            # Comprobar si 'BIDS' es una de las claves en el diccionario cargado
            if not is_valid:
                errors.append(
                    f"[{file}] File does not contain a 'BIDS' field. Please, verify you have recorded it with the proper MEDUSA version (≥2026).")
                continue
        else:
            relative_path = file.relative_to(path)
            relative_path_parts = relative_path.parts

            filename = file.stem # Remove the extension from the filename
            filename_parts = filename.split('_')

            entities_file = {}

            # 1. Validar que el nombre del archivo contiene entidades correctas y en orden
            if filename_parts[-1] != accepted_suffix:
                errors.append(
                    f"[{filename}] Suffix {filename_parts[-1]} is not valid. MEDUSA Studio files must end with {accepted_suffix}.")
                continue

            last_entity_index = -1
            for part in filename_parts[:-1]: # El último elemento en BIDS suele ser el sufijo (ej. 'eeg', 'meg', 'bold'), no una entidad
                if not bids_entity_pattern.match(part):
                    errors.append(
                        f"[{filename}] Entity {part} is not valid. It should follow the format 'key-value'.")
                    continue

                key, value = part.split('-', 1)
                if key not in VALID_BIDS_ENTITIES:
                    errors.append(
                        f"[{filename}] Entity key '{key}' is not a valid or recognized BIDS entity.")
                else:
                    current_entity_index = VALID_BIDS_ENTITIES.index(key)
                    if current_entity_index < last_entity_index:
                        errors.append(
                            f"[{filename}] Entity '{key}' is out of order. Entities must follow the established BIDS sequence.")
                    last_entity_index = current_entity_index

                entities_file[key] = value

            # 2. Comprobar que existe la entidad obligatoria 'sub'
            if 'sub' not in entities_file:
                errors.append(f"[{filename}] Mandatory entity 'sub' is missing.")
                continue

            # 3. Validar coherencia entre el nombre del archivo y el árbol de carpetas
            expected_sub = f"sub-{entities_file['sub']}"
            if expected_sub not in relative_path_parts:
                errors.append(
                    f"[{filename}] Incorrect folder structure. There is no folder named 'sub-{expected_sub}'.")

            if 'ses' in entities_file:
                expected_ses = f"ses-{entities_file['ses']}"
                if expected_ses not in relative_path_parts:
                    errors.append(
                        f"[{filename}] Incorrect folder structure. There is no folder named 'ses-{expected_ses}'.")
                elif expected_sub in relative_path_parts:
                    # Validar que 'sub' sea una carpeta padre o anterior a 'ses' en la ruta
                    sub_index = relative_path_parts.index(expected_sub)
                    ses_index = relative_path_parts.index(expected_ses)
                    if sub_index > ses_index:
                        errors.append(
                            f"[{filename}] Incorrect folder hierarchy. Folder '{expected_sub}' must appear before '{expected_ses}'.")

            # 4. Validar que los nombres de las carpetas padre sigan nomenclatura compatible con BIDS
            # Las carpetas permitidas suelen ser de tipo sub-X, ses-Y.
            # Antes hemos validado que sub y ses existan y estén en su orden, pero esto evalúa que no haya carpetas
            # inválidas ente medias
            for folder in relative_path_parts:
                is_sub = (folder == expected_sub)
                is_ses = ('ses' in entities_file and folder == expected_ses)

                if not (is_sub or is_ses):
                    errors.append(
                        f"[{relative_path}] Folder '{folder}' does not follow a recognized MEDUSA Studio naming convention.")

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }

# --- Ejemplo de Uso ---
if __name__ == "__main__":
    a = 0