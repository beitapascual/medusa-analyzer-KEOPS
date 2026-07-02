from __future__ import annotations

from collections.abc import MutableSequence
from copy import deepcopy

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from medusa_analyzer.frontend.models import Validation
from medusa_analyzer.frontend.widgets.table import EditableTable, TableColumn


"""Creamos una tabla especializada para bandas EEG usando la tabla genérica EditableTable. En esta table, se validan
nombres y cortes de las bandas, se crean las columnas [Enabled, title, low_cut y high_cut], se añaden botones de
añadir fila y reset y se actualizan los límites mínimos/máximos permitidos en función de la frecuencia de nyqust
y si se ha activado o no un filtro pasobanda."""
_band_validation = Validation()


# Hereda de la clase genérica
class EEGFrequencyBandsTable(EditableTable):
    def __init__(self, rows: MutableSequence[dict], default_rows: MutableSequence[dict] | None = None,
        minimum_frequency: float = 0.1, maximum_frequency: float = 10000.0):
        # Al heredar, reutiliza toda la lógica de construir celdas, validar, reordenar, etc.
        # El constructor recibe las filas actuales, las filas por defecto los límites min/max.
        self.minimum_frequency = minimum_frequency
        self.maximum_frequency = maximum_frequency
        default_high_cut = max(self.minimum_frequency + 0.1, 1.0) # calculamos el máximo por defecto

        for row in rows:
            self._normalize_row(row)

        self.default_rows = [self._normalized_row_copy(row) for row in (
            default_rows if default_rows is not None else rows)]

        columns = [TableColumn("enabled", "Enabled", "checkbox", default=True, width=72),
            TableColumn("title", "Band", "text", default="Band"),
            TableColumn("low_cut", "From", "float", default=minimum_frequency, minimum=minimum_frequency,
                maximum=maximum_frequency, decimals=1, suffix=" Hz", width=112),
            TableColumn("high_cut", "To", "float", default=default_high_cut, minimum=minimum_frequency,
                maximum=maximum_frequency, decimals=1, suffix=" Hz", width=112)]
        # LLamamos al constructor de EditableTable
        super().__init__(rows, columns, validator=self._validate_rows, row_role="band-chip", reorderable=True)
        # Creamos un widget extra para la zona de acciones
        self.actions = QWidget()
        actions_layout = QHBoxLayout(self.actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        self.add_row_button = QPushButton("Add new row") # Botón de add new row
        self.add_row_button.setProperty("variant", "secondary")
        self.add_row_button.clicked.connect(self._add_new_row) # Conectamos el botón

        self.reset_button = QPushButton("Reset table") # Botón de reset table
        self.reset_button.setProperty("variant", "secondary")
        self.reset_button.clicked.connect(self.reset_to_defaults) # Conectamos el botón

        actions_layout.addWidget(self.add_row_button)
        actions_layout.addWidget(self.reset_button)
        actions_layout.addStretch(1)
        self.layout().insertWidget(2, self.actions)

        # Inicializamos la tabla con los límites de las bandas
        self.set_frequency_bounds(minimum_frequency=self.minimum_frequency,
            maximum_frequency=self.maximum_frequency, emit_changed=False)

    def _validate_rows(self, current_rows: MutableSequence[dict]) -> list[str]:
        errors: list[str] = []
        for index, row in enumerate(current_rows, start=1):
            if not bool(row.get("enabled", True)):
                continue  # Cuando una fila está desactivada no se valida

            row_prefix = f"Row {index}"
            row_errors: list[str] = []
            row_errors.extend(_band_validation.validate_many(row.get("title"), ["required_text", "no_whitespace"],
                                                             label=f"{row_prefix}: band name"))
            row_errors.extend(_band_validation.validate_many(row.get("low_cut"),["finite_number", ("greater_or_equal",
                            {"minimum": self.minimum_frequency, "suffix": " Hz"}), ("less_or_equal",
                               {"maximum": self.maximum_frequency, "suffix": " Hz"})], label=f"{row_prefix}: low cut"))
            row_errors.extend(_band_validation.validate_many(row.get("high_cut"), ["finite_number", ("greater_or_equal",
                             {"minimum": self.minimum_frequency, "suffix": " Hz"}), ("less_or_equal",
                            {"maximum": self.maximum_frequency, "suffix": " Hz"})], label=f"{row_prefix}: high cut"))
            if row_errors:
                errors.extend(row_errors)
                # Si ya ha fallado una validación básica de la fila, evitamos
                # comparaciones numéricas para no añadir ruido.
                continue

            low_cut = Validation.coerce_float(row.get("low_cut"))
            high_cut = Validation.coerce_float(row.get("high_cut"))
            row_errors.extend(_band_validation.validate_many(high_cut, [("greater_than", {"minimum": low_cut, "suffix": " Hz"})],
                                                                                        label=f"{row_prefix}: high cut"))
            errors.extend(row_errors)
        return errors

    def set_frequency_bounds(self, minimum_frequency: float = 0.1, maximum_frequency: float | None = None,
        emit_changed: bool = True) -> None:
        """Ajusta los límites lógicos de la tabla según Nyquist o bandpass. No modificamos ni el mínimo ni el
        máximo visible, solo es a nivel de validación."""
        self.minimum_frequency = float(minimum_frequency)
        if maximum_frequency is not None:
            self.maximum_frequency = max(self.minimum_frequency, float(maximum_frequency))
        else:
            self.maximum_frequency = max(self.minimum_frequency, self.maximum_frequency)
        self._sync(emit_changed=emit_changed) # El sync ejecuta _run_validator

    def _add_new_row(self) -> None:
        """Method para el botón de 'add new row'"""
        # Primero calculamos el límite superior inicial de la nueva fila
        default_high_cut = min(self.maximum_frequency, max(self.minimum_frequency + 0.1, 1.0))
        # Después llamamos a append_row de EditableTable
        row = self._normalize_row({"enabled": True, "id": "", "title": "", "low_cut": self.minimum_frequency, "high_cut": default_high_cut})
        widgets = self.append_row(row)
        widgets["title"].setFocus() # ponemos el foco en el campo title para que el usuario empiece a escribir ahí

    def reset_to_defaults(self) -> None:
        """Restablecer la tabla a defaults"""
        # Reemplazamos todas las filas por copias de self.default_rows sin emitir cambio todavía
        self.replace_rows([self._normalized_row_copy(row) for row in self.default_rows], emit_changed=False)
        # Volvemos a aplicar los límites de frecuencia actuales y ahora sí que emitimos cambio para que valide
        self.set_frequency_bounds(minimum_frequency=self.minimum_frequency, maximum_frequency=self.maximum_frequency,
            emit_changed=True)
        if self.row_widgets:
            self.row_widgets[0]["title"].setFocus() # ponemos el foco en el título

    def _normalized_row_copy(self, row: dict) -> dict:
        """Helper para hacer una copia profunda de una fila y luego normalizarla. Se hace una copia profunda para que
        el default no comparta el mismo dict que la tabla editable y así al modificar la tabla no rompe los
        defaults guardados."""
        return self._normalize_row(deepcopy(row))

    def _normalize_row(self, row: dict) -> dict:
        """Homogeneizamos la fila para que la tabla trabaje siempre con la misma
        estructura, venga del JSON o de una fila nueva creada por el usuario."""
        default_high_cut = max(self.minimum_frequency + 0.1, 1.0) # calculamos un high cut razonable
        row["enabled"] = bool(row.get("enabled", True)) # aseguramos que enabled sea booleano
        row["title"] = str(row.get("title") or row.get("id") or "Band")
        row["low_cut"] = float(row.get("low_cut", self.minimum_frequency)) # aseguramos que el título sea texto
        # Asegurar que los cuts existen y son floats
        row["high_cut"] = float(row.get("high_cut", default_high_cut))
        return row # devuelve la fila ya normalizada


__all__ = ["EEGFrequencyBandsTable"]
