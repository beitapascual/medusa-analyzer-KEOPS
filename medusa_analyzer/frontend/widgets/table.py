from __future__ import annotations

from collections.abc import Callable, MutableSequence, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QLabel,
    QLineEdit, QSpinBox, QVBoxLayout, QWidget)

# Este módulo construye una tabla editable genérica a partir de una lista de filas 'rows = [{...}, {...}]' y una
# definición de columnas 'TableColumn(...)'. La tabla crea la UI de cada celda, mantiene sincronizada la UI con rows,
# valida el contenido y reordena las filas si está activado el drag & drop.

TableColumnKind = Literal["checkbox", "text", "float", "int", "choice", "label"] # lista de tipos de columna permitidos
TableValidator = Callable[[MutableSequence[dict]], list[str]] # función que recibe las filas y devuelve errores
# Definimos una etiqueta interna para el drag&drop que sirve para reconocer "esto es una fila de esta tabla"
_ROW_MIME_TYPE = "application/x-medusa-editable-table-row"


# Creamos un dataclass para las columnas. Describe una columna diciendo como se llama, el tipo de widget que es y las
# reglas que tiene
@dataclass(frozen=True, slots=True)
class TableColumn:
    key: str # nombre de la clave en el dict de la fila
    title: str
    kind: TableColumnKind # tipo de widget a crear
    default: Any = None # valor por defecto
    width: int | None = None
    options: list[tuple[str, str]] | None = None # opciones del combo si kind == "choice"
    minimum: float | int | None = None # límite para números
    maximum: float | int | None = None # límite para números
    decimals: int = 1
    suffix: str = ""
    editable: bool = True # si el usuario puede editar esa columna


class _RowDragHandle(QLabel):
    # Sirve para detectar cuándo el usuario quiere arrastrar una fila y disparar el inicio de grag. OJO, no mueve filas
    # por sí mismo.
    def __init__(self, row_frame: "_EditableTableRow"):
        super().__init__("::")
        self.row_frame = row_frame
        self._drag_start_position: QPoint | None = None
        self.setProperty("role", "table-drag-handle")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedWidth(22)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Función para guardar el puto donde empezó el click
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # Función que decide si se está haciendo un drag o no.
        # Si el sensor se mueve lo suficiente, decide que eso ya es un drag.
        if (self._drag_start_position is None or not event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start_position).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        self.row_frame.start_drag()
        self._drag_start_position = None
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        # Función que limpia el estado del drag
        self._drag_start_position = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


class _EditableTableRow(QFrame):
    # Esta clase representa una fila entera de la tabla. Sabe su índice dentro de la tabla y sabe aceptar drops si la
    # tabla es reordenable. Cuando cae un drag encima, decide si mover la fila antes o después.
    # Es el puente entre el gesto visual de arrastrar y la operación lógica de reordenar.
    def __init__(self, table: "EditableTable", row_index: int, role: str):
        # Guardamos referencia a la tabla y a su row_index
        super().__init__()
        self.table = table
        self.row_index = row_index
        self.setProperty("role", role)
        self.setAcceptDrops(table.reorderable)

    def start_drag(self) -> None:
        # Función que empaqueta el índice de la fila y lanza el drag de Qt
        if not self.table.reorderable:
            return
        drag = QDrag(self)
        mime_data = self.table._build_row_mime_data(self.row_index)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event) -> None:
        if self._can_accept_drag(event):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._can_accept_drag(event):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        # Función que convierte el drop en una llamada a table.move_row
        source_index = self._source_index(event)
        if source_index is None:
            event.ignore()
            return

        insert_after = event.position().y() >= self.height() / 2
        target_index = self.row_index + (1 if insert_after else 0)
        self.table.move_row(source_index, target_index)
        event.acceptProposedAction()

    def _can_accept_drag(self, event) -> bool:
        # Comprueba si ese drag tiene sentido
        source_index = self._source_index(event)
        return source_index is not None and source_index != self.row_index

    def _source_index(self, event) -> int | None:
        # Intenta leer desde el mimeData qué fila se está arrastrando
        return self.table._decode_row_mime_data(event.mimeData())


