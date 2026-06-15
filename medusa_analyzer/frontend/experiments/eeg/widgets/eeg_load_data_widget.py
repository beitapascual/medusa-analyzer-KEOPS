from medusa_analyzer.backend.io import load_edf_file
from medusa_analyzer.frontend.widgets import LoadDataWidget


class EEGLoadDataWidget(LoadDataWidget):
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__(
            config=defaults.get("load_data", {}),
            state=state,
            loader=load_edf_file,
            title="Load EEG data",
            description="Select one EDF file to inspect its metadata before configuring the workflow.",
        )
