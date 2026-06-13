from collections import defaultdict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QGridLayout, QLabel, QVBoxLayout

from medusa_analyzer.backend.configs.features import FeatureDescriptor, FeatureSelectionConfig


class FeatureSelector(QFrame):
    changed = Signal()

    def __init__(self, features: list[FeatureDescriptor], config: FeatureSelectionConfig):
        super().__init__()
        self.setProperty("role", "feature-selector")
        self.config = config
        self.checkboxes: dict[str, QCheckBox] = {}
        grouped = defaultdict(list)
        for feature in features:
            grouped[feature.category].append(feature)
        root = QGridLayout(self)
        root.setSpacing(16)
        for index, category in enumerate(("Temporal", "Spectral", "Complexity", "Connectivity")):
            panel = QFrame()
            panel.setProperty("role", "feature-group")
            layout = QVBoxLayout(panel)
            title = QLabel(category)
            title.setObjectName("groupTitle")
            layout.addWidget(title)
            for feature in grouped[category]:
                box = QCheckBox(feature.name)
                box.setToolTip(feature.description)
                box.setChecked(feature.id in config.selected_feature_ids)
                box.toggled.connect(self._sync)
                layout.addWidget(box)
                self.checkboxes[feature.id] = box
            layout.addStretch()
            root.addWidget(panel, index // 2, index % 2)

    def _sync(self) -> None:
        self.config.selected_feature_ids = [
            feature_id for feature_id, box in self.checkboxes.items() if box.isChecked()
        ]
        self.changed.emit()
