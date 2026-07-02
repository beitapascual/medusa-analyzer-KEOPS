import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import h5py
import scipy.io


VALID_BIDS_ENTITIES = ["sub", "ses", "task", "acq", "run", "recording"]
ACCEPTED_RECORDING_SUFFIXES = {"recording", "rec"}
DEFAULT_SOURCE_EXTENSIONS = (".mat", ".h5", ".hdf5", ".json")


def _emit_progress(progress_callback: Callable[[int], None] | None, value: int) -> None:
    if progress_callback is not None:
        progress_callback(max(0, min(100, value)))


def _log(
    log_callback: Callable[[str, str], None] | None,
    message: str,
    level: str = "warning",
) -> None:
    if log_callback is not None:
        log_callback(message, level)


def _as_path_list(source: Path | str | List[Path] | List[str] | Tuple[Path | str, ...] | None) -> List[Path]:
    if source is None:
        return []
    if isinstance(source, (str, Path)):
        return [Path(source)]
    return [Path(item) for item in source]


def _discover_files(
    source: Path | str | List[Path] | List[str] | Tuple[Path | str, ...] | None,
    extensions: Tuple[str, ...] | None,
) -> List[Path]:
    paths = _as_path_list(source)
    discovered: list[Path] = []
    normalized_extensions = tuple(extensions or DEFAULT_SOURCE_EXTENSIONS)

    for path in paths:
        if path.is_dir():
            for extension in normalized_extensions:
                discovered.extend(path.rglob(f"*{extension}"))
        else:
            discovered.append(path)

    return list(dict.fromkeys(discovered))


def _contains_bids_field(file: Path, log_callback: Callable[[str, str], None] | None) -> bool:
    try:
        suffix = file.suffix.lower()
        if suffix == ".mat":
            data = scipy.io.loadmat(file)
            return "bids" in data
        if suffix in {".h5", ".hdf5"}:
            with h5py.File(file, "r") as hf:
                return "bids" in hf
        if suffix == ".json":
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return "bids" in data

        _log(log_callback, f"[{file}] Unsupported file extension '{file.suffix}'.")
        return False
    except Exception as exc:
        _log(log_callback, f"[{file}] Could not inspect file: {exc}.")
        return False


def _extract_studio_entities(
    file: Path,
    log_callback: Callable[[str, str], None] | None,
) -> dict[str, str] | None:
    bids_entity_pattern = re.compile(r"^[a-zA-Z0-9]+-[a-zA-Z0-9]+$")
    filename = file.stem
    filename_parts = filename.split("_")

    if not filename_parts or filename_parts[-1] not in ACCEPTED_RECORDING_SUFFIXES:
        suffixes = ", ".join(sorted(ACCEPTED_RECORDING_SUFFIXES))
        _log(
            log_callback,
            f"[{filename}] Suffix '{filename_parts[-1] if filename_parts else ''}' is not valid. "
            f"MEDUSA Studio files must end with one of: {suffixes}.",
        )
        return None

    entities_file: dict[str, str] = {}
    last_entity_index = -1
    for part in filename_parts[:-1]:
        if not bids_entity_pattern.match(part):
            _log(log_callback, f"[{filename}] Entity '{part}' is not valid. It should follow the format 'key-value'.")
            return None

        key, value = part.split("-", 1)
        if key not in VALID_BIDS_ENTITIES:
            _log(log_callback, f"[{filename}] Entity key '{key}' is not a valid or recognized BIDS entity.")
            return None

        current_entity_index = VALID_BIDS_ENTITIES.index(key)
        if current_entity_index < last_entity_index:
            _log(
                log_callback,
                f"[{filename}] Entity '{key}' is out of order. Entities must follow the established BIDS sequence.",
            )
            return None

        last_entity_index = current_entity_index
        entities_file[key] = value

    if "sub" not in entities_file:
        _log(log_callback, f"[{filename}] Mandatory entity 'sub' is missing in the file name.")
        return None

    return entities_file


def _studio_path_matches_entities(
    file: Path,
    root_path: Path | None,
    entities_file: dict[str, str],
    log_callback: Callable[[str, str], None] | None,
) -> bool:
    if root_path is None:
        return True

    try:
        relative_path_parts = file.relative_to(root_path).parts[:-1]
    except ValueError:
        relative_path_parts = file.parts[:-1]

    expected_sub = f"sub-{entities_file['sub']}"
    expected_ses = f"ses-{entities_file['ses']}" if "ses" in entities_file else None

    sub_folders = [folder for folder in relative_path_parts if folder.startswith("sub-")]
    if sub_folders and expected_sub not in sub_folders:
        _log(
            log_callback,
            f"[{file.stem}] Incorrect folder structure. Expected folder '{expected_sub}'.",
        )
        return False

    ses_folders = [folder for folder in relative_path_parts if folder.startswith("ses-")]
    if expected_ses is not None and ses_folders and expected_ses not in ses_folders:
        _log(
            log_callback,
            f"[{file.stem}] Incorrect folder structure. Expected folder '{expected_ses}'.",
        )
        return False

    if expected_ses is not None and expected_sub in relative_path_parts and expected_ses in relative_path_parts:
        sub_index = relative_path_parts.index(expected_sub)
        ses_index = relative_path_parts.index(expected_ses)
        if sub_index > ses_index:
            _log(
                log_callback,
                f"[{file.stem}] Incorrect folder hierarchy. Folder '{expected_sub}' must appear before '{expected_ses}'.",
            )
            return False

    return True


