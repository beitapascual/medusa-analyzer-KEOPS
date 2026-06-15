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

logger = logging.getLogger(__name__)


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
            logger.warning(
                "Ignoring experiment folder %s: info.json requires route and workflow",
                directory.name,
            )
            continue

        experiments.append(
            ExperimentDefinition(
                id=experiment_id,
                package_name=directory.name,
                root=directory,
                info=info,
                defaults=defaults,
            )
        )
    return sorted(
        experiments,
        key=lambda experiment: (
            int(experiment.info.get("order", 0)),
            experiment.info.get("title", experiment.id),
        ),
    )


def _resolve_widget_class(definition: ExperimentDefinition, widget_ref: str) -> type[QWidget]:
    module_name, class_name = widget_ref.rsplit(".", 1)
    if not module_name.startswith("widgets."):
        module_name = f"widgets.{module_name}"
    qualified_module = (
        f"medusa_analyzer.frontend.experiments.{definition.package_name}.{module_name}"
    )
    module = importlib.import_module(qualified_module)
    widget_class = getattr(module, class_name)
    if not issubclass(widget_class, QWidget):
        raise TypeError(f"{qualified_module}.{class_name} is not a QWidget subclass")
    return widget_class


def create_experiment_page(definition: ExperimentDefinition) -> WorkflowShell:
    state: dict[str, Any] = {
        "experiment_id": definition.id,
        "experiment_title": definition.info.get("title", definition.id.upper()),
        "defaults": copy.deepcopy(definition.defaults),
        "loader_result": None,
        "metadata": None,
        "loaded_file_path": None,
        "selected_features": [],
    }
    steps = []
    for step in definition.info.get("workflow", []):
        widget_class = _resolve_widget_class(definition, step["widget"])
        widget = widget_class(definition.info, definition.defaults, state)
        steps.append({"id": step["id"], "title": step["title"], "widget": widget})
    return WorkflowShell(
        title=definition.info.get("title", definition.id.upper()),
        subtitle=definition.info.get("description") or definition.info.get("subtitle", ""),
        steps=steps,
        state=state,
    )


__all__ = ["ExperimentDefinition", "create_experiment_page", "discover_experiments"]
