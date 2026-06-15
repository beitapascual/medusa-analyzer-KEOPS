from medusa_analyzer.frontend.widgets import ReportWidget


class EEGReportWidget(ReportWidget):
    def __init__(self, experiment_info: dict, defaults: dict, state: dict):
        super().__init__(
            config=defaults.get("report", {}),
            state=state,
            title="Final report",
            description="Review the metadata, pre-processing selections and chosen features before handing this experiment to the future processing pipeline.",
        )
