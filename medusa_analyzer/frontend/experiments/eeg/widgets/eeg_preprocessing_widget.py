from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from medusa_analyzer.frontend.widgets.filtering import (FilterControls, FilterPreviewPlot, FilterResponse,
    build_filter_defaults, compute_filter_response, filter_response_error)
from medusa_analyzer.frontend.experiments.eeg.widgets.frequency_bands_table import (EEGFrequencyBandsTable)

class EEGPreprocessingWidget(QScrollArea):

    # Emitimos una señal cuando cambia el widget que se conecta con el WorkflowShell
    changed = Signal()
    _minimum_band_frequency = 0.1 # frecuencia mínima permitida para las bandas

    # En el constructor recibimos el info.json, el defaults.json y es estado.
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__()
        _ = experiment_info # Lo recibo pero no lo uso
        self.config = defaults.get("preprocessing", {})
        self.state = state

        # Copiamos las bandas configuradas para desacoplar config y estado editable.
        self.default_frequency_bands = self._copy_configured_frequency_bands()
        # Buscamos si existe ya una configuración de estado anterior (ya entramos en el paso antes,
        # # cambiamos de opciones, avanzamos y volvimos atrás) o crear un estado nuevo.
        # Si no existe, se crea un estado desde defaults.
        existing_values = self.state.get("preprocessing") or {}
        if not existing_values:
            # Cogemos los valores por defecto del json
            existing_values = self._build_default_state()
            # Añadimos al estado estos valores
            self.state["preprocessing"] = existing_values
        self.values = existing_values
        self._filters_are_valid = False

        title = "Pre-processing"
        description = "Tune the defaults that will be applied to the EEG recording."

        # Configuración del scroll y layout
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(4, 4, 12, 4)
        root.setSpacing(16)

        heading = QLabel(title) # Título
        heading.setObjectName("pageTitle")
        subtitle = QLabel(description) # Subtítulo
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(heading)
        root.addWidget(subtitle)
        root.addSpacing(16)

        # Creamos un panel para la opción CAR
        car_panel = QFrame()
        car_panel.setProperty("role", "surface-panel")
        car_layout = QVBoxLayout(car_panel)
        car_layout.setContentsMargins(24, 20, 24, 20)
        car_title = QLabel("CAR")
        car_title.setObjectName("panelTitle")
        self.car_checkbox = QCheckBox("Apply common average reference")
        self.car_checkbox.setChecked(bool(self.values.get("car_checked", False))) # Marcamos en función de defaults
        car_layout.addWidget(car_title)
        car_layout.addWidget(self.car_checkbox)
        root.addWidget(car_panel)

        # Creamos una rejilla para colocar los controles de los filtros y las gráficas del perfil del filtro
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

        # Creamos el panel de controles para cada filtro
        self.notch = FilterControls("Notch filter", self.values["notch"], fir, iir, "bandstop")
        self.bandpass = FilterControls("Bandpass filter", self.values["bandpass"], fir, iir, "bandpass")
        self.notch.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.bandpass.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        # Creamos los paneles con lsa gráficas para ver la respuesta de los filtros
        self.notch_plot_panel = self._build_filter_plot_panel("Notch filter response",
            "notch_plot")
        self.bandpass_plot_panel = self._build_filter_plot_panel("Bandpass filter response",
            "bandpass_plot")

        filters_grid.addWidget(self.notch, 0, 0)
        filters_grid.addWidget(self.notch_plot_panel, 0, 1)
        filters_grid.addWidget(self.bandpass, 1, 0)
        filters_grid.addWidget(self.bandpass_plot_panel, 1, 1)
        root.addLayout(filters_grid)

        # Creamos el panel de bandas de frecuencia
        bands_panel = QFrame()
        bands_panel.setProperty("role", "surface-panel")
        bands_layout = QVBoxLayout(bands_panel)
        bands_layout.setContentsMargins(24, 20, 24, 20)
        bands_title = QLabel("Frequency bands")
        bands_title.setObjectName("panelTitle")
        bands_layout.addWidget(bands_title)
        # Creamos la tabla de bandas
        self.bands = EEGFrequencyBandsTable(self.values["frequency_bands"],
            default_rows=self.default_frequency_bands)
        bands_layout.addWidget(self.bands)
        root.addWidget(bands_panel)
        root.addStretch()

        self.setWidget(content)
        # Conectamos todas los elementos modificables a la función ._sync. Esta función guarda el estado, calcula la
        # respuesta de los filtros, actualiza los plots y emite señal de changed.
        self.car_checkbox.toggled.connect(self._sync)
        self.notch.changed.connect(self._sync)
        self.bandpass.changed.connect(self._sync)
        self.bands.changed.connect(self._sync)
        self._sync()

    def _build_default_state(self) -> dict[str, Any]:
        # Función que construye el estado inicial de preprocesado
        return {"car_checked": bool(self.config.get("car", {}).get("checked_by_default", False)),
            "notch": build_filter_defaults(self.config.get("notch", {}), "bandstop"),
            "bandpass": build_filter_defaults(self.config.get("bandpass", {}), "bandpass"),
            "frequency_bands": self._copy_configured_frequency_bands()}

    def _build_filter_plot_panel(self, title: str, plot_attribute: str) -> QFrame:
        # Función que crea un panel reutilizable para una gráfica
        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding,)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(24, 20, 24, 20)
        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        plot = FilterPreviewPlot()
        # IMPORTANTE: Creamos atributo dinámicamente. Por ejemplo, si plot_attribute es "notch_plot" entonces hace algo
        # equivalente a self.notch_plot = plot
        setattr(self, plot_attribute, plot)
        panel_layout.addWidget(title_label)
        panel_layout.addWidget(plot)
        return panel

    def _copy_configured_frequency_bands(self) -> list[dict[str, Any]]:
        # Función para hacer una copia independiente de las mandas y evitar modificaciones de lo original.
        return [deepcopy(band) for band in self.config.get("bands", {}).get("available", [])]

    def _resolve_sampling_rate(self) -> float | None:
        metadata_list = self.state.get("metadata_list") or []
        sampling_rates = [metadata.sampling_rate for metadata in metadata_list
            if metadata.sampling_rate is not None and metadata.sampling_rate > 0]
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
        response = compute_filter_response(config, fs, mode)
        if config.get("enabled", True) and response is None:
            error_message = filter_response_error(config, fs)
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
            low_cut = float(bandpass_config["low_cut"])
            high_cut = float(bandpass_config["high_cut"])
        except (KeyError, TypeError, ValueError):
            return None
        if not math.isfinite(low_cut) or not math.isfinite(high_cut):
            return None
        return low_cut, high_cut

    @staticmethod
    def _notch_bandpass_error(notch_config: dict[str, Any],
        bandpass_bounds: tuple[float, float] | None) -> str | None:
        if not notch_config.get("enabled", True) or bandpass_bounds is None:
            return None
        try:
            notch_low_cut = float(notch_config["low_cut"])
            notch_high_cut = float(notch_config["high_cut"])
        except (KeyError, TypeError, ValueError):
            return None
        bandpass_low_cut, bandpass_high_cut = bandpass_bounds
        if notch_low_cut < bandpass_low_cut or notch_high_cut > bandpass_high_cut:
            return (f"Cutoffs must stay within {bandpass_low_cut:g}-{bandpass_high_cut:g} Hz "
                "(active bandpass range).")
        return None

    def _sync(self) -> None:
        # Es la función central del widget. Se llama cada vez que cambia algo. Sirve para guardar el valor del checkbox
        # del CRA, detectar la frecuencia de muestreo, recalcular la respuesta de los filtros, limitar las bandas de
        # frecuencia según fs y bandpass, actualizar las gráficas y emitir changed.

        self.values["car_checked"] = self.car_checkbox.isChecked() # Actualiza el estado (self.values es state[preprocessing])
        fs = self._resolve_sampling_rate() # Cogemos fs
        # Si no hay frecuencia de muestreo, deshabilitamos toodo
        if fs is None:
            self._set_preprocessing_enabled(False)
            self._filters_are_valid = False
            self.bands.set_frequency_bounds(minimum_frequency=self._minimum_band_frequency,
                maximum_frequency=10000.0, emit_changed=False)
            self.notch.set_error_message(None)
            self.bandpass.set_error_message(None)
            self.notch_plot.set_response(None, "Load recordings first to preview the filter response.")
            self.bandpass_plot.set_response(None, "Load recordings first to preview the filter response.")
            self.changed.emit()
            return

        self._set_preprocessing_enabled(True)

        # Calculamos las respuestas de los filtros para mostrar en las gráficas
        notch_response, notch_valid = self._update_filter_feedback(self.notch, self.notch_plot,
            self.values["notch"], fs, "bandstop")
        bandpass_response, bandpass_valid = self._update_filter_feedback(self.bandpass,
            self.bandpass_plot, self.values["bandpass"], fs, "bandpass")
        bandpass_bounds = None
        maximum_band_frequency = fs / 2 # máxima frecuencia permitida para bandas

        # Si el bandpass está activo tenemos que comprobar que las bandas no superen la banda de paso, entonces
        # limitaremos las bandas al mínimo entre fs/2 y el high cut de la banda de paso.
        if self.values["bandpass"].get("enabled", True) and bandpass_valid:
            bandpass_bounds = self._active_bandpass_bounds(self.values["bandpass"])
            try:
                bandpass_high_cut = float(self.values["bandpass"].get("high_cut", maximum_band_frequency))
            except (TypeError, ValueError):
                bandpass_high_cut = maximum_band_frequency
            if math.isfinite(bandpass_high_cut) and bandpass_high_cut > 0:
                maximum_band_frequency = min(maximum_band_frequency, bandpass_high_cut)
        if notch_valid and bandpass_valid:
            notch_bandpass_error = self._notch_bandpass_error(self.values["notch"], bandpass_bounds)
            if notch_bandpass_error:
                self.notch.set_error_message(notch_bandpass_error)
                self.notch_plot.set_response(None, notch_bandpass_error)
                notch_valid = False
        self._filters_are_valid = notch_valid and bandpass_valid
        # Actualizamos los límites
        self.bands.set_frequency_bounds(minimum_frequency=self._minimum_band_frequency,
            maximum_frequency=maximum_band_frequency, emit_changed=False)
        self.changed.emit() # Avisamos al Workflowshell

    def on_step_activated(self) -> None:
        self._sync()

    def can_continue(self) -> bool:
        return self._resolve_sampling_rate() is not None and self._filters_are_valid and self.bands.is_valid()

__all__ = ["EEGPreprocessingWidget"]
