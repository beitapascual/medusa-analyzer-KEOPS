from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QScrollArea, QVBoxLayout, QWidget)
from medusa_analyzer.frontend.widgets.progress_overlay import ProgressOverlay
from medusa_analyzer.frontend.worker import TaskRunner, Worker


@dataclass(frozen=True, slots=True)
class WorkerCall:
    """Callable plus the exact args/kwargs that will be sent to Worker."""

    function: Callable[..., Any]
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LoadDataAction:
    """One selectable way of loading data in a LoadDataWidget."""

    id: str
    label: str
    select: Callable[["LoadDataWidget"], Any | None]
    build_call: Callable[[Any], WorkerCall]
    display_names: Callable[[Any], list[str]]
    status_text: str | Callable[[Any], str]
    overlay_text: str = "Reading recordings..."


def load_files(loader_function: Callable[..., dict], paths: list[str], loader_args: tuple[Any, ...] = (),
    loader_kwargs: dict[str, Any] | None = None, progress_callback: Callable[[int], None] | None = None,
    log_callback: Callable[[str, str], None] | None = None) -> list[dict]:
    """Run the loader only for the first selected file."""
    del log_callback
    if not paths:
        return []

    loader_kwargs = dict(loader_kwargs or {})

    def report_file_progress(file_progress: int) -> None:
        if progress_callback is not None:
            progress_callback(file_progress)

    result = loader_function(paths[0], *loader_args, progress_callback=report_file_progress, **loader_kwargs)
    if progress_callback is not None:
        progress_callback(100)
    return [result]


