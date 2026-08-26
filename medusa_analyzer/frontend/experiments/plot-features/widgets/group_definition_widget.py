from __future__ import annotations

from functools import partial
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from medusa_analyzer.frontend.validation import Validation


class GroupDefinitionWidget(QScrollArea):
    changed = Signal()

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        del experiment_info
        super().__init__()

        self.state = state
        self.config = defaults.get("group_definition", {})
        self.validation = Validation()
        self.validation_errors: list[str] = []
        self.group_rows: dict[str, dict[str, Any]] = {}
        self.custom_colors: dict[str, bool] = {}
        self._syncing = False

        self.min_groups = int(self.config.get("min_groups", 1))
        self.max_groups = int(self.config.get("max_groups", 12))
        self.default_group_count = int(self.config.get("default_group_count", 2))

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.content = QWidget()
        self.setWidget(self.content)
        root = QVBoxLayout(self.content)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(18)

        title = QLabel("Group definition")
        title.setObjectName("pageTitle")
        description = QLabel("Create the groups that will be used in the following assignment steps.")
        description.setObjectName("muted")
        description.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(description)

        root.addWidget(self._build_controls_panel())
        root.addWidget(self._build_groups_panel())
        root.addStretch()

        self._restore_group_count()
        self._sync(emit_changed=False)

    def _build_controls_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        label = QLabel("Number of groups")
        label.setObjectName("panelTitle")
        self.group_count = QSpinBox()
        self.group_count.setRange(self.min_groups, self.max_groups)
        self.group_count.setValue(self.default_group_count)
        self.group_count.valueChanged.connect(self._group_count_changed)

        layout.addWidget(label)
        layout.addWidget(self.group_count)
        layout.addStretch()
        return panel

    def _build_groups_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        heading = QLabel("Groups")
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)

        self.groups_grid = QGridLayout()
        self.groups_grid.setHorizontalSpacing(12)
        self.groups_grid.setVerticalSpacing(12)
        layout.addLayout(self.groups_grid)

        self.status_label = QLabel("")
        self.status_label.setObjectName("selectionStatus")
        self.status_label.setProperty("status", "idle")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        return panel

    def _restore_group_count(self) -> None:
        stored_groups = self._stored_groups()
        if stored_groups:
            group_count = len(stored_groups)
        else:
            group_count = self.default_group_count
        custom_colors = self.state.get("_group_definition_custom_colors", {})
        if isinstance(custom_colors, dict):
            self.custom_colors = {str(group_id): bool(value) for group_id, value in custom_colors.items()}
        else:
            self.custom_colors = {
                group_id: bool(group.get("color_is_custom", False))
                for group_id, group in stored_groups.items()
            }

        self.group_count.blockSignals(True)
        self.group_count.setValue(max(self.min_groups, min(self.max_groups, group_count)))
        self.group_count.blockSignals(False)
        self._rebuild_group_chips()

    def _group_count_changed(self) -> None:
        self._rebuild_group_chips()
        self._sync()

    def _rebuild_group_chips(self) -> None:
        self._clear_groups_grid()
        self.group_rows = {}

        group_count = self.group_count.value()
        stored_groups = self._stored_groups()
        default_colors = self._default_colors(group_count)
        active_group_ids = {self._group_id(index) for index in range(group_count)}
        self.custom_colors = {
            group_id: custom
            for group_id, custom in self.custom_colors.items()
            if group_id in active_group_ids and group_id in stored_groups
        }

        for index in range(group_count):
            group_id = self._group_id(index)
            stored_group = stored_groups.get(group_id, {})
            group_name = str(stored_group.get("group_name") or f"Group {index + 1}")
            if self.custom_colors.get(group_id, False):
                group_color = str(stored_group.get("group_color") or default_colors[index])
            else:
                group_color = default_colors[index]

            chip = self._create_group_chip(group_id, group_name, group_color)
            self.groups_grid.addWidget(chip, index // 2, index % 2)

        self.groups_grid.setColumnStretch(0, 1)
        self.groups_grid.setColumnStretch(1, 1)

    def _create_group_chip(self, group_id: str, group_name: str, group_color: str) -> QFrame:
        chip = QFrame()
        chip.setProperty("role", "group-definition-chip")
        chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(chip)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        swatch = QFrame()
        swatch.setProperty("role", "group-color-swatch")
        swatch.setFixedSize(22, 22)
        swatch.setStyleSheet(f"background: {group_color}; border-radius: 11px;")

        name_input = QLineEdit()
        name_input.setText(group_name)
        name_input.setPlaceholderText("Group name")
        name_input.textChanged.connect(self._sync)

        color_button = QPushButton(group_color.upper())
        color_button.setProperty("variant", "secondary")
        color_button.setProperty("role", "group-color-button")
        color_button.clicked.connect(partial(self._select_group_color, group_id))

        layout.addWidget(swatch)
        layout.addWidget(name_input, 1)
        layout.addWidget(color_button)

        self.group_rows[group_id] = {
            "name_input": name_input,
            "color": group_color.upper(),
            "color_button": color_button,
            "swatch": swatch,
        }
        return chip

    def _select_group_color(self, group_id: str) -> None:
        row = self.group_rows.get(group_id)
        if row is None:
            return

        selected_color = QColorDialog.getColor(QColor(str(row["color"])), self, "Select group color")
        if not selected_color.isValid():
            return

        color = selected_color.name().upper()
        row["color"] = color
        self.custom_colors[group_id] = True
        row["color_button"].setText(color)
        row["swatch"].setStyleSheet(f"background: {color}; border-radius: 11px;")
        self._sync()

    def _sync(self, *_: Any, emit_changed: bool = True) -> None:
        if self._syncing:
            return

        self._syncing = True
        try:
            self.state["grupos"] = self._groups_state()
            self.state["_group_definition_custom_colors"] = {
                group_id: bool(self.custom_colors.get(group_id, False))
                for group_id in self.group_rows
            }
            self.validation_errors = self._validate_groups()
            self._update_status_label()
        finally:
            self._syncing = False

        if emit_changed:
            self.changed.emit()

    def _groups_state(self) -> dict[str, dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        previous_groups = self._stored_groups()
        for index, (group_id, row) in enumerate(self.group_rows.items()):
            previous_group = previous_groups.get(group_id, {})
            groups[group_id] = {
                "group_name": row["name_input"].text().strip(),
                "group_color": str(row["color"]).upper(),
                "subjects": list(previous_group.get("subjects") or []),
                "files": list(previous_group.get("files") or []),
            }
        return groups

    def _validate_groups(self) -> list[str]:
        errors: list[str] = []
        groups = self.state.get("grupos", {})
        errors.extend(self.validation.validate_many(groups, [("minimum_length", {
            "minimum": self.min_groups,
            "item_name": "group",
            "action": "contain",
        })], label="Groups"))

        for index, group in enumerate(groups.values(), start=1):
            errors.extend(self.validation.validate_many(
                group.get("group_name", ""),
                ["required_text"],
                label=f"Group {index} name",
            ))
        return errors

    def _update_status_label(self) -> None:
        if self.validation_errors:
            self.status_label.setText(self.validation_errors[0])
            self.status_label.setProperty("status", "error")
        else:
            self.status_label.setText(f"{len(self.state.get('grupos', {}))} group(s) configured.")
            self.status_label.setProperty("status", "ready")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _clear_groups_grid(self) -> None:
        while self.groups_grid.count():
            item = self.groups_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _stored_groups(self) -> dict[str, dict[str, Any]]:
        groups = self.state.get("grupos")
        if isinstance(groups, dict):
            return {str(group_id): dict(group) for group_id, group in groups.items() if isinstance(group, dict)}
        if isinstance(groups, list):
            return {self._group_id(index): dict(group) for index, group in enumerate(groups) if isinstance(group, dict)}
        return {}

    @staticmethod
    def _group_id(index: int) -> str:
        return f"group_{index + 1}"

    def _default_colors(self, group_count: int) -> list[str]:
        saturation = int(self.config.get("default_color_saturation", 175))
        value = int(self.config.get("default_color_value", 235))
        hue_offset = int(self.config.get("default_color_hue_offset", 345))
        colors: list[str] = []
        for index in range(group_count):
            hue = int((hue_offset + (360 * index / max(1, group_count))) % 360)
            colors.append(QColor.fromHsv(hue, saturation, value).name().upper())
        return colors

    def on_step_activated(self) -> None:
        self._sync()

    def can_continue(self) -> bool:
        self.validation_errors = self._validate_groups()
        return not self.validation_errors


__all__ = ["GroupDefinitionWidget"]
