from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from medusa_analyzer.frontend.navigator import Navigator
from medusa_analyzer.frontend.widgets.step_progress_bar import StepProgressBar


class WorkflowShell(QWidget):
    dashboard_requested = Signal()

    def __init__(self, title: str, subtitle: str, steps: list[dict[str, Any]], state: dict[str, Any]):
        super().__init__()
        self.title = title
        self.subtitle = subtitle
        self.steps = steps
        self.state = state

        root = QVBoxLayout(self)
        root.setContentsMargins(34, 22, 34, 28)
        root.setSpacing(16)

        top = QHBoxLayout()
        back_to_dashboard = QPushButton("Back to dashboard")
        back_to_dashboard.setProperty("variant", "ghost")
        back_to_dashboard.clicked.connect(self.dashboard_requested)
        context = QLabel(title.upper())
        context.setObjectName("eyebrow")
        top.addWidget(back_to_dashboard)
        top.addStretch()
        top.addWidget(context)
        root.addLayout(top)

        page_title = QLabel(title)
        page_title.setObjectName("pageTitle")
        root.addWidget(page_title)
        if subtitle:
            page_subtitle = QLabel(subtitle)
            page_subtitle.setObjectName("muted")
            page_subtitle.setWordWrap(True)
            root.addWidget(page_subtitle)

        self.stepper = StepProgressBar([step["title"] for step in steps])
        root.addWidget(self.stepper)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(divider)

        self.stack = QStackedWidget()
        self.navigator = Navigator(self.stack)
        for step in steps:
            widget = step["widget"]
            self.navigator.add_page(widget)
            changed_signal = getattr(widget, "changed", None)
            if changed_signal is not None:
                changed_signal.connect(self._refresh_navigation)
        root.addWidget(self.stack, 1)

        actions = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.setProperty("variant", "ghost")
        self.back_button.clicked.connect(self._go_back)
        self.next_button = QPushButton("Next")
        self.next_button.setProperty("variant", "primary")
        self.next_button.clicked.connect(self._go_next)
        actions.addWidget(self.back_button)
        actions.addStretch()
        actions.addWidget(self.next_button)
        root.addLayout(actions)

        self._activate_current_step()
        self._refresh_navigation()

    def _go_back(self) -> None:
        if self.navigator.current_index() == 0:
            self.dashboard_requested.emit()
            return
        self.navigator.back()
        self._activate_current_step()
        self._refresh_navigation()

    def _go_next(self) -> None:
        if not self._current_step_can_continue():
            return
        if self.navigator.current_index() == self.navigator.count() - 1:
            self.dashboard_requested.emit()
            return
        self.navigator.next()
        self._activate_current_step()
        self._refresh_navigation()

    def _current_step_can_continue(self) -> bool:
        widget = self.navigator.current_widget()
        if hasattr(widget, "can_continue"):
            return bool(widget.can_continue())
        return True

    def _activate_current_step(self) -> None:
        widget = self.navigator.current_widget()
        if hasattr(widget, "on_step_activated"):
            widget.on_step_activated()

    def _refresh_navigation(self) -> None:
        current = self.navigator.current_index()
        states = []
        for index in range(len(self.steps)):
            if index < current:
                states.append("completed")
            elif index == current:
                states.append("active")
            else:
                states.append("locked")
        self.stepper.set_states(states)
        self.back_button.setText("Back" if current > 0 else "Dashboard")
        self.next_button.setText("Finish" if current == len(self.steps) - 1 else "Next")
        self.next_button.setEnabled(self._current_step_can_continue())
