from __future__ import annotations
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
import numpy as np
from PySide6.QtCore import QPointF, Property, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QLabel, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget)
from scipy import signal
from medusa_analyzer.frontend.models import Validation
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
    - FilerPreviewPlot dibuja la respuesta en frecuencia"""

""" NOTA: Keys soportadas al definir un filtro en un experimento:
    - `id`
    - `title`
    - `mode`
    - `plot_title` identifican el filtro y su UI
    - `enabled`
    - `filter_type`
    - `low_cut`
    - `high_cut`
    - `fir_order`
    - `fir_window`
    - `iir_order`
    - `iir_design`
    - `iir_rp_db`
    - `iir_rs_db` fijan el estado inicial
    `limits_frequency_bands`
    `must_be_within_filter` 
    `out_of_range_warning`"""


FilterMode = Literal["bandpass", "bandstop"] # modos posibles # TODO: INCLUIR LOWPASS Y HIGHPASS
_filter_validation = Validation() # objeto de validación
filter_defaults = json.loads( # Carga de configuración por defecto
    (Path(__file__).resolve().parents[1] / "defaults" / "filtering.json").read_text(encoding="utf-8"))


def normalize_choice(choice: Any) -> tuple[str, str]:
    """Normaliza ids/opciones del JSON para que un combobox siempre reciba (id_interno, titulo_visible)."""
    if isinstance(choice, dict):
        return str(choice["id"]), str(choice.get("title", choice["id"]))
    return str(choice), str(choice).replace("_", " ").title()


def normalize_fir_order(value: int, require_odd: bool = False) -> int:
    """Algunos filtros FIR necesitan orden impar. Este helper normaliza eso en
    un solo sitio para que la UI y el cálculo hablen el mismo idioma."""
    order = max(3, int(value)) # mínimo orden del filtro de valor igual a 3
    if require_odd and order % 2 == 0: # si se trata de un filtro bandstop convertimos el orden a impar
        order += 1
    return order


def build_filter_defaults(config: dict[str, Any], filter_options: dict[str, Any]) -> dict[str, Any]:
    fir_options = filter_options["fir"]
    iir_options = filter_options["iir"]
    """ Construye la configuración inicial del filtro."""
    return {"enabled": bool(config["enabled"]),
        "low_cut": float(config["low_cut"]),
        "high_cut": float(config["high_cut"]),
        "filter_type": str(config["filter_type"]).lower(),
        "fir_order": config["fir_order"],
        "fir_window": str(config.get("fir_window", fir_options["default_window"])),
        "iir_order": int(config["iir_order"]),
        "iir_design": str(config.get("iir_design", iir_options["default_design"])),
        "iir_rp_db": float(config["iir_rp_db"]),
        "iir_rs_db": float(config["iir_rs_db"])}


@dataclass(frozen=True, slots=True)
class FilterResponse:
    """Clase que guarda el resultado del cálculo de un filtro (frecuencia y magnitud)"""
    frequencies: list[float]
    magnitude_db: list[float]

def _option_ids(options: list[dict[str, Any]] | list[str] | tuple[str, ...] | None) -> list[str]:
    """Extrae los ids válidos de una lista de opciones. Se una para validar que el usuario haya elegido
    una opción permitida."""
    ids: list[str] = []
    for option in options or []:
        if isinstance(option, dict):
            if option["id"] is not None:
                ids.append(str(option["id"]))
            continue
        ids.append(str(option))
    return ids

def filter_validation_errors(config: dict[str, Any], fs: float, *, filter_options: dict[str, Any],
    minimum_frequency: float = 0.0, maximum_frequency: float | None = None) -> list[str]:
    """Función de validación. Llama internamente a _filter_config_error y devuelve una lista de errores. Si no hay problemas,
    devuelve []"""

    if not config.get("enabled", True):  # si el filtro está desactivado no se valida nada
        return []

    fir_options = filter_options.get("fir", {})
    iir_options = filter_options.get("iir", {})
    errors: list[str] = []
    nyquist = fs / 2
    minimum_frequency = float(minimum_frequency)
    maximum_frequency = nyquist if maximum_frequency is None else min(float(maximum_frequency), nyquist)
    # Validamos que el filtro sea "fir" o "iir"
    errors.extend(_filter_validation.validate_many(config.get("filter_type"),
        [("one_of", {"options": _option_ids(filter_options.get("families"))})], label="Filter type"))
    # Validamos también low_cut y high_cut.
    errors.extend(_filter_validation.validate_many(config["low_cut"],
        ["finite_number", ("greater_than", {"minimum": minimum_frequency, "suffix": " Hz"}),
            ("less_than", {"maximum": maximum_frequency, "suffix": " Hz"})], label="Low cut"))
    errors.extend(_filter_validation.validate_many(config["high_cut"],
        ["finite_number", ("greater_than", {"minimum": minimum_frequency, "suffix": " Hz"}),
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

    # Si el filtro es fir, validamos que el orden sea entero y mayor o igual que 3
    if str(config["filter_type"]).lower() == "fir":
        errors.extend(_filter_validation.validate_many(config["fir_order"],
            ["integer", ("greater_or_equal", {"minimum": 3})], label="FIR order"))
        # También validamos que fil_window sea una ventana permitida dependiendo del JSON de opciones
        fir_windows = _option_ids((fir_options or {}).get("windows"))
        if fir_windows:
            errors.extend(_filter_validation.validate_many(config.get("fir_window"),
                [("one_of", {"options": fir_windows})], label="FIR window"))
        return errors

    # Si el filtro es iir, valida que el orden sea entero y mayor o igual que 1.
    errors.extend(_filter_validation.validate_many(config.get("iir_order"),
        ["integer", ("greater_or_equal", {"minimum": 1})], label="IIR order"))
    # También valida contra los diseños permitidos
    iir_designs = _option_ids((iir_options or {}).get("designs"))
    if iir_designs:
        errors.extend(_filter_validation.validate_many(config.get("iir_design"),
            [("one_of", {"options": iir_designs})], label="IIR design"))
    if errors:
        return errors
    # después miramos el tipo de diseño
    if str(config["iir_design"]) in {"cheby1", "ellip"}:
        errors.extend(_filter_validation.validate_many(config["iir_rp_db"],
            ["finite_number", ("greater_than", {"minimum": 0.0, "suffix": " dB"})], label="Passband ripple"))
    if str(config["iir_design"]) in {"cheby2", "ellip"}:
        errors.extend(_filter_validation.validate_many(config["iir_rs_db"],
            ["finite_number", ("greater_than", {"minimum": 0.0, "suffix": " dB"})], label="Stopband attenuation"))
    return errors

def filter_response_error(config: dict[str, Any], fs: float, *, filter_options: dict[str, Any],
    minimum_frequency: float = 0.0, maximum_frequency: float | None = None) -> str:
    """Función para construir los mensajes de error. Devolvemos el primer error de la lista de errores."""
    errors = filter_validation_errors(config, fs, filter_options=filter_options, minimum_frequency=minimum_frequency,
        maximum_frequency=maximum_frequency)
    return errors[0] if errors else "Unable to design a response with the selected filter parameters."


def compute_filter_response(config: dict[str, Any], fs: float, mode: FilterMode, *, filter_options: dict[str, Any],
    minimum_frequency: float = 0.0, maximum_frequency: float | None = None) -> FilterResponse | None:
    """Calcula la respuesta en frecuencia de un filtro. Si la configuración no pasa las
    validaciones básicas devolvemos None y el widget mostrará el error."""

    # Si el filtro está desactivado, devolvemos una línea plana a 0 dB
    if not config.get("enabled", True):
        return FilterResponse([0.0, fs / 2], [0.0, 0.0])
    # Después valida la configuración. Si hay errores, no calcula nada.
    if filter_validation_errors(config, fs, filter_options=filter_options, minimum_frequency=minimum_frequency,
        maximum_frequency=maximum_frequency):
        return None

    low_cut = Validation.coerce_float(config["low_cut"])
    high_cut = Validation.coerce_float(config["high_cut"])

    try:
        if str(config["filter_type"]).lower() == "fir": # Filtro FIR
            numtaps = normalize_fir_order(config["fir_order"], require_odd=mode == "bandstop")
            coefficients = signal.firwin(numtaps, [low_cut, high_cut], pass_zero=mode == "bandstop",
                fs=fs, window=str(config["fir_window"])) # utilizamos scipy.signal.firwin
            frequencies, response = signal.freqz(coefficients, worN=1024, fs=fs) # respuesta en frecuencia
        else: # Filtro IIR
            iir_kwargs: dict[str, Any] = {}
            if str(config["iir_design"]) in {"cheby1", "ellip"}:
                iir_kwargs["rp"] = float(config["iir_rp_db"])
            if str(config["iir_design"]) in {"cheby2", "ellip"}:
                iir_kwargs["rs"] = float(config["iir_rs_db"])
            coefficients = signal.iirfilter(int(config["iir_order"]), [low_cut, high_cut], btype=mode,
                fs=fs, ftype=str(config["iir_design"]), output="sos", **iir_kwargs) # utilizamos scipy.signal.iirfilter
            frequencies, response = signal.sosfreqz(coefficients, worN=1024, fs=fs) # respuesta en frecuencia
    except (ValueError, TypeError):
        return None

    magnitude = 20 * np.log10(np.maximum(np.abs(response), 1e-8)) # convertimos magnitud a dB
    return FilterResponse(frequencies.tolist(), magnitude.tolist())


class FilterPreviewPlot(LinePlot):
    """Widget que pinta la gráfica de respuesta en frecuencia."""
    def __init__(self): # inicializamos el widget de la gráfica, sus colores y su estado vacío
        super().__init__(x_axis_label="Frequency (Hz)", top_axis_label="0 dB", bottom_axis_label="-80",
            y_minimum=-80.0, y_maximum=0.0, empty_message="Valid configuration required")
        self.response: FilterResponse | None = None # Guarda la respuesta

    def set_response(self, response: FilterResponse | None, empty_message: str | None = None) -> None:
        """Guarda la respuesta del filtro o el mensaje vacío y repinta el widget."""
        self.response = response
        series = None if response is None else PlotSeries(response.frequencies, response.magnitude_db)
        self.set_series(series, empty_message=empty_message)


class FilterControls(QFrame):
    """Panel editable de los filtros. Este widget es el bloque UI del filtro. Tiene un checkbox por defecto enabled,
    un low_cut y high_cut, un selector FIR/IIR, bloque FIR, bloque IIR, label de error y una señal de changed."""

    changed = Signal() # avisar fuera cuando cambia algo
    def __init__(self, title: str, config: dict[str, Any], filter_options: dict[str, Any], mode: FilterMode,
        minimum_frequency: float = 0.0, maximum_frequency: float | None = None):
        super().__init__()
        self.config = config
        self.mode = mode # dice si este panel representa un bandpass o un bandstop
        self.minimum_frequency = float(minimum_frequency)
        self.maximum_frequency = float(maximum_frequency) if maximum_frequency is not None else None
        fir = filter_options.get("fir", {})
        iir = filter_options.get("iir", {})
        iir_rp = iir["rp_db"]
        iir_rs = iir["rs_db"]
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
        frequency_maximum = self.maximum_frequency
        if frequency_maximum is None:
            frequency_maximum = max(float(config["low_cut"]), float(config["high_cut"]), self.minimum_frequency + 1.0)
        self.low = self._double(float(config["low_cut"]), self.minimum_frequency, frequency_maximum) # spinbox para low_cut
        self.high = self._double(float(config["high_cut"]), self.minimum_frequency, frequency_maximum) # spinbox para high_cut
        self.kind = QComboBox() # combo para elegir FIR o IIR
        for family in filter_options.get("families", []):
            family_id, family_title = normalize_choice(family)
            self.kind.addItem(family_title, family_id)
        family_index = self.kind.findData(str(config["filter_type"]).lower())
        if family_index >= 0:
            self.kind.setCurrentIndex(family_index)
        grid.addWidget(QLabel("Low cut"), 0, 0)
        grid.addWidget(self.low, 1, 0)
        grid.addWidget(QLabel("High cut"), 0, 1)
        grid.addWidget(self.high, 1, 1)
        grid.addWidget(QLabel("Type"), 0, 2)
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
        self.fir_order.setRange(int(fir["minimum_order"]), int(fir["maximum_order"]))
        self.fir_order.setSingleStep(1)
        self.fir_order.setValue(int(config["fir_order"]))
        self.fir_order.setMaximumWidth(140)
        self.window = QComboBox() # combobox para la ventana del filtro
        for window in fir.get("windows", []):
            window_id, window_title = normalize_choice(window) # normalizamos las opciones del combo
            self.window.addItem(window_title, window_id)
        window_index = self.window.findData(str(config.get("fir_window", fir["default_window"])))
        if window_index >= 0:
            self.window.setCurrentIndex(window_index)
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
        self.iir_order.setRange(int(iir["minimum_order"]), int(iir["maximum_order"]))
        self.iir_order.setValue(int(config["iir_order"]))
        self.iir_order.setMaximumWidth(140)
        self.design = QComboBox() # combobox para el diseño del filtro
        for design in iir["designs"]:
            design_id, design_title = normalize_choice(design) # normalizamos las opciones del combo
            self.design.addItem(design_title, design_id)
        design_index = self.design.findData(str(config.get("iir_design", iir["default_design"])))
        if design_index >= 0:
            self.design.setCurrentIndex(design_index)
        self.design.setMaximumWidth(180)
        self.iir_rp = QDoubleSpinBox() # spinbox para el rizado de la banda de paso
        self.iir_rp.setRange(float(iir_rp["minimum"]), float(iir_rp["maximum"]))
        self.iir_rp.setDecimals(2)
        self.iir_rp.setValue(float(config["iir_rp_db"]))
        self.iir_rp.setSuffix(" dB")
        self.iir_rp.setMaximumWidth(140)
        self.iir_rs = QDoubleSpinBox() # spinbox para la atenuación en la banda de rechazo
        self.iir_rs.setRange(float(iir_rs["minimum"]), float(iir_rs["maximum"]))
        self.iir_rs.setDecimals(1)
        self.iir_rs.setValue(float(config["iir_rs_db"]))
        self.iir_rs.setSuffix(" dB")
        self.iir_rs.setMaximumWidth(180)
        iir_layout.addWidget(QLabel("IIR order"), 0, 0)
        iir_layout.addWidget(QLabel("Design"), 0, 1)
        iir_layout.addWidget(self.iir_order, 1, 0)
        iir_layout.addWidget(self.design, 1, 1)
        iir_layout.addWidget(QLabel("Passband ripple"), 2, 0)
        iir_layout.addWidget(QLabel("Stopband attenuation"), 2, 1)
        iir_layout.addWidget(self.iir_rp, 3, 0)
        iir_layout.addWidget(self.iir_rs, 3, 1)

        parameters_layout.addWidget(self.fir_widget)
        parameters_layout.addWidget(self.iir_widget)
        root.addWidget(self.parameters)
        self.error_label = QLabel() # etiqueta donde aparece el mensaje de error del filtro
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)
        root.addStretch(1)

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
        self.iir_rp.valueChanged.connect(self._sync)
        self.iir_rs.valueChanged.connect(self._sync)
        self._sync()

    @staticmethod
    def _double(value: float, minimum_value: float, maximum_value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum_value, maximum_value)
        spin.setDecimals(1)
        spin.setValue(value)
        spin.setSuffix(" Hz")
        return spin

    def set_frequency_bounds(self, minimum_frequency: float, maximum_frequency: float | None) -> None:
        """Actualiza los rangos permitidos para las frecuencias de corte."""
        self.minimum_frequency = float(minimum_frequency)
        self.maximum_frequency = float(maximum_frequency) if maximum_frequency is not None else None
        effective_maximum = self.maximum_frequency
        if effective_maximum is None:
            effective_maximum = max(self.low.value(), self.high.value(), self.minimum_frequency + 1.0)
        for control in (self.low, self.high):
            signals_were_blocked = control.blockSignals(True)
            control.setRange(self.minimum_frequency, effective_maximum)
            control.blockSignals(signals_were_blocked)
        self.config["low_cut"] = self.low.value()
        self.config["high_cut"] = self.high.value()

    def _sync(self) -> None:
        """Lee la interfaz y actualiza self.config, muestra u oculta controles FIR/IIR, y activa/desactiva
        parámetros según el diseño."""
        filter_type = str(self.kind.currentData() or self.kind.currentText()).lower()
        require_odd_fir_order = self.mode == "bandstop" and filter_type == "fir"

        # Leemos toodo lo que el usuario ha puesto en la UI y lo guardamos en self.config
        self.config["enabled"] = self.enabled.isChecked()
        self.config["low_cut"] = self.low.value()
        self.config["high_cut"] = self.high.value()
        self.config["filter_type"] = filter_type
        # (Normalizamos el orden del filtro FIR)
        self.config["fir_order"] = normalize_fir_order(self.fir_order.value(), require_odd=require_odd_fir_order)
        self.config["fir_window"] = self.window.currentData()
        self.config["iir_order"] = self.iir_order.value()
        self.config["iir_design"] = self.design.currentData()
        self.config["iir_rp_db"] = self.iir_rp.value()
        self.config["iir_rs_db"] = self.iir_rs.value()

        # Decidimos si el filtro es FIR o IIR. En función de la decisión, muestra el bloque correcto y oculta el otro.
        is_fir = self.config["filter_type"] == "fir"
        self.fir_widget.setVisible(is_fir)
        self.iir_widget.setVisible(not is_fir)

        self.parameters.adjustSize()
        self.parameters.updateGeometry()
        self.adjustSize()
        self.updateGeometry()

        design = self.config["iir_design"]
        # Activamos/desactivamos 'rp' y 'rs' según el diseño IIR
        self.iir_rp.setEnabled(self.config["enabled"] and not is_fir and design in {"cheby1", "ellip"})
        self.iir_rs.setEnabled(self.config["enabled"] and not is_fir and design in {"cheby2", "ellip"})
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
