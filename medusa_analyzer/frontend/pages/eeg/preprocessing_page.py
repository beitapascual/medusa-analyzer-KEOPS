from dataclasses import asdict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

from medusa_analyzer.backend.configs.filters import FilterConfig
from medusa_analyzer.backend.filters.response import compute_filter_response
from medusa_analyzer.backend.validation.engine import ValidationEngine
from medusa_analyzer.backend.validation.models import ValidationContext, ValidationReport
from medusa_analyzer.backend.workflows.eeg_state import EEGWorkflowState
from medusa_analyzer.frontend.widgets.filter_preview_plot import FilterPreviewPlot
from medusa_analyzer.frontend.widgets.frequency_band_editor import FrequencyBandEditor
from medusa_analyzer.frontend.widgets.validation_panel import ValidationPanel


class FilterControls(QFrame):
    changed = Signal()

    def __init__(self, title: str, config: FilterConfig):
        super().__init__()
        self.config = config
        self.setProperty("role", "filter-controls")
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        self.enabled = QCheckBox(title)
        self.enabled.setObjectName("controlTitle")
        self.enabled.setChecked(config.enabled)
        root.addWidget(self.enabled)
        grid = QGridLayout()
        self.low = self._double(config.low_cut)
        self.high = self._double(config.high_cut)
        self.kind = QComboBox()
        self.kind.addItems(["FIR", "IIR"])
        self.kind.setCurrentText(config.filter_type.upper())
        grid.addWidget(QLabel("Low cut"), 0, 0)
        grid.addWidget(self.low, 1, 0)
        grid.addWidget(QLabel("High cut"), 0, 1)
        grid.addWidget(self.high, 1, 1)
        grid.addWidget(QLabel("Type"), 0, 2)
        grid.addWidget(self.kind, 1, 2)
        root.addLayout(grid)
        self.parameters = QStackedWidget()
        fir = QWidget()
        fir_layout = QGridLayout(fir)
        fir_layout.setContentsMargins(0, 4, 0, 0)
        self.fir_order = QSpinBox()
        self.fir_order.setRange(3, 99999)
        self.fir_order.setSingleStep(2)
        self.fir_order.setValue(config.fir_order)
        self.window = QComboBox()
        self.window.addItems(["Hamming", "Hann", "Blackman"])
        self.window.setCurrentText(config.fir_window.title())
        fir_layout.addWidget(QLabel("FIR order"), 0, 0)
        fir_layout.addWidget(QLabel("Window"), 0, 1)
        fir_layout.addWidget(self.fir_order, 1, 0)
        fir_layout.addWidget(self.window, 1, 1)
        iir = QWidget()
        iir_layout = QGridLayout(iir)
        iir_layout.setContentsMargins(0, 4, 0, 0)
        self.iir_order = QSpinBox()
        self.iir_order.setRange(1, 20)
        self.iir_order.setValue(config.iir_order)
        self.design = QComboBox()
        self.design.addItem("Butterworth")
        iir_layout.addWidget(QLabel("IIR order"), 0, 0)
        iir_layout.addWidget(QLabel("Design"), 0, 1)
        iir_layout.addWidget(self.iir_order, 1, 0)
        iir_layout.addWidget(self.design, 1, 1)
        self.parameters.addWidget(fir)
        self.parameters.addWidget(iir)
        root.addWidget(self.parameters)
        self.controls = [self.low, self.high, self.kind, self.fir_order, self.window, self.iir_order, self.design]
        self.enabled.toggled.connect(self._sync)
        self.kind.currentTextChanged.connect(self._sync)
        for control in (self.low, self.high):
            control.valueChanged.connect(self._sync)
        for control in (self.fir_order, self.iir_order):
            control.valueChanged.connect(self._sync)
        self.window.currentTextChanged.connect(self._sync)
        self.design.currentTextChanged.connect(self._sync)
        self._sync()

    @staticmethod
    def _double(value):
        spin = QDoubleSpinBox()
        spin.setRange(0, 10000)
        spin.setDecimals(1)
        spin.setValue(value)
        spin.setSuffix(" Hz")
        return spin

    def _sync(self):
        self.config.enabled = self.enabled.isChecked()
        self.config.low_cut = self.low.value()
        self.config.high_cut = self.high.value()
        self.config.filter_type = self.kind.currentText().lower()
        self.config.fir_order = self.fir_order.value()
        self.config.fir_window = self.window.currentText().lower()
        self.config.iir_order = self.iir_order.value()
        self.config.iir_design = self.design.currentText().lower()
        self.parameters.setCurrentIndex(0 if self.config.filter_type == "fir" else 1)
        for control in self.controls:
            control.setEnabled(self.config.enabled)
        self.changed.emit()


