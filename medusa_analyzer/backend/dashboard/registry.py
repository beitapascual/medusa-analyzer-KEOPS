from .categories import DashboardCategory, DashboardItem


def get_dashboard_categories() -> list[DashboardCategory]:
    return [
        DashboardCategory("processing", "Processing", "Prepare signals for robust analysis.", 10),
        DashboardCategory("visualization", "Visualization", "Explore signals and derived measures.", 20),
        DashboardCategory("analysis", "Analysis", "Run reproducible biomedical analyses.", 30),
        DashboardCategory("export", "Export", "Package results for downstream workflows.", 40),
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
        )
    ]
