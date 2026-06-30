from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from medusa_analyzer.frontend.experiments.eeg.widgets.frequency_bands_table import EEGFrequencyBandsTable
from medusa_analyzer.frontend.widgets.filtering import (FilterControls, FilterPreviewPlot, FilterResponse,
    build_filter_defaults, compute_filter_response, filter_defaults, filter_response_error)


# Definimos un widget de preprocesado de EEG que gestiona CAR, filtros configurados, preview de la respuesta
# de los filtros, bandas de frecuencia, y decide si el paso puede continuar según los metadatos, validaciones
# y el estado interno.

class EEGPreprocessingWidget(QScrollArea):
    changed = Signal()

    # El constructor recibe lo mismo que todos los widgets
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__()
        step_config = next((step for step in experiment_info.get("workflow", []) if step.get("id") == "preprocessing"),{})
        self.config = defaults.get("preprocessing", {})
        self.state = state
        self.state.setdefault("preprocessing", {})
        self.fs = None
        self.minimum_band_frequency = float(self.state["broadband"].get("low_cut", 0.0))
        self.maximum_band_frequency =  float(self.state["broadband"].get("high_cut"))
        # A continuación, definimos una variable para guardar el rango efectivo que queda después de aplicar filtros
        # que limitan las bandas de EEG.
        self.active_filter_bounds: tuple[float, float] | None = None

        # Cogemos la definición de los filtros particularizado al experimento de eeg. La idea es saber qué filtros
        # existen y cómo se comportan.
        self.filter_definitions = [deepcopy(filter_config) for filter_config in self.config.get("filters", [])]
        self.filters: dict[str, FilterControls] = {} # guardar widgets de control de cada filtro
        self.filter_plots: dict[str, FilterPreviewPlot] = {} # guardar plot asociado a cada filtro

        # Calculamos los valores por defecto
        default_state = self._build_default_state()
        self.default_frequency_bands = [deepcopy(band) for band in default_state["frequency_bands"]]
        # Si state ya tiene preprocessing lo reutilizamos. Si no, creamos el estado inicial con los valores por defecto.
        if not self.state["preprocessing"]:
            self.state["preprocessing"] = default_state # creamos el estado inicial con parámetros por defecto
        self._filters_are_valid = False

        # Parte visual
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget() # widget interno del scroll area
        root = QVBoxLayout(content) # layout vertical principal
        root.setContentsMargins(4, 4, 12, 4)
        root.setSpacing(16)

        heading = QLabel(str(step_config.get("title", "Preprocessing")))
        heading.setObjectName("pageTitle")
        subtitle = QLabel(str(step_config.get("subtitle", "Tune the defaults that will be applied to the EEG recording.")))
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
        self.car_checkbox.setChecked(bool(self.state["preprocessing"]["car_checked"]))
        car_layout.addWidget(car_title)
        car_layout.addWidget(self.car_checkbox)
        root.addWidget(car_panel)

        filters_grid = QGridLayout() # Paneles de filtro - cuadricula con 2 columnas
        filters_grid.setContentsMargins(0, 0, 0, 0)
        filters_grid.setHorizontalSpacing(16)
        filters_grid.setVerticalSpacing(16)
        filters_grid.setColumnStretch(0, 5)
        filters_grid.setColumnStretch(1, 7)
        # Iteramos para crear cada filtro
        for row, filter_definition in enumerate(self.filter_definitions):
            filter_id = str(filter_definition["id"]) # extraemos el identificado del filtro
            # Constructor: título del panel del filtro, configuración que queremos del filtro, modo del filtro y
            # frecuencia mínima permitida inicialmente.
            controls = FilterControls(str(filter_definition["title"]), self.state["preprocessing"]["filters"][filter_id],
                                      str(filter_definition["mode"]), minimum_frequency=self.minimum_band_frequency)
            controls.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            # Creamos el panel visual de la gráfica asociada a ese filtro. plot_panel es el contenedor completo con
            # borde, título, layour, etc. y plot es el widget real donde se pinta la respuesta del filtro.
            plot_panel, plot = self._build_filter_plot_panel(str(filter_definition["plot_title"]))
            self.filters[filter_id] = controls
            self.filter_plots[filter_id] = plot
            filters_grid.addWidget(controls, row, 0)
            filters_grid.addWidget(plot_panel, row, 1)
            filters_grid.setRowStretch(row, 1)
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
        # self.state["preprocessing"]. Esto es eficiente pero puede ser menos robusto si quieres control estricto de
        # cuando se muta el estado.
        self.bands = EEGFrequencyBandsTable(self.state["preprocessing"]["frequency_bands"],
            default_rows=self.default_frequency_bands, minimum_frequency=self.minimum_band_frequency)
        bands_layout.addWidget(self.bands)
        root.addWidget(bands_panel)
        root.addStretch()
        self.setWidget(content)

        # Conectamos todos los parámetros a ._sync para que se actualice el estado
        self.car_checkbox.toggled.connect(self._sync)
        for controls in self.filters.values():
            controls.changed.connect(self._sync)
        self.bands.changed.connect(self._sync)
        self.on_step_activated()

    def _build_default_state(self) -> dict[str, Any]:
        """Construye el estado inicial del widget desde defaults."""
        return {"car_checked": bool(self.config.get("car", {}).get("checked_by_default", False)),
            "filters": {str(filter_config["id"]): build_filter_defaults(filter_config) for filter_config in
                        self.filter_definitions},
            "frequency_bands": [deepcopy(band) for band in self.config.get("bands", {}).get("available", [])],
            "selected_frequency_bands": []}

    def _build_filter_plot_panel(self, title: str) -> tuple[QFrame, FilterPreviewPlot]:
        """Función para construir el panel visual de la respuesta en frecuencia de un filtro."""
        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(24, 20, 24, 20)
        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        plot = FilterPreviewPlot()
        panel_layout.addWidget(title_label)
        panel_layout.addWidget(plot)
        return panel, plot

    def _set_preprocessing_enabled(self, enabled: bool) -> None:
        """ Función para cambiar el estado del widget de preprocessing."""
        self.car_checkbox.setEnabled(enabled)
        for controls in self.filters.values():
            controls.setEnabled(enabled)
        self.bands.setEnabled(enabled)

    def _update_filter_feedback(self, controls: FilterControls, plot: FilterPreviewPlot,
        config: dict[str, Any], fs: float, mode: str) -> tuple[FilterResponse | None, bool]:
        """Función para calcular la respuesta de un filtro llamando a funciones específicas de la clase Filtering.
        Recibe:
        - controls: widget de controles de un filtro concreto
        - plot: gráfica asociada a ese filtro
        - config: configuración actual de ese filtro
        - fs: frecuencia de muestreo
        - mode: tipo de filtro"""

        response = compute_filter_response(config, fs, mode, minimum_frequency=controls.minimum_frequency,
                                           maximum_frequency=controls.maximum_frequency)
        # Si da error
        if config.get("enabled", True) and response is None:
            # Construimos el mensaje de error/warning
            error_message = filter_response_error(config, fs, minimum_frequency=controls.minimum_frequency,
                                                  maximum_frequency=controls.maximum_frequency)
            controls.set_message(error_message) # Mostramos el mensaje de error/warning
            plot.set_response(None, error_message) #ploteamos el mensaje de error/warning en la gráfica
            return None, False

        # Si va bien
        controls.set_message(None)
        plot.set_response(response)
        return response, True

    def _build_selected_frequency_bands(self) -> list[dict[str, Any]]:
        """Función para crear la lista final de bandas. Incluye todas las bandas marcadas como enabled
        y la banda broadband.
        NOTA: la broadband se añade SIEMPRE. Esto está pensado asi de cara al run_pipeline."""
        selected_bands = [deepcopy(row) for row in self.state["preprocessing"]["frequency_bands"] if row.get(
            "enabled", False)]
        if self.state.get("broadband") is not None:
            selected_bands.append(deepcopy(self.state.get("broadband")))
        return selected_bands

    def _sync(self) -> None:
        """Función para sincronizar el estado interno, validar filtros, actualizar plots, recalcular límites de
        bandas y avisar al resto del workflow de que algo ha cambiado."""

        if self.fs is None: # Caso en el que todavía no hay recordings cargados
            self._set_preprocessing_enabled(False) # desactivamos todos los controles
            self._filters_are_valid = False
            self.state["preprocessing"]["selected_frequency_bands"] = [] # vaciamos bandas seleccionadas
            for filter_id, controls in self.filters.items():
                controls.set_message(None) # eliminamos mensajes previos de error
                self.filter_plots[filter_id].set_response(None, "Load recordings first to preview the filter response.")
            self.changed.emit()
            return

        # Cuando fs existe, activamos los controles
        self._set_preprocessing_enabled(True)
        self.minimum_band_frequency = float(self.state["broadband"]["low_cut"])
        self.maximum_band_frequency = float(self.state["broadband"]["high_cut"])
        for controls in self.filters.values():
            controls.set_frequency_bounds(self.minimum_band_frequency, self.fs/2)
            # NOTA: ponemos de límite nyquist, aunque luego se valida con el máximo restringido

        # Copiamos el valor del checkbox CAR al estado
        self.state["preprocessing"]["car_checked"] = self.car_checkbox.isChecked()

        # Calculamos la respuesta de los filtros
        filter_validity = {} # dic para guardar si un filtro es válido o no
        for filter_definition in self.filter_definitions: # recorremos las definiciones de los filtros
            filter_id = str(filter_definition["id"])
            # Guardamos la validez de cada uno de los filtros que tenemos definidos
            _, filter_validity[filter_id] = self._update_filter_feedback(self.filters[filter_id],
                self.filter_plots[filter_id], self.state["preprocessing"]["filters"][filter_id], self.fs,
                str(filter_definition["mode"]))

        # Antes de calcular qué filtros limitan qué bandas, limpiamos el valor anterior para evitar arrastrar límites
        # de una sincronización pasada.
        self.active_filter_bounds = None

        # Si algún filtro activo y válido limita las bandas, actualizamos el rango util de la broadband.
        for filter_definition in self.filter_definitions: # recorremos todos los filtros
            # Si el filtro no está marcado como limitante de bandas, lo saltamos
            if not filter_definition.get("limits_frequency_bands", False):
                continue
            filter_id = str(filter_definition["id"])
            filter_config = self.state["preprocessing"]["filters"].get(filter_id, {})
            # Si el filtro está activado y es válido...
            if filter_config.get("enabled", True) and filter_validity.get(filter_id, False):
                # Extraemos los límites del filtro
                filter_bounds = (float(filter_config["low_cut"]), float(filter_config["high_cut"]))
                # Calculamos la intersección entre todos los filtros limitantes activos
                self.active_filter_bounds = filter_bounds if self.active_filter_bounds is None else (
                    max(self.active_filter_bounds[0], filter_bounds[0]), min(self.active_filter_bounds[1], filter_bounds[1]))
                # Actualizamos los límites restrictivos
                self.minimum_band_frequency = max(self.minimum_band_frequency, filter_bounds[0])
                self.maximum_band_frequency = min(self.maximum_band_frequency, filter_bounds[1])

        # Bucle para comprobar si un filtro debe de estar dentro del rango de otro filtro
        for filter_definition in self.filter_definitions:
            reference_filter_id = filter_definition.get("must_be_within_filter")
            if not reference_filter_id:
                continue
            filter_id = str(filter_definition["id"])
            reference_filter_id = str(reference_filter_id) # id del filtro de referencia (mirar el json para dudas)
            filter_config = self.state["preprocessing"]["filters"].get(filter_id, {})
            reference_config = self.state["preprocessing"]["filters"].get(reference_filter_id, {})
            # Comprobamos que ambos filtros están activos y son válidos
            if not (filter_config.get("enabled", True) and reference_config.get("enabled", True)
                    and filter_validity.get(filter_id, False) and filter_validity.get(reference_filter_id, False)):
                continue
            # Extraemos límites del filtro y del filtro de referencia
            filter_low_cut, filter_high_cut = float(filter_config["low_cut"]), float(filter_config["high_cut"])
            reference_low_cut = float(reference_config["low_cut"])
            reference_high_cut = float(reference_config["high_cut"])
            # Comprobamos si el filtro está fuera del filtro de referencia
            if filter_low_cut < reference_low_cut or filter_high_cut > reference_high_cut:
                self.filters[filter_id].blockSignals(True)
                self.filters[filter_id].enabled.setChecked(False) # desactivamos el filtro
                self.filters[filter_id].blockSignals(False)
                # Mostramos warnings
                self.filters[filter_id].set_message(str(filter_definition.get("out_of_range_warning") or
                    "Filter is outside the active range and will have no practical effect.").format(
                    low=reference_low_cut, high=reference_high_cut), role="warning")

        self._filters_are_valid = all(filter_validity.values()) # validez global de los filtros para continuar

        # Actualizamos límites restrictivos de broadband
        self.state["broadband"]["low_cut"] = float(self.minimum_band_frequency)
        self.state["broadband"]["high_cut"] = float(self.maximum_band_frequency)

        # Actualizamos límites de la tabla de bandas. No se permiten valores fuera de rango de la broadband restringida.
        self.bands.set_frequency_bounds(minimum_frequency=self.minimum_band_frequency,
            maximum_frequency=self.maximum_band_frequency, emit_changed=False)
        self.state["preprocessing"]["selected_frequency_bands"] = self._build_selected_frequency_bands()
        self.changed.emit()

    def on_step_activated(self) -> None:
        """WorkflowShell llama a este hook"""
        metadata_list = self.state.get("metadata_list", [])
        sampling_rates = [float(metadata["sampling_rate"]) for metadata in metadata_list
            if metadata.get("sampling_rate") is not None and metadata.get("sampling_rate") > 0]
        self.fs = min(sampling_rates) if sampling_rates else None
        self._sync()

    def can_continue(self) -> bool:
        return self.fs is not None and self._filters_are_valid and self.bands.is_valid()


__all__ = ["EEGPreprocessingWidget"]
