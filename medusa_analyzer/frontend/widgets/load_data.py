from __future__ import annotations
from collections.abc import Callable
from pathlib import Path
from typing import Any
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QLabel, QListWidget,
    QPushButton, QScrollArea, QVBoxLayout, QWidget)
from medusa_analyzer.frontend.utils import create_metadata_summaries
from medusa_analyzer.frontend.widgets.loading_overlay import LoadingOverlay
from medusa_analyzer.frontend.workers import TaskRunner, Worker

# Script to allow user to select EDF files, load them in a background thread using workers,
# extract metadata from files and show them on the screen.

def _load_files(loader_function: Callable[..., dict], paths: list[str],
    global_progress_callback: Callable[[int], None] | None = None) -> list[dict]:
    """
    """
    # Recibimos loader, función que sabe cargar un archivo, y se aplica para cargar varios archivos.
    # Hay un progress_callback opcional para informar del progreso.

    results = []
    file_count = len(paths)
    for file_index, path in enumerate(paths):

        def report_file_progress(file_progress: int) -> None:
            """ _load_files carga varios archivos, pero loader_function carga uno. Entonces el laoder
            sabe decir este archivo va al 50%, pero la barra necesita sabe 'toda la carga va al 30%).
            Esta función hace de traductora: progreso de este archivo - progreso global"""
            if global_progress_callback is None:
                return
            global_progress = int((file_index * 100 + file_progress) / file_count)
            global_progress_callback(global_progress) # Aquí es donde emitimos (worker.signals.progress.emit(global_progress))

        # NOTA: la función de loader tiene que estar programada para avisar del progreso.
        result = loader_function(path, progress_callback=report_file_progress)
        results.append(result)

        if global_progress_callback is not None:
            global_progress_callback(int(((file_index + 1) * 100) / file_count))

    return results


