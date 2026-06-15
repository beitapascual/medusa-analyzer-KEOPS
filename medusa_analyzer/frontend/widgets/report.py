from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from medusa_analyzer.frontend.models import MetadataSummary


class ReportWidget(QScrollArea):
    def __init__(self, config: dict[str, Any], state: dict[str, Any], title: str, description: str):
        super().__init__()
        self.config = config
        self.state = state
        self.title_text = title
        self.description_text = description
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.content = QWidget()
        self.root = QVBoxLayout(self.content)
        self.root.setContentsMargins(4, 4, 12, 4)
        self.root.setSpacing(16)
        self.setWidget(self.content)
        self.refresh()

    def on_step_activated(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        while self.root.count():
            item = self.root.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        title = QLabel(self.title_text)
        title.setObjectName("pageTitle")
        subtitle = QLabel(self.description_text)
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        self.root.addWidget(title)
        self.root.addWidget(subtitle)

        metadata = self.state.get("metadata")
        if self.config.get("include_metadata", True):
            self.root.addWidget(self._metadata_section(metadata))

        if self.config.get("include_preprocessing_summary", True):
            self.root.addWidget(self._preprocessing_section())

        if self.config.get("include_selected_features", True):
            self.root.addWidget(self._features_section())

        self.root.addStretch()

    def _metadata_section(self, metadata: MetadataSummary | None) -> QFrame:
        if metadata is None:
            return self._section("Metadata", [("Status", "No EDF loaded yet.")])
        return self._section(
            "Metadata",
            [
                ("File", metadata.file_name),
                ("Path", metadata.file_path),
                ("Channels", ", ".join(metadata.channels)),
                ("Sampling rate", f"{metadata.sampling_rate:g} Hz" if metadata.sampling_rate is not None else "-"),
                ("Duration", f"{metadata.duration_seconds:g} s" if metadata.duration_seconds is not None else "-"),
                ("Samples", str(metadata.n_samples) if metadata.n_samples is not None else "-"),
            ],
        )

    def _preprocessing_section(self) -> QFrame:
        preprocessing = self.state.get("preprocessing", {})
        if not preprocessing:
            return self._section("Pre-processing", [("Status", "Using experiment defaults.")])
        notch = preprocessing.get("notch", {})
        bandpass = preprocessing.get("bandpass", {})
        enabled_bands = [
            band.get("title", band.get("id", "Band"))
            for band in preprocessing.get("frequency_bands", [])
            if band.get("enabled", True)
        ]
        return self._section(
            "Pre-processing",
            [
                ("CAR", "Enabled" if preprocessing.get("car_checked") else "Disabled"),
                ("Notch", self._filter_description(notch)),
                ("Bandpass", self._filter_description(bandpass)),
                ("Frequency bands", ", ".join(enabled_bands) if enabled_bands else "None"),
            ],
        )

    @staticmethod
    def _filter_description(config: dict[str, Any]) -> str:
        if not config or not config.get("enabled", False):
            return "Disabled"
        if str(config.get("filter_type", "fir")).lower() == "fir":
            detail = f'order {config.get("fir_order")}, {config.get("fir_window")} window'
        else:
            detail = f'order {config.get("iir_order")}, {config.get("iir_design")}'
        return f'{config.get("low_cut"):g}-{config.get("high_cut"):g} Hz, {str(config.get("filter_type", "")).upper()}, {detail}'

    def _features_section(self) -> QFrame:
        selected = self.state.get("selected_features", [])
        value = ", ".join(selected) if selected else "None selected."
        return self._section("Features", [("Selected feature ids", value)])

    def _section(self, title: str, rows: list[tuple[str, str]]) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "summary-section")
        layout = QGridLayout(panel)
        layout.setContentsMargins(24, 20, 24, 20)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        layout.addWidget(heading, 0, 0, 1, 2)
        for row_index, (label, value) in enumerate(rows, start=1):
            key = QLabel(label)
            key.setObjectName("summaryLabel")
            detail = QLabel(value)
            detail.setWordWrap(True)
            layout.addWidget(key, row_index, 0)
            layout.addWidget(detail, row_index, 1)
        layout.setColumnStretch(1, 1)
        return panel
