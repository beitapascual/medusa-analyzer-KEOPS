from pathlib import Path

from medusa_analyzer.backend.io import load_edf_file
from medusa_analyzer.frontend.widgets import LoadDataAction, LoadDataWidget, WorkerCall, load_files


class EEGLoadDataWidget(LoadDataWidget):
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__(
            config=defaults.get("load_data", {}), # allowed extensions
            state=state,
            actions=[
                LoadDataAction(
                    id="eeg_files",
                    label="Select EDF files",
                    select=lambda widget: widget.select_files("Select recordings"),
                    build_call=lambda paths: WorkerCall(function=load_files, args=(load_edf_file, paths)),
                    display_names=lambda paths: [Path(path).name for path in paths],
                    status_text=lambda paths: f"Reading {len(paths)} recording(s)...",
                    overlay_text="Reading recordings...",
                )
            ],
            title="Load EEG data",
            description="Select one or more EDF files.")

    # Hacemos override de varias funciones para añadir la información de la broadband.
    # Lo hacemos aquí para no acoplar el LoadDataWidget al EEG.
    def _loaded(self, results: list[dict]) -> None:
        super()._loaded(results)
        sampling_rates = [float(metadata["sampling_rate"]) for metadata in self.state.get("metadata_list", [])
            if metadata.get("sampling_rate") is not None and metadata.get("sampling_rate") > 0]
        nyquist = float(sampling_rates[0]/2)
        self.state["broadband"] = {"id": "broadband", "title": "Broadband", "enabled": True,
                                   "low_cut": 0.1, "high_cut": nyquist}
        self.changed.emit()

    def _clear_loaded_state(self) -> None:
        """ Borrar broadband si el usuario carga otros archivos."""
        super()._clear_loaded_state()
        self.state.pop("broadband", None)
