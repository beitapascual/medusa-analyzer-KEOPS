from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from medusa_analyzer.backend.configs.analysis import EEGAnalysisConfig
from medusa_analyzer.backend.workflows.eeg_state import EEGWorkflowState


class ProcessingSummaryPage(QScrollArea):
    back_requested = Signal()

    def __init__(self, state: EEGWorkflowState):
        super().__init__()
        self.state = state
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.content = QWidget()
        self.root = QVBoxLayout(self.content)
        self.root.setContentsMargins(4, 4, 12, 4)
        self.setWidget(self.content)

    def refresh(self):
        while self.root.count():
            item = self.root.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        title = QLabel("Processing summary")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Review the complete analysis specification before handing it to the future processing pipeline.")
        subtitle.setObjectName("muted")
        self.root.addWidget(title)
        self.root.addWidget(subtitle)
        self.root.addSpacing(16)
        metadata = self.state.metadata
        self.root.addWidget(self._section("Recordings", [
            ("Files", ", ".join(Path(path).name for path in self.state.selected_files)),
            ("Sampling rate", f"{metadata.fs:g} Hz"), ("Nyquist", f"{metadata.nyquist:g} Hz"),
            ("Channels", str(metadata.n_channels)), ("Duration", f"{metadata.duration_seconds:g} s"),
        ]))
        config = self.state.preprocessing_config
        self.root.addWidget(self._section("Preprocessing", [
            ("CAR", self._enabled(config.apply_car)),
            ("Notch", self._filter_description(config.notch)),
            ("Bandpass", self._filter_description(config.bandpass)),
            ("Frequency bands", ", ".join(
                f"{band.name} ({band.low_cut:g}–{band.high_cut:g} Hz)"
                for band in config.frequency_bands if band.enabled
            ) or "None"),
        ]))
        self.root.addWidget(self._section("Selected features", [
            ("Feature IDs", ", ".join(self.state.feature_config.selected_feature_ids))
        ]))
        self.root.addStretch()
        actions = QHBoxLayout()
        back = QPushButton("Back")
        back.setProperty("variant", "ghost")
        back.clicked.connect(self.back_requested)
        process = QPushButton("Process")
        process.setProperty("variant", "primary")
        process.clicked.connect(self._process)
        actions.addWidget(back)
        actions.addStretch()
        actions.addWidget(process)
        self.root.addLayout(actions)

    @staticmethod
    def _enabled(value: bool) -> str:
        return "Enabled" if value else "Disabled"

    @staticmethod
    def _filter_description(config) -> str:
        if not config.enabled:
            return "Disabled"
        detail = (
            f"order {config.fir_order}, {config.fir_window} window"
            if config.filter_type == "fir"
            else f"order {config.iir_order}, {config.iir_design}"
        )
        if config.filter_type == "fir":
            detail = f"order {config.fir_order}, {config.fir_window} window"
        else:
            parts = [f"order {config.iir_order}", config.iir_design]
            if config.iir_design in {"cheby1", "ellip"}:
                parts.append(f"rp={config.iir_rp_db:g} dB")
            if config.iir_design in {"cheby2", "ellip"}:
                parts.append(f"rs={config.iir_rs_db:g} dB")
            detail = ", ".join(parts)

        return f"{config.low_cut:g}–{config.high_cut:g} Hz, {config.filter_type.upper()}, {detail}"

    @staticmethod
    def _section(title: str, values: list[tuple[str, str]]) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "summary-section")
        layout = QGridLayout(panel)
        layout.setContentsMargins(24, 20, 24, 20)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        layout.addWidget(heading, 0, 0, 1, 2)
        for row, (label, value) in enumerate(values, 1):
            name = QLabel(label)
            name.setObjectName("summaryLabel")
            detail = QLabel(value)
            detail.setWordWrap(True)
            layout.addWidget(name, row, 0)
            layout.addWidget(detail, row, 1)
        layout.setColumnStretch(1, 1)
        return panel

    def _process(self):
        analysis = EEGAnalysisConfig(
            files=list(self.state.selected_files), metadata=self.state.metadata,
            preprocessing=self.state.preprocessing_config, features=self.state.feature_config,
        )
        print("EEGAnalysisConfig:", asdict(analysis))
        QMessageBox.information(
            self, "Configuration ready",
            "Analysis configuration is ready. Real processing will be integrated in a later stage.",
        )
