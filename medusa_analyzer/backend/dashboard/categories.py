from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DashboardCategory:
    id: str
    title: str
    description: str
    order: int


@dataclass(frozen=True, slots=True)
class DashboardItem:
    id: str
    category_id: str
    title: str
    subtitle: str
    icon_path: str
    route: str
    status: str = ""
    accent: str = "burgundy"
    enabled: bool = True
