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

"""Script para crear parte de una interfaz gráfica para configurar filtros, calcular su respuesta en 
frecuencia y dibujar una previsualización en pantalla. El flujo principal es este:
    - Se cargan los valores por defecto desde filtering.json
    - Se crea una configuración inicial del filtro
    - La clase FilerControls muestra controles en pantalla_ activar/desactivar, frecuencias de corte, tipo 
    FIR/IIR, orden, ventana, diseño, etc. 
    - Cuando el usario modifica algo, _sync() actualiza self.config y se emite señal changed.
    - Otro widget puede llamar a compute_filter_response()
    - Si la configuración es válida, se calcula la curva del filtro
    - FilerPreviewPlot dibuja la respuesta en frecuencia"""

FilterMode = Literal["bandpass", "bandstop"] # modos posibles # TODO: INCLUIR LOWPASS Y HIGHPASS
_filter_validation = Validation() # objeto de validación
filter_defaults = json.loads( # Carga de configuración por defecto
    (Path(__file__).resolve().parents[1] / "defaults" / "filtering.json").read_text(encoding="utf-8"))

def normalize_choice(choice: Any) -> tuple[str, str]:
    # TODO: meter en el validator generalizándolo para otros casos?
    # Normaliza ids/opciones del JSON para que un combobox siempre reciba
    # (id_interno, titulo_visible).
    if isinstance(choice, dict):
        return str(choice["id"]), str(choice.get("title", choice["id"]))
    return str(choice), str(choice).replace("_", " ").title()


def normalize_fir_order(value: int, require_odd: bool = False) -> int:
    # TODO: meter en el validator generalizándolo para otros casos?
    # Algunos filtros FIR necesitan orden impar. Este helper normaliza eso en
    # un solo sitio para que la UI y el cálculo hablen el mismo idioma.
    order = max(3, int(value)) # mínimo orden del filtro de valor igual a 3
    if require_odd and order % 2 == 0: # si se trata de un filtro bandstop convertimos el orden a impar
        order += 1
    return order


def build_filter_defaults(config: dict[str, Any]) -> dict[str, Any]:
    """ Construye la configuración inicial del filtro."""
    # TODO: he quitado comprobaciones de aqui de normalize y odd y demás, porque en lo de por defecto siempre va a venir
    # bien, entonces aquí no hace falta.
    return {"enabled": bool(config["enabled"]),
        "low_cut": float(config["low_cut"]),
        "high_cut": float(config["high_cut"]),
        "filter_type": str(config["filter_type"]).lower(),
        "fir_order": config["fir_order"],
        "fir_window": str(config.get("fir_window", "hamming")),
        "iir_order": int(config.get("iir_order", 4)),
        "iir_design": str(config.get("iir_design", "butter")),
        "iir_rp_db": float(config.get("iir_rp_db", 1.0)),
        "iir_rs_db": float(config.get("iir_rs_db", 40.0))}


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

def _filter_config_errors(config: dict[str, Any], *, label: str, fs: float,
    fir_options: dict[str, Any] | None = None, iir_options: dict[str, Any] | None = None, **_: Any) -> list[str]:
    """Revisa si la configuración del filtro es váldia."""
    _ = label
    if not config.get("enabled", True): # si el filtro está desactivado no se valida nada
        return []

    errors: list[str] = []
    nyquist = fs / 2 #  todo: aquí no se debería parchaer, tendría que ser con los datos que se pasen desde un widget individual no??
    # Validamos que el filtro sea "fir" o "iir"
    filter_type_errors = _filter_validation.validate_many(config.get("filter_type"),
        [("one_of", {"options": ["fir", "iir"]})], label="Filter type")
    errors.extend(filter_type_errors)
    # Validamos también low_cut y high_cut. # TODO: LO MISMO, EL MÍNIMO Y MÁXIMO NO TENDRÍAN QUE VENIR DESDE OTRO LADO?
    errors.extend(_filter_validation.validate_many(config["low_cut"],
        ["finite_number", ("greater_than", {"minimum": 0.0, "suffix": " Hz"}),
            ("less_than", {"maximum": nyquist, "suffix": " Hz"})], label="Low cut"))
    errors.extend(_filter_validation.validate_many(config["high_cut"],
        ["finite_number", ("greater_than", {"minimum": 0.0, "suffix": " Hz"}),
            ("less_than", {"maximum": nyquist, "suffix": " Hz"})], label="High cut"))
    if errors:
        return errors

    low_cut = Validation.coerce_float(config.get("low_cut")) # validamos que sea float
    high_cut = Validation.coerce_float(config.get("high_cut")) # validamos que sea float
    # Validamos que el low_cut sea menor que el high_cut
    errors.extend(_filter_validation.validate_many(low_cut,
        [("less_than", {"maximum": high_cut, "suffix": " Hz"})],
        label="Low cut"))
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
        errors.extend(_filter_validation.validate_many(config["iir_rp_db"]),
            ["finite_number", ("greater_than", {"minimum": 0.0, "suffix": " dB"})], label="Passband ripple")
    if str(config["ir_design"]) in {"cheby2", "ellip"}:
        errors.extend(_filter_validation.validate_many(config["iir_rs_db"],
            ["finite_number", ("greater_than", {"minimum": 0.0, "suffix": " dB"})], label="Stopband attenuation"))
    return errors


