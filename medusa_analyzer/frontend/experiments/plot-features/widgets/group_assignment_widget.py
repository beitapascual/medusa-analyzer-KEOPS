from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QScrollArea,
    QStyle,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from medusa_analyzer.frontend.validation import Validation


_TARGET_TITLES = {
    "subjects": "Subjects",
    "recordings": "Files",
}
_TARGET_ITEM_NAMES = {
    "subjects": "subject",
    "recordings": "file",
}
_GROUP_COLOR_ROLE = Qt.ItemDataRole.UserRole + 1


class GroupAssignmentRowDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: Any, index: Any) -> None:
        painter.save()

        painter.fillRect(option.rect, QColor("#1F171B"))
        group_color = QColor(str(index.data(_GROUP_COLOR_ROLE) or ""))
        if group_color.isValid():
            group_color.setAlpha(135)
            painter.fillRect(option.rect, group_color)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            selection_color = QColor("#4A2030")
            selection_color.setAlpha(170)
            painter.fillRect(option.rect, selection_color)

        painter.setPen(QColor("#FFD6E1" if selected else "#F4E9ED"))
        painter.drawText(
            option.rect.adjusted(7, 0, -7, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            str(index.data(Qt.ItemDataRole.DisplayRole) or ""),
        )
        painter.restore()


class PlotFeaturesGroupAssignmentWidget(QScrollArea):
    changed = Signal()

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        del experiment_info, defaults
        super().__init__()

        self.state = state
        self.validation = Validation()
        self.validation_errors: list[str] = []
        self.items: list[str] = []
        self.assignment_by_item: dict[str, str] = {}
        self.current_target: str | None = None

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.content = QWidget()
        self.setWidget(self.content)
        root = QVBoxLayout(self.content)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(18)

        self.title = QLabel("Group assignment")
        self.title.setObjectName("pageTitle")
        self.description = QLabel("")
        self.description.setObjectName("muted")
        self.description.setWordWrap(True)
        root.addWidget(self.title)
        root.addWidget(self.description)

        root.addWidget(self._build_assignment_panel())
        root.addStretch()

        self._refresh_from_state()

    def _build_assignment_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_label = QLabel("Search")
        search_label.setObjectName("panelTitle")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find items...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_items)
        search_row.addWidget(search_label)
        search_row.addWidget(self.search_input, 1)
        layout.addLayout(search_row)

        self.table = QTableWidget()
        self.table.setProperty("role", "assignment-table")
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Item", "Group"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.setItemDelegate(GroupAssignmentRowDelegate(self.table))
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.table)

        self.instruction_label = QLabel("")
        self.instruction_label.setObjectName("assignmentInstruction")
        self.instruction_label.setWordWrap(True)
        layout.addWidget(self.instruction_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("selectionStatus")
        self.status_label.setProperty("status", "idle")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.summary_layout = QHBoxLayout()
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setSpacing(8)
        layout.addLayout(self.summary_layout)
        return panel

    def _refresh_from_state(self) -> None:
        analysis_mode = str(self.state.get("analysis_mode") or "within")
        if analysis_mode == "within":
            target = "recordings"
        elif analysis_mode == "between":
            target = "subjects"
        else:
            target = None
        self.current_target = target
        if target is None:
            self.items = []
            self.assignment_by_item = {}
            self.table.setRowCount(0)
            self.description.setText("No group assignment is required for no-comparison analysis.")
            self.instruction_label.setText("")
            self.state["group_assignment"] = {
                "target": None,
                "items_by_group": {},
                "group_by_item": {},
            }
            self._clear_layout(self.summary_layout)
            self._update_status_label()
            self.changed.emit()
            return

        target_title = _TARGET_TITLES[target]
        item_name = _TARGET_ITEM_NAMES[target]
        self.items = self._available_items()
        self.description.setText(f"Assign {target_title.lower()} to the groups defined in the previous step.")
        self.instruction_label.setText(
            f"Select one or more {item_name}s, then right-click to assign them to a group."
        )
        self.assignment_by_item = self._stored_assignment_for_target(target)
        self._populate_table()
        self._sync(emit_changed=False)

    def _populate_table(self) -> None:
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.items))
            target_title = _TARGET_TITLES[self.current_target or "recordings"]
            self.table.setHorizontalHeaderLabels([target_title[:-1], "Group"])
            for row, item_name in enumerate(self.items):
                item = QTableWidgetItem(item_name)
                item.setData(Qt.ItemDataRole.UserRole, item_name)
                group_item = QTableWidgetItem("")
                self.table.setItem(row, 0, item)
                self.table.setItem(row, 1, group_item)
                self._render_assignment_for_row(row)
        finally:
            self.table.blockSignals(False)
        self._filter_items(self.search_input.text())

    def _show_context_menu(self, pos: Any) -> None:
        if self.current_target is None:
            return

        index = self.table.indexAt(pos)
        if index.isValid() and not self.table.selectionModel().isRowSelected(index.row()):
            self.table.selectRow(index.row())

        selected_rows = self._selected_rows()
        if not selected_rows:
            return

        groups = self._groups()
        if not groups:
            return

        menu = QMenu(self)
        for group_id, group in groups.items():
            action = menu.addAction(str(group.get("group_name") or group_id))
            action.triggered.connect(lambda checked=False, selected_group_id=group_id: self._assign_selected(selected_group_id))
        menu.addSeparator()
        reset_action = menu.addAction("Reset assignment")
        reset_action.triggered.connect(lambda checked=False: self._assign_selected(None))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _assign_selected(self, group_id: str | None) -> None:
        for row in self._selected_rows():
            item_name = self._item_name_for_row(row)
            if item_name is None:
                continue
            if group_id is None:
                self.assignment_by_item.pop(item_name, None)
            else:
                self.assignment_by_item[item_name] = group_id
            self._render_assignment_for_row(row)
        self._sync()
        self.table.clearSelection()

    def _render_assignment_for_row(self, row: int) -> None:
        item_name = self._item_name_for_row(row)
        if item_name is None:
            return

        group_id = self.assignment_by_item.get(item_name)
        groups = self._groups()
        group = groups.get(group_id or "")
        group_name = str(group.get("group_name") or "") if group else ""
        group_color = ""
        if group:
            color = QColor(str(group.get("group_color") or ""))
            if color.isValid():
                group_color = color.name().upper()

        group_item = self.table.item(row, 1)
        if group_item is None:
            group_item = QTableWidgetItem("")
            self.table.setItem(row, 1, group_item)
        group_item.setText(group_name)
        for col in range(self.table.columnCount()):
            table_item = self.table.item(row, col)
            if table_item is not None:
                table_item.setData(_GROUP_COLOR_ROLE, group_color)
        self.table.viewport().update()

    def _sync(self, emit_changed: bool = True) -> None:
        target = self.current_target
        if target is None:
            self.validation_errors = []
            self._update_status_label()
            return

        groups = self._groups()
        assignment_by_group = {group_id: [] for group_id in groups}
        group_by_item: dict[str, str] = {}
        for item_name in self.items:
            group_id = self.assignment_by_item.get(item_name)
            if group_id in groups:
                assignment_by_group[group_id].append(item_name)
                group_by_item[item_name] = group_id

        self.assignment_by_item = dict(group_by_item)
        self.state["group_assignment"] = {
            "target": target,
            "items_by_group": assignment_by_group,
            "group_by_item": group_by_item,
        }
        self._sync_groups_state(target, assignment_by_group)
        self.validation_errors = self._validate_assignment()
        self._update_status_label()
        self._refresh_summary(assignment_by_group)

        if emit_changed:
            self.changed.emit()

    def _sync_groups_state(self, target: str, assignment_by_group: dict[str, list[str]]) -> None:
        groups = self._groups()
        for group_id, group in groups.items():
            assigned_items = list(assignment_by_group.get(group_id) or [])
            group[target] = assigned_items
            if target == "recordings":
                group["files"] = assigned_items
            elif target == "subjects":
                group["subjects"] = assigned_items
        self.state["grupos"] = groups

    def _validate_assignment(self) -> list[str]:
        target = self.current_target
        if target is None:
            return []

        errors: list[str] = []
        groups = self._groups()
        errors.extend(self.validation.validate_many(groups, [("minimum_length", {
            "minimum": 1,
            "item_name": "group",
            "action": "contain",
        })], label="Groups"))
        errors.extend(self.validation.validate_many(self.items, [("minimum_length", {
            "minimum": 1,
            "item_name": _TARGET_ITEM_NAMES[target],
            "action": "contain",
        })], label=_TARGET_TITLES[target]))
        errors.extend(self.validation.validate_errors(
            self._unassigned_items(),
            "custom",
            label=_TARGET_TITLES[target],
            validator=self._unassigned_items_error,
        ))
        return errors

    def _unassigned_items_error(self, value: list[str], *, label: str) -> str | None:
        if not value:
            return None
        item_name = _TARGET_ITEM_NAMES[self.current_target or "recordings"]
        return f"{label}: assign every {item_name} before continuing."

    def _unassigned_items(self) -> list[str]:
        return [item_name for item_name in self.items if item_name not in self.assignment_by_item]

    def _update_status_label(self) -> None:
        if self.current_target is None:
            self.status_label.setText("No group assignment is required for this analysis mode.")
            self.status_label.setProperty("status", "ready")
        elif self.validation_errors:
            self.status_label.setText(self.validation_errors[0])
            self.status_label.setProperty("status", "error")
        else:
            self.status_label.setText(f"All {_TARGET_ITEM_NAMES[self.current_target]}s assigned.")
            self.status_label.setProperty("status", "ready")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _refresh_summary(self, assignment_by_group: dict[str, list[str]]) -> None:
        self._clear_layout(self.summary_layout)
        groups = self._groups()
        for group_id, group in groups.items():
            count = len(assignment_by_group.get(group_id) or [])
            label = QLabel(f"{group.get('group_name', group_id)}: {count}")
            label.setObjectName("assignmentSummary")
            color = QColor(str(group.get("group_color") or ""))
            if color.isValid():
                label.setStyleSheet(
                    "QLabel#assignmentSummary {"
                    "color: #F8EEF2;"
                    f"background: rgba({color.red()}, {color.green()}, {color.blue()}, 70);"
                    f"border: 1px solid {color.name().upper()};"
                    "border-radius: 8px;"
                    "padding: 6px 10px;"
                    "font-weight: 650;"
                    "}"
                )
            self.summary_layout.addWidget(label)
        self.summary_layout.addStretch()

    def _filter_items(self, text: str) -> None:
        needle = text.lower().strip()
        for row in range(self.table.rowCount()):
            item_name = self._item_name_for_row(row) or ""
            self.table.setRowHidden(row, bool(needle) and needle not in item_name.lower())

    def _selected_rows(self) -> list[int]:
        return sorted({index.row() for index in self.table.selectionModel().selectedRows()})

    def _item_name_for_row(self, row: int) -> str | None:
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else item.text()

    def _stored_assignment_for_target(self, target: str) -> dict[str, str]:
        assignment = self.state.get("group_assignment")
        if isinstance(assignment, dict) and assignment.get("target") == target:
            group_by_item = assignment.get("group_by_item")
            if isinstance(group_by_item, dict):
                groups = self._groups()
                return {
                    str(item): str(group_id)
                    for item, group_id in group_by_item.items()
                    if str(item) in self.items and str(group_id) in groups
                }

        groups = self._groups()
        restored: dict[str, str] = {}
        for group_id, group in groups.items():
            for item_name in group.get(target, []) or []:
                if str(item_name) in self.items:
                    restored[str(item_name)] = group_id
        return restored

    def _available_items(self) -> list[str]:
        key = "plot_features_subjects" if self.current_target == "subjects" else "plot_features_recordings"
        values = self.state.get(key)
        return [str(value) for value in values] if isinstance(values, list) else []

    def _groups(self) -> dict[str, dict[str, Any]]:
        groups = self.state.get("grupos")
        if isinstance(groups, dict):
            return {str(group_id): dict(group) for group_id, group in groups.items() if isinstance(group, dict)}
        if isinstance(groups, list):
            return {f"group_{index + 1}": dict(group) for index, group in enumerate(groups) if isinstance(group, dict)}
        return {}

    @staticmethod
    def _clear_layout(layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def on_step_activated(self) -> None:
        self._refresh_from_state()

    def can_continue(self) -> bool:
        self.validation_errors = self._validate_assignment()
        self._update_status_label()
        return not self.validation_errors


__all__ = ["PlotFeaturesGroupAssignmentWidget"]
