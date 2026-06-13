from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from medusa_analyzer.backend.experiments.eeg import create_eeg_workflow_state
from medusa_analyzer.frontend.pages.eeg.feature_selection_page import FeatureSelectionPage
from medusa_analyzer.frontend.pages.eeg.load_recordings_page import LoadRecordingsPage
from medusa_analyzer.frontend.pages.eeg.preprocessing_page import PreprocessingPage
from medusa_analyzer.frontend.pages.eeg.processing_summary_page import ProcessingSummaryPage
from medusa_analyzer.frontend.widgets.step_progress_bar import StepProgressBar


class EEGWorkflowPage(QWidget):
    dashboard_requested = Signal()

    def __init__(self):
        super().__init__()
        self.state = create_eeg_workflow_state()
        self.valid = [False, True, bool(self.state.feature_config.selected_feature_ids), True]
        self.highest_unlocked = 0
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 22, 34, 28)
        top = QHBoxLayout()
        back = QPushButton("←  Dashboard")
        back.setProperty("variant", "ghost")
        back.clicked.connect(self.dashboard_requested)
        context = QLabel("EEG PROCESSING WORKFLOW")
        context.setObjectName("eyebrow")
        top.addWidget(back)
        top.addStretch()
        top.addWidget(context)
        root.addLayout(top)
        self.stepper = StepProgressBar(["Load data", "Preprocessing", "Features", "Summary"])
        root.addWidget(self.stepper)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(divider)
        self.stack = QStackedWidget()
        self.load_page = LoadRecordingsPage(self.state)
        self.preprocessing_page = PreprocessingPage(self.state)
        self.features_page = FeatureSelectionPage(self.state)
        self.summary_page = ProcessingSummaryPage(self.state)
        for page in (self.load_page, self.preprocessing_page, self.features_page, self.summary_page):
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)
        self.load_page.validity_changed.connect(lambda valid: self._set_valid(0, valid))
        self.preprocessing_page.validity_changed.connect(lambda valid: self._set_valid(1, valid))
        self.features_page.validity_changed.connect(lambda valid: self._set_valid(2, valid))
        self.load_page.next_requested.connect(lambda: self.go_to(1))
        self.preprocessing_page.next_requested.connect(lambda: self.go_to(2))
        self.preprocessing_page.back_requested.connect(lambda: self.go_to(0))
        self.features_page.next_requested.connect(lambda: self.go_to(3))
        self.features_page.back_requested.connect(lambda: self.go_to(1))
        self.summary_page.back_requested.connect(lambda: self.go_to(2))
        self._update_steps()

    def _set_valid(self, index: int, valid: bool):
        self.valid[index] = valid
        if valid and index == self.highest_unlocked and index < 3:
            self.highest_unlocked = index + 1
        self._update_steps()

    def go_to(self, index: int):
        current = self.stack.currentIndex()
        can_advance = index == current + 1 and self.valid[current]
        if index > self.highest_unlocked and not can_advance:
            return
        self.highest_unlocked = max(self.highest_unlocked, index)
        self.stack.setCurrentIndex(index)
        self.state.current_step = ("load", "preprocessing", "features", "summary")[index]
        if index == 3:
            self.summary_page.refresh()
        self._update_steps()

    def _update_steps(self):
        current = self.stack.currentIndex()
        states = []
        for index in range(4):
            if index > self.highest_unlocked:
                states.append("locked")
            elif index == current:
                states.append("active")
            elif index < current and self.valid[index]:
                states.append("completed")
            elif not self.valid[index] and index <= self.highest_unlocked:
                states.append("error")
            else:
                states.append("completed")
        self.stepper.set_states(states)
