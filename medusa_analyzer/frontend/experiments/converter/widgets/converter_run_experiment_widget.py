from medusa_analyzer.frontend.widgets.run_experiment import RunExperimentWidget
from medusa_analyzer.frontend.worker import Worker
from medusa_analyzer.backend.converter.run_conversion import run_conversion

class ConverterRunExperimentWidget(RunExperimentWidget):
    """Run step específico para el experimento de conversión."""

    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        # Inicializa la clase padre genérica con los parámetros necesarios
        super().__init__(experiment_info, defaults, state)

    def run_pipeline(self):
        """Start the converter pipeline in a background worker."""
        if self.pipeline_running:
            return

        self.pipeline_running = True
        self.state["completion_status"] = "incompleted"
        self.changed.emit()

        self.status_label.setText(f"Running {self.experiment_info['title']}...")
        self.clear_logs()
        self.log_callback(f"Starting {self.experiment_info['title']}...")
        self.set_progress(0)

        kwargs = {
            "input_data": self.state['input_data'],
            "output_path": self.state['output_path'],
            "extensions": self.defaults.get("load_data", {}).get("allowed_extensions", {}),
            "progress_callback": self.set_progress,
            "log_callback": self.log_callback
        }

        worker = Worker(run_conversion, **kwargs)
        worker.signals.progress.connect(self.set_progress)
        worker.signals.logging.connect(self.log_callback)
        worker.signals.result.connect(self._pipeline_completed)
        worker.signals.error.connect(self._pipeline_failed)
        worker.signals.finished.connect(self._pipeline_finished)
        self.runner.start(worker)