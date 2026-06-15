from .categories import DashboardCategory, DashboardItem


def get_dashboard_categories() -> list[DashboardCategory]:
    return [
        DashboardCategory("processing", "Processing", "Prepare signals for robust analysis.", 10),
        DashboardCategory("visualization", "Visualization", "Explore signals and derived measures.", 20),
    ]


def get_dashboard_items() -> list[DashboardItem]:
    return [
        DashboardItem(
            id="eeg-processing",
            category_id="processing",
            title="EEG",
            subtitle="Brain signal analysis and processing.",
            icon_path="frontend/assets/icons/eeg_icon.png",
            route="eeg",
            status="Ready",
            accent="burgundy",
        ),
        DashboardItem(
            id="ecg-processing",
            category_id="processing",
            title="ECG",
            subtitle="Heart signal analysis and processing.",
            icon_path="frontend/assets/icons/ecg_icon.png",
            route="ecg",
            status="Coming soon",
            accent="burgundy",
            enabled=False,
        ),
        DashboardItem(
            id="time-plot",
            category_id="visualization",
            title="TIMEPLOT",
            subtitle="Time plot of processed signals",
            icon_path="frontend/assets/icons/timeplot_icon.png",
            route="timeplot",
            status="Coming soon",
            accent="burgundy",
            enabled=False,
        ),

    ]
