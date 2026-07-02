from __future__ import annotations

from collections.abc import Callable, MutableSequence, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout,
    QLabel, QLineEdit, QSpinBox, QVBoxLayout, QWidget)


# Tipos de celda soportados por la tabla
TableColumnKind = Literal["checkbox", "text", "float", "int", "choice", "label"]
# Función opcional de validación: recibe todas las filas y devuelve una lista de errores.
TableValidator = Callable[[MutableSequence[dict[str, Any]]], list[str]]
_ROW_MIME_TYPE = "application/x-medusa-editable-table-row" # # MIME interno para identificar drags de filas de esta tabla


@dataclass(frozen=True, slots=True)
class TableColumn:
    """Define una columna editable de la tabla."""
    key: str
    title: str
    kind: TableColumnKind
    default: Any = None
    width: int | None = None
    options: list[tuple[str, str]] | None = None
    minimum: float | int | None = None
    maximum: float | int | None = None
    decimals: int = 1
    suffix: str = ""
    editable: bool = True


class _EditableRow(QFrame):
    """Fila visual de la tabla. También gestiona el drag & drop si está activado."""
    def __init__(self, table: "EditableTable", index: int):
        super().__init__()
        self.table = table
        self.index = index
        self._drag_start: QPoint | None = None

        self.setProperty("role", table.row_role)
        self.setAcceptDrops(table.reorderable)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Guarda el punto inicial para decidir después si el usuario está arrastrando."""
        if self.table.reorderable and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Inicia el drag solo si el ratón se ha movido suficiente distancia."""
        if not self._drag_start or not event.buttons() & Qt.MouseButton.LeftButton:
            super().mouseMoveEvent(event)
            return

        distance = (event.position().toPoint() - self._drag_start).manhattanLength()
        if distance < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        self._drag_start = None
        self.start_drag()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Limpia el estado visual al soltar el ratón."""
        self._drag_start = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def start_drag(self) -> None:
        """Empaqueta el índice de la fila y lanza el drag de Qt."""
        if not self.table.reorderable:
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(_ROW_MIME_TYPE, f"{id(self.table)}:{self.index}".encode("ascii"))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event) -> None:
        self._accept_or_ignore(event)

    def dragMoveEvent(self, event) -> None:
        self._accept_or_ignore(event)

    def dropEvent(self, event) -> None:
        """Convierte el drop visual en una reordenación real de la lista."""
        source_index = self.table._drag_source_index(event.mimeData())
        if source_index is None or source_index == self.index:
            event.ignore()
            return
        # Si se suelta en la mitad inferior de la fila, insertamos después.
        insert_after = event.position().y() >= self.height() / 2
        target_index = self.index + int(insert_after)

        self.table.move_row(source_index, target_index)
        event.acceptProposedAction()

    def _accept_or_ignore(self, event) -> None:
        """Acepta solo drags válidos de esta misma tabla."""
        source_index = self.table._drag_source_index(event.mimeData())
        if source_index is not None and source_index != self.index:
            event.acceptProposedAction()
        else:
            event.ignore()

class EditableTable(QFrame):
    """Tabla editable genérica basada en una lista de diccionarios."""

    changed = Signal()
    validation_changed = Signal(bool)

    def __init__(self, rows: MutableSequence[dict[str, Any]], columns: Sequence[TableColumn],
        validator: TableValidator | None = None, row_role: str = "table-row", reorderable: bool = False):
        super().__init__()

        self.rows = rows
        self.columns = tuple(columns)
        self.validator = validator
        self.row_role = row_role
        self.reorderable = reorderable
        self.row_widgets: list[dict[str, QWidget]] = []
        self.row_frames: list[_EditableRow] = []
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

        self._build_header()

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(8)
        root.addWidget(self.rows_container)

        self.error_label = QLabel()
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)

        self._rebuild_rows()
        self._sync(emit_changed=False)

    def is_valid(self) -> bool:
        """Devuelve si la tabla no tiene errores de validación."""
        return self._is_valid

    def validation_errors(self) -> list[str]:
        """Devuelve una copia de los errores actuales."""
        return list(self._validation_errors)

    def append_row(self, row: dict[str, Any] | None = None) -> dict[str, QWidget]:
        """Añade una fila nueva, reconstruye la UI y devuelve sus widgets."""
        new_row = row or {}
        self.rows.append(new_row)

        widgets = self._add_row(new_row)
        self._sync()

        return widgets

    def replace_rows(self, rows: Sequence[dict[str, Any]], emit_changed: bool = True) -> None:
        """Sustituye todas las filas y reconstruye la tabla."""
        self.rows[:] = list(rows)
        self._rebuild_rows()
        self._sync(emit_changed=emit_changed)

    def move_row(self, source_index: int, target_index: int) -> None:
        """Mueve una fila dentro de rows y reconstruye la parte visual."""
        if len(self.rows) < 2 or not 0 <= source_index < len(self.rows):
            return

        target_index = max(0, min(target_index, len(self.rows)))

        # Evita movimientos que en la práctica no cambian nada.
        if source_index == target_index or source_index + 1 == target_index:
            return

        # Antes de mover, copiamos a rows cualquier cambio pendiente en los widgets.
        self._sync(emit_changed=False)
        row = self.rows.pop(source_index)
        if source_index < target_index:
            target_index -= 1

        self.rows.insert(target_index, row)
        self._rebuild_rows()
        self._sync()

    def _build_header(self) -> None:
        """Crea la cabecera de la tabla."""
        offset = 1 if self.reorderable else 0

        if self.reorderable:
            spacer = QLabel("")
            spacer.setFixedWidth(22)
            self.header_layout.addWidget(spacer, 0, 0)

        for index, column in enumerate(self.columns):
            label = QLabel(column.title)

            if column.width is not None:
                label.setFixedWidth(column.width)

            self.header_layout.addWidget(label, 0, index + offset)

    def _add_row(self, row: dict[str, Any]) -> dict[str, QWidget]:
        """Crea una fila visual y todos sus widgets."""
        row_frame = _EditableRow(self, len(self.row_frames))
        row_layout = QGridLayout(row_frame)
        self._configure_grid(row_layout)

        offset = 1 if self.reorderable else 0

        if self.reorderable:
            handle = QLabel("☰")
            handle.setFixedWidth(22)
            handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            handle.setCursor(Qt.CursorShape.OpenHandCursor)
            handle.setProperty("role", "table-drag-handle")

            # El QLabel es solo visual: el drag lo gestiona la fila completa.
            handle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

            row_layout.addWidget(handle, 0, 0)

        widgets: dict[str, QWidget] = {}

        for index, column in enumerate(self.columns):
            widget = self._build_cell(row, column)
            widgets[column.key] = widget
            row_layout.addWidget(widget, 0, index + offset)

        self.row_frames.append(row_frame)
        self.row_widgets.append(widgets)
        self.rows_layout.addWidget(row_frame)

        return widgets

    def _clear_rows(self) -> None:
        """Elimina todas las filas visuales actuales."""
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        self.row_frames.clear()
        self.row_widgets.clear()

    def _rebuild_rows(self) -> None:
        """Reconstruye la UI de filas desde self.rows."""
        self._clear_rows()

        for row in self.rows:
            self._add_row(row)

    def _configure_grid(self, layout: QGridLayout, header: bool = False) -> None:
        """Configura márgenes, espaciado y comportamiento de columnas."""
        layout.setContentsMargins(*(0, 0, 0, 0) if header else (12, 10, 12, 10))
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(6)

        offset = 1 if self.reorderable else 0

        if self.reorderable:
            layout.setColumnMinimumWidth(0, 22)
            layout.setColumnStretch(0, 0)

        for index, column in enumerate(self.columns):
            layout_index = index + offset

            if column.width is not None:
                layout.setColumnMinimumWidth(layout_index, column.width)

            # Las columnas de texto sin ancho fijo se expanden; el resto conserva su tamaño.
            stretches = column.kind in {"text", "label"} and column.width is None
            layout.setColumnStretch(layout_index, int(stretches))

    def _build_cell(self, row: dict[str, Any], column: TableColumn) -> QWidget:
        """Crea el widget adecuado para una celda y lo conecta con la sincronización."""
        value = self._value_or_default(row, column)

        if column.kind == "checkbox":
            widget = QCheckBox()
            widget.setChecked(bool(value))
            widget.setEnabled(column.editable)
            widget.toggled.connect(self._sync)
            return widget

        if column.kind == "text":
            widget = QLineEdit(str(value))
            widget.setReadOnly(not column.editable)
            widget.textChanged.connect(self._sync)

        elif column.kind == "float":
            widget = QDoubleSpinBox()
            widget.setRange(float(column.minimum if column.minimum is not None else -1_000_000),
                float(column.maximum if column.maximum is not None else 1_000_000))
            widget.setDecimals(column.decimals)
            widget.setSuffix(column.suffix)
            widget.setValue(float(value))
            widget.setEnabled(column.editable)
            widget.valueChanged.connect(self._sync)

        elif column.kind == "int":
            widget = QSpinBox()
            widget.setRange(int(column.minimum if column.minimum is not None else -1_000_000),
                int(column.maximum if column.maximum is not None else 1_000_000))
            widget.setSuffix(column.suffix)
            widget.setValue(int(value))
            widget.setEnabled(column.editable)
            widget.valueChanged.connect(self._sync)

        elif column.kind == "choice":
            widget = QComboBox()

            for option_value, option_title in column.options or []:
                widget.addItem(option_title, option_value)
            current_index = widget.findData(value)

            # Si rows trae un valor antiguo/no listado, lo mostramos igualmente.
            if current_index < 0 and value is not None:
                widget.addItem(str(value), value)
                current_index = widget.findData(value)

            if current_index >= 0:
                widget.setCurrentIndex(current_index)

            widget.setEnabled(column.editable)
            widget.currentIndexChanged.connect(self._sync)

        else:
            widget = QLabel(str(value))

        if column.width is not None:
            widget.setFixedWidth(column.width)

        return widget

    def _value_or_default(self, row: dict[str, Any], column: TableColumn) -> Any:
        """Devuelve el valor de la fila o escribe un valor por defecto si falta."""
        if column.key in row:
            return row[column.key]

        if column.default is not None:
            default = column.default
        elif column.kind == "checkbox":
            default = False
        elif column.kind in {"float", "int"}:
            default = 0
        else:
            default = ""

        row[column.key] = default
        return default

    def _sync(self, *args, emit_changed: bool = True) -> None:
        """Copia los valores de la UI a rows, valida y emite señales."""
        del args

        for row, widgets in zip(self.rows, self.row_widgets):
            for column in self.columns:
                widget = widgets[column.key]

                if column.kind == "checkbox":
                    row[column.key] = widget.isChecked()
                elif column.kind == "text":
                    row[column.key] = widget.text()
                elif column.kind in {"float", "int"}:
                    row[column.key] = widget.value()
                elif column.kind == "choice":
                    row[column.key] = widget.currentData()
                else:
                    row[column.key] = widget.text()

        self._run_validation(emit_signal=emit_changed)

        if emit_changed:
            self.changed.emit()

    def _run_validation(self, emit_signal: bool) -> None:
        """Ejecuta el validator externo y actualiza el mensaje de error."""
        errors = self.validator(self.rows) if self.validator else []

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

    def _drag_source_index(self, mime_data: QMimeData) -> int | None:
        """Lee el índice de la fila arrastrada, solo si pertenece a esta tabla."""
        if not mime_data.hasFormat(_ROW_MIME_TYPE):
            return None
        try:
            table_id, row_index = bytes(mime_data.data(_ROW_MIME_TYPE)).decode("ascii").split(":", 1)
        except ValueError:
            return None
        if table_id != str(id(self)):
            return None
        try:
            return int(row_index)
        except ValueError:
            return None

__all__ = ["EditableTable", "TableColumn", "TableColumnKind", "TableValidator"]