class LoadDataWidget(QScrollArea):
    """
    - Muestra un botón "Select EDF files"
    - El usuario selecciona uno o varios ficheros
    - Se limpian los datos anteriores
    - Se muestran los nombres de los archivos seleccionados
    - Se cargan archivos en segundo planto con un Worker
    - Se extraen los metadatos
    - Se guardan los resultados en state
    - Se muestran los metadatos en pantalla
    - Se emite changed para avisar al WorkFlowShell
    - can_continue() devuelve True si ya hay datos cargados. """

    changed = Signal() # emit a signal when widget state changes, for example when a file is
    # selected o when files are loaded correctly. Esta señal conecta con la del WorkflowShell
        # changed_signal = getattr(widget, "changed", None)
        # if changed_signal is not None:
        #     changed_signal.connect(self._refresh_navigation)


    def __init__(self,
        config: dict[str, Any], # allowed extensions
        state: dict[str, Any], # memoria compartida del experimento
        loader_function: Callable[..., dict], # function that knows how to load a file
        title: str, # title to show in the UI
        description: str): # description to show in the UI

        super().__init__()
        self.config = config
        self.state = state
        self.loader_function = loader_function
        self.runner = TaskRunner() # será el encargado de lanzar el trabajo en segundo planto

        # Construcción visual del widget
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.setWidget(self.content)
        root = QVBoxLayout(self.content) # layout principal
        root.setContentsMargins(4, 4, 4, 4)
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        description_label = QLabel(description)
        description_label.setObjectName("muted")
        description_label.setWordWrap(True)
        root.addWidget(title_label)
        root.addWidget(description_label)
        root.addSpacing(18)

        panel = QFrame() # Panel de selección con un pushButton para seleccionar archivos
        panel.setProperty("role", "surface-panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        self.select_button = QPushButton("Select EDF files") # Botón
        self.select_button.setProperty("variant", "secondary")
        self.select_button.clicked.connect(self._select_files) # Conexión

        self.files = QListWidget() # Visual list to show selected file names
        self.files.setMinimumHeight(125)
        self.files.setProperty("role", "file-list")

        # Texto de estado. Cambia dinámicamente. Al principio dice que elijas archivos. Luego puede cambiar
        # a 'leyendo...' o 'registros cargados correctamente'.
        self.status_label = QLabel("Choose one or more recordings to load their metadata.")
        self.status_label.setObjectName("selectionStatus")
        self.status_label.setProperty("status", "idle") # ready or error
        self.status_label.setWordWrap(True)
        layout.addWidget(self.select_button)
        layout.addWidget(self.files)
        layout.addWidget(self.status_label)
        root.addWidget(panel)

        self.metadata_panel = QFrame() # Panel de metadatos
        self.metadata_panel.setProperty("role", "surface-panel")
        self.metadata_layout = QGridLayout(self.metadata_panel)
        self.metadata_layout.setContentsMargins(24, 20, 24, 20)
        root.addWidget(self.metadata_panel)
        self.metadata_panel.hide() # only shown when metadata are loaded
        root.addStretch()

        # Creamos una capa de carga, que es una pantalla superpuesta con la barra de progreso
        self.overlay = LoadingOverlay(self)

        # Si en el state ya hay metadatos cargados, los mostramos otra vez. ¿Por qué? Pues porque quizá el usuario
        # vuelve a este paso después de haber avanzado y no queremos que salga el widget vacío si ya se habían
        # cargado archivos antes.
        metadata_list = self.state.get("metadata_list") or []
        if metadata_list:
            self.files.addItems([metadata.get("file_name", "") for metadata in metadata_list])
            self._show_metadata(metadata_list)

    def _select_files(self) -> None:
        """Función para seleccionar archivos a cargar y lanzar el worker.
        No devuelve ningún resultado con return. El resultado de carga llega más tarde, por señal:
        worker.signals.result.connect(self._loaded).
        _loaded(results) recibe los registros cuando el worker termina bien."""
        # Abrimos la ventana para seleccionar archivos.
        paths, _ = QFileDialog.getOpenFileNames(self, "Select recordings", "", self._dialog_filter())
        if not paths: # devolvemos una lista de rutas seleccionadas.
            return
        self._clear_loaded_state() # Borramos del state cualquier archivo cargado antes
        self.files.clear()
        self.files.addItems([Path(path).name for path in paths]) # Añadimos solo nombres de archivos, no path completo
        self.metadata_panel.hide() # Ocultamos panel metadatos
        self.status_label.setText(f"Reading {len(paths)} recording(s)...")
        self.status_label.setProperty("status", "idle")
        # NOTA EXPLICATIVA: Una propiedad dinámica puede tener tres estados: "idle" (estado neutro / esperando /
        # cargando), "ready" (carga correcta) y error (carga fallida).
        self._refresh_status_style() # Actualizamos el texto de la label de estado
        self.changed.emit() # avisamos al WorkflowShell de cambios para deshabilitar el Next.
        self.select_button.setEnabled(False)
        self.overlay.show_loading("Reading recordings...")

        # Creamos el worker
        worker = Worker(_load_files, self.loader_function, paths) # tarea a ejecutar: _load_files
        # Cuando el worker informe del progreso, actualizamos la barra de overlay.
        # self.overlay es el LoadingOverlay(QFrame). Dentro de esta clase se define atributo progress como QProgressBar()
        worker.signals.progress.connect(self.overlay.progress.setValue)
        # Cuando el worker emita el resultado de la carga, ejecutamos self._loaded.
        worker.signals.result.connect(self._loaded)
        worker.signals.error.connect(self._failed)
        worker.signals.finished.connect(self._finished_loading)
        self.runner.start(worker) # Lanzamos el worker. Aquí tiene lugar la carga de archivos.

    def _dialog_filter(self) -> str:
        """Construye el filtro del diálogo de archivos."""
        extensions = self.config.get("allowed_extensions", [".edf"])
        patterns = " ".join(f"*{extension}" for extension in extensions)
        return f"Supported files ({patterns});;All files (*.*)"

    def _clear_loaded_state(self) -> None:
        """Eliminar del estado lo relativo a los metadatos."""
        # Delete from state files loaded previously
        self.state["loaded_file_paths"] = []
        self.state["loader_results"] = []
        self.state["metadata_list"] = []
        self.state.pop("loaded_file_path", None)
        self.state.pop("loader_result", None)
        self.state.pop("metadata", None)

    def _loaded(self, results: list[dict]) -> None:
        """Recibe results (lista de resultados del loader) y los convierte en un MetadataSummary.
        Se ejecuta cuando el worker terminó correctamente.
        Guarda los metadata cargados en el state."""

        # Convertimos cada resultado del loader en un objeto MetadataSummary.
        metadata_list = create_metadata_summaries(results)
        self.state["loaded_file_paths"] = [metadata["file_path"] for metadata in metadata_list]
        self.state["loader_results"] = results
        self.state["metadata_list"] = metadata_list
        self.state.pop("loaded_file_path", None)
        self.state.pop("loader_result", None)
        self.state.pop("metadata", None)
        self.status_label.setText(f"{len(results)} recording(s) loaded successfully.")
        self.status_label.setProperty("status", "ready")
        self._refresh_status_style() # Actualizamos label
        self._show_metadata(metadata_list) # Mostramos el resumen
        # Avisamos al WorkflowShell. Después de cargar bien, can_continue() devolverá True, entonces el botón
        # Next podrá activarse.
        self.changed.emit()

    def _failed(self, error: str) -> None:
        """ Se ejecuta cuando la carga de datos falla."""
        self.status_label.setText(error.splitlines()[0]) # Mostramos solo la primera línea de error en la label dinámica
        self.status_label.setProperty("status", "error") # Cambia el estado visual a error
        self._refresh_status_style()

    def _finished_loading(self) -> None:
        """Se ejecuta al final, tanto si hubo éxito como error"""
        self.overlay.hide() # ocultar el overlay
        self.select_button.setEnabled(True) # Volver a activar el botón de seleccionar archivos.

    def _refresh_status_style(self) -> None:
        """Fuerza a Qt a recalcular el estilo de la label (propiedades dinámicas)."""
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
        return bool(self.state.get("metadata_list")) # hasta que no haya carga válida, Next queda deshabilitado.

