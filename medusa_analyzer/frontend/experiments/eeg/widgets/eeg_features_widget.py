from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from medusa_analyzer.frontend.experiments.eeg.widgets.frequency_bands_table import EEGFrequencyBandsTable
from medusa_analyzer.frontend.validation import Validation
from medusa_analyzer.frontend.widgets import FeatureItem, FeaturesWidget


class EEGFeaturesWidget(FeaturesWidget):
    _absolute_band_power_feature_id = "absolute_band_power"
    _relative_band_power_feature_id = "relative_band_power"
    _psd_feature_id = "psd"
    _multiscale_lz_feature_id = "multiscale_lempel_ziv_complexity"
    _multiscale_lz_scales_param_id = "scales"
    _multiscale_lz_scales_pattern = re.compile(r"^\[(?:[1-9]\d*)(?:, [1-9]\d*)*\]$")

    # Este widget añade la logica EEG específica encima del FeaturesWidget genérico
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        _ = experiment_info
        self.defaults = defaults
        self._validator = Validation()
        self._feature_definitions = self._resolve_feature_definitions(defaults.get("features", {}))
        self._spectral_feature_ids = self._resolve_spectral_feature_ids(defaults.get("features", {}))

        feature_params = state.setdefault("feature_params", {})
        relative_band_power_params = feature_params.setdefault(self._relative_band_power_feature_id, {})
        saved_relative_bands = relative_band_power_params.get("selected_frequency_bands")
        relative_band_power_params["selected_frequency_bands"] = (
            self._copy_rows(saved_relative_bands)
            or self._copy_available_frequency_bands(defaults)
        )

        self._relative_band_power_container: QWidget | None = None
        self._relative_band_power_message: QLabel | None = None
        self._relative_band_power_table: EEGFrequencyBandsTable | None = None
        self._validation_errors: list[str] = []
        self.error_label: QLabel | None = None

        super().__init__(config=defaults.get("features", {}),
            state=state, title="Features",
            description="Pick the feature blocks that should appear in the EEG processing configuration.")

        self.error_label = QLabel()
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        self.widget().layout().insertWidget(2, self.error_label)
        self._sync()

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
    def _copy_available_frequency_bands(cls, defaults: dict[str, Any]) -> list[dict[str, Any]]:
        preprocessing_defaults = defaults.get("preprocessing", {})
        available_bands = preprocessing_defaults.get("bands", {}).get("available", [])
        return cls._copy_rows(available_bands)

    def _effective_broadband(self) -> dict[str, Any] | None:
        return deepcopy(self.state.get("broadband"))

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

        if item.id != self._relative_band_power_feature_id:
            return

        container, message = self._build_band_message_container()
        rows = self.state["feature_params"][self._relative_band_power_feature_id]["selected_frequency_bands"]
        table = EEGFrequencyBandsTable(rows,
            default_rows=self._copy_available_frequency_bands(self.defaults))
        table.changed.connect(self._sync)
        container.layout().addWidget(table)

        self._relative_band_power_container = container
        self._relative_band_power_message = message
        self._relative_band_power_table = table
        layout.addWidget(container)

    def _apply_psd_dependency(self) -> None:
        # Cualquier feature espectral distinta de PSD necesita PSD activada.
        psd_checkbox = self.checkboxes.get(self._psd_feature_id)
        if psd_checkbox is None:
            return

        spectral_features_require_psd = any(
            feature_id != self._psd_feature_id and feature_id in self._spectral_feature_ids and checkbox.isChecked()
            for feature_id, checkbox in self.checkboxes.items()
        )
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
        # Si preprocessing ya ha calculado las bandas seleccionadas, las usamos.
        # Si no, solo tenemos la broadband de metadata y relative_band_power muestra su tabla propia.
        preprocessing_state = self.state.get("preprocessing") or {}
        broadband = self._effective_broadband()
        selected_frequency_bands = self._copy_rows(preprocessing_state.get("selected_frequency_bands"))
        if selected_frequency_bands:
            return selected_frequency_bands, broadband

        if broadband is not None:
            return [deepcopy(broadband)], broadband
        return [], broadband

    def _refresh_relative_band_power_defaults(self) -> None:
        if self._relative_band_power_table is None:
            return
        preprocessing_bands = self._copy_available_frequency_bands(self.defaults)
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

    def _selected_relative_band_power_bands(self) -> list[dict[str, Any]]:
        if self._relative_band_power_table is None:
            return []
        return [deepcopy(row) for row in self._relative_band_power_table.rows if row.get("enabled", False)]

    def _set_relative_band_power_params(
        self,
        feature_params: dict[str, dict[str, Any]],
        selected_frequency_bands: list[dict[str, Any]],
    ) -> None:
        feature_params[self._relative_band_power_feature_id] = {
            "selected_frequency_bands": self._copy_rows(selected_frequency_bands),
        }

    def _set_relative_band_power_table_params(self, feature_params: dict[str, dict[str, Any]]) -> None:
        feature_params[self._relative_band_power_feature_id] = {
            "selected_frequency_bands": self._selected_relative_band_power_bands(),
        }

    def _sync_absolute_band_power(self, selected_features: list[str], feature_params: dict[str, dict[str, Any]]) -> None:
        is_selected = self._absolute_band_power_feature_id in selected_features
        if not is_selected:
            return

        selected_frequency_bands, _ = self._preprocessing_selected_frequency_state()
        if selected_frequency_bands:
            feature_params.pop(self._absolute_band_power_feature_id, None)

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

        is_selected = self._relative_band_power_feature_id in selected_features
        self._relative_band_power_container.setVisible(is_selected)
        if not is_selected:
            return

        if preprocessing_named_bands:
            self._relative_band_power_message.setText(self._band_summary_message(preprocessing_named_bands))
            self._relative_band_power_table.setVisible(False)
            self._set_relative_band_power_params(feature_params, preprocessing_named_bands)
            return

        selected_relative_bands = self._selected_relative_band_power_bands()
        self._relative_band_power_message.setText(self._band_summary_message(selected_relative_bands))
        self._relative_band_power_table.setVisible(True)
        self._set_relative_band_power_table_params(feature_params)

    def _feature_title(self, feature_id: str) -> str:
        feature_definition = self._feature_definitions.get(feature_id, {})
        return str(feature_definition.get("title") or feature_id)

    def _feature_param_label(self, feature_id: str, param: dict[str, Any]) -> str:
        feature_title = self._feature_title(feature_id)
        param_title = str(param.get("title") or param.get("id") or "Parameter")
        return f"{feature_title}: {param_title}"

    def _multiscale_lz_scales_errors(self, value: Any, *, label: str, **_: Any) -> list[str]:
        # Regla personalizada: en este caso no basta con "texto". Queremos una
        # lista tipo Python con enteros positivos y separador coma+espacio.
        if not isinstance(value, str):
            return [f"{label} must be written as a text list like [1, 3, 5]."]
        return self._validator.validate_many(value,
            [("pattern", {"pattern": self._multiscale_lz_scales_pattern,
                "message": f"{label} must follow the format [1, 3, 5]."})],
            label=label)

    def _absolute_band_power_errors(self, _value: Any, *, label: str, **_: Any) -> list[str]:
        # Regla compuesta: si se activa absolute band power, debe existir al
        # menos una banda util procedente del preprocessing o de la broadband.
        selected_frequency_bands, _ = self._preprocessing_selected_frequency_state()
        return self._validator.validate_many(selected_frequency_bands,
            [("minimum_length", {"minimum": 1, "item_name": "pre-processing band", "action": "select"})],
            label=label)

    def _relative_band_power_errors(self, _value: Any, *, label: str, **_: Any) -> list[str]:
        # Regla compuesta: si preprocessing ya aporta bandas nominales, se usan.
        # Si no, la tabla custom debe tener al menos una banda valida.
        selected_frequency_bands, _ = self._preprocessing_selected_frequency_state()
        preprocessing_named_bands = [band for band in selected_frequency_bands if str(band.get("id", "")) != "broadband"]
        if preprocessing_named_bands:
            return []

        selected_relative_bands = self._selected_relative_band_power_bands()
        errors = self._validator.validate_many(selected_relative_bands,
            [("minimum_length", {"minimum": 1, "item_name": "frequency band", "action": "select"})],
            label=label)
        if errors:
            return errors
        if self._relative_band_power_table is not None and not self._relative_band_power_table.is_valid():
            return [f"{label}: {error}" for error in self._relative_band_power_table.validation_errors()]
        return []

    def _feature_param_rules(self, feature_id: str, param: dict[str, Any]
        ) -> list[str | tuple[str, dict[str, Any]]]:
        param_type = str(param.get("type", "text"))
        rules: list[str | tuple[str, dict[str, Any]]] = []

        if param_type == "int":
            rules.append("integer")
        elif param_type == "float":
            rules.append("finite_number")
        elif param_type == "checkbox":
            rules.append("boolean")
        elif param_type == "combo":
            rules.append(("one_of", {"options": [option.get("id") for option in param.get("options", [])]}))

        if param_type in {"int", "float"}:
            minimum = param.get("min")
            maximum = param.get("max")
            if minimum is not None:
                rules.append(("greater_or_equal", {"minimum": minimum}))
            if maximum is not None:
                rules.append(("less_or_equal", {"maximum": maximum}))

        if (feature_id == self._multiscale_lz_feature_id
            and str(param.get("id", "")) == self._multiscale_lz_scales_param_id):
            rules.append(("custom", {"validator": self._multiscale_lz_scales_errors}))

        return rules

    def _validate_feature_param(self, feature_id: str, param: dict[str, Any], value: Any) -> list[str]:
        rules = self._feature_param_rules(feature_id, param)
        if not rules:
            return []
        return self._validator.validate_many(value, rules, label=self._feature_param_label(feature_id, param))

    def _validate_feature_configuration(self, selected_features: list[str], feature_params: dict[str, dict[str, Any]]
        ) -> list[str]:
        errors: list[str] = []

        if self._absolute_band_power_feature_id in selected_features:
            errors.extend(self._validator.validate_errors(feature_params.get(self._absolute_band_power_feature_id),
                "custom", label="Absolute band power", validator=self._absolute_band_power_errors))

        if self._relative_band_power_feature_id in selected_features:
            errors.extend(self._validator.validate_errors(feature_params.get(self._relative_band_power_feature_id),
                "custom", label="Relative band power", validator=self._relative_band_power_errors))

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
        # Sincroniza dependencias, guarda el estado final y recalcula si se
        # puede continuar al siguiente paso.
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
