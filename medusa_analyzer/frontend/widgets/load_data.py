from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
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

    def __init__(self, config: dict[str, Any], state: dict[str, Any], actions: list[LoadDataAction],
        title: str, description: str, metadata_labels: dict[str, str],
        metadata_builder: Callable[[list[dict] | dict[str, Any], Any], dict[str, Any]] | None = None):
        super().__init__()
        if not actions:
            raise ValueError("LoadDataWidget requires at least one LoadDataAction.")

        self.config = config
        self.state = state
        self.actions = actions
        self.action_buttons: dict[str, QPushButton] = {}
        self._selected_source: Any | None = None
        self.metadata_builder = metadata_builder or self._build_metadata
        self.metadata_labels = dict(metadata_labels)
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
        # self.select_button = next(iter(self.action_buttons.values()))

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
        loaded_file_paths = self.state.get("loaded_file_paths", [])
        if loaded_file_paths:
            self.files.addItems([Path(path).name for path in loaded_file_paths])

        if isinstance(metadata, dict) and metadata:
            self._show_metadata(metadata)

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
        # archivos y extraer task de los nombres.
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
        self.state.pop("loaded_file_path", None)
        self.state.pop("loader_result", None)
        self.state.pop("broadband", None)
        self.state.pop("metadata", None)

    @staticmethod
    def _build_metadata(results: dict[str, Any], selection: Any) -> dict[str, Any]:
        """Construye el metadata nuevo para el panel partiendo del primer archivo y de la seleccion completa."""
        del selection
        return dict(results)

    def _loaded(self, results: list[dict] | dict[str, Any]) -> None:
        """Recibe el resultado del loader, guarda el estado y pinta el panel de metadata."""

        if isinstance(self._selected_source, (list, tuple)):
            selected_paths = [str(path) for path in self._selected_source]
        elif self._selected_source is None:
            selected_paths = []
        else:
            selected_paths = [str(self._selected_source)]

        loader_results = [] if isinstance(results, dict) else list(results)
        metadata = dict(self.metadata_builder(results, self._selected_source) or {})

        self.state["loaded_file_paths"] = selected_paths
        self.state["loader_results"] = loader_results
        self.state["metadata"] = metadata
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

        for index, (key, value) in enumerate(metadata.items()):
            label = self.metadata_labels[key]
            if isinstance(value, (list, tuple, set)):
                formatted_value = ", ".join(str(item) for item in value)
            else:
                formatted_value = str(value)

            name = QLabel(label)
            name.setObjectName("metricLabel")
            number = QLabel(formatted_value)
            number.setObjectName("metricValue")
            number.setWordWrap(True)
            self.metadata_layout.addWidget(name, (index // 3) * 2, index % 3)
            self.metadata_layout.addWidget(number, (index // 3) * 2 + 1, index % 3)
        self.metadata_panel.show()

    def can_continue(self) -> bool:
        """Validacion del step. Hasta que no haya una lista de metadatos no avanza.
        NOTA RECORDATORIA: WorkflowShell hace lo de if hasattr(widget, "can_continue")."""
        return bool(self.state.get("metadata"))
