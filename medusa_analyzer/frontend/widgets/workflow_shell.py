from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget)
from medusa_analyzer.frontend.navigator import Navigator
from medusa_analyzer.frontend.widgets.step_progress_bar import StepProgressBar

# Nota: create_experiment_page() crea los widgets y WorkflowShell los muestra y permite navegar entre ellos

class WorkflowShell(QWidget):
    # Se encarga de mostrar el título del experimento, el subtítulo, la barra de progreso, meter cada widget en una
    # pantalla, gestionar botones Back / Next / Finish, bloquear Next si el widget actual no permite continuar y avisar
    # cuando hay que volver al dashboard.

    dashboard_requested = Signal()

    # El constructor recibe exactamente lo que pasa create_experiment_page()
    def __init__(self, title: str, subtitle: str, steps: list[dict[str, Any]], state: dict[str, Any]):
        super().__init__()
        self.title = title
        self.subtitle = subtitle
        self.steps = steps
        self.state = state

        # Layout principal
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 22, 34, 28)
        root.setSpacing(16)

        top = QHBoxLayout()
        back_to_dashboard = QPushButton("Back to dashboard")
        back_to_dashboard.setProperty("variant", "ghost")
        back_to_dashboard.clicked.connect(self.dashboard_requested)
        context = QLabel(title.upper()) # Título pequeño de arriba
        context.setObjectName("eyebrow")
        top.addWidget(back_to_dashboard)
        top.addStretch()
        top.addWidget(context)
        root.addLayout(top)

        page_title = QLabel(title) # Título principal
        page_title.setObjectName("pageTitle")
        root.addWidget(page_title)
        if subtitle:
            page_subtitle = QLabel(subtitle) # Subtítulo
            page_subtitle.setObjectName("muted")
            page_subtitle.setWordWrap(True)
            root.addWidget(page_subtitle)

        self.stepper = StepProgressBar([step["title"] for step in steps]) # Barra con los títulos de los pasos
        root.addWidget(self.stepper)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(divider)

        self.stack = QStackedWidget() # StackWidget para los pasos del experimento
        self.navigator = Navigator(self.stack) # El navegador nos permité movernos por los diferentes steps
        for step in steps:
            widget = step["widget"]
            self.navigator.add_page(widget)

            # IMPORTANTE: Algunos widgets pueden tener una señal llamada changed. Por ejemplo, un widget de carga de
            # archivo puede tener changed = Signal() y cuando el usuario carga un archivo, el widget hace
            # self.changed.emit(). Entonces WorkflowShell refresca para actualizar botones, barra de progreso, etc.

            changed_signal = getattr(widget, "changed", None)
            if changed_signal is not None:
                changed_signal.connect(self._refresh_navigation)
        root.addWidget(self.stack, 1)

        actions = QHBoxLayout()

        # Botón para volver al dashboard
        self.back_button = QPushButton("Back to dashboard")
        self.back_button.setProperty("variant", "ghost")
        self.back_button.clicked.connect(self._go_back) # cuando se pulsa el botón, se emite la señal dashboard_requested
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
        # Si estamos en el primer paso, pulsar Back te lleva al dashboard
        if self.navigator.current_index() == 0:
            self.dashboard_requested.emit()
            return
        # Si no estamos en el primer paso, vamos al paso anterior
        self.navigator.back()
        # Después, actualizamos el paso actual y los botones
        self._activate_current_step()
        self._refresh_navigation()

    def _go_next(self) -> None:
        # Primero comprueba si se puede continuar. Si no se puede, no hace nada.
        if not self._current_step_can_continue():
            return
        # Si estamos en el último paso, pulsar Next significa terminar, así que vuelve al dashboard.
        if self.navigator.current_index() == self.navigator.count() - 1:
            self.dashboard_requested.emit()
            return
        # Si no estamos en el último paso, avanza al siguiente y actualiza la interfaz.
        self.navigator.next()
        self._activate_current_step()
        self._refresh_navigation()

    def _current_step_can_continue(self) -> bool:
        # Mira si el widget tiene métoodo de valiadación. Si el widget no tiene can_continue, entonces deja
        # avanzar por defeto
        widget = self.navigator.current_widget()
        if hasattr(widget, "can_continue"):
            return bool(widget.can_continue())
        return True

    def _activate_current_step(self) -> None:
        # Esta función se llama cuando se entra a un paso. Sirve para que un widget actualice su contenido
        # justo al mostrarse. Es útil para un paso de resultados, porque quizá necesita leer datos que se cargatron
        # en el paso anterior.
        widget = self.navigator.current_widget()
        if hasattr(widget, "on_step_activated"):
            widget.on_step_activated()

    def _refresh_navigation(self) -> None:
        # Función para actualizar la interfaz en función del paso

        current = self.navigator.current_index()
        states = []
        for index in range(len(self.steps)):
            if index < current:
                states.append("completed")
            elif index == current:
                states.append("active")
            else:
                states.append("locked")
        # Le pasa a la barra el estado de cada uno de los pasos para que pueda actualizarse
        self.stepper.set_states(states)
        self.back_button.setText("Back" if current > 0 else "Dashboard")
        self.next_button.setText("Finish" if current == len(self.steps) - 1 else "Next")
        self.next_button.setEnabled(self._current_step_can_continue())
