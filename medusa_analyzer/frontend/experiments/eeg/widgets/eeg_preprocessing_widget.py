from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)
from pip._internal.operations.build import metadata

from medusa_analyzer.frontend.experiments.eeg.widgets.frequency_bands_table import EEGFrequencyBandsTable
from medusa_analyzer.frontend.models import Validation
from medusa_analyzer.frontend.widgets.filtering import (FilterControls, FilterPreviewPlot, FilterResponse,
    build_filter_defaults, compute_filter_response, filter_response_error)


_preprocessing_validation = Validation()

# Definimos un widget de preprocesado de EEG que gestiona CAR, filtros notch y bandpass, preview de la respuesta
# de los filtros, bandas de frecuencia, y decide si el paso puede continuar según los metadatos, validaciones
# y el estado interno.
class EEGPreprocessingWidget(QScrollArea):
    changed = Signal()

    # El constructor recibe lo mismo que todos los widgets
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__()
        _ = experiment_info
        self.config = defaults.get("preprocessing", {})
        self.state = state
        self.metadata_list = self.state.get("metadata_list", [])
        self.fs = None
        if self.metadata_list:
            fs = self.metadata_list[0].get("sampling_rate")
            if fs is not None and fs <= 0:
                fs = None
        # TODO: no se podría poner aquí también lo del broadband en self.broadband para que quede más ordenado?
        # Y sacarlo del sync. También lo de que la max sea fs/2 y tal.

        # Calculamos los valores por defecto
        default_state = self._build_default_state()
        self.default_frequency_bands = [deepcopy(band) for band in default_state["frequency_bands"]]
        # Si state ya tiene preprocessing lo reutilizamos. Si no, creamos el estado inicial con los valores por defecto.
        if not self.state.get("preprocessing"):
            self.state["preprocessing"] = default_state # creamos el estado inicial con parámetros por defecto
        self._filters_are_valid = False

        # Parte visual
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget() # widget interno del scroll area
        root = QVBoxLayout(content) # layout vertical principal
        root.setContentsMargins(4, 4, 12, 4)
        root.setSpacing(16)

        heading = QLabel("Preprocessing")
        heading.setObjectName("pageTitle")
        subtitle = QLabel("Tune the defaults that will be applied to the EEG recording.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(heading)
        root.addWidget(subtitle)
        root.addSpacing(16)

        car_panel = QFrame() # CAR panel
        car_panel.setProperty("role", "surface-panel")
        car_layout = QVBoxLayout(car_panel)
        car_layout.setContentsMargins(24, 20, 24, 20)
        car_title = QLabel("CAR")
        car_title.setObjectName("panelTitle")
        self.car_checkbox = QCheckBox("Apply common average reference")
        # Lo inicializamos desde el estado
        self.car_checkbox.setChecked(bool(self.state["preprocessing"].get("car_checked", False)))
        car_layout.addWidget(car_title)
        car_layout.addWidget(self.car_checkbox)
        root.addWidget(car_panel)

        filters_grid = QGridLayout() # Paneles de filtro - cuadrícula con 2 columnas
        filters_grid.setContentsMargins(0, 0, 0, 0)
        filters_grid.setHorizontalSpacing(16)
        filters_grid.setVerticalSpacing(16)
        filters_grid.setColumnStretch(0, 5)
        filters_grid.setColumnStretch(1, 7)
        filters_grid.setRowStretch(0, 1)
        filters_grid.setRowStretch(1, 1)

        # Extraemos las opciones globales para filtros fir e iir (en defaults.json)
        filter_options = self.config.get("filter_options", {})
        fir = filter_options.get("fir", {})
        iir = filter_options.get("iir", {})

        # TODO: dar una vuelta a tema filtros. No me acaba de convencer que en el json de defaults del eeg
        # se meta todo lo de la configuración de iir y fir. Igual eso tendría que ir en otro lado ajeno.
        # TODO: también dar una vuelta a FilterControls
        self.notch = FilterControls("Notch filter", self.state["preprocessing"]["notch"], fir, iir, "bandstop")
        self.bandpass = FilterControls("Bandpass filter", self.state["preprocessing"]["bandpass"], fir, iir, "bandpass")
        self.notch.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.bandpass.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        # Panel de los filtros
        self.notch_plot_panel = self._build_filter_plot_panel("Notch filter response", "notch_plot")
        self.bandpass_plot_panel = self._build_filter_plot_panel("Bandpass filter response", "bandpass_plot")

        filters_grid.addWidget(self.notch, 0, 0)
        filters_grid.addWidget(self.notch_plot_panel, 0, 1)
        filters_grid.addWidget(self.bandpass, 1, 0)
        filters_grid.addWidget(self.bandpass_plot_panel, 1, 1)
        root.addLayout(filters_grid)

        bands_panel = QFrame() # Panel de las bandas
        bands_panel.setProperty("role", "surface-panel")
        bands_layout = QVBoxLayout(bands_panel)
        bands_layout.setContentsMargins(24, 20, 24, 20)
        bands_title = QLabel("Frequency bands")
        bands_title.setObjectName("panelTitle")
        bands_layout.addWidget(bands_title)
        # La tabla recibe las bandas actuales y los defaults.
        # TODO: igual que con los filtros, parece que la tabla trabaja directamente sobre la lista de diccs de
        # self.values. Esto es eficiente pero puede ser menos robusto si quieres control estricto de cuándo se muta
        # el estado.
        self.bands = EEGFrequencyBandsTable(self.state["preprocessing"]["frequency_bands"],
                                            default_rows=self.default_frequency_bands)
        bands_layout.addWidget(self.bands)
        root.addWidget(bands_panel)
        root.addStretch()

        self.setWidget(content)

        # Conectamos todos los parámetros a ._sync para que se actualice el estado
        self.car_checkbox.toggled.connect(self._sync)
        self.notch.changed.connect(self._sync)
        self.bandpass.changed.connect(self._sync)
        self.bands.changed.connect(self._sync)
        self._sync()

    def _build_default_state(self) -> dict[str, Any]:
        """Construye el estado inicial del widget desde defaults."""
        return {"car_checked": bool(self.config.get("car", {}).get("checked_by_default", False)),
            "notch": build_filter_defaults(self.config.get("notch", {}), "bandstop"),
            "bandpass": build_filter_defaults(self.config.get("bandpass", {}), "bandpass"),
            "frequency_bands": [deepcopy(band) for band in self.config.get("bands", {}).get("available", [])],
            "selected_frequency_bands": []}

    def _build_filter_plot_panel(self, title: str, plot_attribute: str) -> QFrame:
        """Función para construir el panel visual de la respuesta en frecuencia de un filtro."""
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

    def _set_preprocessing_enabled(self, enabled: bool) -> None:
        """ Función para cambiar el estado del widget de preprocessing."""
        self.car_checkbox.setEnabled(enabled)
        self.notch.setEnabled(enabled)
        self.bandpass.setEnabled(enabled)
        self.bands.setEnabled(enabled)

    def _update_filter_feedback(self, controls: FilterControls, plot: FilterPreviewPlot,
        config: dict[str, Any], fs: float, mode: str) -> tuple[FilterResponse | None, bool]:
        """Función para calcular la respuesta de un filtro."""

        response = compute_filter_response(config, fs, mode, fir_options=controls.fir, iir_options=controls.iir)
        # Si da error
        if config.get("enabled", True) and response is None:
            # Construimos el mensaje de error
            error_message = filter_response_error(config, fs, fir_options=controls.fir, iir_options=controls.iir)
            controls.set_error_message(error_message) # Mostramos el mensaje de error
            plot.set_response(None, error_message) #ploteamos el mensaje de error en la gráfica
            return None, False

        # Si va bien
        controls.set_error_message(None)
        plot.set_response(response)
        return response, True

    @staticmethod
    def _notch_bandpass_errors(notch_config: dict[str, Any], *, label: str,
        bandpass_bounds: tuple[float, float] | None = None, **_: Any) -> list[str]:
        """ Función para regla personalizada. Si hay bandpass activo, el notch tiene que estar dentro de ese rango."""
        _ = label
        if not notch_config.get("enabled", True) or bandpass_bounds is None:
            return []
        notch_low_cut = float(notch_config["low_cut"])
        notch_high_cut = float(notch_config["high_cut"])

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
        # TODO: desde el punto de vista de UX quizá sería mejor mostrar un warning tipo 'the notch filter is outside the
        # active bandpass range and will have no practical effect. Algo así. Y que se guarde como que no está marcado en
        # el estado.
        return []

    def _build_selected_frequency_bands(self) -> list[dict[str, Any]]:
        """Función para crear la lista final de bandas. Incluye todas las bandas marcadas como enabled
        y la banda broadband.
        NOTA: la broadband se añade SIEMPRE. Esto está pensado así de cara al run_pipeline."""
        selected_bands = [deepcopy(row) for row in self.state["preprocessing"]["frequency_bands"] if row.get("enabled", False)]
        selected_bands.append(deepcopy(self.state["broadband"]))
        return selected_bands

    def _sync(self) -> None:
        """Función para sincronizar el estado interno, validar filtros, actualizar plots, recalcular límites de
        bandas y avisar al resto del workflow de que algo ha cambiado."""

        if self.fs is None: # Caso en el que todavía no hay recordings cargados
            self._set_preprocessing_enabled(False) # desactivamos todos los controles
            self._filters_are_valid = False
            self.state["preprocessing"]["selected_frequency_bands"] = [] # vacíamos bandas seleccionadas
            self.notch.set_error_message(None) # eliminamos mensajes previos de error
            self.bandpass.set_error_message(None) # eliminamos mensajes previos de error
            self.notch_plot.set_response(None, "Load recordings first to preview the filter response.")
            self.bandpass_plot.set_response(None, "Load recordings first to preview the filter response.")
            self.changed.emit()
            return

        # Cuando fs existe, activamos los controles
        self._set_preprocessing_enabled(True)
        # Copiamos el valor del checkbox CAR al estado
        # TODO: seguro que hay que hacerlo aquí, siempre? Porque solo este? No se puede quitar?
        self.state["preprocessing"]["car_checked"] = self.car_checkbox.isChecked()
        # Calculamos la respuesta de los filtros
        _, notch_valid = self._update_filter_feedback(self.notch, self.notch_plot,
                                                      self.state["preprocessing"]["notch"], self.fs, "bandstop")
        _, bandpass_valid = self._update_filter_feedback(self.bandpass,
                                                         self.bandpass_plot, self.state["preprocessing"]["bandpass"], self.fs, "bandpass")

        # TODO: estas dos cosas no se pueden hacer en otro lado?
        bandpass_bounds = None
        maximum_band_frequency = self.fs / 2

        # Si el bandpass está activo y es válido, limitamos el máximo de la broadband
        if self.state["preprocessing"]["bandpass"].get("enabled", True) and bandpass_valid:
            bandpass_bounds = (float(self.state["preprocessing"]["bandpass"]["low_cut"]),
                               float(self.state["preprocessing"]["bandpass"]["high_cut"]))
        maximum_band_frequency = min(maximum_band_frequency, bandpass_valid[1])
        # TODO: también habría que mirar el mínimo. Coger el máximo de los mínimos.
        # Regla personalizada: el notch no puede salir del rango de bandpass activo.
        if notch_valid and bandpass_valid:
            notch_bandpass_errors = _preprocessing_validation.validate_errors(
                self.state["preprocessing"]["notch"], "custom", label="Notch filter",
                validator=self._notch_bandpass_errors, bandpass_bounds=bandpass_bounds)
            if notch_bandpass_errors: # TODO: cambiar de error a warning y que simplemente no se gaurde en estado
                self.notch.set_error_message(notch_bandpass_errors[0])
                self.notch_plot.set_response(None, notch_bandpass_errors[0])
                notch_valid = False

        self._filters_are_valid = notch_valid and bandpass_valid

        # Actualizamos límites de broadband
        minimum_band_frequency = float(self.state["broadband"]["low_cut"])
        if bandpass_bounds is not None:
            minimum_band_frequency = max(minimum_band_frequency, float(bandpass_bounds[0]))
        self.state["broadband"]["low_cut"] = minimum_band_frequency
        self.state["broadband"]["high_cut"] = float(maximum_band_frequency)

        # Actualizamos límites de la tabla de bandas. No se permiten valores fuera de rango de la broadband actualizada.
        self.bands.set_frequency_bounds(minimum_frequency=minimum_band_frequency,
            maximum_frequency=maximum_band_frequency, emit_changed=False)
        self.state["preprocessing"]["selected_frequency_bands"] = self._build_selected_frequency_bands()
        self.changed.emit()

    def on_step_activated(self) -> None:
        """WorkflowShell llama a este hook"""
        self._sync()

    def can_continue(self) -> bool:
        return self.fs is not None and self._filters_are_valid and self.bands.is_valid()

__all__ = ["EEGPreprocessingWidget"]
