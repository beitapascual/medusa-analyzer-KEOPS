from medusa_analyzer.frontend.widgets import PreprocessingWidget


class EEGPreprocessingWidget(PreprocessingWidget):
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__(
            config=defaults.get("preprocessing", {}),
            state=state,
            title="Pre-processing",
            description="Tune the defaults that will be applied to the EEG recording. This step is intentionally simple and does not run advanced validation layers.",
        )
