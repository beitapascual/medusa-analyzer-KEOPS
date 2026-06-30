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
        bands = defaults.get("preprocessing", {}).get("bands", {}).get("available", [])
        self._minimum_band_frequency = min((float(band["low_cut"]) for band in bands if band.get("low_cut") is not None),
            default=0.0)

    # Hacemos override de varias funciones para añadir la información de la broadband.
    # Lo hacemos aquí para no acoplar el LoadDataWidget al EEG.
    def _loaded(self, results: list[dict]) -> None:
        super()._loaded(results)
        self.state["broadband"] = self._build_metadata_broadband()
        self.changed.emit()

    def _build_metadata_broadband(self) -> dict | None:
        metadata_list = self.state.get("metadata_list", [])
        sampling_rates = [metadata.get("sampling_rate") for metadata in metadata_list
            if metadata.get("sampling_rate") is not None and metadata.get("sampling_rate") > 0]
        if not sampling_rates:
            return None
        return {"id": "broadband", "title": "Broadband", "enabled": True, "low_cut": self._minimum_band_frequency,
                "high_cut": float(min(sampling_rates) / 2)}

    def _clear_loaded_state(self) -> None:
        """ Borrar broadband si el usuario carga otros archivos."""
        super()._clear_loaded_state()
        self.state.pop("broadband", None)