class PreprocessingPage(QScrollArea):
    validity_changed = Signal(bool)
    next_requested = Signal()
    back_requested = Signal()

    def __init__(self, state: EEGWorkflowState):
        super().__init__()
        self.state = state
        self.engine = ValidationEngine()
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(4, 4, 12, 4)
        title = QLabel("Preprocessing")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Configure referencing, filters and analysis bands. Every enabled setting is validated against the recording metadata.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(16)

        car_panel = QFrame()
        car_panel.setProperty("role", "surface-panel")
        car_layout = QVBoxLayout(car_panel)
        self.car = QCheckBox("Apply common average reference (CAR)")
        self.car.setChecked(state.preprocessing_config.apply_car)
        self.car.toggled.connect(self._validate)
        car_layout.addWidget(self.car)
        root.addWidget(car_panel)

        columns = QHBoxLayout()
        controls_column = QVBoxLayout()
        self.notch = FilterControls("Notch filter", state.preprocessing_config.notch)
        self.bandpass = FilterControls("Bandpass filter", state.preprocessing_config.bandpass)
        controls_column.addWidget(self.notch)
        controls_column.addWidget(self.bandpass)
        columns.addLayout(controls_column, 5)
        plots = QVBoxLayout()
        for label, attribute in (
            ("Notch filter response", "notch_plot"), ("Bandpass filter response", "bandpass_plot")
        ):
            panel = QFrame()
            panel.setProperty("role", "surface-panel")
            panel_layout = QVBoxLayout(panel)
            heading = QLabel(label)
            heading.setObjectName("panelTitle")
            plot = FilterPreviewPlot()
            setattr(self, attribute, plot)
            panel_layout.addWidget(heading)
            panel_layout.addWidget(plot)
            plots.addWidget(panel)
        columns.addLayout(plots, 7)
        root.addLayout(columns)

        bands_panel = QFrame()
        bands_panel.setProperty("role", "surface-panel")
        bands_layout = QVBoxLayout(bands_panel)
        bands_title = QLabel("Frequency bands")
        bands_title.setObjectName("panelTitle")
        bands_layout.addWidget(bands_title)
        self.bands = FrequencyBandEditor(state.preprocessing_config.frequency_bands)
        bands_layout.addWidget(self.bands)
        root.addWidget(bands_panel)
        self.validation = ValidationPanel()
        root.addWidget(self.validation)
        actions = QHBoxLayout()
        back = QPushButton("Back")
        back.setProperty("variant", "ghost")
        back.clicked.connect(self.back_requested)
        self.next_button = QPushButton("Continue to features")
        self.next_button.setProperty("variant", "primary")
        self.next_button.clicked.connect(self.next_requested)
        actions.addWidget(back)
        actions.addStretch()
        actions.addWidget(self.next_button)
        root.addLayout(actions)
        self.setWidget(content)
        self.notch.changed.connect(self._validate)
        self.bandpass.changed.connect(self._validate)
        self.bands.changed.connect(self._validate)
        self._validate()

    def _validate(self):
        config = self.state.preprocessing_config
        config.apply_car = self.car.isChecked()
        metadata = self.state.metadata
        nyquist = metadata.nyquist if metadata else 500.0
        fs = metadata.fs if metadata else 1000.0
        bandpass_low = config.bandpass.low_cut if config.bandpass.enabled else 0.0
        bandpass_high = config.bandpass.high_cut if config.bandpass.enabled else nyquist
        context = ValidationContext(fs, nyquist, bandpass_low, bandpass_high)
        report = ValidationReport()
        report.extend(self.engine.validate("notch_filter", config.notch, context))
        report.extend(self.engine.validate("bandpass_filter", config.bandpass, context))
        for band in config.frequency_bands:
            report.extend(self.engine.validate("frequency_band", band, context))
        self.state.validation_report = report
        self.validation.set_report(report)
        self.next_button.setEnabled(report.is_valid)
        self.validity_changed.emit(report.is_valid)
        notch_report = self.engine.validate("notch_filter", asdict(config.notch), context)
        bandpass_report = self.engine.validate("bandpass_filter", asdict(config.bandpass), context)
        if notch_report.is_valid:
            self.notch_plot.set_response(compute_filter_response(config.notch, fs))
        if bandpass_report.is_valid:
            self.bandpass_plot.set_response(compute_filter_response(config.bandpass, fs))
