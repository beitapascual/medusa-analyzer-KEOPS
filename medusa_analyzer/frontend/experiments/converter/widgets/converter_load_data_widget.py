from typing import Any

from PySide6.QtWidgets import (
    QPushButton,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QFrame,
    QFileDialog,
)

from medusa_analyzer.backend.converter.validate_input import read_folder_for_converter
from medusa_analyzer.frontend.widgets import LoadDataWidget


class ConverterLoadDataWidget(LoadDataWidget):
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__(
            config=defaults.get("load_data", {}),  # allowed extensions
            state=state,
            loader_function=read_folder_for_converter,
            args=[defaults.get("load_data").get("allowed_extensions")],
            title="Load data",
            description="Select a MEDUSA Studio dataset.",
        )

        self.select_button.setText("Load MEDUSA Files")

        # The parent widget's layout is where the button is.
        original_layout = self.select_button.parentWidget().layout()
        if original_layout:
            # Find the position of the button.
            index = original_layout.indexOf(self.select_button)
            if index != -1:
                # Create a horizontal layout to hold the buttons side-by-side.
                button_layout = QHBoxLayout()

                # When we add the existing button to the new layout, it's
                # automatically removed from the old one. No duplication occurs.
                button_layout.addWidget(self.select_button)

                # Create and add the new button.
                self.load_files_button = QPushButton("Load MEDUSA Studio")
                self.load_files_button.setProperty("variant", "secondary")
                self.load_files_button.clicked.connect(lambda: self._select_files('folder'))
                button_layout.addWidget(self.load_files_button)

                # Insert the new horizontal layout of buttons at the original button's position.
                original_layout.insertLayout(index, button_layout)

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
