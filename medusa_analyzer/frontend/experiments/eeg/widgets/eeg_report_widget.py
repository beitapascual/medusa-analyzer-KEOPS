from __future__ import annotations
from typing import Any
from PySide6.QtWidgets import QFrame
from medusa_analyzer.frontend.widgets import ReportWidget

# Este archivo es la parte EEG específica del report. ReportWidget genérico ya sabe crear la pantalla, meter el scroll,
# poner título/subtítulo, y dibujar secciónes.
# EEGReportWidget lo que hace es decirle como es la sección de preprocesado en EEG, como es la sección de features,
# como resumir filtros, bandas y parámetros, etc.
class EEGReportWidget(ReportWidget):
    # TODO: PORUQE ESTO? QUIERO QUE NO HAYA QUE HARDCODEARLO
    _absolute_band_power_feature_id = "absolute_band_power"
    _relative_band_power_feature_id = "relative_band_power"

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        _ = experiment_info
        self.defaults = defaults
        # Guardamos la parte de features del JSON
        self._features_config = defaults.get("features", {})
        # Construimos un diccionario para localizar rápido cada feature por id en vez de estar recorriendo el JSON completo
        self._feature_definitions = self._resolve_feature_definitions(self._features_config)

        # Llamamos al constructor de la clase base
        super().__init__(config=defaults.get("report", {}), state=state, title="Final report",
            description="Review the metadata, pre-processing selections and chosen features before handing this experiment to the future processing pipeline.")

    @staticmethod
    def _format_frequency(value: Any) -> str:
        # Convierte una frecuencia numérica en un texto bonito
        return f"{float(value):g} Hz"

    @classmethod
    def _describe_band(cls, band: dict[str, Any], include_parentheses: bool = True) -> str:
        # Convierte una banda EEG en una farse legible
        title = str(band.get("title") or band.get("id") or "Band")
        low_cut = cls._format_frequency(band.get("low_cut", 0.0))
        high_cut = cls._format_frequency(band.get("high_cut", 0.0))
        if include_parentheses:
            return f"{title} ({low_cut}-{high_cut})"
        return f"{title} {low_cut}-{high_cut}"

    @classmethod
    def _bands_summary(cls, bands: list[dict[str, Any]]) -> str:
        # Convierte una lista de bandas en un solo string
        if not bands:
            return "None"
        return ", ".join(cls._describe_band(band) for band in bands)

    @staticmethod
    def _filter_description(config: dict[str, Any]) -> str:
        # Resume un filtro EEG en una línea
        if not config or not config.get("enabled", False):
            return "Disabled"
        if str(config.get("filter_type", "fir")).lower() == "fir":
            detail = f'order {config.get("fir_order")}, {config.get("fir_window")} window'
        else:
            detail = f'order {config.get("iir_order")}, {config.get("iir_design")}'
        return f'{config.get("low_cut"):g}-{config.get("high_cut"):g} Hz, {str(config.get("filter_type", "")).upper()}, {detail}'

    def _preprocessing_section(self) -> QFrame | None:
        # Este métoodo rellena el hueco que ReportWidget dejó vacío. Construye el panel de Preprocessing específico de EEG
        preprocessing = self.state.get("preprocessing", {}) # leemos del estado
        # TODO: habrá que cambiar esto
        if not preprocessing:
            return self._section("Pre-processing", [("Status", "Using experiment defaults.")])

        selected_frequency_bands = preprocessing.get("selected_frequency_bands", [])
        notch = preprocessing.get("notch", {})
        bandpass = preprocessing.get("bandpass", {})
        return self._section("Pre-processing", # llamamos a _section
            [("CAR", "Enabled" if preprocessing.get("car_checked") else "Disabled"),
                ("Notch", self._filter_description(notch)), ("Bandpass", self._filter_description(bandpass)),
                ("Analysis bands", self._bands_summary(selected_frequency_bands))])

    @classmethod
    def _collect_leaf_feature_ids(cls, group: dict[str, Any]) -> list[str]:
        # Recorre el árbol de categorías/features y saca los id de las features reales
        feature_ids: list[str] = []
        for feature in group.get("features", []):
            if feature.get("features") or feature.get("subcategories"):
                feature_ids.extend(cls._collect_leaf_feature_ids(feature))
                continue
            feature_id = feature.get("id")
            if feature_id:
                feature_ids.append(str(feature_id))
        # Accedemos también a subcategorías anidadas
        for subcategory in group.get("subcategories", []):
            feature_ids.extend(cls._collect_leaf_feature_ids(subcategory))

        return feature_ids

    @classmethod
    def _collect_leaf_feature_definitions(cls, group: dict[str, Any], feature_definitions: dict[str, dict[str, Any]]) -> None:
        # Función que hace un índice rápido de todas las características del JSON para que sea más rápido acceder a su
        # información (título, parámetros, opciones del combo, etc.)
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
        # TODO: no eniendo mucho la diferencia con _collect_leaf_feature_definitions, no se podrían unificar?
        feature_definitions: dict[str, dict[str, Any]] = {}
        for category in features_config.get("categories", []):
            cls._collect_leaf_feature_definitions(category, feature_definitions)
        return feature_definitions

    def _combo_value_title(self, param: dict[str, Any], value: Any) -> str:
        # Métoodo que hace que si un parámetros era un combo, enseña el nombre bonito y no el id en crudo
        for option in param.get("options", []):
            if option.get("id") == value:
                return str(option.get("title") or value)
        return str(value)

    def _feature_param_summaries(self, feature_id: str, feature_definition: dict[str, Any]) -> list[str]:
        # Construye una lista de "detalles" que acompañan a una feature en el report
        # Leemos los parámetros guardados de una característica
        # TODO: no se podrían considerar las bandas como parámetros para no hardcodear esto?
        feature_params = self.state.get("feature_params", {}).get(feature_id, {})
        if feature_id in (self._absolute_band_power_feature_id, self._relative_band_power_feature_id):
            selected_frequency_bands = feature_params.get("selected_frequency_bands", [])
            if selected_frequency_bands:
                return [", ".join(self._describe_band(band, include_parentheses=False) for band in selected_frequency_bands)]
            return []

        param_summaries: list[str] = []
        # Recorremos los parámetros de la feature
        for param in feature_definition.get("params", []):
            param_id = str(param.get("id", ""))
            if param_id not in feature_params:
                continue
            value = feature_params[param_id]
            # Convertimos el valor del parámetro a texto
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
        # Construye el texto final de una feature concreta

        feature_definition = self._feature_definitions.get(feature_id, {})
        feature_title = str(feature_definition.get("title") or feature_id)
        # Sacamos los resúmenes de los parámetros
        param_summaries = self._feature_param_summaries(feature_id, feature_definition)
        if not param_summaries:
            return feature_title # si no hay parámetros, devolvemos solo el título
        return f'{feature_title} ({", ".join(param_summaries)})'

    def _feature_rows(self) -> list[tuple[str, str]]:
        # Agrupa las características seleccionadas por categoría top-level y devuelve las filas listas para _sections
        selected_features = self.state.get("selected_features", []) # lee la lista de seleccionadas
        selected_feature_ids = set(selected_features) # la convierte en set para búsquedas rápidas
        rows: list[tuple[str, str]] = []
        # Bucle para recorrer categorías top-level del json
        for category in self._features_config.get("categories", []):
            ordered_feature_ids = [feature_id for feature_id in self._collect_leaf_feature_ids(category)
                if feature_id in selected_feature_ids]
            if not ordered_feature_ids:
                continue
            rows.append((str(category.get("title") or category.get("id") or "Category"),
                "; ".join(self._feature_summary(feature_id) for feature_id in ordered_feature_ids)))
        if rows:
            return rows
        return [("Status", "None selected.")]

    def _features_section(self) -> QFrame | None:
        # Rellena el hueco de ReportWidget para la sección Features
        return self._section("Features", self._feature_rows())

    def _additional_section_builders(self) -> list:
        builders = []
        if self.config.get("include_preprocessing_summary", True):
            builders.append(self._preprocessing_section)
        if self.config.get("include_selected_features", True):
            builders.append(self._features_section)
        return builders
