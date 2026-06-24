from __future__ import annotations
from typing import Any
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget
from medusa_analyzer.frontend.models import MetadataSummary


class ReportWidget(QScrollArea):
    # Clase para montar la estructura general del report, poniendo el título y el subtítulo, y luego
    # metiendo "secciones". La sección de metadata es general, pero luego se meten secciones dependientes del experimento
    def __init__(self, config: dict[str, Any], state: dict[str, Any], title: str, description: str):
        super().__init__()
        self.config = config # para ver qué secciones hay que mostrar
        self.state = state # estado compartido del workflow
        self.title_text = title # título del report
        self.description_text = description # subtítulo del report
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.content = QWidget()
        self.root = QVBoxLayout(self.content)
        self.root.setContentsMargins(4, 4, 12, 4)
        self.root.setSpacing(16)
        self.setWidget(self.content)
        self.refresh() # dibujamos el report por primera vez

    def on_step_activated(self) -> None:
        # Métoodo que cuando el workflow entra en este paso, vuelve a regenerar el report potque puede ser que el usuario
        # cambie cosas en pasos anteriores y vuelva a generar el report, entonces tiene que reflejar el estado nuevo.
        self.refresh()

    def refresh(self) -> None:
        # Borra el contenido actual del report y lo vuelve a construir desde el estado
        # Bucle para iterar por todos los elementos (widgets) y decir a Qt que los destruya.
        while self.root.count():
            item = self.root.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        title = QLabel(self.title_text) # Volvemos a crear el título
        title.setObjectName("pageTitle")
        subtitle = QLabel(self.description_text) # Volvemos a crear el subtítulo
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        self.root.addWidget(title)
        self.root.addWidget(subtitle)

        # Bucle para ir añadiendo las diferentes secciones en el report.
        for section in self._sections():
            if section is not None:
                self.root.addWidget(section)

        self.root.addStretch()

    def _sections(self) -> list[QWidget]:
        # Métoodo que decide qué secciones tiene el report y en qué orden.
        sections: list[QWidget] = [] # lista vacía para guardar las secciones
        metadata_list = self.state.get("metadata_list") or [] # leemos metadata_list del estado
        if self.config.get("include_metadata", True):
            sections.append(self._metadata_section(metadata_list))

        if self.config.get("include_preprocessing_summary", True):
            preprocessing_section = self._preprocessing_section()
            if preprocessing_section is not None:
                sections.append(preprocessing_section)

        if self.config.get("include_selected_features", True):
            features_section = self._features_section()
            if features_section is not None:
                sections.append(features_section)

        # Esto permite añadir cualquier sección extra
        sections.extend(self._additional_section_builders())
        return sections

    def _section_builders(self) -> list:
        # Lista de funciones que construyen secciones.
        # La clase base solo conoce metadata. Las clases hijas añaden el resto.
        builders = []
        if self.config.get("include_metadata", True):
            builders.append(lambda: self._metadata_section(self.state.get("metadata_list") or []))
        builders.extend(self._additional_section_builders())
        return builders

    def _additional_section_builders(self) -> list:
        # ReportWidget solo define la estructura común del report.
        # Las secciones específicas del experimento se añaden desde las clases hijas mediante _additional_section_builders().
        return []

    def _metadata_section(self, metadata_list: list[MetadataSummary]) -> QFrame:
        # Métoodo para construir el panel de Metada
        if not metadata_list:
            return self._section("Metadata", [("Status", "No EDF loaded yet.")])
        # Mostramos la frecuencia de muestreo
        sampling_rates = {metadata.sampling_rate for metadata in metadata_list if metadata.sampling_rate is not None}
        sampling_rate = (f"{next(iter(sampling_rates)):g} Hz" if len(sampling_rates) == 1 else "Mixed")
        # Mostrar los canales sin duplicados
        channels = list(dict.fromkeys(channel for metadata in metadata_list for channel in metadata.channels))
        # LLamamos a _section() y le pasamos la información para que lo transforme en una tabla visual legible
        return self._section("Metadata",
            [("Files", ", ".join(metadata.file_name for metadata in metadata_list)),
                ("Paths", ", ".join(metadata.file_path for metadata in metadata_list)),
                ("Channels", ", ".join(channels)), ("Sampling rate", sampling_rate),
                ("Total duration", f"{sum(metadata.duration_seconds or 0 for metadata in metadata_list):g} s"),
                ("Total samples", str(sum(metadata.n_samples or 0 for metadata in metadata_list)))])

    def _section(self, title: str, rows: list[tuple[str, str]]) -> QFrame:
        # Constructor visual genérico de una sección a partir del t´tiulo, y la lista de pares (etiqueta, valor)
        panel = QFrame()
        panel.setProperty("role", "summary-section")
        layout = QGridLayout(panel)
        layout.setContentsMargins(24, 20, 24, 20)
        heading = QLabel(title) # título de la sección
        heading.setObjectName("panelTitle")
        layout.addWidget(heading, 0, 0, 1, 2)
        # Recorremos cada fila
        for row_index, (label, value) in enumerate(rows, start=1):
            key = QLabel(label)
            key.setObjectName("summaryLabel")
            detail = QLabel(value)
            detail.setWordWrap(True)
            layout.addWidget(key, row_index, 0)
            layout.addWidget(detail, row_index, 1)
        layout.setColumnStretch(1, 1)
        return panel
