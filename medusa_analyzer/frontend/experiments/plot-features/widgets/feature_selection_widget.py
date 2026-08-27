from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QTableWidgetSelectionRange, QVBoxLayout, QWidget)
from medusa_analyzer.frontend.validation import Validation


class PlotFeaturesFeatureSelectionWidget(QScrollArea):
    changed = Signal()

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        del experiment_info, defaults
        super().__init__()

        self.state = state
        self.validation = Validation()
        self.validation_errors: list[str] = []
        self.features: list[str] = []

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.content = QWidget()
        self.setWidget(self.content)
        root = QVBoxLayout(self.content)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(18)

        title = QLabel("Feature selection")
        title.setObjectName("pageTitle")
        description = QLabel("Select the computed features that will be plotted later.")
        description.setObjectName("muted")
        description.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(description)

        root.addWidget(self._build_selection_panel())
        root.addStretch()

        self._refresh_from_state()

    def _build_selection_panel(self) -> QFrame:
        """Crea el panel con buscador, acciones rapidas y la tabla de features."""
        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        search_label = QLabel("Search")
        search_label.setObjectName("panelTitle")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find features...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_features)
        select_all_button = QPushButton("Select all")
        select_all_button.setProperty("variant", "secondary")
        select_all_button.clicked.connect(self.table_select_all)
        clear_selection_button = QPushButton("Clear")
        clear_selection_button.setProperty("variant", "ghost")
        clear_selection_button.clicked.connect(self.table_clear_selection)
        actions.addWidget(search_label)
        actions.addWidget(self.search_input, 1)
        actions.addWidget(select_all_button)
        actions.addWidget(clear_selection_button)
        layout.addLayout(actions)

        self.table = QTableWidget()
        self.table.setProperty("role", "assignment-table")
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Feature"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._sync)
        layout.addWidget(self.table)

        self.status_label = QLabel("")
        self.status_label.setObjectName("selectionStatus")
        self.status_label.setProperty("status", "idle")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        return panel

    def _refresh_from_state(self) -> None:
        """Lee las features calculadas del config cargado y reconstruye la seleccion."""
        self.features = self._features_from_loaded_config()
        self._populate_table()
        self._restore_selection()
        self._sync(emit_changed=False)

    def _features_from_loaded_config(self) -> list[str]:
        """Devuelve los ids de features calculadas guardados en config.json."""
        config_data = self.state.get("plot_features_config")
        if not isinstance(config_data, dict):
            return []

        selected_features = config_data.get("selected_features")
        if not isinstance(selected_features, list):
            return []

        features: list[str] = []
        seen: set[str] = set()
        for feature in selected_features:
            feature_id = str(feature).strip()
            if not feature_id or feature_id in seen:
                continue
            features.append(feature_id)
            seen.add(feature_id)
        return features

    def _populate_table(self) -> None:
        """Rellena la tabla con una fila por feature calculada."""
        self.table.blockSignals(True)
        try:
            self.table.clearSelection()
            self.table.setRowCount(len(self.features))
            for row, feature_id in enumerate(self.features):
                item = QTableWidgetItem(feature_id)
                item.setData(Qt.ItemDataRole.UserRole, feature_id)
                self.table.setItem(row, 0, item)
        finally:
            self.table.blockSignals(False)
        self._filter_features(self.search_input.text())

    def _restore_selection(self) -> None:
        """Restaura una seleccion previa o marca todo si aun no habia seleccion guardada."""
        stored_selection = self._stored_selection()
        selection = set(self.features) if stored_selection is None else stored_selection

        self.table.blockSignals(True)
        try:
            for row in range(self.table.rowCount()):
                feature_id = self._feature_id_for_row(row)
                if feature_id in selection:
                    row_range = QTableWidgetSelectionRange(row, 0, row, self.table.columnCount() - 1)
                    self.table.setRangeSelected(row_range, True)
        finally:
            self.table.blockSignals(False)

    def table_select_all(self) -> None:
        """Selecciona todas las features calculadas visibles en la tabla."""
        self.table.selectAll()
        self._sync()

    def table_clear_selection(self) -> None:
        """Limpia la seleccion actual de features para plotear."""
        self.table.clearSelection()
        self._sync()

    def _sync(self, *_: Any, emit_changed: bool = True) -> None:
        """Guarda la seleccion actual en el estado compartido del workflow."""
        selected_features = self._selected_features()
        self.state["plot_selected_features"] = selected_features
        self.validation_errors = self._validate_selection(selected_features)
        self._update_status_label(selected_features)
        if emit_changed:
            self.changed.emit()

    def _validate_selection(self, selected_features: list[str]) -> list[str]:
        """Valida que haya features calculadas y al menos una seleccionada."""
        errors: list[str] = []
        errors.extend(self.validation.validate_many(self.features, [("minimum_length", {
            "minimum": 1,
            "item_name": "feature",
            "action": "contain",
        })], label="Features"))
        errors.extend(self.validation.validate_many(selected_features, [("minimum_length", {
            "minimum": 1,
            "item_name": "feature",
            "action": "select",
        })], label="Features"))
        return errors

    def _update_status_label(self, selected_features: list[str]) -> None:
        """Actualiza el mensaje inferior con el estado de la seleccion."""
        if self.validation_errors:
            self.status_label.setText(self.validation_errors[0])
            self.status_label.setProperty("status", "error")
        else:
            self.status_label.setText(f"{len(selected_features)} feature(s) selected.")
            self.status_label.setProperty("status", "ready")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _filter_features(self, text: str) -> None:
        """Oculta las filas que no coinciden con el texto de busqueda."""
        needle = text.lower().strip()
        for row in range(self.table.rowCount()):
            feature_id = self._feature_id_for_row(row) or ""
            self.table.setRowHidden(row, bool(needle) and needle not in feature_id.lower())

    def _selected_features(self) -> list[str]:
        """Devuelve los ids seleccionados respetando el orden original del config."""
        selected_features: list[str] = []
        selection_model = self.table.selectionModel()
        for row in range(self.table.rowCount()):
            if selection_model.isRowSelected(row):
                feature_id = self._feature_id_for_row(row)
                if feature_id:
                    selected_features.append(feature_id)
        return selected_features

    def _feature_id_for_row(self, row: int) -> str | None:
        """Obtiene el id real de la feature asociada a una fila."""
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else item.text()

    def _stored_selection(self) -> set[str] | None:
        """Recupera la seleccion guardada, filtrando ids que ya no existen en el config."""
        if "plot_selected_features" not in self.state:
            return None
        selected_features = self.state.get("plot_selected_features")
        if not isinstance(selected_features, list):
            return set()
        available = set(self.features)
        return {str(feature) for feature in selected_features if str(feature) in available}

    def on_step_activated(self) -> None:
        self._refresh_from_state()

    def can_continue(self) -> bool:
        selected_features = self._selected_features()
        self.validation_errors = self._validate_selection(selected_features)
        self._update_status_label(selected_features)
        return not self.validation_errors


__all__ = ["PlotFeaturesFeatureSelectionWidget"]
