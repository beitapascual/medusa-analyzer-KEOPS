from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
    QWidget)


class PlotFeaturesVisualizationWidget(QScrollArea):
    changed = Signal()

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        del experiment_info
        super().__init__()

        self.state = state
        self.config = defaults.get("plots", {})
        self.plot_types = list(self.config.get("available_plot_types", []))
        self.feature_tabs: dict[str, dict[str, Any]] = {}
        self._refreshing = False

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.content = QWidget()
        self.setWidget(self.content)
        root = QVBoxLayout(self.content)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(18)

        title = QLabel("Plot visualization")
        title.setObjectName("pageTitle")
        description = QLabel("Configure one plot for each selected feature.")
        description.setObjectName("muted")
        description.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(description)

        self.tabs = QTabWidget()
        self.tabs.setProperty("role", "features-tabs")
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self.tabs, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("selectionStatus")
        self.status_label.setProperty("status", "idle")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self._refresh_from_state()

    def _refresh_from_state(self) -> None:
        """Reconstruye las tabs a partir de las features seleccionadas."""
        self._refreshing = True
        if "plot_selected_features" in self.state:
            selected_features = [str(feature) for feature in self.state.get("plot_selected_features", [])]
        else:
            selected_features = []
            config_data = self.state.get("plot_features_config")
            if isinstance(config_data, dict) and isinstance(config_data.get("selected_features"), list):
                selected_features = [str(feature) for feature in config_data["selected_features"]]

        self.feature_tabs.clear()
        self.tabs.clear()
        stored_configs = self.state.setdefault("plot_feature_configs", {})
        if not isinstance(stored_configs, dict):
            stored_configs = {}
            self.state["plot_feature_configs"] = stored_configs

        for feature_id in list(stored_configs):
            if feature_id not in selected_features:
                stored_configs.pop(feature_id, None)

        for feature_id in selected_features:
            available_plots = self._available_plots_for_feature(feature_id)
            page = self._build_feature_tab(feature_id, available_plots)
            self.tabs.addTab(page, self._feature_title(feature_id))

        self._refreshing = False
        for feature_id in selected_features:
            self._sync_feature_config(feature_id, emit_changed=False)

        if not selected_features:
            self.status_label.setText("Select at least one feature before configuring plots.")
            self.status_label.setProperty("status", "error")
        else:
            self.status_label.setText(f"{len(selected_features)} plot tab(s) ready.")
            self.status_label.setProperty("status", "ready")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _build_feature_tab(self, feature_id: str, available_plots: list[dict[str, Any]]) -> QWidget:
        """Construye una tab completa: controles a la izquierda y canvas a la derecha."""
        page = QWidget()
        page.setProperty("role", "feature-tab-page")
        root = QVBoxLayout(page)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        control_scroll = QScrollArea()
        control_scroll.setWidgetResizable(True)
        control_scroll.setFrameShape(QFrame.Shape.NoFrame)
        control_panel = QFrame()
        control_panel.setProperty("role", "surface-panel")
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(20, 18, 20, 18)
        control_layout.setSpacing(12)
        control_scroll.setWidget(control_panel)

        plot_panel = QFrame()
        plot_panel.setProperty("role", "plot-type-panel")
        plot_layout = QVBoxLayout(plot_panel)
        plot_layout.setContentsMargins(16, 14, 16, 14)
        plot_layout.setSpacing(8)
        plot_label = QLabel("Plot type")
        plot_label.setObjectName("plotTypeTitle")
        plot_select_label = QLabel("Select")
        plot_select_label.setObjectName("plotTypeSelectLabel")
        plot_combo = QComboBox()
        plot_combo.setProperty("role", "plot-type-combo")
        for plot_info in available_plots:
            plot_combo.addItem(str(plot_info.get("title", plot_info.get("id", "Plot"))), str(plot_info.get("id", "")))
        if not available_plots:
            plot_combo.addItem("No compatible plot", "")
            plot_combo.setEnabled(False)
        plot_layout.addWidget(plot_label)
        plot_layout.addWidget(plot_select_label)
        plot_layout.addWidget(plot_combo)
        control_layout.addWidget(plot_panel)

        options_tabs = QTabWidget()
        options_tabs.setProperty("role", "plot-control-tabs")
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_layout.setContentsMargins(14, 14, 14, 14)
        general_layout.setSpacing(12)
        visualization_tab = QWidget()
        visualization_layout = QVBoxLayout(visualization_tab)
        visualization_layout.setContentsMargins(14, 14, 14, 14)
        visualization_layout.setSpacing(12)

        channel_header = QHBoxLayout()
        channel_title = QLabel("Channels")
        channel_title.setObjectName("panelTitle")
        average_all_button = QPushButton("Average all")
        average_all_button.setProperty("variant", "secondary")
        clear_channels_button = QPushButton("Clear")
        clear_channels_button.setProperty("variant", "ghost")
        channel_header.addWidget(channel_title)
        channel_header.addStretch()
        channel_header.addWidget(average_all_button)
        channel_header.addWidget(clear_channels_button)
        general_layout.addLayout(channel_header)

        channel_note = QLabel("Select one or more channels. Multiple selected channels will be averaged.")
        channel_note.setObjectName("assignmentInstruction")
        channel_note.setWordWrap(True)
        general_layout.addWidget(channel_note)

        channel_table = QTableWidget()
        channel_table.setProperty("role", "assignment-table")
        channel_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        channel_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        channel_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        channel_table.verticalHeader().hide()
        channel_table.horizontalHeader().hide()
        channel_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        channels = self._channel_names()
        columns = 4 if len(channels) > 12 else max(1, min(3, len(channels)))
        rows = max(1, (len(channels) + columns - 1) // columns)
        channel_table.setColumnCount(columns)
        channel_table.setRowCount(rows)
        for index, channel_name in enumerate(channels):
            item = QTableWidgetItem(str(channel_name))
            item.setData(Qt.ItemDataRole.UserRole, index)
            channel_table.setItem(index // columns, index % columns, item)
        for column in range(columns):
            channel_table.horizontalHeader().setSectionResizeMode(column, channel_table.horizontalHeader().ResizeMode.Stretch)
        self._fit_table_height_to_contents(channel_table)
        general_layout.addWidget(channel_table)

        band_label = QLabel("Band")
        band_label.setObjectName("panelTitle")
        band_combo = QComboBox()
        bands = self._bands_from_config()
        for band in bands:
            band_combo.addItem(str(band["title"]), str(band["id"]))
        general_layout.addWidget(band_label)
        general_layout.addWidget(band_combo)
        general_layout.addStretch()

        visualization_title = QLabel("Visualization options")
        visualization_title.setObjectName("panelTitle")
        dynamic_widget = QWidget()
        dynamic_layout = QGridLayout(dynamic_widget)
        dynamic_layout.setContentsMargins(0, 0, 0, 0)
        dynamic_layout.setHorizontalSpacing(10)
        dynamic_layout.setVerticalSpacing(8)
        visualization_layout.addWidget(visualization_title)
        visualization_layout.addWidget(dynamic_widget)
        visualization_layout.addStretch()

        options_tabs.addTab(general_tab, "General options")
        options_tabs.addTab(visualization_tab, "Visualization")
        control_layout.addWidget(options_tabs, 1)
        control_layout.addStretch()

        figure_panel = QFrame()
        figure_panel.setProperty("role", "plot-preview-panel")
        figure_layout = QVBoxLayout(figure_panel)
        figure_layout.setContentsMargins(12, 12, 12, 12)
        figure_header = QHBoxLayout()
        figure_header.setContentsMargins(0, 0, 0, 0)
        figure_title = QLabel("Figure")
        figure_title.setObjectName("panelTitle")
        export_button = QPushButton("Export")
        export_button.setProperty("variant", "primary")
        export_button.setProperty("role", "plot-export-button")
        export_status = QLabel("")
        export_status.setObjectName("selectionStatus")
        export_status.setProperty("status", "idle")
        export_status.setWordWrap(True)
        figure_header.addWidget(figure_title)
        figure_header.addStretch()
        figure_header.addWidget(export_button)
        figure_layout.addLayout(figure_header)
        figure = Figure(figsize=(8, 5), dpi=100)
        canvas = FigureCanvas(figure)
        canvas.setMinimumHeight(420)
        figure_layout.addWidget(canvas, 1)
        figure_layout.addWidget(export_status)

        splitter.addWidget(control_scroll)
        splitter.addWidget(figure_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([360, 720])

        self.feature_tabs[feature_id] = {
            "plot_combo": plot_combo,
            "available_plots": available_plots,
            "channel_table": channel_table,
            "band_combo": band_combo,
            "dynamic_layout": dynamic_layout,
            "dynamic_widget": dynamic_widget,
            "dynamic_controls": {},
            "figure": figure,
            "canvas": canvas,
            "export_status": export_status,
            "last_export": {"width": 8.0, "height": 5.0, "dpi": 300, "path": ""},
        }

        stored = self.state.get("plot_feature_configs", {}).get(feature_id, {})
        if isinstance(stored, dict):
            plot_type = str(stored.get("plot_type") or "")
            if plot_type:
                index = plot_combo.findData(plot_type)
                if index >= 0:
                    plot_combo.setCurrentIndex(index)

            band_id = str(stored.get("selected_band") or "")
            if band_id:
                index = band_combo.findData(band_id)
                if index >= 0:
                    band_combo.setCurrentIndex(index)

            selected_channels = stored.get("selected_channels")
            if isinstance(selected_channels, list):
                self._select_channels(channel_table, [int(channel) for channel in selected_channels if str(channel).isdigit()])
            else:
                self._select_channels(channel_table, list(range(len(channels))))

        else:
            self._select_channels(channel_table, list(range(len(channels))))

        self._rebuild_dynamic_controls(feature_id)
        plot_combo.currentIndexChanged.connect(lambda _index, feature=feature_id: self._rebuild_dynamic_controls(feature))
        band_combo.currentIndexChanged.connect(lambda _index, feature=feature_id: self._sync_feature_config(feature))
        channel_table.itemSelectionChanged.connect(lambda feature=feature_id: self._sync_feature_config(feature))
        average_all_button.clicked.connect(lambda _checked=False, table=channel_table, feature=feature_id:
            (self._select_channels(table, list(range(len(channels)))), self._sync_feature_config(feature)))
        clear_channels_button.clicked.connect(lambda _checked=False, table=channel_table, feature=feature_id:
            (table.clearSelection(), self._sync_feature_config(feature)))
        export_button.clicked.connect(lambda _checked=False, feature=feature_id: self._export_feature_figure(feature))

        return page

    def _rebuild_dynamic_controls(self, feature_id: str) -> None:
        """Crea los widgets de Visualization options según el plot seleccionado."""
        tab = self.feature_tabs[feature_id]
        layout = tab["dynamic_layout"]
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tab["dynamic_controls"] = {}
        plot_info = self._plot_info_for_tab(feature_id)
        params = []
        if plot_info:
            params = list(plot_info.get("default_params", {}).get("visualization", []))

        current_plot_id = str(tab["plot_combo"].currentData() or "")
        stored_config = self.state.get("plot_feature_configs", {}).get(feature_id, {})
        stored_params = stored_config.get("visualization", {})
        if stored_config.get("plot_type") != current_plot_id:
            stored_params = {}
        if not isinstance(stored_params, dict):
            stored_params = {}

        for row, param in enumerate(params):
            param_id = str(param.get("id", ""))
            param_type = str(param.get("type", "text"))
            label = QLabel(str(param.get("title", param_id)))
            layout.addWidget(label, row, 0)

            default_value = self._resolved_default(feature_id, param)
            value = stored_params.get(param_id, default_value)
            if param_type == "checkbox":
                control = QCheckBox()
                control.setChecked(bool(value))
                control.toggled.connect(lambda _checked, feature=feature_id: self._sync_feature_config(feature))
                layout.addWidget(control, row, 1)
            elif param_type == "int":
                control = QSpinBox()
                control.setRange(int(param.get("min", 0)), int(param.get("max", 9999)))
                control.setValue(int(value))
                control.valueChanged.connect(lambda _value, feature=feature_id: self._sync_feature_config(feature))
                layout.addWidget(control, row, 1)
            elif param_type == "float":
                control = QDoubleSpinBox()
                control.setRange(float(param.get("min", -999999.0)), float(param.get("max", 999999.0)))
                control.setDecimals(3)
                control.setSingleStep(float(param.get("step", 0.1)))
                control.setValue(float(value))
                control.valueChanged.connect(lambda _value, feature=feature_id: self._sync_feature_config(feature))
                layout.addWidget(control, row, 1)
            elif param_type == "combo":
                control = QComboBox()
                for option in param.get("options", []):
                    control.addItem(str(option.get("title", option.get("id", ""))), str(option.get("id", "")))
                index = control.findData(str(value))
                if index >= 0:
                    control.setCurrentIndex(index)
                control.currentIndexChanged.connect(lambda _index, feature=feature_id: self._sync_feature_config(feature))
                layout.addWidget(control, row, 1)
            elif param_type == "feature_band_combo":
                control = QComboBox()
                current_feature = feature_id
                current_band = str(tab["band_combo"].currentData() or "")
                for option in self._feature_band_options():
                    control.addItem(option["title"], option["value"])
                if value is None and control.count() > 0:
                    for index in range(control.count()):
                        if control.itemData(index) != f"{current_feature}|{current_band}":
                            control.setCurrentIndex(index)
                            break
                elif value is not None:
                    index = control.findData(str(value))
                    if index >= 0:
                        control.setCurrentIndex(index)
                control.currentIndexChanged.connect(lambda _index, feature=feature_id: self._sync_feature_config(feature))
                layout.addWidget(control, row, 1)
            elif param_type == "range":
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                min_input = QLineEdit()
                max_input = QLineEdit()
                min_input.setPlaceholderText("Auto")
                max_input.setPlaceholderText("Auto")
                if isinstance(value, list) and len(value) == 2:
                    min_input.setText("" if value[0] is None else str(value[0]))
                    max_input.setText("" if value[1] is None else str(value[1]))
                min_input.textChanged.connect(lambda _text, feature=feature_id: self._sync_feature_config(feature))
                max_input.textChanged.connect(lambda _text, feature=feature_id: self._sync_feature_config(feature))
                row_layout.addWidget(min_input)
                row_layout.addWidget(max_input)
                control = (min_input, max_input)
                layout.addWidget(row_widget, row, 1)
            else:
                control = QLineEdit()
                control.setText(str(value))
                control.textChanged.connect(lambda _text, feature=feature_id: self._sync_feature_config(feature))
                layout.addWidget(control, row, 1)

            tab["dynamic_controls"][param_id] = {"control": control, "type": param_type}

        layout.setColumnStretch(1, 1)
        self._sync_feature_config(feature_id)

    def _sync_feature_config(self, feature_id: str, emit_changed: bool = True) -> None:
        """Lee los controles de una tab, guarda el state y actualiza el canvas."""
        if self._refreshing or feature_id not in self.feature_tabs:
            return

        tab = self.feature_tabs[feature_id]
        plot_id = str(tab["plot_combo"].currentData() or "")
        selected_channels = []
        for item in tab["channel_table"].selectedItems():
            channel_index = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(channel_index, int):
                selected_channels.append(channel_index)

        visualization = {}
        for param_id, data in tab["dynamic_controls"].items():
            control = data["control"]
            control_type = data["type"]
            if control_type == "checkbox":
                visualization[param_id] = control.isChecked()
            elif control_type in ("int", "float"):
                visualization[param_id] = control.value()
            elif control_type in ("combo", "feature_band_combo"):
                visualization[param_id] = control.currentData()
            elif control_type == "range":
                values = []
                for input_widget in control:
                    text = input_widget.text().strip()
                    if not text:
                        values.append(None)
                        continue
                    try:
                        values.append(float(text))
                    except ValueError:
                        values.append(None)
                visualization[param_id] = values
            else:
                visualization[param_id] = control.text()

        self.state.setdefault("plot_feature_configs", {})[feature_id] = {
            "plot_type": plot_id,
            "selected_channels": sorted(set(selected_channels)),
            "selected_band": tab["band_combo"].currentData(),
            "visualization": visualization,
        }

        figure = tab["figure"]
        figure.clear()
        ax = figure.add_subplot(111)
        title = str(visualization.get("title") or self._feature_title(feature_id))
        x_label = str(visualization.get("x_label") or "")
        y_label = str(visualization.get("y_label") or "")
        ax.set_title(title, fontsize=int(visualization.get("title_size", 14)),
            fontweight=str(visualization.get("title_weight", "normal")))
        ax.set_xlabel(x_label, fontsize=int(visualization.get("font_size", 10)),
            fontweight=str(visualization.get("font_weight", "normal")))
        ax.set_ylabel(y_label, fontsize=int(visualization.get("font_size", 10)),
            fontweight=str(visualization.get("font_weight", "normal")))
        ax.text(0.5, 0.5, "Plot preview", transform=ax.transAxes, ha="center", va="center",
            color="#756F77", fontsize=12)
        ax.grid(True, linestyle="--", alpha=0.3)
        figure.tight_layout()
        tab["canvas"].draw_idle()

        if emit_changed:
            self.changed.emit()

    def _export_feature_figure(self, feature_id: str) -> None:
        tab = self.feature_tabs[feature_id]
        last_export = tab["last_export"]
        dialog = QDialog(self)
        dialog.setWindowTitle("Export plot")
        layout = QGridLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)

        width_spin = QDoubleSpinBox()
        width_spin.setRange(1.0, 40.0)
        width_spin.setDecimals(1)
        width_spin.setSingleStep(0.5)
        width_spin.setValue(float(last_export.get("width", 8.0)))
        height_spin = QDoubleSpinBox()
        height_spin.setRange(1.0, 40.0)
        height_spin.setDecimals(1)
        height_spin.setSingleStep(0.5)
        height_spin.setValue(float(last_export.get("height", 5.0)))
        dpi_spin = QSpinBox()
        dpi_spin.setRange(72, 1200)
        dpi_spin.setValue(int(last_export.get("dpi", 300)))
        path_input = QLineEdit()
        path_input.setText(str(last_export.get("path") or ""))
        path_input.setPlaceholderText("Select export path")
        browse_button = QPushButton("Browse")
        browse_button.setProperty("variant", "secondary")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        def browse_path() -> None:
            current_path = path_input.text().strip() or f"{self._feature_title(feature_id).replace(' ', '_').lower()}.png"
            selected_path, _ = QFileDialog.getSaveFileName(dialog, "Export plot", current_path, "PNG image (*.png)")
            if selected_path:
                path_input.setText(selected_path)

        browse_button.clicked.connect(browse_path)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addWidget(QLabel("Width"), 0, 0)
        layout.addWidget(width_spin, 0, 1)
        layout.addWidget(QLabel("Height"), 1, 0)
        layout.addWidget(height_spin, 1, 1)
        layout.addWidget(QLabel("DPI"), 2, 0)
        layout.addWidget(dpi_spin, 2, 1)
        layout.addWidget(QLabel("Path"), 3, 0)
        layout.addWidget(path_input, 3, 1)
        layout.addWidget(browse_button, 3, 2)
        layout.addWidget(buttons, 4, 0, 1, 3)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        path_text = path_input.text().strip()
        if not path_text:
            tab["export_status"].setText("Select an export path.")
            tab["export_status"].setProperty("status", "error")
            tab["export_status"].style().unpolish(tab["export_status"])
            tab["export_status"].style().polish(tab["export_status"])
            return

        try:
            figure = tab["figure"]
            figure.set_size_inches(width_spin.value(), height_spin.value())
            Path(path_text).parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(path_text, dpi=dpi_spin.value())
            tab["last_export"] = {"width": width_spin.value(), "height": height_spin.value(),
                "dpi": dpi_spin.value(), "path": path_text}
            tab["export_status"].setText(f"Saved to {path_text}")
            tab["export_status"].setProperty("status", "ready")
        except Exception as error:
            tab["export_status"].setText(str(error))
            tab["export_status"].setProperty("status", "error")

        tab["export_status"].style().unpolish(tab["export_status"])
        tab["export_status"].style().polish(tab["export_status"])

    def _available_plots_for_feature(self, feature_id: str) -> list[dict[str, Any]]:
        config_data = self.state.get("plot_features_config")
        experiment_id = str(config_data.get("experiment_id", "eeg")) if isinstance(config_data, dict) else "eeg"
        available = []
        for plot_info in self.plot_types:
            experiments = {str(item) for item in plot_info.get("compatible_experiments", [])}
            features = {str(item) for item in plot_info.get("allowed_features", [])}
            if experiment_id in experiments and feature_id in features:
                available.append(plot_info)
        return available

    def _plot_info_for_tab(self, feature_id: str) -> dict[str, Any] | None:
        tab = self.feature_tabs.get(feature_id)
        if tab is None:
            return None

        plot_id = str(tab["plot_combo"].currentData() or "")
        for plot_info in tab["available_plots"]:
            if str(plot_info.get("id")) == plot_id:
                return plot_info
        return None

    def _resolved_default(self, feature_id: str, param: dict[str, Any]):
        value = deepcopy(param.get("default"))
        if not isinstance(value, str):
            return value

        tab = self.feature_tabs.get(feature_id, {})
        band_title = tab["band_combo"].currentText() if "band_combo" in tab else "Broadband"
        x_parameter = ""
        x_control_data = tab.get("dynamic_controls", {}).get("x_feature")
        if x_control_data is not None and hasattr(x_control_data["control"], "currentText"):
            x_parameter = x_control_data["control"].currentText()
        else:
            for option in self._feature_band_options():
                x_parameter = option["title"]
                break

        return value.replace("{feature_title}", self._feature_title(feature_id)).replace("{band_title}", band_title
            ).replace("{x_parameter}", x_parameter)

    def _channel_names(self) -> list[str]:
        channels = self.state.get("channel_names")
        if isinstance(channels, list) and channels:
            return [str(channel) for channel in channels]

        config_data = self.state.get("plot_features_config")
        metadata = config_data.get("metadata") if isinstance(config_data, dict) else {}
        channel_set = metadata.get("channel_set") if isinstance(metadata, dict) else []
        return [str(channel) for channel in channel_set] if isinstance(channel_set, list) else []

    def _bands_from_config(self) -> list[dict[str, str]]:
        config_data = self.state.get("plot_features_config")
        preprocessing = config_data.get("preprocessing") if isinstance(config_data, dict) else {}
        bands = preprocessing.get("selected_frequency_bands") if isinstance(preprocessing, dict) else []
        if not isinstance(bands, list) or not bands:
            feature_params = config_data.get("feature_params") if isinstance(config_data, dict) else {}
            relative_power = feature_params.get("relative_band_power") if isinstance(feature_params, dict) else {}
            bands = relative_power.get("selected_frequency_bands") if isinstance(relative_power, dict) else []

        normalized = []
        for band in bands if isinstance(bands, list) else []:
            if not isinstance(band, dict):
                continue
            band_id = str(band.get("id") or band.get("title") or "").strip()
            if not band_id:
                continue
            title = str(band.get("title") or band_id.replace("_", " ").title())
            normalized.append({"id": band_id, "title": title})

        if not normalized:
            normalized.append({"id": "broadband", "title": "Broadband"})
        return sorted(normalized, key=lambda band: 0 if band["id"].lower() == "broadband" else 1)

    def _feature_band_options(self) -> list[dict[str, str]]:
        features = [str(feature) for feature in self.state.get("plot_selected_features", [])]
        options = []
        for feature_id in features:
            if feature_id == "psd":
                continue
            for band in self._bands_from_config():
                title = f"{self._feature_title(feature_id)} - {band['title']}"
                options.append({"value": f"{feature_id}|{band['id']}", "title": title})
        return options

    def _select_channels(self, table: QTableWidget, channel_indices: list[int]) -> None:
        table.clearSelection()
        wanted = set(channel_indices)
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                item = table.item(row, column)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) in wanted:
                    item.setSelected(True)

    @staticmethod
    def _fit_table_height_to_contents(table: QTableWidget) -> None:
        """Ajusta la altura minima para que se vea toda la tabla sin recortar filas."""
        table.resizeRowsToContents()
        frame_height = table.frameWidth() * 2
        header_height = table.horizontalHeader().height() if table.horizontalHeader().isVisible() else 0
        rows_height = sum(table.rowHeight(row) for row in range(table.rowCount()) if not table.isRowHidden(row))
        table.setMinimumHeight(frame_height + header_height + rows_height)

    def _feature_title(self, feature_id: str) -> str:
        titles = {
            "psd": "PSD",
            "erp": "ERP",
            "ctm": "CTM",
            "aec": "AEC",
            "iac": "IAC",
            "plv": "PLV",
            "pli": "PLI",
            "wpli": "wPLI",
        }
        return titles.get(feature_id, feature_id.replace("_", " ").title())

    def on_step_activated(self) -> None:
        self._refresh_from_state()

    def can_continue(self) -> bool:
        if self.tabs.count() == 0:
            return False
        for feature_id, tab in self.feature_tabs.items():
            config = self.state.get("plot_feature_configs", {}).get(feature_id, {})
            if not config.get("plot_type") or not tab["channel_table"].selectedItems():
                return False
        return True


__all__ = ["PlotFeaturesVisualizationWidget"]
