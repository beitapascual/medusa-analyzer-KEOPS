from __future__ import annotations
from collections.abc import Callable
from pathlib import Path
from typing import Any
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QLabel, QListWidget,
    QPushButton, QVBoxLayout, QWidget)
from medusa_analyzer.frontend.models import MetadataSummary
from medusa_analyzer.frontend.widgets.loading_overlay import LoadingOverlay
from medusa_analyzer.frontend.workers import TaskRunner, Worker

# Script to allow usert to select EDF files, load them in a background thread using workers,
# extract metadata from files and show them on the screen.

def _load_files(loader: Callable[..., dict], paths: list[str],
    progress_callback: Callable[[int], None] | None = None) -> list[dict]:
    results = []
    file_count = len(paths)
    for index, path in enumerate(paths):
        # Function to convert the progress of one individual file in a global progress
        def report_progress(value: int, file_index: int = index) -> None:
            if progress_callback:
                progress_callback(int((file_index * 100 + value) / file_count))

        results.append(loader(path, progress_callback=report_progress))
    return results


class LoadDataWidget(QWidget):
    changed = Signal() # emit a signal when widget state changes, por example when a file is
    # selected o when files are loaded correctly.

    def __init__(self,
        config: dict[str, Any], # allowed extensions
        state: dict[str, Any], # dic to store loaded data
        loader: Callable[..., dict], # function that knows how to load a file
        title: str, # title to show in the UI
        description: str): # description to show in the UI

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
        self.select_button = QPushButton("Select EDF files")
        self.select_button.setProperty("variant", "secondary")
        self.select_button.clicked.connect(self._select_files)
        self.files = QListWidget() # List to show selected file names
        self.files.setMinimumHeight(125)
        self.files.setProperty("role", "file-list")
        self.status_label = QLabel("Choose one or more recordings to load their metadata.")
        self.status_label.setObjectName("selectionStatus")
        self.status_label.setProperty("status", "idle") # ready or error
        layout.addWidget(self.select_button)
        layout.addWidget(self.files)
        layout.addWidget(self.status_label)
        root.addWidget(panel)

        self.metadata_panel = QFrame()
        self.metadata_panel.setProperty("role", "surface-panel")
        self.metadata_layout = QGridLayout(self.metadata_panel)
        self.metadata_layout.setContentsMargins(24, 20, 24, 20)
        root.addWidget(self.metadata_panel)
        self.metadata_panel.hide() # only shown when metadada are laoded
        root.addStretch()

        self.overlay = LoadingOverlay(self)
        metadata_list = self.state.get("metadata_list") or []
        if not metadata_list and self.state.get("metadata") is not None:
            metadata_list = [self.state["metadata"]]
        if metadata_list:
            self.files.addItems([metadata.file_name for metadata in metadata_list])
            self._show_metadata(metadata_list)

    def _select_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select recordings",
            "", self._dialog_filter())
        if not paths:
            return
        self._clear_loaded_state()
        self.files.clear()
        self.files.addItems([Path(path).name for path in paths])
        self.metadata_panel.hide()
        self.status_label.setText(f"Reading {len(paths)} recording(s)...")
        self.status_label.setProperty("status", "idle")
        self._refresh_status_style()
        self.changed.emit()
        self.select_button.setEnabled(False)
        self.overlay.show_loading("Reading recordings...")
        worker = Worker(_load_files, self.loader, paths)
        worker.signals.progress.connect(self.overlay.progress.setValue)
        worker.signals.result.connect(self._loaded)
        worker.signals.error.connect(self._failed)
        worker.signals.finished.connect(self._finished_loading)
        self.runner.start(worker)

    def _dialog_filter(self) -> str:
        extensions = self.config.get("allowed_extensions", [".edf"])
        patterns = " ".join(f"*{extension}" for extension in extensions)
        return f"Supported files ({patterns});;All files (*.*)"

    def _clear_loaded_state(self) -> None:
        # delete files loaded previously
        self.state["loaded_file_paths"] = []
        self.state["loader_results"] = []
        self.state["metadata_list"] = []
        self.state["loaded_file_path"] = None
        self.state["loader_result"] = None
        self.state["metadata"] = None

    def _loaded(self, results: list[dict]) -> None:
        # Convierte cada resultado del loader en un metadata summary
        metadata_list = [
            MetadataSummary.from_loader_result(result)
            for result in results
        ]
        self.state["loaded_file_paths"] = [
            result.get("path")
            for result in results
        ]
        self.state["loader_results"] = results
        self.state["metadata_list"] = metadata_list

        first_result = results[0]
        first_metadata = metadata_list[0]
        self.state["loaded_file_path"] = first_result.get("path")
        self.state["loader_result"] = first_result
        self.state["metadata"] = first_metadata

        self.status_label.setText(f"{len(results)} recording(s) loaded successfully.")
        self.status_label.setProperty("status", "ready")
        self._refresh_status_style()
        self._show_metadata(metadata_list)
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

    def _show_metadata(self, metadata_list: list[MetadataSummary]) -> None:
        while self.metadata_layout.count():
            item = self.metadata_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sampling_rates = {
            metadata.sampling_rate
            for metadata in metadata_list
            if metadata.sampling_rate is not None
        }
        sampling_rate = (
            f"{next(iter(sampling_rates)):g} Hz"
            if len(sampling_rates) == 1
            else "Mixed"
        )
        channel_counts = [len(metadata.channels) for metadata in metadata_list]
        channel_count = (
            str(channel_counts[0])
            if len(set(channel_counts)) == 1
            else f"{min(channel_counts)}-{max(channel_counts)} per file"
        )
        duration = sum(
            metadata.duration_seconds or 0.0
            for metadata in metadata_list
        )
        samples = sum(
            metadata.n_samples or 0
            for metadata in metadata_list
        )
        channels = list(
            dict.fromkeys(
                channel
                for metadata in metadata_list
                for channel in metadata.channels
            )
        )
        values = [
            ("Number of files", str(len(metadata_list))),
            ("Sampling rate", sampling_rate),
            ("Channels", channel_count),
            ("Total duration", f"{duration:g} s"),
            ("Total samples", str(samples)),
            ("Channel list", ", ".join(channels) or "-"),
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
        return bool(self.state.get("metadata_list") or self.state.get("metadata"))