def filter_validation_errors(config: dict[str, Any], fs: float, *, fir_options: dict[str, Any] | None = None,
    iir_options: dict[str, Any] | None = None) -> list[str]:
    """Función de validación. Llama internamente a _filter_config_error y deveulve una lista de errores. Si no hay problemas,
    devuelve []"""
    # TODO: porque no se unifican en una???
    return _filter_validation.validate_errors(config, "custom", label="Filter",
        validator=_filter_config_errors, fs=fs, fir_options=fir_options, iir_options=iir_options)


def compute_filter_response(config: dict[str, Any], fs: float, mode: FilterMode, *,
    fir_options: dict[str, Any] | None = None, iir_options: dict[str, Any] | None = None) -> FilterResponse | None:
    """Calcula la respuesta en frecuencia de un filtro. Si la configuración no pasa las
    validaciones básicas devolvemos None y el widget mostrará el error."""

    # Si el filtro está desactivado, devolvemos una línea plana a 0 dB
    if not config.get("enabled", True):
        return FilterResponse([0.0, fs / 2], [0.0, 0.0])
    # Después valida la configuración. Si hay errores, no calcula nada.
    if filter_validation_errors(config, fs, fir_options=fir_options, iir_options=iir_options):
        return None

    low_cut = Validation.coerce_float(config["low_cut"])
    high_cut = Validation.coerce_float(config["high_cut"])

    try:
        if str(config["filter_type"]).lower() == "fir": # Filtro FIR
            # TODO: porque hardcodeamos que es bandstop?? No sería en función de lo que se diga en un json? Osea dependiente de argumento??
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


def filter_response_error(config: dict[str, Any], fs: float, *, fir_options: dict[str, Any] | None = None,
    iir_options: dict[str, Any] | None = None) -> str:
    """"Función para construir los mensajes de error."""
    # Primero pide los errores de validación
    validation_errors = filter_validation_errors(config, fs, fir_options=fir_options, iir_options=iir_options)
    if validation_errors:
        return validation_errors[0] # Si hay alguno el primero
    # TODO: de alguna forma no se podrían combinar esta función con esta filter_validation_errors y esta _filter_config_errors???
    return "Unable to design a response with the selected filter parameters."


