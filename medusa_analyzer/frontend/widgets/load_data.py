from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from medusa_analyzer.frontend.utils import create_metadata_summaries
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


def load_files(
    loader_function: Callable[..., dict],
    paths: list[str],
    loader_args: tuple[Any, ...] = (),
    loader_kwargs: dict[str, Any] | None = None,
    progress_callback: Callable[[int], None] | None = None,
    log_callback: Callable[[str, str], None] | None = None,
) -> list[dict]:
    """Run a single-file loader over several selected files."""
    del log_callback
    results = []
    file_count = len(paths)
    loader_kwargs = dict(loader_kwargs or {})

    for file_index, path in enumerate(paths):

        def report_file_progress(file_progress: int) -> None:
            if progress_callback is None:
                return
            global_progress = int((file_index * 100 + file_progress) / file_count)
            progress_callback(global_progress)

        result = loader_function(path, *loader_args, progress_callback=report_file_progress, **loader_kwargs)
        results.append(result)

        if progress_callback is not None:
            progress_callback(int(((file_index + 1) * 100) / file_count))

    return results


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

    def __init__(
        self,
        config: dict[str, Any],
        state: dict[str, Any],
        actions: list[LoadDataAction],
        title: str,
        description: str,
    ):
        super().__init__()
        if not actions:
            raise ValueError("LoadDataWidget requires at least one LoadDataAction.")

        self.config = config
        self.state = state
        self.actions = actions
        self.action_buttons: dict[str, QPushButton] = {}
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

        metadata_list = self.state.get("metadata_list") or []
        if metadata_list:
            self.files.addItems([metadata.get("file_name", "") for metadata in metadata_list])
            self._show_metadata(metadata_list)

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
        selection = action.select(self)
        if selection is None:
            return

        worker_call = action.build_call(selection)
        self.files.clear()
        self.files.addItems(action.display_names(selection))
        status_text = action.status_text(selection) if callable(action.status_text) else action.status_text
        self.status_label.setText(status_text)

        self._clear_loaded_state()
        self.metadata_panel.hide()
        self.status_label.setProperty("status", "idle")
        self._refresh_status_style()
        self.changed.emit()
        self._set_action_buttons_enabled(False)
        self.overlay.start_process(action.overlay_text)

        worker = Worker(worker_call.function, *worker_call.args, **worker_call.kwargs)
        worker.signals.progress.connect(self.overlay.progress.setValue)
        worker.signals.logging.connect(self.overlay.add_log_message)
        worker.signals.result.connect(self._loaded)
        worker.signals.error.connect(self._failed)
        worker.signals.finished.connect(self._finished_loading)
        self.runner.start(worker)

    def _set_action_buttons_enabled(self, enabled: bool) -> None:
        for button in self.action_buttons.values():
            button.setEnabled(enabled)

    def _dialog_filter(self) -> str:
        """Construye el filtro del dialogo de archivos."""
        extensions = self.config.get("allowed_extensions", [".edf"])
        patterns = " ".join(f"*{extension}" for extension in extensions)
        return f"Supported files ({patterns})"

    def _clear_loaded_state(self) -> None:
        """Eliminar del estado lo relativo a los metadatos."""
        self.state["loaded_file_paths"] = []
        self.state["loader_results"] = []
        self.state["metadata_list"] = []
        self.state.pop("loaded_file_path", None)
        self.state.pop("loader_result", None)
        self.state.pop("broadband", None)
        self.state.pop("metadata", None)

    def _loaded(self, results: list[dict]) -> None:
        """Recibe results (lista de resultados del loader) y los convierte en resumenes normalizados.
        Se ejecuta cuando el worker termino correctamente.
        Guarda los metadata cargados en el state."""

        metadata_list = create_metadata_summaries(results)
        self.state["loaded_file_paths"] = [metadata["file_path"] for metadata in metadata_list]
        self.state["loader_results"] = results
        self.state["metadata_list"] = metadata_list
        self.state.pop("loaded_file_path", None)
        self.state.pop("loader_result", None)
        self.state.pop("metadata", None)
        self.status_label.setText(f"{len(results)} recording(s) loaded successfully.")
        self.status_label.setProperty("status", "ready")
        self._refresh_status_style()
        self._show_metadata(metadata_list)
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

    def _show_metadata(self, metadata_list: list[dict[str, Any]]) -> None:
        """Función para pintar los metadatos en el panel"""
        # TODO: está función va a haber que cambiarla. Lo ideal sería que de alguna forma sea capaz de detectar
        #  archivos con cosas diferentes. Que haga un summary general de todo lo común, y luego que comente
        # individualmente lo diferente o algo así.

        # Limpiamos los metadata anteriores
        while self.metadata_layout.count():
            item = self.metadata_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Creamos un conjunto con las frecuencias de muestreo
        sampling_rates = {metadata.get("sampling_rate") for metadata in metadata_list
            if metadata.get("sampling_rate") is not None}
        sampling_rate = (f"{next(iter(sampling_rates)):g} Hz" if len(sampling_rates) == 1
            else "Mixed") # TODO: que muestre que archivos tienen diferentes y que si sample_rate estÃ¡ vacÃ­o
        # todo muestre "-" en vez de "Mixed"
        # Creamos una lista con el nº de canales de cada archivo
        channel_counts = [len(metadata.get("channels") or []) for metadata in metadata_list]
        # Si todos tienen el mismo nº, ponemos X canales; si varían ponemos X-Y per file
        channel_count = (str(channel_counts[0]) if len(set(channel_counts)) == 1
            else f"{min(channel_counts)}-{max(channel_counts)} per file")
        # Suma la duración de todos los registros
        duration = sum(metadata.get("duration_seconds") or 0.0 for metadata in metadata_list)
        # Suma el nº de muestras
        samples = sum(metadata.get("n_samples") or 0 for metadata in metadata_list)
        # Lista de canales únicos
        channels = list(dict.fromkeys(channel for metadata in metadata_list for channel in (metadata.get("channels") or [])))
        # Valores a mostrar en el metadata summary de la pantalla
        values = [("Number of files", str(len(metadata_list))),
            ("Sampling rate", sampling_rate),
            ("Channels", channel_count),
            ("Total duration", f"{duration:g} s"),
            ("Total samples", str(samples)),
            ("Channel list", ", ".join(channels) or "-")]

        # Summary de metadata
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
        """Validación del step. Hasta que no haya una lista de metadatos no avanza.
        NOTA RECORDATORIA: WorkflowShell hace lo de if hasattr(widget, "can_continue")."""
        return bool(self.state.get("metadata_list"))
