from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget, QComboBox, QDoubleSpinBox, \
    QFormLayout, QLineEdit, QSpinBox, QVBoxLayout

# Este widget muestra una lista de features agrupadas por categorías con checkboxes. Su trabajo es pintar los grupos y
# opciones, marcar por defecto algunas opciones, guardar en el estado cuáles están activadas y avisar con changed
# cuando algo cambia.

# Creamos una clase simple de datos cuyos atributos no se deben cambiar después (frozen = True) y usa menos memoria
# (slots = True).
@dataclass(frozen=True, slots=True)
class FeatureItem:
    id: str # identificador interno de la característica
    title: str # nombre visible de la característica
    subtitle: str # texto explicativo de la característica
    category_id: str # a qué categoría pertenece
    checked_by_default: bool = False # si debe venir marcada al principio
    params: list[dict[str, Any]] | None = None # parámetros de la característica

# Definimos el widget visual completo
class FeaturesWidget(QWidget):
    changed = Signal() # señal que se emite cuando cambia la selección

    # El constructor recibe la definición de categorías y features (config), el estado compartido donde se guarda lo
    # seleccionado, el título grande de la página  y el subtítulo descriptivo.
    def __init__(self, config: dict[str, Any], state: dict[str, Any], title: str, description: str):
        super().__init__()
        self.config = config
        self.state = state
        self.checkboxes: dict[str, QCheckBox] = {} # diccionario para guardar cada checkbox por feature_id
        self.param_widgets: dict[str, dict[str, QWidget]] = {} # diccionario para guardar los widgets de parámetros

        # Si no existe selected_features, reconstruye la selección por defecto
        if "selected_features" not in self.state or not self.state["selected_features"]:
            self.state["selected_features"] = self._default_selection()
        # Inicializamos también en el estado el diccionario de los parámetros
        if "feature_params" not in self.state:
            self.state["feature_params"] = {}

        root = QVBoxLayout(self) # layout principal
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(16)

        heading = QLabel(title) # cabecera con el título
        heading.setObjectName("pageTitle")
        subtitle = QLabel(description) # subtítulo
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True) # si el texto es largo, salta de línea
        root.addWidget(heading)
        root.addWidget(subtitle)

        grid_container = QWidget() # contenedor de las categorías
        grid = QGridLayout(grid_container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(16)

        # Bucle recorriendo las categorías
        for index, category in enumerate(self.config.get("categories", [])):
            panel = QFrame() # Creamos un panel para esa categoría
            panel.setProperty("role", "feature-group")
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(24, 20, 24, 20)
            category_title = QLabel(category["title"]) # Nombre de la categoría
            category_title.setObjectName("groupTitle")
            layout.addWidget(category_title)

            for feature in category.get("features", []): # Bucle de features dentro de esa categoría
                # Creamos un objeto Feature para cada característica
                item = FeatureItem(id=feature["id"], title=feature["title"], subtitle=feature.get("subtitle", ""),
                    category_id=category["id"], checked_by_default=bool(feature.get("checked_by_default", False)),
                    params=feature.get("params", []))

                box = QCheckBox(item.title) # creamos el checkbox de la característica con su texto visible
                box.setToolTip(item.subtitle) # mostramos el subtítulo como tooltip
                box.setChecked(item.id in self.state["selected_features"])
                box.toggled.connect(self._sync) # cuando se marca o desmarca, llama a _sync
                layout.addWidget(box)
                # Creamos una label explicativa cuando haya subtítulo
                if item.subtitle:
                    detail = QLabel(item.subtitle)
                    detail.setObjectName("muted")
                    detail.setWordWrap(True)
                    layout.addWidget(detail)

                # Guardamos la referencia al checkbox en el diccionario de checkboxes usando el id de la característica
                # como clave. Esto esmuy importante porque luego _sync no busca checkboses en la UI; ya los tiene aquí.
                self.checkboxes[item.id] = box

                if item.params:
                    params_form = self._build_params_form(item)
                    layout.addLayout(params_form)
                    # Subcategorías dentro de la categoría

            # Subcategorías dentro de la categoría
            for subcategory in category.get("subcategories", []):
                subcategory_title = QLabel(subcategory["title"])
                subcategory_title.setObjectName("subgroupTitle")
                layout.addWidget(subcategory_title)

                for feature in subcategory.get("features", []):
                    item = FeatureItem(id=feature["id"], title=feature["title"], subtitle=feature.get("subtitle", ""),
                        category_id=subcategory["id"], checked_by_default=bool(feature.get("checked_by_default", False)),
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

                    self.checkboxes[item.id] = box

                    if item.params:
                        params_form = self._build_params_form(item)
                        layout.addLayout(params_form)

            layout.addStretch()
            grid.addWidget(panel, index // 2, index % 2)

        root.addWidget(grid_container)
        root.addStretch()
        self._sync()

    def _default_selection(self) -> list[str]:
        # Métoodo que calcula la selección incial por defecto
        selected: list[str] = []
        for category in self.config.get("categories", []): # recorre categorías
            for feature in category.get("features", []): # recorre características
                if feature.get("checked_by_default", False):
                    selected.append(feature["id"])
            for subcategory in category.get("subcategories", []):
                for feature in subcategory.get("features", []):
                    if feature.get("checked_by_default", False):
                        selected.append(feature["id"])
        return selected

    def _build_params_form(self, item: FeatureItem) -> QFormLayout:
        # Crea el formulario visual de parámetros para una feature concreta.
        form = QFormLayout()
        form.setContentsMargins(24, 0, 0, 8)
        form.setSpacing(8)

        self.param_widgets[item.id] = {}

        for param in item.params or []:
            widget = self._create_param_widget(item.id, param)
            label = QLabel(param["title"])
            label.setToolTip(param.get("tooltip", ""))
            widget.setToolTip(param.get("tooltip", ""))
            form.addRow(label, widget)
            self.param_widgets[item.id][param["id"]] = widget

        return form

    def _create_param_widget(self, feature_id: str, param: dict[str, Any]) -> QWidget:
        # Crea el widget adecuado para cada parámetro según su tipo: int, float, combo o text.
        param_id = param["id"]
        param_type = param.get("type", "text")

        saved_value = (self.state .get("feature_params", {}) .get(feature_id, {})
            .get(param_id, param.get("default")))

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

    def _sync(self) -> None:
        # Métoodo que mantiene el estado sincronizado con la UI.
        # Primero reconstruimos la lista de ids seleccionados.
        self.state["selected_features"] = [feature_id for feature_id, checkbox in self.checkboxes.items()
            if checkbox.isChecked()]

        # Después guardamos SOLO los parámetros de las features seleccionadas.
        self.state["feature_params"] = {}
        for feature_id, params in self.param_widgets.items():
            if feature_id not in self.state["selected_features"]:
                continue
            self.state["feature_params"][feature_id] = {}
            for param_id, widget in params.items():
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
                self.state["feature_params"][feature_id][param_id] = value
        self.changed.emit() # emite señal de que algo ha cambiado

    def can_continue(self) -> bool:
        # Métodoo que usa el workflow para saber si puede avanzar. Ahora mismo se puede seguir aunque no haya ninguna
        # marcada.
        return True
