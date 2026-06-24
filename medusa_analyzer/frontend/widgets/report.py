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

        for section in self._sections():
            if section is not None:
                self.root.addWidget(section)

        self.root.addStretch()

    def _sections(self) -> list[QWidget]:
        sections: list[QWidget] = []
        metadata_list = self.state.get("metadata_list") or []
        if self.config.get("include_metadata", True):
            sections.append(self._metadata_section(metadata_list))

        if self.config.get("include_preprocessing_summary", True):
            preprocessing_section = self._preprocessing_section()
            if preprocessing_section is not None:
                sections.append(preprocessing_section)

        if self.config.get("include_selected_features", True):
            features_section = self._features_section()
            if features_section is not None:
                sections.append(features_section)

        sections.extend(self._additional_sections())
        return sections

    def _preprocessing_section(self) -> QFrame | None:
        return None

    def _features_section(self) -> QFrame | None:
        return None

    def _additional_sections(self) -> list[QWidget]:
        return []

    def _metadata_section(self, metadata_list: list[MetadataSummary]) -> QFrame:
        if not metadata_list:
            return self._section("Metadata", [("Status", "No EDF loaded yet.")])

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
        channels = list(
            dict.fromkeys(
                channel
                for metadata in metadata_list
                for channel in metadata.channels
            )
        )
        return self._section(
            "Metadata",
            [
                ("Files", ", ".join(metadata.file_name for metadata in metadata_list)),
                ("Paths", ", ".join(metadata.file_path for metadata in metadata_list)),
                ("Channels", ", ".join(channels)),
                ("Sampling rate", sampling_rate),
                (
                    "Total duration",
                    f"{sum(metadata.duration_seconds or 0 for metadata in metadata_list):g} s",
                ),
                (
                    "Total samples",
                    str(sum(metadata.n_samples or 0 for metadata in metadata_list)),
                ),
            ],
        )

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
