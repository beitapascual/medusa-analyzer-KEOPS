from typing import Optional
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QHBoxLayout,
                               QFileDialog, QMessageBox, QSpacerItem, QSizePolicy)

from medusa.core.data.recording import Recording
from medusa.widgets import RecordingInspectorWindow


# Deberás importar tu función real de carga de datos, por ejemplo:
# from medusa.io import load_recording_from_file

class ExplorerExploreFileWidget(QWidget):
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__()

        self.allowed_extensions = defaults['load_data']['allowed_extensions']

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("Load Recording...")
        button.setProperty("variant", "secondary")
        button.clicked.connect(self._on_load_button_clicked)
        button_layout.addWidget(button)
        self.main_layout.addLayout(button_layout)

        # Crear espaciador vertical expansivo
        vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.main_layout.addSpacerItem(vertical_spacer)

        self.inspector_window: Optional[RecordingInspectorWindow] = None

    def _on_load_button_clicked(self) -> None:
        """Abre un diálogo para seleccionar el archivo y lo carga."""
        # Formateamos la lista para asegurar que cada extensión tenga el prefijo "*."
        # Esto funciona tanto si la lista tiene ['.medusa', '.bdf'] como ['medusa', 'bdf']
        extensions_str = " ".join([f"*{ext}" if ext.startswith(".") else f"*.{ext}" for ext in self.allowed_extensions])

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            caption="Select MEDUSA File",
            dir="",
            filter=f"Data Files ({extensions_str});;All Files (*)"
        )

        # Si el usuario cierra la ventana sin seleccionar nada, salimos
        if not file_path:
            return

        try:
            rec = Recording.load(file_path)

            # 3. Inicializar el inspector con los datos cargados
            self.load_recording(rec)

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Could not load file:\n{e}")

    def load_recording(self, recording: Recording) -> None:
        """Inicializa y emebe el inspector utilizando el objeto Recording."""
        if self.inspector_window is not None:
            self.main_layout.removeWidget(self.inspector_window)
            self.inspector_window.deleteLater()

        self.inspector_window = RecordingInspectorWindow(recording)
        self.inspector_window.setWindowFlags(Qt.Widget)
        self.inspector_window.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Insertar el widget en el layout
        self.main_layout.insertWidget(1, self.inspector_window)

        # Asignar un factor de estiramiento alto (1) al índice donde se insertó el inspector
        # Esto forzará al widget a expandirse y aplastará al espaciador vertical
        self.main_layout.setStretch(1, 1)

        if hasattr(self.inspector_window, 'widget'):
            # Ocultar los botones inferiores sin eliminarlos de memoria
            self.inspector_window.widget._apply_btn.hide()
            self.inspector_window.widget._revert_btn.hide()

            # Conexión de señales
            self.inspector_window.widget.dirty.connect(self._on_dirty_state_changed)
            self.inspector_window.widget.validated.connect(self._on_validation_completed)
            self.inspector_window.widget.applied.connect(self._on_changes_applied)

    # --- Callbacks de señales ---

    def _on_dirty_state_changed(self, is_dirty: bool) -> None:
        pass

    def _on_validation_completed(self, issues: list) -> None:
        pass

    def _on_changes_applied(self, recording: Recording) -> None:
        pass