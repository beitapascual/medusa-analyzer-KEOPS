from __future__ import annotations
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QLabel, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget)
from scipy import signal
from medusa_analyzer.frontend.validation import Validation
from medusa_analyzer.frontend.widgets.plots import LinePlot, PlotSeries

"""Script para crear parte de una interfaz gráfica para configurar filtros, calcular su respuesta en 
frecuencia y dibujar una previsualización en pantalla. El flujo principal es este:
    - Se cargan los valores por defecto desde filtering.json
    - Se crea una configuración inicial del filtro
    - La clase FilerControls muestra controles en pantalla_ activar/desactivar, frecuencias de corte, tipo 
    FIR/IIR, orden, ventana, diseño, etc. 
    - Cuando el usuario modifica algo, _sync() actualiza self.config y se emite señal changed.
    - Otro widget puede llamar a compute_filter_response()
    - Si la configuración es válida, se calcula la curva del filtro
    - FilerPreviewPlot dibuja la respuesta en frecuencia
    
NOTA: Keys soportadas al definir un filtro en un experimento:
    - `id`
    - `title`
    - `plot_title` identifican el filtro y su UI
    - `enabled`
    - `filter_type`
    - `filter_design`
    - `low_cut`
    - `high_cut`
    - `order`
    - `window`
    `limits_frequency_bands`
    `must_be_within_filter` 
    `out_of_range_warning`"""

FilterMode = Literal["bandpass", "bandstop"] # modos posibles # TODO: FUTURO INCLUIR LOWPASS Y HIGHPASS
_filter_validation = Validation() # objeto de validación
filter_defaults = json.loads( # Carga de configuración por defecto
    (Path(__file__).resolve().parents[1] / "defaults" / "filtering.json").read_text(encoding="utf-8"))

@dataclass(frozen=True, slots=True)
class FilterResponse:
    """Clase que guarda el resultado del cálculo de un filtro (frecuencia y magnitud)"""
    frequencies: list[float]
    magnitude_db: list[float]

def _filter_family_options(family: str) -> dict[str, Any]:
    """Recibe una familia de filtros, por ejemplo fir o iir y devuelve su configuración correspondiente."""
    return filter_defaults.get(family, {})

def _filter_families() -> list[Any]:
    """Devuelve una lista con las familias de filtros disponibles."""
    return filter_defaults.get("families", [])

def _filter_family_ids() -> list[str]:
    return _option_ids(_filter_families())

def _filter_modes() -> list[str]:
    return ["bandpass", "bandstop"]

def _fir_options() -> dict[str, Any]:
    """Devuelve la configuración específica de filtros FIR"""
    return _filter_family_options("fir")

def _iir_options() -> dict[str, Any]:
    """Devuelve la configuración específica de filtros IIR"""
    return _filter_family_options("iir")

def _integer_bounds(options: dict[str, Any], minimum_key: str, maximum_key: str) -> tuple[int, int]:
    """Obtener límites como orden mínimo y máximo"""
    return int(options[minimum_key]), int(options[maximum_key])

def _default_order_for_design(filter_design: str) -> int:
    options = _iir_options() if filter_design == "iir" else _fir_options()
    return int(options.get("default_order", options.get("minimum_order", 1)))

def _default_window_for_design(filter_design: str) -> str:
    if filter_design == "iir":
        return str(_iir_options().get("default_design", "butter"))
    return str(_fir_options().get("default_window", "hamming"))

def normalize_choice(choice: Any) -> tuple[str, str]:
    """Normaliza ids/opciones del JSON para que un combobox siempre reciba (id_interno, titulo_visible)."""
    if isinstance(choice, dict):
        return str(choice["id"]), str(choice.get("title", choice["id"]))
    return str(choice), str(choice).replace("_", " ").title() #

