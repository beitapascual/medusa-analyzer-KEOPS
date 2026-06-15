from dataclasses import dataclass


# Defines a conceptual category
@dataclass(frozen=True, slots=True)
class DashboardCategory:
    id: str
    title: str
    description: str
    order: int

# Defines items inside one category
@dataclass(frozen=True, slots=True)
class DashboardItem:
    id: str
    category_id: str
    title: str
    subtitle: str
    icon_path: str
    route: str
    status: str = "" # for example 'ready' or 'updating'
    accent: str = "burgundy"
    enabled: bool = True # if we can clisk or no
