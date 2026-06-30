from importlib.metadata import metadata

from medusa_analyzer.backend.io import load_edf_file
from medusa_analyzer.frontend.widgets import LoadDataWidget


class EEGLoadDataWidget(LoadDataWidget):
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__(
            config=defaults.get("load_data", {}), # allowed extensions
            state=state,
            loader_function=load_edf_file,
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