def normalize_fir_order(value: int, require_odd: bool = False) -> int:
    """Algunos filtros FIR necesitan orden impar. Este helper normaliza eso en
    un solo sitio para que la UI y el cálculo hablen el mismo idioma."""
    order = max(3, int(value)) # mínimo orden del filtro de valor igual a 3
    if require_odd and order % 2 == 0: # si se trata de un filtro bandstop convertimos el orden a impar
        order += 1 # incrementamos en 1 si el orden actual es par
    return order

def build_filter_defaults(config: dict[str, Any]) -> dict[str, Any]:
    """ Construye la configuración inicial de un filtro a partir de los parámetros definidos en un JSON (particular
    de un experimento)."""
    return {"enabled": bool(config["enabled"]),
        "low_cut": float(config["low_cut"]),
        "high_cut": float(config["high_cut"]),
        "filter_type": str(config["filter_type"]).lower(),
        "filter_design": str(config["filter_design"]).lower(),
        "order": int(config["order"]),
        "window": str(config["window"])}

def _option_ids(options: list[dict[str, Any]] | list[str] | tuple[str, ...] | None) -> list[str]:
    """Extrae los ids válidos de una lista de opciones. Se usa para validar que el usuario haya elegido
    una opción permitida."""
    ids: list[str] = []
    for option in options or []:
        if isinstance(option, dict):
            if option["id"] is not None:
                ids.append(str(option["id"]))
            continue
        ids.append(str(option))
    return ids

def filter_validation_errors(config: dict[str, Any], fs: float, *, minimum_frequency: float = 0.0,
    maximum_frequency: float | None = None) -> list[str]:
    """Función que valida la configuración de un filtro. Llama internamente a _filter_config_error y devuelve
    una lista de errores. Si no hay problemas, devuelve []"""

    if not config.get("enabled", True):  # si el filtro está desactivado no se valida nada
        return []

    fir = _fir_options() # Cargamos las opciones de un filtro FIR
    iir = _iir_options() # Cargamos las opciones de un filtro IIR
    errors: list[str] = []
    nyquist = fs / 2
    minimum_frequency = float(minimum_frequency)
    maximum_frequency = nyquist if maximum_frequency is None else min(float(maximum_frequency), nyquist)
    # Validamos el tipo funcional del filtro y su diseño FIR/IIR.
    errors.extend(_filter_validation.validate_many(config.get("filter_type"),
        [("one_of", {"options": _filter_modes()})], label="Filter type"))
    errors.extend(_filter_validation.validate_many(config.get("filter_design"),
        [("one_of", {"options": _filter_family_ids()})], label="Filter design"))
    # Validamos también low_cut y high_cut.
    errors.extend(_filter_validation.validate_many(config["low_cut"],
        ["finite_number", ("greater_or_equal", {"minimum": minimum_frequency, "suffix": " Hz"}),
            ("less_than", {"maximum": maximum_frequency, "suffix": " Hz"})], label="Low cut"))
    errors.extend(_filter_validation.validate_many(config["high_cut"],
        ["finite_number", ("greater_or_equal", {"minimum": minimum_frequency, "suffix": " Hz"}),
            ("less_than", {"maximum": maximum_frequency, "suffix": " Hz"})], label="High cut"))
    if errors:
        return errors

    low_cut = Validation.coerce_float(config.get("low_cut")) # validamos que sea float
    high_cut = Validation.coerce_float(config.get("high_cut")) # validamos que sea float
    # Validamos que el low_cut sea menor que el high_cut
    errors.extend(_filter_validation.validate_many(low_cut,
        [("less_than", {"maximum": high_cut, "suffix": " Hz"})], label="Low cut"))
    if errors:
        return errors

    filter_design = str(config["filter_design"]).lower()
    # Si el filtro es fir, validamos que el orden sea entero y mayor o igual que 3
    if filter_design == "fir":
        errors.extend(_filter_validation.validate_many(config["order"],
            ["integer", ("greater_or_equal", {"minimum": 3})], label="Order"))
        # También validamos que window sea una ventana permitida dependiendo del JSON de opciones
        fir_windows = _option_ids(fir.get("windows")) # extraemos los ids de las ventanas permitidas
        if fir_windows:
            errors.extend(_filter_validation.validate_many(config.get("window"),
                [("one_of", {"options": fir_windows})], label="Window"))
        return errors

    # Si el filtro es iir, valida que el orden sea entero y mayor o igual que 1. NOTA: si no es FIR, se asume IIR
    errors.extend(_filter_validation.validate_many(config.get("order"),
        ["integer", ("greater_or_equal", {"minimum": 1})], label="Order"))
    # También valida que el diseño elegido sea uno permitido
    iir_designs = _option_ids(iir.get("designs"))
    if iir_designs:
        errors.extend(_filter_validation.validate_many(config.get("window"),
            [("one_of", {"options": iir_designs})], label="Window"))
    if errors:
        return errors
    return errors

