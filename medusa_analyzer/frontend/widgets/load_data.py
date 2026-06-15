from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from medusa_analyzer.frontend.models import MetadataSummary
from medusa_analyzer.frontend.widgets.loading_overlay import LoadingOverlay
from medusa_analyzer.frontend.workers import TaskRunner, Worker


class LoadDataWidget(QWidget):
    changed = Signal()

    def __init__(
        self,
        config: dict[str, Any],
        state: dict[str, Any],
        loader: Callable[..., dict],
        title: str,
        description: str,
    ):
        super().__init__()
        self.config = config
        self.state = state
        self.loader = loader
        self.runner = TaskRunner()

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        description_label = QLabel(description)
        description_label.setObjectName("muted")
        description_label.setWordWrap(True)
        root.addWidget(title_label)
        root.addWidget(description_label)
        root.addSpacing(18)

        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        self.select_button = QPushButton("Select EDF file")
        self.select_button.setProperty("variant", "secondary")
        self.select_button.clicked.connect(self._select_file)
        self.files = QListWidget()
        self.files.setMinimumHeight(125)
        self.files.setProperty("role", "file-list")
        self.status_label = QLabel("Choose one recording to load its metadata.")
        self.status_label.setObjectName("selectionStatus")
        self.status_label.setProperty("status", "idle")
        layout.addWidget(self.select_button)
        layout.addWidget(self.files)
        layout.addWidget(self.status_label)
        root.addWidget(panel)

        self.metadata_panel = QFrame()
        self.metadata_panel.setProperty("role", "surface-panel")
        self.metadata_layout = QGridLayout(self.metadata_panel)
        self.metadata_layout.setContentsMargins(24, 20, 24, 20)
        root.addWidget(self.metadata_panel)
        self.metadata_panel.hide()
        root.addStretch()

        self.overlay = LoadingOverlay(self)
        metadata = self.state.get("metadata")
        if metadata is not None:
            self.files.addItem(metadata.file_name)
            self._show_metadata(metadata)

    def _select_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select recording",
            "",
            self._dialog_filter(),
        )
        if not path:
            return
        self.files.clear()
        self.files.addItem(Path(path).name)
        self.status_label.setText("Reading EDF metadata...")
        self.status_label.setProperty("status", "idle")
        self._refresh_status_style()
        self.select_button.setEnabled(False)
        self.overlay.show_loading("Reading EDF file...")
        worker = Worker(self.loader, path)
        worker.signals.progress.connect(self.overlay.progress.setValue)
        worker.signals.result.connect(self._loaded)
        worker.signals.error.connect(self._failed)
        worker.signals.finished.connect(self._finished_loading)
        self.runner.start(worker)

    def _dialog_filter(self) -> str:
        extensions = self.config.get("allowed_extensions", [".edf"])
        patterns = " ".join(f"*{extension}" for extension in extensions)
        return f"Supported files ({patterns});;All files (*.*)"

    def _loaded(self, result: dict) -> None:
        metadata = MetadataSummary.from_loader_result(result)
        self.state["loaded_file_path"] = result.get("path")
        self.state["loader_result"] = result
        self.state["metadata"] = metadata
        self.status_label.setText("EDF loaded successfully.")
        self.status_label.setProperty("status", "ready")
        self._refresh_status_style()
        self._show_metadata(metadata)
        self.changed.emit()

    def _failed(self, error: str) -> None:
        self.status_label.setText(error.splitlines()[0])
        self.status_label.setProperty("status", "error")
        self._refresh_status_style()

    def _finished_loading(self) -> None:
        self.overlay.hide()
        self.select_button.setEnabled(True)

    def _refresh_status_style(self) -> None:
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _show_metadata(self, metadata: MetadataSummary) -> None:
        while self.metadata_layout.count():
            item = self.metadata_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        values = [
            ("Number of files", "1"),
            (
                "Sampling rate",
                f"{metadata.sampling_rate:g} Hz" if metadata.sampling_rate is not None else "-",
            ),
            ("Channels", str(len(metadata.channels))),
            (
                "Duration",
                f"{metadata.duration_seconds:g} s" if metadata.duration_seconds is not None else "-",
            ),
            ("Samples", str(metadata.n_samples) if metadata.n_samples is not None else "-"),
            ("Channel list", ", ".join(metadata.channels) or "-"),
        ]
        for index, (label, value) in enumerate(values):
            name = QLabel(label)
            name.setObjectName("metricLabel")
            number = QLabel(value)
            number.setObjectName("metricValue")
            number.setWordWrap(True)
            self.metadata_layout.addWidget(name, (index // 3) * 2, index % 3)
            self.metadata_layout.addWidget(number, (index // 3) * 2 + 1, index % 3)
        self.metadata_panel.show()

    def can_continue(self) -> bool:
        return self.state.get("metadata") is not None