class LoadDataWidget(QScrollArea):
    """
    - Muestra un botón para seleccionar datos.
    - El usuario selecciona una entrada mediante una LoadDataAction.
    - Se limpian los datos anteriores.
    - Se muestran los nombres seleccionados.
    - Se cargan datos en segundo plano con un Worker.
    - Se extraen los metadatos.
    - Se guardan los resultados en state.
    - Se muestran los metadatos en pantalla.
    - Se emite changed para avisar al WorkFlowShell.
    - can_continue() devuelve True si ya hay datos cargados.
    """

    changed = Signal()
    _task_pattern = re.compile(r"(?:^|_)task[-_]([^_]+)", re.IGNORECASE)

    def __init__(self, config: dict[str, Any], state: dict[str, Any], actions: list[LoadDataAction],
        title: str, description: str):
        super().__init__()
        if not actions:
            raise ValueError("LoadDataWidget requires at least one LoadDataAction.")

        self.config = config
        self.state = state
        self.actions = actions
        self.action_buttons: dict[str, QPushButton] = {}
        self._selected_source: Any | None = None
        self.runner = TaskRunner()

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.setWidget(self.content)
        root = QVBoxLayout(self.content)
        root.setContentsMargins(4, 4, 4, 4)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        description_label = QLabel(description)
        description_label.setObjectName("muted")
        description_label.setWordWrap(True)
        root.addWidget(title_label)
        root.addWidget(description_label)
        root.addSpacing(18)

        panel = QFrame()
        panel.setProperty("role", "surface-panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        for action in self.actions:
            button = QPushButton(action.label)
            button.setProperty("variant", "secondary")
            button.clicked.connect(lambda checked=False, selected_action=action: self._run_action(selected_action))
            button_layout.addWidget(button)
            self.action_buttons[action.id] = button
        self.select_button = next(iter(self.action_buttons.values()))

        self.files = QListWidget()
        self.files.setMinimumHeight(125)
        self.files.setProperty("role", "file-list")

        self.status_label = QLabel("Choose one or more recordings to load their metadata.")
        self.status_label.setObjectName("selectionStatus")
        self.status_label.setProperty("status", "idle")
        self.status_label.setWordWrap(True)
        layout.addLayout(button_layout)
        layout.addWidget(self.files)
        layout.addWidget(self.status_label)
        root.addWidget(panel)

        self.metadata_panel = QFrame()
        self.metadata_panel.setProperty("role", "surface-panel")
        self.metadata_layout = QGridLayout(self.metadata_panel)
        self.metadata_layout.setContentsMargins(24, 20, 24, 20)
        root.addWidget(self.metadata_panel)
        self.metadata_panel.hide()
        root.addStretch()

        self.overlay = ProgressOverlay(self)

        metadata = self.state.get("metadata")
        # TODO: ahora mismo esta lo de metadata_list para que no rompa con lo que ya habría, pero hay que quitar
        #  y refactorizar aguas abajo
        metadata_list = self.state.get("metadata_list") or []
        loaded_file_paths = self.state.get("loaded_file_paths", [])
        if loaded_file_paths:
            self.files.addItems([Path(path).name for path in loaded_file_paths])
        elif metadata_list: # TODO: quitar
            file_names = [metadata_item.get("file_name", "") for metadata_item in metadata_list
                if isinstance(metadata_item, dict) and metadata_item.get("file_name")]
            if file_names:
                self.files.addItems(file_names)

        if isinstance(metadata, dict) and metadata:
            self._show_metadata(metadata)
        elif metadata_list: # TODO: quitar
            self._show_metadata(self._metadata_from_legacy_list(metadata_list))

    def select_files(self, caption: str = "Select recordings") -> list[str] | None:
        """Open a multi-file dialog using this widget's configured extension filter."""
        paths, _ = QFileDialog.getOpenFileNames(self, caption, "", self._dialog_filter())
        return paths or None

    def select_directory(self, caption: str = "Select directory") -> str | None:
        """Open a directory dialog and return the selected path."""
        path = QFileDialog.getExistingDirectory(self, caption, "")
        return path or None

    def _run_action(self, action: LoadDataAction) -> None:
        """Select data and run the action's worker call."""
        ## Llamamos  al selector definido para esa acción. Puede abrir un diálogo de ficheros o de carpeta.
        selection = action.select(self)
        if selection is None:
            return # si el usuario canceló la selección, sale sin hacer nada

        self.files.clear() # limpia la lista visual de ficheros mostrados antes
        self.files.addItems(action.display_names(selection)) # metemos los nombres de los que el usuario acaba de seleccionar
        status_text = action.status_text(selection) if callable(action.status_text) else action.status_text
        self.status_label.setText(status_text)

        self._clear_loaded_state() # Borramos del state lo cargado anteriormente
        # Guardamos la selección anterior para usarla luego en _loaded, por ejemplo para contar
        # archios y extraer task de los nombres.
        # TODO: independientemente de la selección vamos a extraer la TASK-
        self._selected_source = selection
        worker_call = action.build_call(selection) # definimos la función, args y kwargs del worker
        self.metadata_panel.hide() # ocultamos panel mientras se procesa la nueva carga
        self.status_label.setProperty("status", "idle")
        self._refresh_status_style()
        self.changed.emit()
        self._set_action_buttons_enabled(False) # desactivamos botones
        # Mostramos el overlay del progreso son la función y argumentos preparados en worker_call
        self.overlay.start_process(action.overlay_text)

        # Creamos un worker con la función y argumentos preparados en worker_call
        worker = Worker(worker_call.function, *worker_call.args, **worker_call.kwargs)
        worker.signals.progress.connect(self.overlay.progress.setValue)
        worker.signals.logging.connect(self.overlay.add_log_message)
        worker.signals.result.connect(self._loaded)
        worker.signals.error.connect(self._failed)
        worker.signals.finished.connect(self._finished_loading)
        self.runner.start(worker) # lanza el worker en segundo plano

    def _set_action_buttons_enabled(self, enabled: bool) -> None:
        """Activar/desactivar los botones dependientes de la acción del usuario"""
        for button in self.action_buttons.values():
            button.setEnabled(enabled)

    def _dialog_filter(self) -> str:
        """Construye el filtro del dialogo de archivos."""
        extensions = self.config.get("allowed_extensions", [".edf"])
        patterns = " ".join(f"*{extension}" for extension in extensions)
        return f"Supported files ({patterns})"

    def _clear_loaded_state(self) -> None:
        """Eliminar del estado lo relativo a los metadatos."""
        self._selected_source = None
        self.state["loaded_file_paths"] = []
        self.state["loader_results"] = []
        self.state["metadata_list"] = []
        self.state.pop("loaded_file_path", None)
        self.state.pop("loader_result", None)
        self.state.pop("broadband", None)
        self.state.pop("metadata", None)

    @staticmethod
    def _selection_file_paths(selection: Any) -> list[str]:
        """Devuelve una lista con los paths de todos los archivos cargados."""
        if isinstance(selection, (list, tuple)):
            return [str(path) for path in selection]
        if selection is None:
            return []
        return [str(selection)]

    @classmethod
    def _extract_tasks_from_paths(cls, paths: list[str]) -> list[str]:
        """Method para extraer la tarea directamente de los nombres de los archivos, sin abrir
        los registros. """
        tasks: list[str] = []
        missing_task = False

        for path in paths:
            match = cls._task_pattern.search(Path(path).stem)
            if match is None:
                missing_task = True
                continue
            task_name = match.group(1).strip()
            if task_name:
                tasks.append(task_name)
        ordered_tasks = list(dict.fromkeys(tasks))
        if missing_task:
            ordered_tasks.append("No task")
        return ordered_tasks

    @classmethod
    def _build_metadata_from_first_result(cls, first_result: dict[str, Any], file_paths: list[str]) -> dict[str, Any]:
        channels = list(first_result.get("channels") or [])
        return {
            "n_files": len(file_paths) if file_paths else 1,
            "n_channels": int(first_result.get("n_channels") or len(channels)),
            "channel_set": channels,
            "fs": first_result.get("sampling_rate"),
            "task": cls._extract_tasks_from_paths(file_paths),
        }

    @classmethod
    def _build_metadata_state_entry(cls, first_result: dict[str, Any], file_paths: list[str]) -> dict[str, Any]:
        file_path = file_paths[0] if file_paths else str(first_result.get("path") or "")
        file_name = str(first_result.get("name") or first_result.get("file_name") or Path(file_path).name)
        metadata_entry = {
            "file_name": file_name,
            "file_path": file_path,
            "channels": list(first_result.get("channels") or []),
            "sampling_rate": first_result.get("sampling_rate"),
            "duration_seconds": first_result.get("duration_seconds"),
            "n_samples": first_result.get("n_samples"),
            "task": cls._extract_tasks_from_paths(file_paths),
        }
        if "broadband" in first_result:
            metadata_entry["broadband"] = first_result.get("broadband")
        return metadata_entry

    @classmethod
    def _metadata_from_legacy_list(cls, metadata_list: list[dict[str, Any]]) -> dict[str, Any]:
        if not metadata_list:
            return {}

        first_metadata = metadata_list[0]
        channels = list(first_metadata.get("channels") or [])
        file_paths = [str(metadata.get("file_path") or "") for metadata in metadata_list if metadata.get("file_path")]
        return {
            "n_files": len(metadata_list),
            "n_channels": len(channels),
            "channel_set": channels,
            "fs": first_metadata.get("sampling_rate"),
            "task": cls._extract_tasks_from_paths(file_paths),
        }

    @staticmethod
    def _metadata_label(key: str) -> str:
        labels = {
            "n_files": "Number of files",
            "n_channels": "Number of channels",
            "channel_set": "Channel set",
            "fs": "Sampling rate",
            "task": "Task",
        }
        if key in labels:
            return labels[key]
        return str(key).replace("_", " ").strip().title()

    @classmethod
    def _format_metadata_value(cls, key: str, value: Any) -> str:
        if value is None:
            return "-"

        if isinstance(value, dict):
            if not value:
                return "-"
            return ", ".join(f"{sub_key}: {sub_value}" for sub_key, sub_value in value.items())

        if isinstance(value, (list, tuple, set)):
            items = [str(item) for item in value if str(item)]
            return ", ".join(items) if items else "-"

        if key == "fs":
            try:
                return f"{float(value):g} Hz"
            except (TypeError, ValueError):
                return str(value)

        return str(value)

    def _loaded(self, results: list[dict] | dict[str, Any]) -> None:
        """Recibe el resultado del loader, guarda el estado y pinta el panel de metadata."""

        selected_paths = self._selection_file_paths(self._selected_source)
        metadata: dict[str, Any]
        metadata_list: list[dict[str, Any]]
        loader_results: list[dict[str, Any]]

        if isinstance(results, dict):
            metadata = dict(results)
            metadata_list = [metadata]
            loader_results = []
        else:
            loader_results = list(results)
            metadata = (self._build_metadata_from_first_result(loader_results[0], selected_paths)
                if loader_results else {})
            metadata_list = ([self._build_metadata_state_entry(loader_results[0], selected_paths)]
                if loader_results else [])

        self.state["loaded_file_paths"] = selected_paths
        self.state["loader_results"] = loader_results
        self.state["metadata"] = metadata
        self.state["metadata_list"] = metadata_list
        self.state.pop("loaded_file_path", None)
        self.state.pop("loader_result", None)

        loaded_count = metadata.get("n_files") or metadata.get("total_files") or len(selected_paths) or len(loader_results)
        self.status_label.setText(f"{loaded_count} recording(s) loaded successfully.")
        self.status_label.setProperty("status", "ready")
        self._refresh_status_style()
        self._show_metadata(metadata)
        self.changed.emit()

    def _failed(self, error: str) -> None:
        """Se ejecuta cuando la carga de datos falla."""
        self.status_label.setText(error.splitlines()[0])
        self.status_label.setProperty("status", "error")
        self._refresh_status_style()

    def _finished_loading(self) -> None:
        """Se ejecuta al final, tanto si hubo exito como error."""
        self.overlay.hide()
        self._set_action_buttons_enabled(True)

    def _refresh_status_style(self) -> None:
        """Fuerza a Qt a recalcular el estilo de la label (propiedades dinamicas)."""
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _show_metadata(self, metadata: dict[str, Any]) -> None:
        """Pinta en el panel cualquier diccionario plano de metadatos."""
        while self.metadata_layout.count():
            item = self.metadata_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not metadata:
            self.metadata_panel.hide()
            return

        values = [(self._metadata_label(key), self._format_metadata_value(key, value))
            for key, value in metadata.items()]

        for index, (label, value) in enumerate(values):
            name = QLabel(label)
            name.setObjectName("metricLabel")
            number = QLabel(value)
            number.setObjectName("metricValue")
            number.setWordWrap(True)
            self.metadata_layout.addWidget(name, (index // 3) * 2, index % 3)
            self.metadata_layout.addWidget(number, (index // 3) * 2 + 1, index % 3)
        self.metadata_panel.show()

    def can_continue(self) -> bool:
        """Validacion del step. Hasta que no haya una lista de metadatos no avanza.
        NOTA RECORDATORIA: WorkflowShell hace lo de if hasattr(widget, "can_continue")."""
        return bool(self.state.get("metadata") or self.state.get("metadata_list"))
