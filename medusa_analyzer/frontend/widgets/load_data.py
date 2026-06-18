from __future__ import annotations
from collections.abc import Callable
from pathlib import Path
from typing import Any
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QLabel, QListWidget,
    QPushButton, QScrollArea, QVBoxLayout, QWidget)
from medusa_analyzer.frontend.models import MetadataSummary
from medusa_analyzer.frontend.widgets.loading_overlay import LoadingOverlay
from medusa_analyzer.frontend.workers import TaskRunner, Worker

# Script to allow user to select EDF files, load them in a background thread using workers,
# extract metadata from files and show them on the screen.

def _load_files(loader: Callable[..., dict], paths: list[str],
    progress_callback: Callable[[int], None] | None = None) -> list[dict]:
    # Recibimos loader, funciÃ³n que sabe cargar un archivo, y se aplica para cargar varios archivos. Esa funciÃ³n laoder
    # ahora es mock, pero luego serÃ¡ la que cargue el experimento en BIDS. Hay un progress_callback opcional para
    # informar del progreso.

    results = []
    file_count = len(paths)
    for index, path in enumerate(paths):
        # Function to convert the progress of one individual file in a global progress
        def report_progress(value: int, file_index: int = index) -> None:
            if progress_callback:
                progress_callback(int((file_index * 100 + value) / file_count))
        results.append(loader(path, progress_callback=report_progress))

    return results


