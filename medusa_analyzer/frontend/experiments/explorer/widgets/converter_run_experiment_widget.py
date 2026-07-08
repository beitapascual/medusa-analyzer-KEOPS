from PySide6.QtWidgets import QWidget
from medusa_analyzer.frontend.widgets.run_experiment import RunExperimentWidget

class ConverterRunExperimentWidget(RunExperimentWidget):
    """
    A specific run experiment widget for the converter experiment.
    It inherits from the general RunExperimentWidget and can be
    extended with specific functionalities for the converter.
    """
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__(
            title="Hola",
            description="Hola amigo que tal.",
        )
        self.setObjectName("converterRunExperimentWidget")

        
        # The log_area and progress_bar are already created in the parent class.
        # You can access them via self.log_area and self.progress_bar.
        self.add_log_message("Converter experiment runner initialized.")

    def run_conversion_process(self):
        """
        A placeholder method to demonstrate how you might run a process
        and update the UI.
        """
        self.clear_logs()
        self.add_log_message("Starting conversion...")
        self.set_progress(0)

        # Simulate a process using the state data if needed
        # For example: files_to_process = self.state.get("files", [])

        import time
        for i in range(101):
            time.sleep(0.05) # Simulate work
            self.set_progress(i)
            if i % 10 == 0:
                self.add_log_message(f"Processing step {i//10}...")
        
        self.add_log_message("Conversion finished successfully!", role="info")
