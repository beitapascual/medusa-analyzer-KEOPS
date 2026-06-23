from medusa_analyzer.frontend.widgets import FeaturesWidget


class EEGFeaturesWidget(FeaturesWidget):
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__(
            config=defaults.get("features", {}),
            state=state,
            title="Features",
            description="Pick the feature blocks that should appear in the EEG processing configuration.")
