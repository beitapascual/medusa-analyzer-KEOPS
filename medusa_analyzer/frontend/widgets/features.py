from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class FeatureItem:
    id: str # identificador interno de la característica
    title: str # nombre visible de la característica
    subtitle: str # texto explicativo de la característica
    category_id: str # a qué categoría pertenece
    checked_by_default: bool = False # si debe venir marcada al principio
    params: list[dict[str, Any]] | None = None # parámetros de la característica


class FeaturesWidget(QScrollArea):
    changed = Signal() # señal que se emite cuando cambia la selección
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

        # Si no existe selected_features, reconstruye la selección por defecto
        if "selected_features" not in self.state or not self.state["selected_features"]:
            self.state["selected_features"] = self._default_selection()
        # Inicializamos también en el estado el diccionario de los parámetros
        if "feature_params" not in self.state:
            self.state["feature_params"] = {}

        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        root = QVBoxLayout(content) # layout principal
        root.setContentsMargins(4, 4, 12, 4)
        root.setSpacing(16)

        heading = QLabel(title) # cabecera con el título
        heading.setObjectName("pageTitle")
        subtitle = QLabel(description) # subtítulo
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True) # si el texto es largo, salta de línea
        root.addWidget(heading)
        root.addWidget(subtitle)

        categories_container = QWidget() # contenedor de las categorías
        self.category_grid = QGridLayout(categories_container)
        self.category_grid.setContentsMargins(0, 0, 0, 0)
        self.category_grid.setHorizontalSpacing(16)
        self.category_grid.setVerticalSpacing(16)
        self.category_grid.setColumnStretch(0, 1)
        self.category_grid.setColumnStretch(1, 1)

        categories = self.config.get("categories", [])
        # Bucle recorriendo las categorías
        for index, category in enumerate(categories):
            panel = self._build_group_panel(category, heading_object_name="groupTitle")
            self.category_panels.append(panel) # Creamos un panel para esa categoría
            row = index // self._column_count
            column = index % self._column_count
            is_last_odd_panel = len(categories) % self._column_count == 1 and index == len(categories) - 1
            self.category_grid.addWidget(panel, row, column, 1, self._column_count if is_last_odd_panel else 1)

        root.addWidget(categories_container)

        self.setWidget(content)
        self._sync()

    def _build_group_panel(self, group: dict[str, Any], heading_object_name: str) -> QFrame:
        # Función que crea el panel visual de una categoría top-level, le pone título, le mete un QScrollArea interno
        panel = QFrame()
        panel.setProperty("role", "feature-group")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        panel.setFixedHeight(self._panel_height)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        group_title = QLabel(str(group.get("title", ""))) # Título de la categoría
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
        # Métoodo que rellena un layout con el contenido de un grupo. Para ello, recorre features. Si una entrada es una
        # característica normal, la dibuja.
        # Bucle iterando por las características de una categoría
        for feature in group.get("features", []):
            # Esto es para iterar en las top-features. Por ejemplo, una top feature sería 'spectral' que tiene varias
            # features: PSD, RP, AP.
            if feature.get("features"):
                subgroup_title = QLabel(str(feature.get("title", "")))
                subgroup_title.setObjectName("subgroupTitle")
                layout.addWidget(subgroup_title)
                self._populate_group(layout, feature)
                continue
            self._add_feature_controls(layout, feature, str(group.get("id", "")))

        # Esto es para subcategorías de una top-feature. Por ejemplo, la top-feature 'connectivity' tiene las categorías
        # amplitud, fase y coherencia. A su vez, cada subcategoría tiene varias features.
        for subcategory in group.get("subcategories", []):
            subgroup_title = QLabel(str(subcategory.get("title", "")))
            subgroup_title.setObjectName("subgroupTitle")
            layout.addWidget(subgroup_title)
            self._populate_group(layout, subcategory)

    def _add_feature_controls(self, layout: QVBoxLayout, feature: dict[str, Any], category_id: str) -> None:
        # Función que crea el checkbox de una feature real, añade su subtítulo (si existe), guarda el checkbox en
        # self.checkboxes y si la feature tiene parámetros, crea también su bloque de parámetros
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
            params_container.setVisible(box.isChecked()) # solo se deja visible si el checkbox está marcado
            self.param_containers[item.id] = params_container # diccionario para guardar el bloque de parámetros
            layout.addWidget(params_container)

    def _default_selection(self) -> list[str]:
        # Obetner las selecciones por defecto
        selected: list[str] = []
        for category in self.config.get("categories", []):
            self._collect_default_selection(category, selected)
        return selected

    def _collect_default_selection(self, group: dict[str, Any], selected: list[str]) -> None:
        # Métoodo que recorre recursivamente un grupo para encontrar todas las características que deben venir
        # seleccionadas por defecto. Considera también la posibilidad de que haya subgrupos.

        for feature in group.get("features", []):
            if feature.get("features") or feature.get("subcategories"):
                self._collect_default_selection(feature, selected)
                continue
            if feature.get("checked_by_default", False):
                selected.append(feature["id"])

        for subcategory in group.get("subcategories", []):
            self._collect_default_selection(subcategory, selected)

    def _build_params_form(self, item: FeatureItem) -> QWidget:
        # Crea el bloque visual de parámetros de una característica. Crea una fila por parámetro y guarda tanto los
        # widgets como sus valores por defecto.
        container = QWidget()
        form = QFormLayout(container)
        form.setContentsMargins(24, 0, 0, 8)
        form.setSpacing(8)

        # Creamos dos diccionarios para esa feature
        self.param_widgets[item.id] = {} # diccionario de widgets de los parámetros
        self.param_defaults[item.id] = {} # diccioanrio de los defaults de los parámetros
        # Recorremos todos los parámetros de la feature
        for param in item.params or []:
            widget = self._create_param_widget(item.id, param)
            label = QLabel(param["title"])
            label.setToolTip(param.get("tooltip", ""))
            widget.setToolTip(param.get("tooltip", ""))
            form.addRow(label, widget)
            self.param_widgets[item.id][param["id"]] = widget
            self.param_defaults[item.id][param["id"]] = param.get("default")
        return container

    def _create_param_widget(self, feature_id: str, param: dict[str, Any]) -> QWidget:
        # Crea el widget correcto según el tipo de parámetro
        param_id = param["id"]
        param_type = param.get("type", "text")
        # Buscamos el valor por defecto del parámetro
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
        # Función que recibe un widget de un parámetro y un valor y le pone ese valor correctamente según el tipo de
        # widget. Además bloquea señales mientras lo hace.
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
        finally:
            widget.blockSignals(False)

    def _reset_feature_params(self, feature_id: str) -> None:
        # Resetea todos los parámetros de una característica a los valores por defecto
        defaults = self.param_defaults.get(feature_id, {})
        widgets = self.param_widgets.get(feature_id, {})
        for param_id, widget in widgets.items():
            self._set_param_widget_value(widget, defaults.get(param_id))

    def _sync(self) -> None:
        # Primero, reconstruimos las características seleccionadas
        self.state["selected_features"] = [feature_id for feature_id, checkbox in self.checkboxes.items() if checkbox.isChecked()]

        # Recorremos todos los contenedos de parámetros
        for feature_id, container in self.param_containers.items():
            is_selected = feature_id in self.state["selected_features"]
            container.setVisible(is_selected) # si la característica está marcada, mostramos los parámetros
            if not is_selected:
                self._reset_feature_params(feature_id) # si no reseteamos los valores

        # Reconstruimos el diccionario de los parámetros de las características
        self.state["feature_params"] = {}
        for feature_id, params in self.param_widgets.items(): # recorremos todas las features que tienen parámetros
            if feature_id not in self.state["selected_features"]: # si no está seleccionada, pasamos
                continue
            self.state["feature_params"][feature_id] = {} # solo guardamos parámetros de features activas
            for param_id, widget in params.items(): # recorremos cada widget de parámetros de esa feature
                if isinstance(widget, QSpinBox):
                    value = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    value = widget.value()
                elif isinstance(widget, QComboBox):
                    value = widget.currentData()
                elif isinstance(widget, QLineEdit):
                    value = widget.text()
                else:
                    value = None
                self.state["feature_params"][feature_id][param_id] = value # guardamos el valor leído en el estado
        self.changed.emit() # emitimos señal de que algo ha cambiado

    def can_continue(self) -> bool:
        # Métodoo que usa el workflow para saber si puede avanzar. Ahora mismo se puede seguir aunque no haya ninguna
        # marcada.
        return True


__all__ = ["FeatureItem", "FeaturesWidget"]
