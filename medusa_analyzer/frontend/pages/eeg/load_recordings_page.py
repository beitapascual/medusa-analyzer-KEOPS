from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QLabel, QListWidget, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from medusa_analyzer.backend.io.recording_loader import load_recordings
from medusa_analyzer.backend.workflows.eeg_state import EEGWorkflowState, RecordingMetadata
from medusa_analyzer.frontend.widgets.loading_overlay import LoadingOverlay
from medusa_analyzer.frontend.workers.task_runner import TaskRunner
from medusa_analyzer.frontend.workers.worker import Worker


class LoadRecordingsPage(QWidget):
    validity_changed = Signal(bool)
    next_requested = Signal()

    def __init__(self, state: EEGWorkflowState):
        super().__init__()
        self.state = state
        self.runner = TaskRunner()
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        title = QLabel("Load EEG recordings")
        title.setObjectName("pageTitle")
        description = QLabel("Choose one or more recordings. This MVP validates them asynchronously and creates representative metadata.")
        description.setObjectName("muted")
        description.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(description)
        root.addSpacing(18)

        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        self.select_button = QPushButton("Select recordings")
        self.select_button.setProperty("variant", "secondary")
        self.select_button.clicked.connect(self._select_files)
        self.files = QListWidget()
        self.files.setMinimumHeight(125)
        self.files.setProperty("role", "file-list")
        layout.addWidget(self.select_button)
        layout.addWidget(self.files)
        root.addWidget(panel)

        self.metadata_panel = QFrame()
        self.metadata_panel.setProperty("role", "surface-panel")
        self.metadata_layout = QGridLayout(self.metadata_panel)
        self.metadata_layout.setContentsMargins(24, 20, 24, 20)
        root.addWidget(self.metadata_panel)
        self.metadata_panel.hide()
        root.addStretch()
        self.next_button = QPushButton("Continue to preprocessing")
        self.next_button.setProperty("variant", "primary")
        self.next_button.setEnabled(state.metadata is not None)
        self.next_button.clicked.connect(self.next_requested)
        root.addWidget(self.next_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.overlay = LoadingOverlay(self)

    def _select_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select EEG recordings", "", "EEG recordings (*.edf *.bdf *.set *.mat *.csv);;All files (*.*)"
        )
        if not paths:
            return
        self.state.selected_files = paths
        self.files.clear()
        self.files.addItems([Path(path).name for path in paths])
        self.select_button.setEnabled(False)
        self.overlay.show_loading("Validating recordings and reading metadata...")
        worker = Worker(load_recordings, paths)
        worker.signals.progress.connect(self.overlay.progress.setValue)
        worker.signals.result.connect(self._loaded)
        worker.signals.error.connect(self._failed)
        worker.signals.finished.connect(lambda: self.select_button.setEnabled(True))
        self.runner.start(worker)

    def _loaded(self, metadata: RecordingMetadata):
        self.state.metadata = metadata
        self.overlay.hide()
        self.next_button.setEnabled(True)
        self._show_metadata(metadata)
        self.validity_changed.emit(True)

    def _failed(self, error: str):
        self.overlay.hide()
        self.next_button.setEnabled(False)
        self.validity_changed.emit(False)
        QMessageBox.critical(self, "Could not load recordings", error.splitlines()[0])

    def _show_metadata(self, metadata: RecordingMetadata):
        while self.metadata_layout.count():
            item = self.metadata_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        values = [
            ("Number of files", str(metadata.n_files)), ("Sampling rate", f"{metadata.fs:g} Hz"),
            ("Nyquist frequency", f"{metadata.nyquist:g} Hz"), ("Channels", str(metadata.n_channels)),
            ("Duration", f"{metadata.duration_seconds:g} s"),
            ("Frequency range", f"{metadata.frequency_range[0]:g}–{metadata.frequency_range[1]:g} Hz"),
        ]
        for index, (label, value) in enumerate(values):
            name = QLabel(label)
            name.setObjectName("metricLabel")
            number = QLabel(value)
            number.setObjectName("metricValue")
            self.metadata_layout.addWidget(name, (index // 3) * 2, index % 3)
            self.metadata_layout.addWidget(number, (index // 3) * 2 + 1, index % 3)
        self.metadata_panel.show()
