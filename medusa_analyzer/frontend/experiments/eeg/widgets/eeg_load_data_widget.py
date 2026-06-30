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
        self.state["broadband"] = self._build_metadata_broadband()
        self.changed.emit()

    def _build_metadata_broadband(self) -> dict | None:
        metadata_bands = [metadata.get("broadband") for metadata in self.state.get("metadata_list", [])
            if isinstance(metadata.get("broadband"), dict)]
        if not metadata_bands:
            return None
        low_cuts = [float(band["low_cut"]) for band in metadata_bands if band.get("low_cut") is not None]
        high_cuts = [float(band["high_cut"]) for band in metadata_bands if band.get("high_cut") is not None]
        if not low_cuts or not high_cuts:
            return None
        return {"id": "broadband", "title": "Broadband", "enabled": True,
                "low_cut": max(low_cuts), "high_cut": min(high_cuts)}

    def _clear_loaded_state(self) -> None:
        """ Borrar broadband si el usuario carga otros archivos."""
        super()._clear_loaded_state()
        self.state.pop("broadband", None)