class FilterPreviewPlot(QFrame):
    """Widget que pinta la gráfica de respuesta en frecuencia."""
    # TODO: IGUAL EN UN FUTURO SE PODRÍA HACER UNA CLASE PLOT Y HEREDAR DE ESA
    def __init__(self): # inicializamos el widget de la gráfica, sus colores y su estado vacío
        super().__init__()
        self.setProperty("role", "plot")
        self.setMinimumHeight(225)
        self._plot_background_color = QColor("#FBFAF8")
        self._grid_color = QColor("#E5DFDD")
        self._axis_line_color = QColor("#B8B0B4")
        self._axis_text_color = QColor("#756F77")
        self._response_line_color = QColor("#0E7C86")
        self._empty_message_color = QColor("#756F77")
        self.response: FilterResponse | None = None # Guarda la respuesta
        self.empty_message = "Valid configuration required" # Guarda mensaje vacío si no hay respuesta

    def set_response(self, response: FilterResponse | None, empty_message: str | None = None) -> None:
        """Guarda la respuesta del filtro o el mensaje vacío y repinta el widget."""
        self.response = response
        self.empty_message = empty_message or "Valid configuration required"
        self.update()

    def _set_color(self, attribute: str, value) -> None:
        """Cambia uno de los colores internos y repinta."""
        setattr(self, attribute, QColor(value))
        self.update()

    def get_plot_background_color(self) -> QColor:
        """Devuelve el color del fondo de la gráfica."""
        return self._plot_background_color

    def set_plot_background_color(self, value) -> None:
        self._set_color("_plot_background_color", value) # cambia el color de fondo de la gráfica

    def get_grid_color(self) -> QColor:
        return self._grid_color # devuelve el color de la rejilla

    def set_grid_color(self, value) -> None:
        self._set_color("_grid_color", value) # cambia el color de la rejilla

    def get_axis_line_color(self) -> QColor:
        return self._axis_line_color # devuelve el color de la línea del eje

    def set_axis_line_color(self, value) -> None:
        self._set_color("_axis_line_color", value) # cambia el color de la línea del eje

    def get_axis_text_color(self) -> QColor:
        return self._axis_text_color # devuelve el color del texto de los ejes

    def set_axis_text_color(self, value) -> None:
        self._set_color("_axis_text_color", value) # cambia el color del texto de los ejes

    def get_response_line_color(self) -> QColor: # devuelve el color de la curva de la respuesta
        return self._response_line_color

    def set_response_line_color(self, value) -> None: # cambia el color de la curva de la respuesta
        self._set_color("_response_line_color", value)

    def get_empty_message_color(self) -> QColor:
        return self._empty_message_color # devuelve el color del mensaje cuando no hay gráfica

    def set_empty_message_color(self, value) -> None:
        self._set_color("_empty_message_color", value) # cambia el color del mensaje vacío

    @staticmethod
    def _nice_step(value: float) -> float:
        """Función para que el eje X del gráfico quede bonito. Va de la mano de _frequency_ticks."""
        if value <= 0:
            return 1.0
        exponent = math.floor(math.log10(value))
        fraction = value / 10 ** exponent
        if fraction <= 1:
            nice_fraction = 1
        elif fraction <= 2:
            nice_fraction = 2
        elif fraction <= 5:
            nice_fraction = 5
        else:
            nice_fraction = 10
        return nice_fraction * 10 ** exponent

    @classmethod
    def _frequency_ticks(cls, maximum_frequency: float, plot_width: float) -> tuple[float, list[float]]:
        """Función para que el eje X del gráfico quede bonito. Va de la mano de _nice_step."""
        target_intervals = max(2, min(6, int(plot_width // 72)))
        step = cls._nice_step(maximum_frequency / target_intervals)
        axis_maximum = max(step, math.ceil(maximum_frequency / step) * step)
        tick_count = int(round(axis_maximum / step))
        ticks = [index * step for index in range(tick_count + 1)]
        return axis_maximum, ticks

    def paintEvent(self, event):
        """Función para pintar todoo del gráfico: fondo, rejilla, ejes, etiquetas, mensaje vacío si no hay respuesta,
        curva (si la hay), etc."""

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self.rect().adjusted(48, 18, -18, -55)
        painter.fillRect(plot, self._plot_background_color)

        maximum_frequency = max(self.response.frequencies) if self.response and self.response.frequencies else 1.0
        axis_maximum, frequency_ticks = self._frequency_ticks(maximum_frequency, plot.width())

        painter.setPen(QPen(self._grid_color, 1))
        for index in range(5):
            y = plot.top() + plot.height() * index / 4
            painter.drawLine(plot.left(), int(y), plot.right(), int(y))

        for frequency in frequency_ticks:
            x = plot.left() + plot.width() * frequency / axis_maximum
            painter.drawLine(int(x), plot.top(), int(x), plot.bottom())

        painter.setPen(QPen(self._axis_line_color, 1))
        painter.drawLine(plot.left(), plot.bottom(), plot.right(), plot.bottom())

        axis_font = QFont(painter.font())
        axis_font.setPointSizeF(max(7.0, axis_font.pointSizeF() - 1.0))
        painter.setFont(axis_font)
        painter.setPen(self._axis_text_color)
        painter.drawText(QRectF(5, plot.top(), 38, 20), Qt.AlignmentFlag.AlignRight, "0 dB")
        painter.drawText(QRectF(5, plot.bottom() - 15, 38, 20), Qt.AlignmentFlag.AlignRight, "-80")

        for frequency in frequency_ticks:
            x = plot.left() + plot.width() * frequency / axis_maximum
            label_width = 58.0
            label_left = max(1.0, min(self.width() - label_width - 1.0, x - label_width / 2))
            painter.drawText(QRectF(label_left, plot.bottom() + 4, label_width, 17),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, f"{frequency:g}")

        painter.drawText(plot.left(), plot.bottom() + 25, plot.width(), 20, Qt.AlignmentFlag.AlignCenter,
            "Frequency (Hz)")
        if not self.response or len(self.response.frequencies) < 2:
            painter.setPen(self._empty_message_color)
            painter.drawText(plot.adjusted(24, 24, -24, -24), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self.empty_message)
            return

        path = QPainterPath()
        for index, (frequency, magnitude) in enumerate(zip(self.response.frequencies, self.response.magnitude_db)):
            x = plot.left() + plot.width() * frequency / axis_maximum
            y = plot.bottom() - plot.height() * min(80, max(0, magnitude + 80)) / 80
            point = QPointF(x, y)
            path.moveTo(point) if index == 0 else path.lineTo(point)
        painter.setPen(QPen(self._response_line_color, 2.4))
        painter.drawPath(path)

    plotBackgroundColor = Property(QColor, get_plot_background_color, set_plot_background_color)
    gridColor = Property(QColor, get_grid_color, set_grid_color)
    axisLineColor = Property(QColor, get_axis_line_color, set_axis_line_color)
    axisTextColor = Property(QColor, get_axis_text_color, set_axis_text_color)
    responseLineColor = Property(QColor, get_response_line_color, set_response_line_color)
    emptyMessageColor = Property(QColor, get_empty_message_color, set_empty_message_color)


class FilterControls(QFrame):
    """Panel editable de los filtros. Este widget es el bloque UI del filtro. Tiene un checkbox por defecto enabled,
    un low_cut y hight_cut, un selector FIR/IIR, bloque FIR, bloque IIR, label de error y una señal de changed."""

    changed = Signal() # avisar fuera cuando cambia algo
    # TODO: proque hay que definir aquí esto?? cogerlo del filtering.json no??
    FILTER_FAMILIES = ("FIR", "IIR") # familias de filtros que puede elegir el usuario

    def __init__(self, title: str, config: dict[str, Any], fir: dict[str, Any],
        iir: dict[str, Any], mode: FilterMode):
        super().__init__()
        self.config = config
        self.fir = fir # TODO: no entiendo porque hay que guardar esto
        self.iir = iir # TODO: no entiendo porque hay que guardar esto
        self.mode = mode # dice si este panel representa un bandpass o un bandstop
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
        self.low = self._double(float(config["low_cut"])) # spinbox para low_cut
        self.high = self._double(float(config["high_cut"])) # spinbox para high_cut
        self.kind = QComboBox() # combo para elegir FIR o IIR
        for family in self.FILTER_FAMILIES:
            self.kind.addItem(str(family))
        self.kind.setCurrentText(str(config["filter_type"]).upper())
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
        self.fir_order.setRange(0, 99999)
        self.fir_order.setSingleStep(1)
        self.fir_order.setValue(int(config["fir_order"], fir["default_order"]))
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
        self.iir_order.setRange(1, 20)
        self.iir_order.setValue(int(config.get["iir_order"], iir["default_order"]))
        self.iir_order.setMaximumWidth(140)
        self.design = QComboBox() # combobox para el diseño del filtro
        for design in iir["designs"]:
            design_id, design_title = normalize_choice(design) # normalizamos las opciones del combo
            self.design.addItem(design_title, design_id)
        design_index = self.design.findData(str(config["iir_design"], iir["default_design"]))
        if design_index >= 0:
            self.design.setCurrentIndex(design_index)
        self.design.setMaximumWidth(180)
        self.iir_rp = QDoubleSpinBox() # spinbox para el rizado de la banda de paso
        self.iir_rp.setRange(0.1, 20.0)
        self.iir_rp.setDecimals(2)
        self.iir_rp.setValue(float(config["iir_rp_db"], iir["default_rp_db"]))
        self.iir_rp.setSuffix(" dB")
        self.iir_rp.setMaximumWidth(140)
        self.iir_rs = QDoubleSpinBox() # spinbox para la atenuación en la banda de rechazo
        self.iir_rs.setRange(1.0, 200.0)
        self.iir_rs.setDecimals(1)
        self.iir_rs.setValue(float(config["iir_rs_db"], iir["default_rs_db"]))
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
    def _double(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 10000) # TODO: no se debería de coger de un argumento?? sin parchear
        spin.setDecimals(1)
        spin.setValue(value)
        spin.setSuffix(" Hz")
        return spin

    def _sync(self) -> None:
        """Lee la interfaz y actualiza self.config, muestra u oculta controles FIR/IIR, y activa/desactiva
        parámetros según el diseño."""
        filter_type = self.kind.currentText().lower()
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

    def set_error_message(self, message: str | None) -> None:
        """Función para mostrar/ocultar el mensaje de error."""
        # TODO: no es redundante con otras funciones de error que hay arriba???
        if message:
            self.error_label.setProperty("role", "error")
            self.error_label.style().unpolish(self.error_label)
            self.error_label.style().polish(self.error_label)
            self.error_label.setText(message)
            self.error_label.show()
            return
        self.error_label.clear()
        self.error_label.hide()


__all__ = ["FilterControls", "FilterMode", "FilterPreviewPlot", "FilterResponse", "build_filter_defaults",
    "compute_filter_response", "filter_response_error", "filter_validation_errors", "normalize_choice",
    "normalize_fir_order", "filter_defaults"]
