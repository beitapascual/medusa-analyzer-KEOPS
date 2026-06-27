from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from medusa_analyzer.frontend.experiments.eeg.widgets.frequency_bands_table import EEGFrequencyBandsTable
from medusa_analyzer.frontend.models import Validation
from medusa_analyzer.frontend.widgets.filtering import (FilterControls, FilterPreviewPlot, FilterResponse,
    build_filter_defaults, compute_filter_response, filter_response_error)


_preprocessing_validation = Validation()


class EEGPreprocessingWidget(QScrollArea):
    changed = Signal()
    _minimum_band_frequency = 0.1

    # Este paso construye y mantiene el estado de preprocesado EEG. Aquí se
    # sincronizan filtros, preview de respuesta y bandas de frecuencia.
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__()
        _ = experiment_info
        self.config = defaults.get("preprocessing", {})
        self.state = state

        # Guardamos una copia desacoplada de las bandas configuradas para usarla
        # como referencia de defaults y para los resets de la tabla.
        self.default_frequency_bands = self._copy_configured_frequency_bands()

        existing_values = self.state.get("preprocessing") or {}
        if not existing_values:
            existing_values = self._build_default_state()
            self.state["preprocessing"] = existing_values
        self.values = existing_values
        self.values.setdefault("selected_frequency_bands", [])
        self.values.setdefault("broadband", None)
        self._filters_are_valid = False

        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(4, 4, 12, 4)
        root.setSpacing(16)

        heading = QLabel("Pre-processing")
        heading.setObjectName("pageTitle")
        subtitle = QLabel("Tune the defaults that will be applied to the EEG recording.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(heading)
        root.addWidget(subtitle)
        root.addSpacing(16)

        car_panel = QFrame()
        car_panel.setProperty("role", "surface-panel")
        car_layout = QVBoxLayout(car_panel)
        car_layout.setContentsMargins(24, 20, 24, 20)
        car_title = QLabel("CAR")
        car_title.setObjectName("panelTitle")
        self.car_checkbox = QCheckBox("Apply common average reference")
        self.car_checkbox.setChecked(bool(self.values.get("car_checked", False)))
        car_layout.addWidget(car_title)
        car_layout.addWidget(self.car_checkbox)
        root.addWidget(car_panel)

        filters_grid = QGridLayout()
        filters_grid.setContentsMargins(0, 0, 0, 0)
        filters_grid.setHorizontalSpacing(16)
        filters_grid.setVerticalSpacing(16)
        filters_grid.setColumnStretch(0, 5)
        filters_grid.setColumnStretch(1, 7)
        filters_grid.setRowStretch(0, 1)
        filters_grid.setRowStretch(1, 1)

        filter_options = self.config.get("filter_options", {})
        fir = filter_options.get("fir", {})
        iir = filter_options.get("iir", {})

        self.notch = FilterControls("Notch filter", self.values["notch"], fir, iir, "bandstop")
        self.bandpass = FilterControls("Bandpass filter", self.values["bandpass"], fir, iir, "bandpass")
        self.notch.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.bandpass.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.notch_plot_panel = self._build_filter_plot_panel("Notch filter response", "notch_plot")
        self.bandpass_plot_panel = self._build_filter_plot_panel("Bandpass filter response", "bandpass_plot")

        filters_grid.addWidget(self.notch, 0, 0)
        filters_grid.addWidget(self.notch_plot_panel, 0, 1)
        filters_grid.addWidget(self.bandpass, 1, 0)
        filters_grid.addWidget(self.bandpass_plot_panel, 1, 1)
        root.addLayout(filters_grid)

        bands_panel = QFrame()
        bands_panel.setProperty("role", "surface-panel")
        bands_layout = QVBoxLayout(bands_panel)
        bands_layout.setContentsMargins(24, 20, 24, 20)
        bands_title = QLabel("Frequency bands")
        bands_title.setObjectName("panelTitle")
        bands_layout.addWidget(bands_title)
        self.bands = EEGFrequencyBandsTable(self.values["frequency_bands"],
            default_rows=self.default_frequency_bands)
        bands_layout.addWidget(self.bands)
        root.addWidget(bands_panel)
        root.addStretch()

        self.setWidget(content)

        self.car_checkbox.toggled.connect(self._sync)
        self.notch.changed.connect(self._sync)
        self.bandpass.changed.connect(self._sync)
        self.bands.changed.connect(self._sync)
        self._sync()

    def _build_default_state(self) -> dict[str, Any]:
        # Estado inicial coherente con defaults.json.
        return {
            "car_checked": bool(self.config.get("car", {}).get("checked_by_default", False)),
            "notch": build_filter_defaults(self.config.get("notch", {}), "bandstop"),
            "bandpass": build_filter_defaults(self.config.get("bandpass", {}), "bandpass"),
            "frequency_bands": self._copy_configured_frequency_bands(),
            "selected_frequency_bands": [],
        }

    def _build_filter_plot_panel(self, title: str, plot_attribute: str) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(24, 20, 24, 20)
        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        plot = FilterPreviewPlot()
        setattr(self, plot_attribute, plot)
        panel_layout.addWidget(title_label)
        panel_layout.addWidget(plot)
        return panel

    def _copy_configured_frequency_bands(self) -> list[dict[str, Any]]:
        return [deepcopy(band) for band in self.config.get("bands", {}).get("available", [])]

    def _resolve_sampling_rate(self) -> float | None:
        # Si hay varios registros cogemos la menor fs, porque es la que marca el
        # limite de Nyquist mas restrictivo.
        metadata_list = self.state.get("metadata_list") or []
        sampling_rates = [metadata.get("sampling_rate") for metadata in metadata_list
            if metadata.get("sampling_rate") is not None and metadata.get("sampling_rate") > 0]
        if sampling_rates:
            return min(sampling_rates)
        return None

    def _set_preprocessing_enabled(self, enabled: bool) -> None:
        self.car_checkbox.setEnabled(enabled)
        self.notch.setEnabled(enabled)
        self.bandpass.setEnabled(enabled)
        self.bands.setEnabled(enabled)

    def _update_filter_feedback(self, controls: FilterControls, plot: FilterPreviewPlot,
        config: dict[str, Any], fs: float, mode: str) -> tuple[FilterResponse | None, bool]:
        # Intentamos calcular la respuesta. Si la configuracion no pasa las
        # validaciones basicas reutilizamos el mensaje del modulo de filtering.
        response = compute_filter_response(config, fs, mode, fir_options=controls.fir, iir_options=controls.iir)
        if config.get("enabled", True) and response is None:
            error_message = filter_response_error(config, fs, fir_options=controls.fir, iir_options=controls.iir)
            controls.set_error_message(error_message)
            plot.set_response(None, error_message)
            return None, False

        controls.set_error_message(None)
        plot.set_response(response)
        return response, True

    @staticmethod
    def _active_bandpass_bounds(bandpass_config: dict[str, Any]) -> tuple[float, float] | None:
        if not bandpass_config.get("enabled", True):
            return None
        try:
            return Validation.coerce_float(bandpass_config["low_cut"]), Validation.coerce_float(
                bandpass_config["high_cut"])
        except (KeyError, ValueError):
            return None

    @staticmethod
    def _notch_bandpass_errors(notch_config: dict[str, Any], *, label: str,
        bandpass_bounds: tuple[float, float] | None = None, **_: Any) -> list[str]:
        # Esta es la regla personalizada del paso de preprocessing:
        # si hay bandpass activo, el notch tiene que vivir dentro de ese rango.
        _ = label
        if not notch_config.get("enabled", True) or bandpass_bounds is None:
            return []
        try:
            notch_low_cut = Validation.coerce_float(notch_config["low_cut"])
            notch_high_cut = Validation.coerce_float(notch_config["high_cut"])
        except (KeyError, ValueError):
            return []

        bandpass_low_cut, bandpass_high_cut = bandpass_bounds
        low_errors = _preprocessing_validation.validate_many(notch_low_cut,
            [("greater_or_equal", {"minimum": bandpass_low_cut, "suffix": " Hz"})],
            label="Notch filter: low cut")
        high_errors = _preprocessing_validation.validate_many(notch_high_cut,
            [("less_or_equal", {"maximum": bandpass_high_cut, "suffix": " Hz"})],
            label="Notch filter: high cut")
        if low_errors or high_errors:
            return [f"Cutoffs must stay within {bandpass_low_cut:g}-{bandpass_high_cut:g} Hz "
                "(active bandpass range)."]
        return []

    def _update_state_broadband(self, maximum_band_frequency: float,
        bandpass_bounds: tuple[float, float] | None) -> dict[str, Any] | None:
        broadband = self.state.get("broadband")
        if broadband is None:
            return None

        low_cut = self._minimum_band_frequency
        if bandpass_bounds is not None:
            low_cut = max(low_cut, float(bandpass_bounds[0]))
        broadband["low_cut"] = low_cut
        broadband["high_cut"] = float(maximum_band_frequency)
        return broadband

    def _selected_frequency_bands_with_broadband(self, broadband: dict[str, Any] | None) -> list[dict[str, Any]]:
        selected_bands = [deepcopy(row) for row in self.values["frequency_bands"] if row.get("enabled", False)]
        if broadband is not None:
            selected_bands.append(deepcopy(broadband))
        return selected_bands

    def _sync(self) -> None:
        # Metodo central del widget. Aqui se persiste el estado, se recalculan
        # filtros y se acotan las bandas con fs/2 y con el bandpass activo.
        self.values["car_checked"] = self.car_checkbox.isChecked()
        fs = self._resolve_sampling_rate()

        if fs is None:
            self._set_preprocessing_enabled(False)
            self._filters_are_valid = False
            self.values["selected_frequency_bands"] = []
            self.bands.set_frequency_bounds(minimum_frequency=self._minimum_band_frequency,
                maximum_frequency=10000.0, emit_changed=False)
            self.notch.set_error_message(None)
            self.bandpass.set_error_message(None)
            self.notch_plot.set_response(None, "Load recordings first to preview the filter response.")
            self.bandpass_plot.set_response(None, "Load recordings first to preview the filter response.")
            self.changed.emit()
            return

        self._set_preprocessing_enabled(True)

        notch_response, notch_valid = self._update_filter_feedback(self.notch, self.notch_plot,
            self.values["notch"], fs, "bandstop")
        bandpass_response, bandpass_valid = self._update_filter_feedback(self.bandpass,
            self.bandpass_plot, self.values["bandpass"], fs, "bandpass")
        _ = notch_response
        _ = bandpass_response

        bandpass_bounds = None
        maximum_band_frequency = fs / 2

        # Si el bandpass es valido y esta activo, limita el maximo util para la
        # tabla de bandas y para la broadband efectiva.
        if self.values["bandpass"].get("enabled", True) and bandpass_valid:
            bandpass_bounds = self._active_bandpass_bounds(self.values["bandpass"])
            if bandpass_bounds is not None:
                maximum_band_frequency = min(maximum_band_frequency, bandpass_bounds[1])

        # Regla personalizada: el notch no puede salir del bandpass activo.
        if notch_valid and bandpass_valid:
            notch_bandpass_errors = _preprocessing_validation.validate_errors(
                self.values["notch"], "custom", label="Notch filter",
                validator=self._notch_bandpass_errors, bandpass_bounds=bandpass_bounds)
            if notch_bandpass_errors:
                self.notch.set_error_message(notch_bandpass_errors[0])
                self.notch_plot.set_response(None, notch_bandpass_errors[0])
                notch_valid = False

        self._filters_are_valid = notch_valid and bandpass_valid

        self.bands.set_frequency_bounds(minimum_frequency=self._minimum_band_frequency,
            maximum_frequency=maximum_band_frequency, emit_changed=False)
        broadband = self._update_state_broadband(maximum_band_frequency, bandpass_bounds)
        self.values["selected_frequency_bands"] = self._selected_frequency_bands_with_broadband(broadband)
        self.changed.emit()

    def on_step_activated(self) -> None:
        # WorkflowShell llama a este hook al entrar en el paso para refrescar el
        # estado visible sin conocer detalles internos del widget.
        self._sync()

    def can_continue(self) -> bool:
        return self._resolve_sampling_rate() is not None and self._filters_are_valid and self.bands.is_valid()


__all__ = ["EEGPreprocessingWidget"]
