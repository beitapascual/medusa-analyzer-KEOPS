from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget


@dataclass(frozen=True, slots=True)
class FeatureItem:
    id: str
    title: str
    subtitle: str
    category_id: str
    checked_by_default: bool = False


class FeaturesWidget(QWidget):
    changed = Signal()

    def __init__(self, config: dict[str, Any], state: dict[str, Any], title: str, description: str):
        super().__init__()
        self.config = config
        self.state = state
        self.checkboxes: dict[str, QCheckBox] = {}

        if "selected_features" not in self.state or not self.state["selected_features"]:
            self.state["selected_features"] = self._default_selection()

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(16)

        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        subtitle = QLabel(description)
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(heading)
        root.addWidget(subtitle)

        grid_container = QWidget()
        grid = QGridLayout(grid_container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(16)

        for index, category in enumerate(self.config.get("categories", [])):
            panel = QFrame()
            panel.setProperty("role", "feature-group")
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(24, 20, 24, 20)
            category_title = QLabel(category["title"])
            category_title.setObjectName("groupTitle")
            layout.addWidget(category_title)
            for feature in category.get("features", []):
                item = FeatureItem(
                    id=feature["id"],
                    title=feature["title"],
                    subtitle=feature.get("subtitle", ""),
                    category_id=category["id"],
                    checked_by_default=bool(feature.get("checked_by_default", False)),
                )
                box = QCheckBox(item.title)
                box.setToolTip(item.subtitle)
                box.setChecked(item.id in self.state["selected_features"])
                box.toggled.connect(self._sync)
                layout.addWidget(box)
                if item.subtitle:
                    detail = QLabel(item.subtitle)
                    detail.setObjectName("muted")
                    detail.setWordWrap(True)
                    layout.addWidget(detail)
                self.checkboxes[item.id] = box
            layout.addStretch()
            grid.addWidget(panel, index // 2, index % 2)

        root.addWidget(grid_container)
        root.addStretch()
        self._sync()

    def _default_selection(self) -> list[str]:
        selected: list[str] = []
        for category in self.config.get("categories", []):
            for feature in category.get("features", []):
                if feature.get("checked_by_default", False):
                    selected.append(feature["id"])
        return selected

    def _sync(self) -> None:
        self.state["selected_features"] = [
            feature_id for feature_id, checkbox in self.checkboxes.items() if checkbox.isChecked()
        ]
        self.changed.emit()

    def can_continue(self) -> bool:
        return True
