from __future__ import annotations

import copy
import importlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from PySide6.QtWidgets import QWidget

from medusa_analyzer.frontend.widgets.workflow_shell import WorkflowShell

logger = logging.getLogger(__name__) # objeto para escribir logs desde este archivo


@dataclass(frozen=True, slots=True)
class ExperimentDefinition:
    id: str
    package_name: str
    root: Path
    info: dict[str, Any]
    defaults: dict[str, Any]

    @property
    def route(self) -> str:
        return str(self.info["route"])

    @property
    def icon_path(self) -> Path:
        return self.root / self.info.get("icon", "")


def _experiments_root() -> Path:
    return Path(__file__).resolve().parent


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_experiments() -> list[ExperimentDefinition]:
    # Función que recorre frontend/experiments/, comprueba que existe info.json y defaults.json, lee ambos, valida que
    # info.json tenga route y workflow, y construye un ExperimentDefinition.

    experiments: list[ExperimentDefinition] = []
    for directory in sorted(_experiments_root().iterdir()):
        if not directory.is_dir():
            continue
        if directory.name.startswith("__"):
            continue
        info_path = directory / "info.json"
        defaults_path = directory / "defaults.json"
        if not info_path.exists():
            logger.warning("Ignoring experiment folder without info.json: %s", directory.name)
            continue
        if not defaults_path.exists():
            logger.warning("Ignoring experiment folder without defaults.json: %s", directory.name)
            continue
        try:
            info = _read_json(info_path)
            defaults = _read_json(defaults_path)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Ignoring experiment folder %s: %s", directory.name, exc)
            continue

        experiment_id = info.get("id", directory.name)
        route = info.get("route")
        workflow = info.get("workflow")
        if not route or not isinstance(workflow, list) or not workflow:
            logger.warning("Ignoring experiment folder %s: info.json requires route and workflow", directory.name)
            continue

        # Vamos guardando la información de todos los experimentos detectados
        experiments.append(ExperimentDefinition(
                id=experiment_id,
                package_name=directory.name, # devuelve lo que va detrás de la última /
                root=directory,
                info=info,
                defaults=defaults))
    # Devolvemos la lista de experimentos ordenada por dos posibles criterios. Primero ordenamos por el orden y, si dos
    # experimentos tienen el mismo orden, ordena por el título.
    return sorted(experiments, key=lambda experiment: (int(experiment.info.get("order", 0)),
            experiment.info.get("title", experiment.id)))


def _resolve_widget_class(definition: ExperimentDefinition, widget_ref: str) -> type[QWidget]:

    module_name, class_name = widget_ref.rsplit(".", 1)

    # Construimos el nombre completo del path donde se encuentran los widgets dentro del experimento
    if not module_name.startswith("widgets."):
        module_name = f"widgets.{module_name}"
    qualified_module = (f"medusa_analyzer.frontend.experiments.{definition.package_name}.{module_name}")

    # Convertimos el widget en una clase real
    module = importlib.import_module(qualified_module)
    widget_class = getattr(module, class_name)
    if not issubclass(widget_class, QWidget):
        raise TypeError(f"{qualified_module}.{class_name} is not a QWidget subclass")
    return widget_class


def create_experiment_page(definition: ExperimentDefinition) -> WorkflowShell:
    # Recibe una definición de un experimento y construye una página completa. Es decir, agrupa/define todos los widgets
    # de un experimento.

    # El state es una memoria compartida del experimento. Todos los widgets reciben este diccionario. Por ejemplo,
    # si el primer widget carga un archivo, puede guardarlo en state. Luego el segundo widget puede leerlo. Así todos los
    # pasos se comunican entre sí. Sin state cada pantalla estaría aislada y no podría saber que ha hecho la anterior.

    state: dict[str, Any] = {
        "experiment_id": definition.id,
        "experiment_title": definition.info.get("title", definition.id.upper()),
        "defaults": copy.deepcopy(definition.defaults),
        "loader_result": None,
        "loader_results": [],
        "metadata": None,
        "metadata_list": [],
        "loaded_file_path": None,
        "loaded_file_paths": [],
        "selected_features": []}

    # Leemos los pasos definidos en el info.json
    steps = []
    for step in definition.info.get("workflow", []):
        # Definimos como clases oficiales de python los diferentes widgets de los steps
        widget_class = _resolve_widget_class(definition, step["widget"])

        widget = widget_class(definition.info, definition.defaults, state) # TODO: no entiendo porque tenemos que definir estas clases
        steps.append({"id": step["id"], "title": step["title"], "widget": widget})

    return WorkflowShell(title=definition.info.get("title", definition.id.upper()),
        subtitle=definition.info.get("description") or definition.info.get("subtitle", ""),
        steps=steps,
        state=state)

__all__ = ["ExperimentDefinition", "create_experiment_page", "discover_experiments"]