class LoadDataWidget(QScrollArea):
    # Muestra un botÃ³n "Select EDF files", el usuario selecciona uno o varios ficheros, se limpian los datos anteriores,
    # se muestran los nombres de los archivos seleccionados, se cargan archivos en segundo planto, se extraen los
    # metadatos, se guardan los resultados en state, se muestran los metadatos en pantalla, se emite changed para avisar
    # al WorkFlowShell y can_continue() devuelve True si ya hay datos cargados

    changed = Signal() # emit a signal when widget state changes, por example when a file is
    # selected o when files are loaded correctly.
    # Esta seÃ±al conectar con la del WorkflowShell
        # changed_signal = getattr(widget, "changed", None)
        # if changed_signal is not None:
        #     changed_signal.connect(self._refresh_navigation)


    def __init__(self,
        config: dict[str, Any], # allowed extensions
        state: dict[str, Any], # memoria compartida del experimento
        loader: Callable[..., dict], # function that knows how to load a file
        title: str, # title to show in the UI
        description: str): # description to show in the UI

        super().__init__()
        self.config = config
        self.state = state
        self.loader = loader
        self.runner = TaskRunner() # serÃ¡ el encargado de lanzar el trabajo en segundo planto

        # ConstrucciÃ³n visual del widget
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

        panel = QFrame() # Panel de selecciÃ³n con un pushButton para seleccioanr archivos
        panel.setProperty("role", "surface-panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        self.select_button = QPushButton("Select EDF files")
        self.select_button.setProperty("variant", "secondary")
        self.select_button.clicked.connect(self._select_files) # ConexiÃ³n

        self.files = QListWidget() # Visual list to show selected file names
        self.files.setMinimumHeight(125)
        self.files.setProperty("role", "file-list")

        # Texto de estado que al principio dice que elijas archivos, pero luego puede cambiar a 'leyendo...' o
        # 'registros cargados correctamente'.
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
        self.metadata_panel.hide() # only shown when metadada are laoded
        root.addStretch()

        # Creamos una capa de carga, que es una pantalla superpuesta con la barra de progreso
        self.overlay = LoadingOverlay(self)

        # Si en el state ya hay metadatos cargados, los mostramos otra vez. Â¿Por quÃ©? Pues porque quizÃ¡ el usuario
        # vuelve a este paso despuÃ©s de haber avanzado y no queremos que salga el widget vacÃ­o si ya se habÃ­an
        # cargado archivos antes.

        metadata_list = self.state.get("metadata_list") or []
        if metadata_list:
            self.files.addItems([metadata.file_name for metadata in metadata_list])
            self._show_metadata(metadata_list)

    def _select_files(self) -> None:
        # Abrimos la ventana tÃ­pica para seleccionar archivos
        paths, _ = QFileDialog.getOpenFileNames(self, "Select recordings", "", self._dialog_filter())
        if not paths:
            return
        self._clear_loaded_state() # Borramos del state cualquier archivo cargado antes
        self.files.clear()
        self.files.addItems([Path(path).name for path in paths]) # AÃ±adimos solo los nombres de los archivos, no el path completo
        self.metadata_panel.hide()
        self.status_label.setText(f"Reading {len(paths)} recording(s)...")
        self.status_label.setProperty("status", "idle")
        self._refresh_status_style()
        self.changed.emit() # avisamos al WorkflowShell
        self.select_button.setEnabled(False)
        self.overlay.show_loading("Reading recordings...")

        # Creamos el worker y la tarea que va a ejecutar es la de _load_files
        worker = Worker(_load_files, self.loader, paths)
        # Cuando el worker informe del progreso, actualizamos la barra de overlay
        worker.signals.progress.connect(self.overlay.progress.setValue)
        worker.signals.result.connect(self._loaded) # Todo: tengo que mirar esto
        worker.signals.error.connect(self._failed) # Todo: tengo que mirar esto
        worker.signals.finished.connect(self._finished_loading)
        self.runner.start(worker) # Lanzamos el worker

    def _dialog_filter(self) -> str:
        # FunciÃ³n que construye el filtro del diÃ¡logo de archivos.
        extensions = self.config.get("allowed_extensions", [".edf"])
        patterns = " ".join(f"*{extension}" for extension in extensions)
        return f"Supported files ({patterns});;All files (*.*)"

    def _clear_loaded_state(self) -> None:
        # Delete from state files loaded previously
        self.state["loaded_file_paths"] = []
        self.state["loader_results"] = []
        self.state["metadata_list"] = []
        self.state.pop("loaded_file_path", None)
        self.state.pop("loader_result", None)
        self.state.pop("metadata", None)

    def _loaded(self, results: list[dict]) -> None:
        # Esta funciÃ³n se ejecuta cuando el worker terminÃ³ correctamente. Recibe results, que es la lista de
        # resultados del loader, y convierte cada resultado del loader en un metadata summary.
        # AdemÃ¡s, guarda un montÃ³n de cosas en el state.

        # Convertimos cada resultado del loader en un objeto MetadataSummary.
        metadata_list = [MetadataSummary.from_loader_result(result) for result in results]
        self.state["loaded_file_paths"] = [result.get("path") for result in results]
        self.state["loader_results"] = results
        self.state["metadata_list"] = metadata_list
        self.state.pop("loaded_file_path", None)
        self.state.pop("loader_result", None)
        self.state.pop("metadata", None)
        self.status_label.setText(f"{len(results)} recording(s) loaded successfully.")
        self.status_label.setProperty("status", "ready")
        self._refresh_status_style()
        self._show_metadata(metadata_list)
        # Avisamos al WorkflowShell. DespuÃ©s de cargar bien, can_continue() devolverÃ¡ True, entonces el botÃ³n
        # Next podrÃ¡ activarse.
        self.changed.emit()

    def _failed(self, error: str) -> None:
        # Se ejecuta si la carga falla, muestra solo la primera lÃ­nea del error y cambia el estado visual a error.
        self.status_label.setText(error.splitlines()[0])
        self.status_label.setProperty("status", "error")
        self._refresh_status_style()

    def _finished_loading(self) -> None:
        # Se ejecuta al final, tanto si hubo Ã©xito como error. Oculta el overlay y vuelve a activar el botÃ³n de
        # seleccionar archivos.
        self.overlay.hide()
        self.select_button.setEnabled(True)

    def _refresh_status_style(self) -> None:
        # FunciÃ³n para forzar a Qt a recalcular el estilo del label porque estamos usando propiedades dinÃ¡micas.
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _show_metadata(self, metadata_list: list[MetadataSummary]) -> None:
        # FunciÃ³n para pintar los metadatos en el panel
        # Primero limpia los metadatos anteriores porque, por ejemplo si antes cargamos 2 archivos y ahora 3, no
        # queremos que se mezclen los datos viejos con los nuevos.

        while self.metadata_layout.count():
            item = self.metadata_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Creamos un conjunto con las frecuencias de muestreo
        sampling_rates = {metadata.sampling_rate for metadata in metadata_list if metadata.sampling_rate is not None}
        sampling_rate = (f"{next(iter(sampling_rates)):g} Hz" if len(sampling_rates) == 1
            else "Mixed") # TODO: que muestre que archivos tienen diferentes y que si sample_rate estÃ¡ vacÃ­o
        # todo muestre "-" en vez de "Mixed"
        # Creamos una lista con el nÂº de canales de cada archivo
        channel_counts = [len(metadata.channels) for metadata in metadata_list]
        # Si todos tienen el mismo nÃºmero, ponemos X canales; si varÃ­an ponemos X-Y per file
        channel_count = (str(channel_counts[0]) if len(set(channel_counts)) == 1
            else f"{min(channel_counts)}-{max(channel_counts)} per file")
        # Suma la duraciÃ³n de todos los registros
        duration = sum(metadata.duration_seconds or 0.0 for metadata in metadata_list)
        # Suma el nÂº de muestras
        samples = sum(metadata.n_samples or 0 for metadata in metadata_list)
        # Lista de canales Ãºnicos
        channels = list(dict.fromkeys(channel for metadata in metadata_list for channel in metadata.channels))
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
        # Recuerda de WorkflowShell hace lo de if hasattr(widget, "can_continue"). Hasta que no haya una carga vÃ¡lida,
        # el Next queda deshabilitado.
        return bool(self.state.get("metadata_list"))