def filter_response_error(config: dict[str, Any], fs: float, *, minimum_frequency: float = 0.0,
    maximum_frequency: float | None = None) -> str:
    """Función para construir los mensajes de error. Llama a la función anterior para obtener toda la lista de errores.
    Devolvemos el primer error de la lista de errores."""
    errors = filter_validation_errors(config, fs, minimum_frequency=minimum_frequency, maximum_frequency=maximum_frequency)
    return errors[0] if errors else "Unable to design a response with the selected filter parameters."


def compute_filter_response(config: dict[str, Any], fs: float, mode: FilterMode, *,  minimum_frequency: float = 0.0,
    maximum_frequency: float | None = None) -> FilterResponse | None:
    """Calcula la respuesta en frecuencia de un filtro. Si la configuración no pasa las
    validaciones básicas devolvemos None y el widget mostrará el error."""

    # Si el filtro está desactivado, devolvemos una línea plana a 0 dB
    if not config.get("enabled", True):
        return FilterResponse([0.0, fs / 2], [0.0, 0.0])
    # Después valida la configuración. Si hay errores, no calcula nada.
    if filter_validation_errors(config, fs, minimum_frequency=minimum_frequency, maximum_frequency=maximum_frequency):
        return None

    low_cut = Validation.coerce_float(config["low_cut"])
    high_cut = Validation.coerce_float(config["high_cut"])

    try:
        if str(config["filter_design"]).lower() == "fir": # Filtro FIR
            numtaps = normalize_fir_order(config["order"], require_odd=mode == "bandstop")
            coefficients = signal.firwin(numtaps, [low_cut, high_cut], pass_zero=mode == "bandstop",
                fs=fs, window=str(config["window"])) # utilizamos scipy.signal.firwin
            frequencies, response = signal.freqz(coefficients, worN=1024, fs=fs) # respuesta en frecuencia
        else: # Filtro IIR
            coefficients = signal.iirfilter(int(config["order"]), [low_cut, high_cut], btype=mode,
                fs=fs, ftype=str(config["window"]), output="sos") # utilizamos scipy.signal.iirfilter
            frequencies, response = signal.sosfreqz(coefficients, worN=1024, fs=fs) # respuesta en frecuencia
    except (ValueError, TypeError):
        return None

    magnitude = 20 * np.log10(np.maximum(np.abs(response), 1e-8)) # convertimos magnitud a dB
    # Llamamos a la clase FilterResponse
    return FilterResponse(frequencies.tolist(), magnitude.tolist())


class FilterPreviewPlot(LinePlot):
    """Define una clase que hereda de LinePlot. Es el widget encargado de dibujar la respuesta en frecuencia."""
    def __init__(self):
        # Llamamos al constructor de LinePlot
        super().__init__(x_axis_label="Frequency (Hz)", top_axis_label="0 dB", bottom_axis_label="-80",
            y_minimum=-80.0, y_maximum=0.0, empty_message="Valid configuration required")
        self.response: FilterResponse | None = None # Guarda la respuesta

    def set_response(self, response: FilterResponse | None, empty_message: str | None = None) -> None:
        """Función para actualizar la respuesta mostrada en la gráfica."""
        self.response = response # guarda la respuesta recibida
        series = None if response is None else PlotSeries(response.frequencies, response.magnitude_db)
        self.set_series(series, empty_message=empty_message) # actualizamos la gráfica


