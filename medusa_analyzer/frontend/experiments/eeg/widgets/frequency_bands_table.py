from __future__ import annotations

import math
from copy import deepcopy
from collections.abc import MutableSequence
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget
from medusa_analyzer.frontend.widgets.table import EditableTable, TableColumn

# Creamos una tabla especializada para bandas EEG usando la tabla genérica EditableTable. En esta table, se validan
# nombres y cortes de las bandas, se crean las columnas [Enabled, title, low_cut y high_cut], se añaden botones de
# añadir fila y reset y se actualizan los límites mínimos/máximos permitidos en función de la frecuencia de nyquits
# y si se ha activado o no un filtro pasobanda.

def validate_eeg_frequency_bands(rows: MutableSequence[dict], minimum_frequency: float = 0.1,
    # Función de validación para las bandas de EEG
    maximum_frequency: float = 10000.0) -> list[str]:

    errors: list[str] = [] # Lista donde se van gaurdando los errores
    for index, row in enumerate(rows, start=1): # Recorremos todas las filas
        title = str(row.get("title", "")).strip()
        if not title:
            errors.append(f"Row {index}: band name is required.")
        elif any(character.isspace() for character in title):
            errors.append(f"Row {index}: band name must not contain spaces.")

        try:
            low_cut = float(row.get("low_cut", 0.0))
            high_cut = float(row.get("high_cut", 0.0))
        except (TypeError, ValueError):
            errors.append(f"Row {index}: cut values must be numeric.")
            continue

        if not math.isfinite(low_cut) or not math.isfinite(high_cut):
            errors.append(f"Row {index}: cut values must be finite.")
            continue
        if low_cut < minimum_frequency:
            errors.append(f"Row {index}: low cut must be greater than or equal to {minimum_frequency:g} Hz.")
        if high_cut < minimum_frequency:
            errors.append(f"Row {index}: high cut must be greater than or equal to {minimum_frequency:g} Hz.")
        if high_cut <= low_cut:
            errors.append(f"Row {index}: high cut must be greater than low cut.")
        if low_cut > maximum_frequency or high_cut > maximum_frequency:
            errors.append(f"Row {index}: cut values must be lower than or equal to {maximum_frequency:g} Hz.")
    return errors # deolvemos lista de errores; si está vacía, la tabla es válida.


class EEGFrequencyBandsTable(EditableTable): # Hereda de la clase genérica
    def __init__(self, rows: MutableSequence[dict], default_rows: MutableSequence[dict] | None = None,
        minimum_frequency: float = 0.1, maximum_frequency: float = 10000.0):
        # Al heredar, reutiliza toda la lógica de construir celdas, validar, reordenar, etc.
        # El contructor recibe las filas actuales, las filas por defecto los límites min/max.
        self.minimum_frequency = minimum_frequency
        self.maximum_frequency = maximum_frequency
        default_high_cut = max(self.minimum_frequency + 0.1, 1.0) # calculamos el máximo por defecto
        for row in rows:
            self._normalize_row(row)
        # Construimos las filas por defecto
        self.default_rows = [self._normalized_row_copy(row) for row in (default_rows if default_rows is not None else rows)]

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
        # Función que llama a la validación pero usando los límites actuales guardados en la clase
        return validate_eeg_frequency_bands(current_rows, minimum_frequency=self.minimum_frequency,
            maximum_frequency=self.maximum_frequency)

    def set_frequency_bounds(self, minimum_frequency: float = 0.1, maximum_frequency: float | None = None,
        emit_changed: bool = True) -> None:

        # Recalcula los máximos en función de lo que se le pasa como argumento y llama a sync para recalcular datos y
        # hacer la validación. IMPORTANTE: aquí i que se cambia el mínimo visible del spinbox, pero NO se cambia el
        # máximo visible del spinbox. Por eso puede pasar que el usuario vea escrito 200 pero en la tabla marque error
        # porque el máximo lógico ya es menor.

        self.minimum_frequency = float(minimum_frequency)
        if maximum_frequency is not None:
            self.maximum_frequency = max(self.minimum_frequency, float(maximum_frequency))
        else:
            self.maximum_frequency = max(self.minimum_frequency, self.maximum_frequency)

        for widgets_by_key in self.row_widgets:
            for key in ("low_cut", "high_cut"):
                spin = widgets_by_key[key]
                spin.blockSignals(True)
                spin.setMinimum(self.minimum_frequency)
                spin.blockSignals(False)

        self._sync(emit_changed=emit_changed)

    def _add_new_row(self) -> None:
        # Métoodo para el botón de 'add new row'
        # Primero calculamos el límite superior inicial de la nueva fila
        default_high_cut = min(self.maximum_frequency, max(self.minimum_frequency + 0.1, 1.0))
        # Después llamamos a append_row de EditableTable
        widgets = self.append_row({"enabled": True, "id": "", "title": "", "low_cut": self.minimum_frequency,
                "high_cut": default_high_cut})
        widgets["title"].setFocus() # ponemos el foco en el campo title para que el usuario empiece a escribir ahí

    def reset_to_defaults(self) -> None:
        # Métoodo para restablecer la tabla a defaults

        # Reemplazamos todas las filas por copias de self.default_rows sin emitir cambio todavía
        self.replace_rows([self._normalized_row_copy(row) for row in self.default_rows], emit_changed=False)
        # Volvemos a aplicar los límites de frecuencia actuales y ahora si que emitimos cambio para que valide
        self.set_frequency_bounds(minimum_frequency=self.minimum_frequency, maximum_frequency=self.maximum_frequency,
            emit_changed=True)
        if self.row_widgets:
            self.row_widgets[0]["title"].setFocus() # ponemos el foco en el título

    def _normalized_row_copy(self, row: dict) -> dict:
        # helper para hacer una copia profunda de una fila y luego normalizarla. Se hace una copia profunda para que
        # el default no comparta el mismo dict que la tabla editable y así al modificar la tabla no rompe los
        # defaults guardados.
        return self._normalize_row(deepcopy(row))

    def _normalize_row(self, row: dict) -> dict:
        # Este métoodo "arregla" una fila para que tenga un formato consistente
        default_high_cut = max(self.minimum_frequency + 0.1, 1.0) # calculamos un high cut razonable
        row["enabled"] = bool(row.get("enabled", True)) # aseguramos que enabled sea booleano
        row["title"] = str(row.get("title") or row.get("id") or "Band") # aseguramos que el título sea texto
        # Asegurar que los cuts existen y son floats
        row["low_cut"] = float(row.get("low_cut", self.minimum_frequency))
        row["high_cut"] = float(row.get("high_cut", default_high_cut))
        return row # devuelve la fila ya normalizada


__all__ = ["EEGFrequencyBandsTable", "validate_eeg_frequency_bands"]
