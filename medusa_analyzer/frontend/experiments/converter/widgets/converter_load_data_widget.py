from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QHBoxLayout,QLabel,QLineEdit,QFrame,QFileDialog,QPushButton

from medusa_analyzer.backend.converter.inspect_source import load_converter_source
from medusa_analyzer.frontend.widgets import LoadDataAction, LoadDataWidget, WorkerCall


class ConverterLoadDataWidget(LoadDataWidget):
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        load_data_config = defaults.get("load_data", {})
        allowed_extensions = tuple(load_data_config.get("allowed_extensions", ()))

        super().__init__(
            config=load_data_config,  # allowed extensions
            state=state,
            actions=[
                LoadDataAction(
                    id="medusa_files",
                    label="Load MEDUSA Files",
                    select=lambda widget: widget.select_files("Select MEDUSA files"),
                    build_call=lambda paths: WorkerCall(
                        function=load_converter_source,
                        kwargs={"input_data": [Path(path) for path in paths],
                            "validation_type": "files"}),
                    display_names=lambda paths: [Path(path).name for path in paths],
                    status_text=lambda paths: f"Reading {len(paths)} MEDUSA file(s)...",
                    overlay_text="Reading MEDUSA files...",
                ),
                LoadDataAction(id="medusa_studio",
                    label="Load MEDUSA Studio",
                    select=lambda widget: widget.select_directory("Select MEDUSA Studio directory"),
                    build_call=lambda path: WorkerCall(
                        function=load_converter_source,
                        kwargs={"input_data": Path(path),
                            "validation_type": "studio",
                            "extensions": allowed_extensions}),
                    display_names=lambda path: [Path(path).name or str(path)],
                    status_text="Reading folder...",
                    overlay_text="Reading MEDUSA Studio folder...",
                ),
            ],
            title="Load data",
            description="Select a MEDUSA Studio dataset.",
            metadata_labels={
                "Total files": "Total files",
                "Number of subjects": "Number of subjects",
                "Number of tasks": "Number of tasks",
                "Task list": "Task list",
            },
        )

        # --- New sections for dataset name and output path ---

        self.output_panel = QFrame()
        self.output_panel.setProperty("role", "surface-panel")
        output_layout = QHBoxLayout(self.output_panel)
        output_layout.setContentsMargins(24, 20, 24, 20)

        # Dataset name
        output_layout.addWidget(QLabel("Dataset name:"))
        self.dataset_name_input = QLineEdit()
        self.dataset_name_input.textChanged.connect(self._update_full_path)
        output_layout.addWidget(self.dataset_name_input)

        output_layout.addSpacing(20)

        # Output path
        output_layout.addWidget(QLabel("Output path:"))
        self.output_path_display = QLineEdit()
        self.output_path_display.setReadOnly(True)
        self.base_path = ""
        output_layout.addWidget(self.output_path_display)
        self.select_path_button = QPushButton("...")
        self.select_path_button.clicked.connect(self._select_output_path)
        output_layout.addWidget(self.select_path_button)

        # Add the new panel to the main layout, after the metadata panel
        root_layout = self.content.layout()
        metadata_panel_index = root_layout.indexOf(self.metadata_panel)
        root_layout.insertWidget(metadata_panel_index + 1, self.output_panel)

        self.output_panel.hide()


    def _select_output_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.base_path = path
            self._update_full_path()

    def _update_full_path(self):
        dataset_name = self.dataset_name_input.text()
        if self.base_path and dataset_name:
            self.output_path_display.setText(f"{self.base_path}/{dataset_name}")
        elif self.base_path:
            self.output_path_display.setText(self.base_path)
        else:
            self.output_path_display.clear()

    def _show_metadata(self, metadata_list: list[dict[str, Any]]) -> None:
        # For showing/hiding the new output panel.
        super()._show_metadata(metadata_list)
        if metadata_list:
            self.output_panel.show()
        else:
            self.output_panel.hide()

    def _clear_loaded_state(self) -> None:
        # For clearing the new panels and input fields.
        super()._clear_loaded_state()
        self.output_panel.hide()
        self.dataset_name_input.clear()
        self.output_path_display.clear()
        self.base_path = ""
