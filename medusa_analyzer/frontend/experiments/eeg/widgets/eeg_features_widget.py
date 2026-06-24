from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QLabel, QLineEdit, QSpinBox, QVBoxLayout,
    QWidget)

from medusa_analyzer.frontend.experiments.eeg.widgets.frequency_bands_table import EEGFrequencyBandsTable
from medusa_analyzer.frontend.widgets import FeatureItem, FeaturesWidget


class EEGFeaturesWidget(FeaturesWidget):
    _legacy_absolute_band_power_feature_id = "band_power"
    _absolute_band_power_feature_id = "absolute_band_power"
    _psd_feature_id = "psd"
    _relative_band_power_feature_id = "relative_band_power"
    _multiscale_lz_feature_id = "multiscale_lempel_ziv_complexity"
    _multiscale_lz_scales_param_id = "scales"
    _multiscale_lz_scales_pattern = re.compile(r"^\[(?:[1-9]\d*)(?:, [1-9]\d*)*\]$")

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        _ = experiment_info
        self._migrate_absolute_band_power_state(state)
        self.defaults = defaults
        self._feature_definitions = self._resolve_feature_definitions(defaults.get("features", {}))
        self._spectral_feature_ids = self._resolve_spectral_feature_ids(defaults.get("features", {}))
        self._eeg_feature_state = state.setdefault("eeg_feature_state", {})
        if "relative_band_power_frequency_bands" not in self._eeg_feature_state:
            self._eeg_feature_state["relative_band_power_frequency_bands"] = self._copy_default_frequency_bands(
                defaults)
        self._relative_band_power_rows = self._eeg_feature_state["relative_band_power_frequency_bands"]
        self._absolute_band_power_container: QWidget | None = None
        self._absolute_band_power_message: QLabel | None = None
        self._relative_band_power_container: QWidget | None = None
        self._relative_band_power_message: QLabel | None = None
        self._relative_band_power_table: EEGFrequencyBandsTable | None = None
        self._validation_errors: list[str] = []
        self.error_label: QLabel | None = None
        super().__init__(
            config=defaults.get("features", {}),
            state=state,
            title="Features",
            description="Pick the feature blocks that should appear in the EEG processing configuration.")
        self.error_label = QLabel()
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        self.widget().layout().insertWidget(2, self.error_label)
        self._sync()

    @classmethod
    def _migrate_absolute_band_power_state(cls, state: dict[str, Any]) -> None:
        selected_features = state.get("selected_features")
        if isinstance(selected_features, list):
            migrated_selected_features: list[str] = []
            for feature_id in selected_features:
                if feature_id == cls._legacy_absolute_band_power_feature_id:
                    feature_id = cls._absolute_band_power_feature_id
                if feature_id not in migrated_selected_features:
                    migrated_selected_features.append(feature_id)
            state["selected_features"] = migrated_selected_features

        feature_params = state.get("feature_params")
        if isinstance(feature_params, dict):
            if (cls._legacy_absolute_band_power_feature_id in feature_params
                and cls._absolute_band_power_feature_id not in feature_params):
                feature_params[cls._absolute_band_power_feature_id] = feature_params.pop(
                    cls._legacy_absolute_band_power_feature_id)

    @staticmethod
    def _copy_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        return [deepcopy(row) for row in (rows or [])]

    @classmethod
    def _collect_leaf_feature_ids(cls, group: dict[str, Any]) -> list[str]:
        feature_ids: list[str] = []
        for feature in group.get("features", []):
            if feature.get("features") or feature.get("subcategories"):
                feature_ids.extend(cls._collect_leaf_feature_ids(feature))
                continue
            feature_id = feature.get("id")
            if feature_id:
                feature_ids.append(str(feature_id))

        for subcategory in group.get("subcategories", []):
            feature_ids.extend(cls._collect_leaf_feature_ids(subcategory))

        return feature_ids

    @classmethod
    def _collect_leaf_feature_definitions(cls, group: dict[str, Any], feature_definitions: dict[str, dict[str, Any]]) -> None:
        for feature in group.get("features", []):
            if feature.get("features") or feature.get("subcategories"):
                cls._collect_leaf_feature_definitions(feature, feature_definitions)
                continue
            feature_id = feature.get("id")
            if feature_id:
                feature_definitions[str(feature_id)] = feature

        for subcategory in group.get("subcategories", []):
            cls._collect_leaf_feature_definitions(subcategory, feature_definitions)

    @classmethod
    def _resolve_feature_definitions(cls, features_config: dict[str, Any]) -> dict[str, dict[str, Any]]:
        feature_definitions: dict[str, dict[str, Any]] = {}
        for category in features_config.get("categories", []):
            cls._collect_leaf_feature_definitions(category, feature_definitions)
        return feature_definitions

    @classmethod
    def _resolve_spectral_feature_ids(cls, features_config: dict[str, Any]) -> set[str]:
        for category in features_config.get("categories", []):
            if str(category.get("id", "")) == "spectral":
                return set(cls._collect_leaf_feature_ids(category))
        return set()

    @classmethod
    def _copy_preprocessing_frequency_bands(cls, state: dict[str, Any], defaults: dict[str, Any]) -> list[dict[str, Any]]:
        preprocessing_state = state.get("preprocessing") or {}
        if preprocessing_state.get("frequency_bands"):
            return cls._copy_rows(preprocessing_state.get("frequency_bands"))
        preprocessing_defaults = defaults.get("preprocessing", {})
        available_bands = preprocessing_defaults.get("bands", {}).get("available", [])
        return cls._copy_rows(available_bands)

    @classmethod
    def _copy_default_frequency_bands(cls, defaults: dict[str, Any]) -> list[dict[str, Any]]:
        preprocessing_defaults = defaults.get("preprocessing", {})
        available_bands = preprocessing_defaults.get("bands", {}).get("available", [])
        return cls._copy_rows(available_bands)

    @staticmethod
    def _build_band_message_container() -> tuple[QWidget, QLabel]:
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 0, 0, 8)
        container_layout.setSpacing(8)

        message = QLabel()
        message.setObjectName("muted")
        message.setWordWrap(True)
        container_layout.addWidget(message)
        return container, message

    def _after_feature_controls_added(self, layout: QVBoxLayout, item: FeatureItem, checkbox: QCheckBox) -> None:
        _ = checkbox

        if item.id == self._absolute_band_power_feature_id:
            container, message = self._build_band_message_container()
            self._absolute_band_power_container = container
            self._absolute_band_power_message = message
            layout.addWidget(container)
            return

        if item.id != self._relative_band_power_feature_id:
            return

        container, message = self._build_band_message_container()
        table = EEGFrequencyBandsTable(self._relative_band_power_rows,
            default_rows=self._copy_default_frequency_bands(self.defaults))
        table.changed.connect(self._sync)
        container.layout().addWidget(table)

        self._relative_band_power_container = container
        self._relative_band_power_message = message
        self._relative_band_power_table = table
        layout.addWidget(container)

    def _apply_psd_dependency(self) -> None:
        psd_checkbox = self.checkboxes.get(self._psd_feature_id)
        if psd_checkbox is None:
            return

        spectral_features_require_psd = any(feature_id != self._psd_feature_id and feature_id in self._spectral_feature_ids
            and checkbox.isChecked() for feature_id, checkbox in self.checkboxes.items())
        if spectral_features_require_psd:
            psd_checkbox.blockSignals(True)
            try:
                psd_checkbox.setChecked(True)
            finally:
                psd_checkbox.blockSignals(False)
            psd_checkbox.setEnabled(False)
            return

        psd_checkbox.setEnabled(True)

    def _preprocessing_selected_frequency_state(self) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        preprocessing_state = self.state.get("preprocessing") or {}
        broadband = deepcopy(preprocessing_state.get("broadband"))
        selected_frequency_bands = self._copy_rows(preprocessing_state.get("selected_frequency_bands"))
        if selected_frequency_bands:
            return selected_frequency_bands, broadband

        enabled_bands = [deepcopy(row) for row in preprocessing_state.get("frequency_bands", [])
            if row.get("enabled", False)]
        if broadband is not None:
            if enabled_bands:
                enabled_bands.append(deepcopy(broadband))
                return enabled_bands, broadband
            return [deepcopy(broadband)], broadband
        return enabled_bands, broadband

    def _refresh_relative_band_power_defaults(self) -> None:
        if self._relative_band_power_table is None:
            return
        preprocessing_bands = self._copy_default_frequency_bands(self.defaults)
        self._relative_band_power_table.default_rows = [
            self._relative_band_power_table._normalized_row_copy(row) for row in preprocessing_bands]

    @staticmethod
    def _format_frequency(value: Any) -> str:
        return f"{float(value):g} Hz"

    @classmethod
    def _describe_band(cls, band: dict[str, Any]) -> str:
        title = str(band.get("title") or band.get("id") or "Band")
        low_cut = cls._format_frequency(band.get("low_cut", 0.0))
        high_cut = cls._format_frequency(band.get("high_cut", 0.0))
        return f"{title} ({low_cut}-{high_cut})"

    @classmethod
    def _band_summary_message(cls, bands: list[dict[str, Any]]) -> str:
        if not bands:
            return ""
        if len(bands) == 1:
            return f"Banda: {cls._describe_band(bands[0])}."
        return f"Bandas: {', '.join(cls._describe_band(band) for band in bands)}."

    def _selected_relative_band_power_bands(self, broadband: dict[str, Any] | None) -> list[dict[str, Any]]:
        selected_bands = [deepcopy(row) for row in self._relative_band_power_rows if row.get("enabled", False)]
        return selected_bands

    def _sync_absolute_band_power(self, selected_features: list[str], feature_params: dict[str, dict[str, Any]]) -> None:
        if self._absolute_band_power_container is None or self._absolute_band_power_message is None:
            return

        absolute_band_power_selected = self._absolute_band_power_feature_id in selected_features
        self._absolute_band_power_container.setVisible(absolute_band_power_selected)
        if not absolute_band_power_selected:
            return

        selected_frequency_bands, broadband = self._preprocessing_selected_frequency_state()
        feature_params[self._absolute_band_power_feature_id] = {
            "bands_source": "preprocessing",
            "frequency_bands": self._copy_rows((self.state.get("preprocessing") or {}).get("frequency_bands")),
            "selected_frequency_bands": self._copy_rows(selected_frequency_bands),
            "broadband": deepcopy(broadband),
        }
        self._absolute_band_power_message.setText(self._band_summary_message(selected_frequency_bands))

    def _sync_relative_band_power(self, selected_features: list[str], feature_params: dict[str, dict[str, Any]]) -> None:
        if (self._relative_band_power_container is None or self._relative_band_power_message is None
            or self._relative_band_power_table is None):
            return

        self._refresh_relative_band_power_defaults()
        selected_frequency_bands, broadband = self._preprocessing_selected_frequency_state()
        preprocessing_named_bands = [band for band in selected_frequency_bands if str(band.get("id", "")) != "broadband"]
        if broadband is not None:
            self._relative_band_power_table.set_frequency_bounds(
                minimum_frequency=float(broadband["low_cut"]),
                maximum_frequency=float(broadband["high_cut"]),
                emit_changed=False)

        relative_band_power_selected = self._relative_band_power_feature_id in selected_features
        self._relative_band_power_container.setVisible(relative_band_power_selected)
        if not relative_band_power_selected:
            return

        if preprocessing_named_bands:
            self._relative_band_power_message.setText(self._band_summary_message(preprocessing_named_bands))
            self._relative_band_power_table.setVisible(False)
            feature_params[self._relative_band_power_feature_id] = {
                "bands_source": "preprocessing",
                "frequency_bands": self._copy_rows((self.state.get("preprocessing") or {}).get("frequency_bands")),
                "selected_frequency_bands": self._copy_rows(preprocessing_named_bands),
                "broadband": deepcopy(broadband),
            }
            return

        selected_relative_bands = self._selected_relative_band_power_bands(broadband)
        self._relative_band_power_message.setText(self._band_summary_message(selected_relative_bands))
        self._relative_band_power_table.setVisible(True)
        feature_params[self._relative_band_power_feature_id] = {
            "bands_source": "custom",
            "frequency_bands": self._copy_rows(self._relative_band_power_rows),
            "selected_frequency_bands": selected_relative_bands,
            "broadband": deepcopy(broadband),
        }

    def _feature_title(self, feature_id: str) -> str:
        feature_definition = self._feature_definitions.get(feature_id, {})
        return str(feature_definition.get("title") or feature_id)

    def _validate_numeric_param(self, feature_id: str, param: dict[str, Any], value: Any, expect_integer: bool) -> list[str]:
        feature_title = self._feature_title(feature_id)
        param_title = str(param.get("title") or param.get("id") or "Parameter")
        if isinstance(value, bool):
            return [f"{feature_title}: {param_title} must be numeric."]
        if expect_integer:
            if not isinstance(value, int):
                return [f"{feature_title}: {param_title} must be an integer."]
            numeric_value = value
        else:
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                return [f"{feature_title}: {param_title} must be a finite number."]
            numeric_value = float(value)

        minimum = param.get("min")
        maximum = param.get("max")
        if minimum is not None and numeric_value < minimum:
            return [f"{feature_title}: {param_title} must be greater than or equal to {minimum}."]
        if maximum is not None and numeric_value > maximum:
            return [f"{feature_title}: {param_title} must be lower than or equal to {maximum}."]
        return []

    def _validate_scales_text(self, value: Any) -> list[str]:
        feature_title = self._feature_title(self._multiscale_lz_feature_id)
        if not isinstance(value, str):
            return [f"{feature_title}: Scales must be written as a text list like [1, 3, 5]."]
        if not self._multiscale_lz_scales_pattern.fullmatch(value):
            return [f"{feature_title}: Scales must follow the format [1, 3, 5]."]
        return []

    def _validate_feature_param(self, feature_id: str, param: dict[str, Any], value: Any) -> list[str]:
        param_type = str(param.get("type", "text"))
        if param_type == "int":
            return self._validate_numeric_param(feature_id, param, value, expect_integer=True)
        if param_type == "float":
            return self._validate_numeric_param(feature_id, param, value, expect_integer=False)
        if param_type == "checkbox":
            if isinstance(value, bool):
                return []
            return [f"{self._feature_title(feature_id)}: {param.get('title', param.get('id', 'Parameter'))} must be boolean."]
        if param_type == "combo":
            allowed_options = {option.get("id") for option in param.get("options", [])}
            if value in allowed_options:
                return []
            return [f"{self._feature_title(feature_id)}: {param.get('title', param.get('id', 'Parameter'))} has an invalid option."]
        if feature_id == self._multiscale_lz_feature_id and str(param.get("id", "")) == self._multiscale_lz_scales_param_id:
            return self._validate_scales_text(value)
        return []

    def _validate_feature_configuration(self, selected_features: list[str], feature_params: dict[str, dict[str, Any]]) -> list[str]:
        errors: list[str] = []

        if self._absolute_band_power_feature_id in selected_features:
            selected_frequency_bands, _ = self._preprocessing_selected_frequency_state()
            if not selected_frequency_bands:
                errors.append("Absolute band power: no valid pre-processing bands are available.")

        if self._relative_band_power_feature_id in selected_features:
            selected_frequency_bands, _ = self._preprocessing_selected_frequency_state()
            preprocessing_named_bands = [band for band in selected_frequency_bands if str(band.get("id", "")) != "broadband"]
            if not preprocessing_named_bands:
                selected_relative_bands = self._selected_relative_band_power_bands(None)
                if not selected_relative_bands:
                    errors.append("Relative band power: select at least one frequency band.")
                elif self._relative_band_power_table is not None and not self._relative_band_power_table.is_valid():
                    errors.append("Relative band power: fix the custom frequency bands table.")

        for feature_id in selected_features:
            feature_definition = self._feature_definitions.get(feature_id, {})
            for param in feature_definition.get("params", []):
                param_id = str(param.get("id", ""))
                value = feature_params.get(feature_id, {}).get(param_id)
                errors.extend(self._validate_feature_param(feature_id, param, value))

        return errors

    def _set_validation_errors(self, errors: list[str]) -> None:
        self._validation_errors = list(errors)
        if self.error_label is None:
            return
        if self._validation_errors:
            self.error_label.setText("\n".join(f"- {error}" for error in self._validation_errors))
            self.error_label.show()
            return
        self.error_label.clear()
        self.error_label.hide()

    def _sync(self) -> None:
        self._apply_psd_dependency()
        selected_features = self._selected_feature_ids()
        self.state["selected_features"] = selected_features
        self._sync_param_containers(selected_features)
        feature_params = self._rebuild_feature_params(selected_features)
        self._sync_absolute_band_power(selected_features, feature_params)
        self._sync_relative_band_power(selected_features, feature_params)
        self.state["feature_params"] = feature_params
        self._set_validation_errors(self._validate_feature_configuration(selected_features, feature_params))
        self.changed.emit()

    def on_step_activated(self) -> None:
        self._sync()

    def can_continue(self) -> bool:
        return not self._validation_errors