def _is_valid_converter_file(
    file: Path,
    validation_type: str,
    root_path: Path | None,
    log_callback: Callable[[str, str], None] | None,
) -> bool:
    if any(part.startswith(".") for part in file.parts):
        _log(log_callback, f"[{file}] Hidden files or folders are ignored.")
        return False

    if not file.exists() or not file.is_file():
        _log(log_callback, f"[{file}] File does not exist or is not a regular file.")
        return False

    if validation_type == "studio":
        entities_file = _extract_studio_entities(file, log_callback)
        if entities_file is None:
            return False
        if not _studio_path_matches_entities(file, root_path, entities_file, log_callback):
            return False

    if not _contains_bids_field(file, log_callback):
        _log(
            log_callback,
            f"[{file}] File does not contain a 'bids' field. Please, verify you have recorded it with "
            "the proper MEDUSA version (>=2026).",
        )
        return False

    return True


def _inspect_valid_files(
    files: List[Path],
    validation_type: str,
    root_path: Path | None,
    progress_callback: Callable[[int], None] | None,
    log_callback: Callable[[str, str], None] | None,
) -> tuple[list[Path], list[Path]]:
    valid_files: list[Path] = []
    invalid_files: list[Path] = []

    if not files:
        return valid_files, invalid_files

    for index, file in enumerate(files, start=1):
        if _is_valid_converter_file(file, validation_type, root_path, log_callback):
            valid_files.append(file)
        else:
            invalid_files.append(file)
        _emit_progress(progress_callback, int(index * 95 / len(files)))

    return valid_files, invalid_files


def summarize_source_dataset(valid_files: List[Path], invalid_files: List[Path] | None = None) -> Dict[str, Any]:
    invalid_files = invalid_files or []
    subs = set()
    tasks = set()
    sess = set()

    for file in valid_files:
        base_name = file.stem
        parts = base_name.split("_")

        for part in parts:
            if "-" not in part:
                continue
            key, value = part.split("-", 1)

            if key == "sub":
                subs.add(value)
            elif key == "ses":
                sess.add(value)
            elif key == "task":
                tasks.add(value)

    return {
        "Total files": len(valid_files),
        "Total number of files": {
            "total": len(valid_files) + len(invalid_files),
            "valid": len(valid_files),
            "invalid": len(invalid_files),
        },
        "Number of subjects": len(subs),
        "Number of sessions": len(sess),
        "Number of tasks": len(tasks),
        "Task list": sorted(tasks),
        "Valid files": [str(file) for file in valid_files],
        "Invalid files": [str(file) for file in invalid_files],
    }


def inspect_converter_source(
    files: Path | List[Path] | None = None,
    validation_type: str = "files",
    path: Path | List[Path] | None = None,
    progress_callback: Callable[[int], None] | None = None,
    log_callback: Callable[[str, str], None] | None = None,
    extensions: Tuple[str, ...] | None = None,
) -> Dict[str, Any]:
    """Inspect converter input and return a summary based only on valid files.

    The function accepts both supported loading modes:
    - validation_type="files": a single file or a list of files.
    - validation_type="studio": a directory, or a pre-discovered list of files.

    The legacy ``path`` argument is also accepted as the source when ``files``
    is not provided, which keeps the current frontend worker calls working.
    """
    if validation_type not in {"files", "studio"}:
        raise ValueError("validation_type must be 'files' or 'studio'.")

    source = files if files is not None else path
    root_path = None
    if validation_type == "studio":
        if isinstance(source, (str, Path)) and Path(source).is_dir():
            root_path = Path(source)
        elif isinstance(path, (str, Path)) and Path(path).is_dir():
            root_path = Path(path)

    _emit_progress(progress_callback, 0)
    source_files = _discover_files(source, extensions)
    if not source_files:
        extension_list_str = ", ".join(extensions or DEFAULT_SOURCE_EXTENSIONS)
        _log(log_callback, f"No files with the following extensions were found: {extension_list_str}.", "error")
        _emit_progress(progress_callback, 100)
        return summarize_source_dataset([])

    valid_files, invalid_files = _inspect_valid_files(
        source_files,
        validation_type,
        root_path,
        progress_callback,
        log_callback,
    )
    _emit_progress(progress_callback, 100)

    return summarize_source_dataset(valid_files, invalid_files)


def load_converter_source(
    input_data: Path | List[Path],
    validation_type: str,
    extensions: Tuple[str, ...] | None = None,
    progress_callback: Callable[[int], None] | None = None,
    log_callback: Callable[[str, str], None] | None = None,
) -> Dict[str, Any]:
    return inspect_converter_source(
        files=input_data,
        validation_type=validation_type,
        extensions=extensions,
        progress_callback=progress_callback,
        log_callback=log_callback,
    )


# # --- Ejemplo de Uso ---
# if __name__ == "__main__":
#     results = inspect_converter_source(
#         Path(r"D:\MEDUSA\medusa-analyzer-KEOPS\sample_data\medusa_files_new_model"),
#         "studio",
#         extensions=(".json",),
#     )
#     print(results)
