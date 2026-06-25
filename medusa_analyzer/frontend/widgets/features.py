from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QGridLayout, QLabel,
    QLineEdit, QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QWidget)

@dataclass(frozen=True, slots=True)
class FeatureItem:
    id: str # identificador interno de la característica
    title: str # nombre visible de la característica
    subtitle: str # texto explicativo de la característica
    category_id: str # a quÃ© categoría pertenece
    checked_by_default: bool = False # si debe venir marcada al principio
    params: list[dict[str, Any]] | None = None # parámetros de la característica


class FeaturesWidget(QScrollArea):
    changed = Signal() # seÃ±al que se emite cuando cambia la selección
    _column_count = 2
    _panel_height = 360

    # El constructor recibe la definición de categorías y features (config), el estado compartido donde se guarda lo
    # seleccionado, el título grande de la página  y el subtítulo descriptivo.
    def __init__(self, config: dict[str, Any], state: dict[str, Any], title: str, description: str):
        super().__init__()
        self.config = config
        self.state = state
        self.checkboxes: dict[str, QCheckBox] = {}
        self.param_widgets: dict[str, dict[str, QWidget]] = {} # diccionario para guardar cada checkbox por feature_id
        self.param_defaults: dict[str, dict[str, Any]] = {}
        self.param_containers: dict[str, QWidget] = {}
        self.category_panels: list[QFrame] = []

        # Si no existe selected_features, reconstruye la selecciÃ³n por defecto
        if "selected_features" not in self.state or not self.state["selected_features"]:
            self.state["selected_features"] = self._default_selection()
        # Inicializamos tambiÃ©n en el estado el diccionario de los parÃ¡metros
        if "feature_params" not in self.state:
            self.state["feature_params"] = {}

        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        root = QVBoxLayout(content) # layout principal
        root.setContentsMargins(4, 4, 12, 4)
        root.setSpacing(16)

        heading = QLabel(title) # cabecera con el tÃ­tulo
        heading.setObjectName("pageTitle")
        subtitle = QLabel(description) # subtÃ­tulo
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True) # si el texto es largo, salta de lÃ­nea
        root.addWidget(heading)
        root.addWidget(subtitle)

        categories_container = QWidget() # contenedor de las categorÃ­as
        self.category_grid = QGridLayout(categories_container)
        self.category_grid.setContentsMargins(0, 0, 0, 0)
        self.category_grid.setHorizontalSpacing(16)
        self.category_grid.setVerticalSpacing(16)
        self.category_grid.setColumnStretch(0, 1)
        self.category_grid.setColumnStretch(1, 1)

        categories = self.config.get("categories", [])
        # Bucle recorriendo las categorÃ­as
        for index, category in enumerate(categories):
            panel = self._build_group_panel(category, heading_object_name="groupTitle")
            self.category_panels.append(panel) # Creamos un panel para esa categorÃ­a
            row = index // self._column_count
            column = index % self._column_count
            is_last_odd_panel = len(categories) % self._column_count == 1 and index == len(categories) - 1
            self.category_grid.addWidget(panel, row, column, 1, self._column_count if is_last_odd_panel else 1)

        root.addWidget(categories_container)

        self.setWidget(content)
        self._sync()

    def _build_group_panel(self, group: dict[str, Any], heading_object_name: str) -> QFrame:
        # FunciÃ³n que crea el panel visual de una categorÃ­a top-level, le pone tÃ­tulo, le mete un QScrollArea interno
        panel = QFrame()
        panel.setProperty("role", "feature-group")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        panel.setFixedHeight(self._panel_height)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        group_title = QLabel(str(group.get("title", ""))) # TÃ­tulo de la categorÃ­a
        group_title.setObjectName(heading_object_name)
        layout.addWidget(group_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        self._populate_group(content_layout, group)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return panel

    def _populate_group(self, layout: QVBoxLayout, group: dict[str, Any]) -> None:
        # MÃ©toodo que rellena un layout con el contenido de un grupo. Para ello, recorre features. Si una entrada es una
        # caracterÃ­stica normal, la dibuja.
        # Bucle iterando por las caracterÃ­sticas de una categorÃ­a
        for feature in group.get("features", []):
            # Esto es para iterar en las top-features. Por ejemplo, una top feature serÃ­a 'spectral' que tiene varias
            # features: PSD, RP, AP.
            if feature.get("features") or feature.get("subcategories"):
                subgroup_title = QLabel(str(feature.get("title", "")))
                subgroup_title.setObjectName("subgroupTitle")
                layout.addWidget(subgroup_title)
                self._populate_group(layout, feature)
                continue
            self._add_feature_controls(layout, feature, str(group.get("id", "")))

        # Esto es para subcategorÃ­as de una top-feature. Por ejemplo, la top-feature 'connectivity' tiene las categorÃ­as
        # amplitud, fase y coherencia. A su vez, cada subcategorÃ­a tiene varias features.
        for subcategory in group.get("subcategories", []):
            subgroup_title = QLabel(str(subcategory.get("title", "")))
            subgroup_title.setObjectName("subgroupTitle")
            layout.addWidget(subgroup_title)
            self._populate_group(layout, subcategory)

    def _add_feature_controls(self, layout: QVBoxLayout, feature: dict[str, Any], category_id: str) -> None:
        # FunciÃ³n que crea el checkbox de una feature real, aÃ±ade su subtÃ­tulo (si existe), guarda el checkbox en
        # self.checkboxes y si la feature tiene parÃ¡metros, crea tambiÃ©n su bloque de parÃ¡metros
        item = FeatureItem(id=feature["id"], title=feature["title"], subtitle=feature.get("subtitle", ""),
            category_id=category_id, checked_by_default=bool(feature.get("checked_by_default", False)),
            params=feature.get("params", []))

        box = QCheckBox(item.title)
        box.setToolTip(item.subtitle)
        box.setChecked(item.id in self.state["selected_features"])
        box.toggled.connect(self._sync)
        layout.addWidget(box)

        if item.subtitle:
            detail = QLabel(item.subtitle)
            detail.setObjectName("muted")
            detail.setWordWrap(True)
            layout.addWidget(detail)

        self.checkboxes[item.id] = box # diccionario para guardar los checkboxes

        if item.params:
            params_container = self._build_params_form(item)
            params_container.setVisible(box.isChecked()) # solo se deja visible si el checkbox estÃ¡ marcado
            self.param_containers[item.id] = params_container # diccionario para guardar el bloque de parÃ¡metros
            layout.addWidget(params_container)
            if item.id not in self.param_widgets:
                layout.removeWidget(params_container)
                params_container.deleteLater()
                self.param_containers.pop(item.id, None)
        self._after_feature_controls_added(layout, item, box)

    def _default_selection(self) -> list[str]:
        # Obetner las selecciones por defecto
        selected: list[str] = []
        for category in self.config.get("categories", []):
            self._collect_default_selection(category, selected)
        return selected

    def _collect_default_selection(self, group: dict[str, Any], selected: list[str]) -> None:
        # MÃ©toodo que recorre recursivamente un grupo para encontrar todas las caracterÃ­sticas que deben venir
        # seleccionadas por defecto. Considera tambiÃ©n la posibilidad de que haya subgrupos.

        for feature in group.get("features", []):
            if feature.get("features") or feature.get("subcategories"):
                self._collect_default_selection(feature, selected)
                continue
            if feature.get("checked_by_default", False):
                selected.append(feature["id"])

        for subcategory in group.get("subcategories", []):
            self._collect_default_selection(subcategory, selected)

    def _build_params_form(self, item: FeatureItem) -> QWidget:
        # Crea el bloque visual de parÃ¡metros de una caracterÃ­stica. Crea una fila por parÃ¡metro y guarda tanto los
        # widgets como sus valores por defecto.
        container = QWidget()
        form = QFormLayout(container)
        form.setContentsMargins(24, 0, 0, 8)
        form.setSpacing(8)

        # Creamos dos diccionarios para esa feature
        self.param_widgets[item.id] = {} # diccionario de widgets de los parÃ¡metros
        self.param_defaults[item.id] = {} # diccioanrio de los defaults de los parÃ¡metros
        # Recorremos todos los parÃ¡metros de la feature
        for param in item.params or []:
            if str(param.get("type", "")) == "derived":
                continue
            widget = self._create_param_widget(item.id, param)
            label = QLabel(param["title"])
            label.setToolTip(param.get("tooltip", ""))
            widget.setToolTip(param.get("tooltip", ""))
            form.addRow(label, widget)
            self.param_widgets[item.id][param["id"]] = widget
            self.param_defaults[item.id][param["id"]] = param.get("default")
        if not self.param_widgets[item.id]:
            self.param_widgets.pop(item.id, None)
            self.param_defaults.pop(item.id, None)
        return container

    def _after_feature_controls_added(self, layout: QVBoxLayout, item: FeatureItem, checkbox: QCheckBox) -> None:
        # Hook para que una subclase pueda aÃ±adir UI especÃ­fica justo despuÃ©s de dibujar una feature concreta.
        _ = layout
        _ = item
        _ = checkbox

    def _create_param_widget(self, feature_id: str, param: dict[str, Any]) -> QWidget:
        # Crea el widget correcto segÃºn el tipo de parÃ¡metro
        param_id = param["id"]
        param_type = param.get("type", "text")
        # Buscamos el valor por defecto del parÃ¡metro
        saved_value = (self.state.get("feature_params", {}).get(feature_id, {}).get(param_id, param.get("default")))

        if param_type == "int":
            widget = QSpinBox()
            widget.setMinimum(int(param.get("min", -999999)))
            widget.setMaximum(int(param.get("max", 999999)))
            widget.setValue(int(saved_value))
            widget.valueChanged.connect(self._sync)
            return widget

        if param_type == "float":
            widget = QDoubleSpinBox()
            widget.setMinimum(float(param.get("min", -999999.0)))
            widget.setMaximum(float(param.get("max", 999999.0)))
            widget.setSingleStep(float(param.get("step", 0.01)))
            widget.setDecimals(int(param.get("decimals", 3)))
            widget.setValue(float(saved_value))
            widget.valueChanged.connect(self._sync)
            return widget

        if param_type == "checkbox":
            widget = QCheckBox()
            widget.setChecked(bool(saved_value))
            widget.toggled.connect(self._sync)
            return widget

        if param_type == "combo":
            widget = QComboBox()
            for option in param.get("options", []):
                widget.addItem(option["title"], option["id"])
            index = widget.findData(saved_value)
            if index >= 0:
                widget.setCurrentIndex(index)
            widget.currentIndexChanged.connect(self._sync)
            return widget

        widget = QLineEdit()
        widget.setText(str(saved_value))
        widget.textChanged.connect(self._sync)
        return widget

    def _set_param_widget_value(self, widget: QWidget, value: Any) -> None:
        # FunciÃ³n que recibe un widget de un parÃ¡metro y un valor y le pone ese valor correctamente segÃºn el tipo de
        # widget. AdemÃ¡s bloquea seÃ±ales mientras lo hace.
        widget.blockSignals(True)
        try:
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(value)
            elif isinstance(widget, QComboBox):
                index = widget.findData(value)
                if index >= 0:
                    widget.setCurrentIndex(index)
            elif isinstance(widget, QLineEdit):
                widget.setText("" if value is None else str(value))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
        finally:
            widget.blockSignals(False)

    def _reset_feature_params(self, feature_id: str) -> None:
        # Resetea todos los parÃ¡metros de una caracterÃ­stica a los valores por defecto
        defaults = self.param_defaults.get(feature_id, {})
        widgets = self.param_widgets.get(feature_id, {})
        for param_id, widget in widgets.items():
            self._set_param_widget_value(widget, defaults.get(param_id))

    def _selected_feature_ids(self) -> list[str]:
        # Reconstruye la lista de ids marcados mirando el estado real de los checkboxes.
        return [feature_id for feature_id, checkbox in self.checkboxes.items() if checkbox.isChecked()]

    def _sync_param_containers(self, selected_features: list[str]) -> None:
        # Recorremos todos los contenedos de parÃ¡metros
        for feature_id, container in self.param_containers.items():
            is_selected = feature_id in selected_features
            container.setVisible(is_selected) # si la caracterÃ­stica estÃ¡ marcada, mostramos los parÃ¡metros
            if not is_selected:
                self._reset_feature_params(feature_id) # si no reseteamos los valores

    def _read_param_widget_value(self, widget: QWidget) -> Any:
        # Devuelve el valor actual del widget de un parÃ¡metro segÃºn su tipo real.
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QComboBox):
            return widget.currentData()
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        return None

    def _rebuild_feature_params(self, selected_features: list[str]) -> dict[str, dict[str, Any]]:
        # Reconstruimos el diccionario de los parÃ¡metros de las caracterÃ­sticas activas.
        feature_params: dict[str, dict[str, Any]] = {}
        for feature_id, params in self.param_widgets.items(): # recorremos todas las features que tienen parÃ¡metros
            if feature_id not in selected_features: # si no estÃ¡ seleccionada, pasamos
                continue
            feature_params[feature_id] = {} # solo guardamos parÃ¡metros de features activas
            for param_id, widget in params.items(): # recorremos cada widget de parÃ¡metros de esa feature
                feature_params[feature_id][param_id] = self._read_param_widget_value(widget)
        return feature_params

    def _sync(self) -> None:
        # Primero, reconstruimos las caracterÃ­sticas seleccionadas
        selected_features = self._selected_feature_ids()
        self.state["selected_features"] = selected_features
        self._sync_param_containers(selected_features)
        self.state["feature_params"] = self._rebuild_feature_params(selected_features)
        self.changed.emit() # emitimos seÃ±al de que algo ha cambiado

    def can_continue(self) -> bool:
        # MÃ©todoo que usa el workflow para saber si puede avanzar. Ahora mismo se puede seguir aunque no haya ninguna
        # marcada.
        return True


__all__ = ["FeatureItem", "FeaturesWidget"]