class FilterControls(QFrame):
    """Panel editable de los filtros. Este widget es el bloque UI del filtro. Tiene un checkbox por defecto enabled,
    un low_cut y high_cut, un selector FIR/IIR, bloque FIR, bloque IIR, label de error y una señal de changed."""

    changed = Signal() # avisar fuera cuando cambia algo
    def __init__(self, title: str, config: dict[str, Any], mode: FilterMode,
        minimum_frequency: float = 0.0, maximum_frequency: float | None = None):
        super().__init__()
        self.config = config
        self.mode = str(config["filter_type"]).lower() # dice si este panel representa un bandpass o un bandstop
        self.minimum_frequency = float(minimum_frequency)
        self.maximum_frequency = float(maximum_frequency) if maximum_frequency is not None else None
        filter_design = str(config["filter_design"]).lower()
        fir = _fir_options() # obtenemos las opciones FIR del filtering.json
        iir = _iir_options() # obtenemos las opciones IIR del filtering.json
        # Leemos el orden mínimo y máximo
        fir_minimum_order, fir_maximum_order = _integer_bounds(fir, "minimum_order", "maximum_order")
        iir_minimum_order, iir_maximum_order = _integer_bounds(iir, "minimum_order", "maximum_order")
        self.setProperty("role", "filter-controls")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)

        # Checkbox para activar/desactivar el filtro
        self.enabled = QCheckBox(title)
        self.enabled.setObjectName("controlTitle")
        self.enabled.setChecked(bool(config.get("enabled", True)))
        root.addWidget(self.enabled)

        # Bloque base
        grid = QGridLayout()
        if self.maximum_frequency is None:
            self.maximum_frequency = max(float(config["low_cut"]), float(config["high_cut"]), self.minimum_frequency + 1.0)
        # Creamos QDoubleSpinBox para los límites de frecuencia
        self.low = self._double(float(config["low_cut"]), self.minimum_frequency, self.maximum_frequency) # spinbox para low_cut
        self.high = self._double(float(config["high_cut"]), self.minimum_frequency, self.maximum_frequency) # spinbox para high_cut
        self.kind = QComboBox() # combo para elegir FIR o IIR
        for family in _filter_families(): # recorremos las familias disponibles
            family_id, family_title = normalize_choice(family)
            self.kind.addItem(family_title, family_id)
        # Buscamos en el combo la opción que coincide con el tipo de filtro actúal
        family_index = self.kind.findData(filter_design)
        if family_index >= 0:
            self.kind.setCurrentIndex(family_index) # si la encuentra, selecciona esa opción
        grid.addWidget(QLabel("Low cut"), 0, 0)
        grid.addWidget(self.low, 1, 0)
        grid.addWidget(QLabel("High cut"), 0, 1)
        grid.addWidget(self.high, 1, 1)
        grid.addWidget(QLabel("Design"), 0, 2)
        grid.addWidget(self.kind, 1, 2)
        root.addLayout(grid)

        # Bloque contenedor de parámetros
        self.parameters = QWidget()
        self.parameters.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        parameters_layout = QVBoxLayout(self.parameters)
        parameters_layout.setContentsMargins(0, 0, 0, 0)
        parameters_layout.setSpacing(0)

        # Bloque del filtro FIR
        self.fir_widget = QWidget() # subpanel
        self.fir_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        fir_layout = QGridLayout(self.fir_widget)
        fir_layout.setContentsMargins(0, 4, 0, 0)
        fir_layout.setHorizontalSpacing(12)
        fir_layout.setVerticalSpacing(6)
        fir_layout.setColumnStretch(0, 0)
        fir_layout.setColumnStretch(1, 0)
        fir_layout.setColumnStretch(2, 1)
        self.fir_order = QSpinBox() # spinbox para el orden del filtro
        self.fir_order.setRange(fir_minimum_order, fir_maximum_order)
        self.fir_order.setSingleStep(1)
        fir_order_value = int(config["order"]) if filter_design == "fir" else _default_order_for_design("fir")
        self.fir_order.setValue(fir_order_value)
        self.fir_order.setMaximumWidth(140)
        self.window = QComboBox() # combobox para la ventana del filtro
        for window in fir.get("windows", []): # recorremos ventanas definidas en filtering.json
            window_id, window_title = normalize_choice(window) # normalizamos las opciones del combo
            self.window.addItem(window_title, window_id)
        # Buscamos la ventana configurada actualmente
        fir_window_value = str(config["window"]) if filter_design == "fir" else _default_window_for_design("fir")
        window_index = self.window.findData(fir_window_value)
        if window_index >= 0:
            self.window.setCurrentIndex(window_index) # si la encuentra, la selecciona
        self.window.setMaximumWidth(180)
        fir_layout.addWidget(QLabel("FIR order"), 0, 0)
        fir_layout.addWidget(QLabel("Window"), 0, 1)
        fir_layout.addWidget(self.fir_order, 1, 0)
        fir_layout.addWidget(self.window, 1, 1)

        # Bloque del filtro IIR
        self.iir_widget = QWidget() # subpanel
        self.iir_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        iir_layout = QGridLayout(self.iir_widget)
        iir_layout.setContentsMargins(0, 4, 0, 0)
        iir_layout.setHorizontalSpacing(12)
        iir_layout.setVerticalSpacing(6)
        iir_layout.setColumnStretch(0, 0)
        iir_layout.setColumnStretch(1, 0)
        iir_layout.setColumnStretch(2, 1)
        self.iir_order = QSpinBox() # spinbox para el orden del filtro
        self.iir_order.setRange(iir_minimum_order, iir_maximum_order)
        iir_order_value = int(config["order"]) if filter_design == "iir" else _default_order_for_design("iir")
        self.iir_order.setValue(iir_order_value)
        self.iir_order.setMaximumWidth(140)
        self.design = QComboBox() # combobox para el diseño del filtro
        for design in iir["designs"]:
            design_id, design_title = normalize_choice(design) # normalizamos las opciones del combo
            self.design.addItem(design_title, design_id)
        # Buscamos el diseño configurado actualmente
        iir_window_value = str(config["window"]) if filter_design == "iir" else _default_window_for_design("iir")
        design_index = self.design.findData(iir_window_value)
        if design_index >= 0:
            self.design.setCurrentIndex(design_index) # si encuentra el diseño, lo selecciona
        self.design.setMaximumWidth(180)
        iir_layout.addWidget(QLabel("IIR order"), 0, 0)
        iir_layout.addWidget(QLabel("Design"), 0, 1)
        iir_layout.addWidget(self.iir_order, 1, 0)
        iir_layout.addWidget(self.design, 1, 1)

        # Añadimos los sub-paneles FIR e IIR al contenedor de parámetros.
        # Luego _sync() decide cuál se muestra y cuál se oculta.
        parameters_layout.addWidget(self.fir_widget)
        parameters_layout.addWidget(self.iir_widget)
        root.addWidget(self.parameters)
        self.error_label = QLabel() # etiqueta vacía para mostrar errores o warnings
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide() # lo ocultamos al inicio
        root.addWidget(self.error_label)
        root.addStretch(1)

        # Guardamos todos los controles editables en una lista para poder (des)activarlos de golpe.
        self.controls = [self.low, self.high, self.kind, self.fir_order, self.window, self.iir_order, self.design]

        # Conectamos todos los controles a _sync() para que cualquier cambio de la UI dispare
        self.enabled.toggled.connect(self._sync)
        self.kind.currentTextChanged.connect(self._sync)
        for control in (self.low, self.high):
            control.valueChanged.connect(self._sync)
        for control in (self.fir_order, self.iir_order):
            control.valueChanged.connect(self._sync)
        self.window.currentIndexChanged.connect(self._sync)
        self.design.currentIndexChanged.connect(self._sync)
        self._sync()

    @staticmethod
    def _double(value: float, minimum_value: float, maximum_value: float) -> QDoubleSpinBox:
        """Helper para crear spinboxes decimales de frecuencia"""
        spin = QDoubleSpinBox()
        spin.setRange(minimum_value, maximum_value)
        spin.setDecimals(1)
        spin.setValue(value)
        spin.setSuffix(" Hz")
        return spin

    def set_cut_frequency_bounds(self, minimum_frequency: float, maximum_frequency: float | None) -> None:
        """Actualiza los rangos permitidos para las frecuencias de corte."""
        minimum = float(minimum_frequency)
        maximum = float(maximum_frequency) if maximum_frequency is not None else max(self.low.value(), self.high.value())
        maximum = max(minimum+1, maximum)
        if self.minimum_frequency == minimum and self.maximum_frequency == maximum:
            return
        self.minimum_frequency = minimum
        self.maximum_frequency = maximum
        for control in (self.low, self.high):
            signals_were_blocked = control.blockSignals(True)
            control.setRange(minimum, maximum) # actualizamos rango permitido
            control.blockSignals(signals_were_blocked)

        # Actualizamos la configuración con los valores actuales
        self.config["low_cut"] = self.low.value()
        self.config["high_cut"] = self.high.value()

    def _sync(self) -> None:
        """Lee la interfaz y actualiza self.config, muestra u oculta controles FIR/IIR, y activa/desactiva
        parámetros según el diseño."""
        # Obtenemos el diseño FIR/IIR seleccionado
        filter_design = str(self.kind.currentData() or self.kind.currentText()).lower()
        require_odd_fir_order = self.mode == "bandstop" and filter_design == "fir"

        # Leemos lo que el usuario ha puesto en la UI y lo guardamos en self.config
        self.config.clear()
        self.config["enabled"] = self.enabled.isChecked()
        self.config["filter_type"] = self.mode
        self.config["filter_design"] = filter_design
        self.config["low_cut"] = self.low.value()
        self.config["high_cut"] = self.high.value()
        if filter_design == "fir":
            # (Normalizamos el orden del filtro FIR)
            self.config["order"] = normalize_fir_order(self.fir_order.value(), require_odd=require_odd_fir_order)
            self.config["window"] = self.window.currentData()
        else:
            self.config["order"] = self.iir_order.value()
            self.config["window"] = self.design.currentData()

        # Decidimos si el filtro es FIR o IIR. En función de la decisión, muestra el bloque correcto y oculta el otro.
        is_fir = self.config["filter_design"] == "fir"
        self.fir_widget.setVisible(is_fir)
        self.iir_widget.setVisible(not is_fir)

        self.parameters.adjustSize()
        self.parameters.updateGeometry()
        self.adjustSize()
        self.updateGeometry()

        # Desactivamos todos los controles si el filtro está apagado
        for control in self.controls:
            control.setEnabled(self.config["enabled"])

        # Emitimos señal de que algo ha cambiado
        self.changed.emit()

    def set_message(self, message: str | None, *, role: str = "error") -> None:
        """Muestra u oculta el mensaje del filtro con estilo de error o warning. La diferencia con
        filter_response_error es que una dice qué texto sale y la otra decide cómo se enseña en la UI."""
        if message is None:
            self.error_label.clear()
            self.error_label.hide()
            return

        self.error_label.setProperty("role", role)
        self.error_label.style().unpolish(self.error_label)
        self.error_label.style().polish(self.error_label)
        self.error_label.setText(message)
        self.error_label.show()


__all__ = ["FilterControls", "FilterMode", "FilterPreviewPlot", "FilterResponse", "build_filter_defaults",
    "compute_filter_response", "filter_response_error", "filter_validation_errors", "normalize_choice",
    "normalize_fir_order", "filter_defaults"]
