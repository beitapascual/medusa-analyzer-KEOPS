from pathlib import Path
import re
from typing import Any

from medusa_analyzer.backend.io import load_edf_file
from medusa_analyzer.frontend.widgets import LoadDataAction, LoadDataWidget, WorkerCall, load_files


_TASK_PATTERN = re.compile(r"(?:^|_)task[-_]([^_]+)", re.IGNORECASE)


def _build_eeg_metadata(results: list[dict], selection: Any) -> dict[str, Any]:
    if not results:
        return {}

    if isinstance(selection, (list, tuple)):
        file_paths = [str(path) for path in selection]
    elif selection is None:
        file_paths = []
    else:
        file_paths = [str(selection)]

    tasks: list[str] = []
    missing_task = False
    for path in file_paths:
        match = _TASK_PATTERN.search(Path(path).stem)
        if match is None:
            missing_task = True
            continue
        task_name = match.group(1).strip()
        if task_name:
            tasks.append(task_name)

    ordered_tasks = list(dict.fromkeys(tasks))
    if missing_task:
        ordered_tasks.append("No task")

    first_result = results[0]
    channels = list(first_result.get("channels") or [])
    return {"n_files": len(file_paths) if file_paths else len(results),
        "n_channels": int(first_result.get("n_channels") or len(channels)),
        "channel_set": channels,
        "fs": first_result.get("sampling_rate"),
        "task": ordered_tasks}


class EEGLoadDataWidget(LoadDataWidget):
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__(
            config=defaults.get("load_data", {}), # allowed extensions
            state=state,
            actions=[LoadDataAction(
                    id="eeg_files",
                    label="Select EDF files",
                    select=lambda widget: widget.select_files("Select recordings"),
                    build_call=lambda paths: WorkerCall(function=load_files, args=(load_edf_file, paths)),
                    display_names=lambda paths: [Path(path).name for path in paths],
                    status_text=lambda paths: f"Reading {len(paths)} recording(s)...",
                    overlay_text="Reading recordings...")],
            title="Load EEG data",
            description="Select one or more EDF files.",
            metadata_builder=_build_eeg_metadata,
            metadata_labels={"n_files": "Number of files",
                "n_channels": "Number of channels",
                "channel_set": "Channel set",
                "fs": "Sampling frequency",
                "task": "Tasks"})

    # Hacemos override de varias funciones para añadir la información de la broadband.
    # Lo hacemos aquí para no acoplar el LoadDataWidget al EEG.
    def _loaded(self, results: list[dict]) -> None:
        super()._loaded(results)
        nyquist = float(float(self.state["metadata"]["fs"])/2)
        self.state["broadband"] = {"id": "broadband", "title": "Broadband", "enabled": True,
                                   "low_cut": 0.1, "high_cut": nyquist}
        self.changed.emit()

    def _clear_loaded_state(self) -> None:
        """ Borrar broadband si el usuario carga otros archivos."""
        super()._clear_loaded_state()
        self.state.pop("broadband", None)
