from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from medusa_analyzer.backend.features.registry import get_feature_catalog
from medusa_analyzer.backend.workflows.eeg_state import EEGWorkflowState
from medusa_analyzer.frontend.widgets.feature_selector import FeatureSelector


class FeatureSelectionPage(QWidget):
    validity_changed = Signal(bool)
    next_requested = Signal()
    back_requested = Signal()

    def __init__(self, state: EEGWorkflowState):
        super().__init__()
        self.state = state
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        title = QLabel("Feature selection")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Select at least one measure. Features are grouped by the scientific question they support.")
        subtitle.setObjectName("muted")
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(16)
        self.selector = FeatureSelector(get_feature_catalog(), state.feature_config)
        self.selector.changed.connect(self._validate)
        root.addWidget(self.selector, 1)
        self.status = QLabel()
        self.status.setObjectName("selectionStatus")
        root.addWidget(self.status)
        actions = QHBoxLayout()
        back = QPushButton("Back")
        back.setProperty("variant", "ghost")
        back.clicked.connect(self.back_requested)
        self.next_button = QPushButton("Review configuration")
        self.next_button.setProperty("variant", "primary")
        self.next_button.clicked.connect(self.next_requested)
        actions.addWidget(back)
        actions.addStretch()
        actions.addWidget(self.next_button)
        root.addLayout(actions)
        self._validate()

    def _validate(self):
        count = len(self.state.feature_config.selected_feature_ids)
        valid = count > 0
        self.status.setText(f"{count} feature{'s' if count != 1 else ''} selected" if valid else "Select at least one feature to continue.")
        self.status.setProperty("status", "valid" if valid else "error")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.next_button.setEnabled(valid)
        self.validity_changed.emit(valid)
