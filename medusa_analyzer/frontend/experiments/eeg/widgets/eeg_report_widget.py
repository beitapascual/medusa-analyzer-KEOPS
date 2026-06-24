from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFrame

from medusa_analyzer.frontend.widgets import ReportWidget


class EEGReportWidget(ReportWidget):
    _absolute_band_power_feature_id = "absolute_band_power"
    _relative_band_power_feature_id = "relative_band_power"

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        _ = experiment_info
        self.defaults = defaults
        self._features_config = defaults.get("features", {})
        self._feature_definitions = self._resolve_feature_definitions(self._features_config)
        super().__init__(
            config=defaults.get("report", {}),
            state=state,
            title="Final report",
            description="Review the metadata, pre-processing selections and chosen features before handing this experiment to the future processing pipeline.",
        )

    @staticmethod
    def _format_frequency(value: Any) -> str:
        return f"{float(value):g} Hz"

    @classmethod
    def _describe_band(cls, band: dict[str, Any], include_parentheses: bool = True) -> str:
        title = str(band.get("title") or band.get("id") or "Band")
        low_cut = cls._format_frequency(band.get("low_cut", 0.0))
        high_cut = cls._format_frequency(band.get("high_cut", 0.0))
        if include_parentheses:
            return f"{title} ({low_cut}-{high_cut})"
        return f"{title} {low_cut}-{high_cut}"

    @classmethod
    def _bands_summary(cls, bands: list[dict[str, Any]]) -> str:
        if not bands:
            return "None"
        return ", ".join(cls._describe_band(band) for band in bands)

    @staticmethod
    def _filter_description(config: dict[str, Any]) -> str:
        if not config or not config.get("enabled", False):
            return "Disabled"
        if str(config.get("filter_type", "fir")).lower() == "fir":
            detail = f'order {config.get("fir_order")}, {config.get("fir_window")} window'
        else:
            detail = f'order {config.get("iir_order")}, {config.get("iir_design")}'
        return f'{config.get("low_cut"):g}-{config.get("high_cut"):g} Hz, {str(config.get("filter_type", "")).upper()}, {detail}'

    def _preprocessing_section(self) -> QFrame | None:
        preprocessing = self.state.get("preprocessing", {})
        if not preprocessing:
            return self._section("Pre-processing", [("Status", "Using experiment defaults.")])

        selected_frequency_bands = preprocessing.get("selected_frequency_bands", [])
        notch = preprocessing.get("notch", {})
        bandpass = preprocessing.get("bandpass", {})
        return self._section(
            "Pre-processing",
            [
                ("CAR", "Enabled" if preprocessing.get("car_checked") else "Disabled"),
                ("Notch", self._filter_description(notch)),
                ("Bandpass", self._filter_description(bandpass)),
                ("Analysis bands", self._bands_summary(selected_frequency_bands)),
            ],
        )

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

    def _combo_value_title(self, param: dict[str, Any], value: Any) -> str:
        for option in param.get("options", []):
            if option.get("id") == value:
                return str(option.get("title") or value)
        return str(value)

    def _feature_param_summaries(self, feature_id: str, feature_definition: dict[str, Any]) -> list[str]:
        feature_params = self.state.get("feature_params", {}).get(feature_id, {})
        if feature_id in (self._absolute_band_power_feature_id, self._relative_band_power_feature_id):
            selected_frequency_bands = feature_params.get("selected_frequency_bands", [])
            if selected_frequency_bands:
                return [", ".join(self._describe_band(band, include_parentheses=False) for band in selected_frequency_bands)]
            return []

        param_summaries: list[str] = []
        for param in feature_definition.get("params", []):
            param_id = str(param.get("id", ""))
            if param_id not in feature_params:
                continue
            value = feature_params[param_id]
            if str(param.get("type", "")) == "combo":
                value_text = self._combo_value_title(param, value)
            elif isinstance(value, bool):
                value_text = "Yes" if value else "No"
            elif isinstance(value, float):
                value_text = f"{value:g}"
            else:
                value_text = str(value)
            param_summaries.append(f'{param.get("title", param_id)}={value_text}')
        return param_summaries

    def _feature_summary(self, feature_id: str) -> str:
        feature_definition = self._feature_definitions.get(feature_id, {})
        feature_title = str(feature_definition.get("title") or feature_id)
        param_summaries = self._feature_param_summaries(feature_id, feature_definition)
        if not param_summaries:
            return feature_title
        return f'{feature_title} ({", ".join(param_summaries)})'

    def _feature_rows(self) -> list[tuple[str, str]]:
        selected_features = self.state.get("selected_features", [])
        selected_feature_ids = set(selected_features)
        rows: list[tuple[str, str]] = []
        for category in self._features_config.get("categories", []):
            ordered_feature_ids = [
                feature_id
                for feature_id in self._collect_leaf_feature_ids(category)
                if feature_id in selected_feature_ids
            ]
            if not ordered_feature_ids:
                continue
            rows.append((
                str(category.get("title") or category.get("id") or "Category"),
                "; ".join(self._feature_summary(feature_id) for feature_id in ordered_feature_ids),
            ))
        if rows:
            return rows
        return [("Status", "None selected.")]

    def _features_section(self) -> QFrame | None:
        return self._section("Features", self._feature_rows())