class EditableTable(QFrame):
    # Es la tabla entera. Construye la cabecera, construye als filas, crea widgets según el tipo de columna, mantiene
    # rows actualizado, ejecuta la validación y emite señales cuando algo cambie.
    changed = Signal()
    validation_changed = Signal(bool)

    def __init__(self, rows: MutableSequence[dict], columns: Sequence[TableColumn], validator: TableValidator | None = None,
        row_role: str = "table-row", reorderable: bool = False):
        super().__init__()
        self.rows = rows
        self.columns = tuple(columns)
        self.validator = validator
        self.row_role = row_role
        self.reorderable = reorderable
        self.row_widgets: list[dict[str, QWidget]] = [] # guardar para cada fila, los widgets reales de cada celda
        self.row_frames: list[_EditableTableRow] = [] # guardar los contenedores visuales de cada fila
        self._is_valid = True
        self._validation_errors: list[str] = []

        self.setProperty("role", "editable-table")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.header = QFrame()
        self.header.setProperty("role", "table-header")
        self.header_layout = QGridLayout(self.header)
        self._configure_grid(self.header_layout, header=True)
        root.addWidget(self.header)

        if self.reorderable:
            drag_header = QLabel("")
            drag_header.setFixedWidth(22)
            self.header_layout.addWidget(drag_header, 0, 0)

        for index, column in enumerate(self.columns):
            header_label = QLabel(column.title)
            if column.width is not None:
                header_label.setFixedWidth(column.width)
            self.header_layout.addWidget(header_label, 0, index + (1 if self.reorderable else 0))

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(8)
        root.addWidget(self.rows_container)

        for row in self.rows:
            self._add_row(row)

        self.error_label = QLabel()
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)

        self._sync(emit_changed=False)

    def is_valid(self) -> bool:
        # Devuelve si la tabla es válida
        return self._is_valid

    def validation_errors(self) -> list[str]:
        # Devuelve una copia de los errores actuales
        return list(self._validation_errors)

    def append_row(self, row: dict | None = None) -> dict[str, QWidget]:
        # Añade una fila nueva a rows, crea sus widgets, sincroniza ay valida y devuelve los widgets de esa fila.
        # Sirve cuando una subclase quiere permitir "Add new row".
        new_row = {} if row is None else row
        self.rows.append(new_row)
        widgets_by_key = self._add_row(new_row)
        self._sync()
        return widgets_by_key

    def replace_rows(self, rows: Sequence[dict], emit_changed: bool = True) -> None:
        # Reconstruye toda la UI del filas. Sirve para rests, cargar defaults, recargar datos, etc.
        self.rows[:] = list(rows)
        self._rebuild_rows()
        self._sync(emit_changed=emit_changed)

    def _build_row_mime_data(self, row_index: int) -> QMimeData:
        # Crea el payload del drag, y mete dentro dos cosas: la identidad de la tabla y el índice de la fila. Eso evita
        # que una tabla mezcle filas de otras por accidente.
        mime_data = QMimeData()
        mime_data.setData(_ROW_MIME_TYPE, f"{id(self)}:{row_index}".encode("ascii"))
        return mime_data

    def _decode_row_mime_data(self, mime_data: QMimeData) -> int | None:
        # Intenta leer eñ payload, comprueba que pertenece a esta tabla, devuelve el índice de fila origen y, si algo
        # fala, devuelve None.
        if not mime_data.hasFormat(_ROW_MIME_TYPE):
            return None

        try:
            table_id_text, row_index_text = bytes(mime_data.data(_ROW_MIME_TYPE)).decode("ascii").split(":", 1)
        except ValueError:
            return None

        if table_id_text != str(id(self)):
            return None

        try:
            return int(row_index_text)
        except ValueError:
            return None

    def move_row(self, source_index: int, target_index: int) -> None:
        # Mueve una fila de una posición a otra, actualiza self.rows, reconstruye las filas visuales y vuelve a
        # sincronizar y validar. Es la operación real de reordenación. Toodo el drag termina aquí.
        if len(self.rows) < 2:
            return
        if not 0 <= source_index < len(self.rows):
            return

        bounded_target = max(0, min(target_index, len(self.rows)))
        if source_index == bounded_target or source_index + 1 == bounded_target:
            return

        self._sync(emit_changed=False)
        row = self.rows.pop(source_index)
        if source_index < bounded_target:
            bounded_target -= 1
        self.rows.insert(bounded_target, row)
        self._rebuild_rows()
        self._sync()

    def _add_row(self, row: dict) -> dict[str, QWidget]:
        # Construcción visual de las filas
        row_frame = _EditableTableRow(self, len(self.row_frames), self.row_role)
        row_layout = QGridLayout(row_frame)
        self._configure_grid(row_layout)

        column_offset = 0
        if self.reorderable:
            row_layout.addWidget(_RowDragHandle(row_frame), 0, 0)
            column_offset = 1

        widgets_by_key: dict[str, QWidget] = {}
        for index, column in enumerate(self.columns):
            cell = self._build_cell(row, column)
            widgets_by_key[column.key] = cell
            row_layout.addWidget(cell, 0, index + column_offset)

        self.row_widgets.append(widgets_by_key)
        self.row_frames.append(row_frame)
        self.rows_layout.addWidget(row_frame)
        return widgets_by_key

    def _clear_rows(self) -> None:
        # Borra visualmente todas las filas
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.row_widgets.clear()
        self.row_frames.clear()

    def _rebuild_rows(self) -> None:
        self._clear_rows()
        for row in self.rows:
            self._add_row(row)

    def _configure_grid(self, layout: QGridLayout, header: bool = False) -> None:
        # Función de layout puro para configurar márgenes, spacing, etc.
        margins = (0, 0, 0, 0) if header else (12, 10, 12, 10)
        layout.setContentsMargins(*margins)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(6)
        if self.reorderable:
            layout.setColumnMinimumWidth(0, 22)
            layout.setColumnStretch(0, 0)
        for index, column in enumerate(self.columns):
            layout_index = index + (1 if self.reorderable else 0)
            if column.width is not None:
                layout.setColumnMinimumWidth(layout_index, column.width)
            if column.kind in {"text", "label"} and column.width is None:
                layout.setColumnStretch(layout_index, 1)
            else:
                layout.setColumnStretch(layout_index, 0)

    def _build_cell(self, row: dict, column: TableColumn) -> QWidget:
        # Esta función es importante. Es la que recibe una row y una colum y decide qué widget crear según colum.kind.
        # Después, carga el valor inicial y conecta ese widget a _sync
        value = self._resolve_value(row, column)

        if column.kind == "checkbox":
            widget = QCheckBox()
            widget.setText("")
            widget.setChecked(bool(value))
            widget.setEnabled(column.editable)
            widget.toggled.connect(self._sync)
            return widget

        if column.kind == "text":
            widget = QLineEdit(str(value))
            widget.setReadOnly(not column.editable)
            widget.textChanged.connect(self._sync)
            if column.width is not None:
                widget.setFixedWidth(column.width)
            return widget

        if column.kind == "float":
            widget = QDoubleSpinBox()
            widget.setRange(float(column.minimum if column.minimum is not None else -1_000_000.0),
                float(column.maximum if column.maximum is not None else 1_000_000.0))
            widget.setDecimals(column.decimals)
            widget.setSuffix(column.suffix)
            widget.setValue(float(value))
            widget.setEnabled(column.editable)
            widget.valueChanged.connect(self._sync)
            if column.width is not None:
                widget.setFixedWidth(column.width)
            return widget

        if column.kind == "int":
            widget = QSpinBox()
            widget.setRange(int(column.minimum if column.minimum is not None else -1_000_000),
                int(column.maximum if column.maximum is not None else 1_000_000))
            widget.setSuffix(column.suffix)
            widget.setValue(int(value))
            widget.setEnabled(column.editable)
            widget.valueChanged.connect(self._sync)
            if column.width is not None:
                widget.setFixedWidth(column.width)
            return widget

        if column.kind == "choice":
            widget = QComboBox()
            for option_value, option_title in column.options or []:
                widget.addItem(option_title, option_value)
            current_index = widget.findData(value)
            if current_index < 0 and value is not None:
                widget.addItem(str(value), value)
                current_index = widget.findData(value)
            if current_index >= 0:
                widget.setCurrentIndex(current_index)
            widget.setEnabled(column.editable)
            widget.currentIndexChanged.connect(self._sync)
            if column.width is not None:
                widget.setFixedWidth(column.width)
            return widget

        widget = QLabel(str(value))
        if column.width is not None:
            widget.setFixedWidth(column.width)
        return widget

    def _resolve_value(self, row: dict, column: TableColumn) -> Any:
        # Función que asegura que haya valores por defecto
        if column.key in row:
            return row[column.key]

        default = column.default
        if default is None:
            if column.kind == "checkbox":
                default = False
            elif column.kind in {"float", "int"}:
                default = 0
            else:
                default = ""

        row[column.key] = default
        return default

    def _sync(self, *args, emit_changed: bool = True) -> None:
        # Valida todos elementos y emite señal de changed
        del args
        for row, widgets_by_key in zip(self.rows, self.row_widgets):
            for column in self.columns:
                widget = widgets_by_key[column.key]
                if column.kind == "checkbox":
                    row[column.key] = widget.isChecked()
                elif column.kind == "text":
                    row[column.key] = widget.text()
                elif column.kind == "float":
                    row[column.key] = widget.value()
                elif column.kind == "int":
                    row[column.key] = widget.value()
                elif column.kind == "choice":
                    row[column.key] = widget.currentData()
                else:
                    row[column.key] = widget.text()

        self._run_validation(emit_signal=emit_changed)
        if emit_changed:
            self.changed.emit()

    def _run_validation(self, emit_signal: bool) -> None:
        # Función que ejecuta el validator (si existe) y guarda la lista de errores.
        errors = self.validator(self.rows) if self.validator is not None else []
        self._validation_errors = list(errors)
        self._is_valid = not self._validation_errors
        if self._validation_errors:
            self.error_label.setText("\n".join(f"- {error}" for error in self._validation_errors))
            self.error_label.show()
        else:
            self.error_label.clear()
            self.error_label.hide()

        if emit_signal:
            self.validation_changed.emit(self._is_valid)


__all__ = ["EditableTable", "TableColumn", "TableColumnKind", "TableValidator"]
