import sys
import logging
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from medusa_analyzer.frontend.dashboard import DashboardPage, build_dashboard_catalog
from medusa_analyzer.frontend.experiments import create_experiment_page, discover_experiments
from medusa_analyzer.frontend.router import Router

logger = logging.getLogger(__name__) # logger para que cuando haya un error sea vea de dónde viene

# Punto de entrada visual de tu aplicación: crea la ventana principal, carga los experimentos disponibles,
# monta el dashboard, registra rutas y arranca Qt. NOTA IMPORTANTE: el addWidget al stackWidget se hace dentro
# del router
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Medusa Analyzer")
        self.resize(1200, 800)
        self.setMinimumSize(1020, 700)

        stack = QStackedWidget() # Creamos el stackWidget, que es el contenedor principal de páginas
        self.setCentralWidget(stack)
        # Creamos un router y le pasamos el stack. El router usará ese stack para registrar páginas y cambiar entre ellas
        self.router = Router(stack)

        self.experiments = [] # aquí se guardan los experimentos que hay definidos
        self.pages = {} # diccionario para guardas las páginas de cada experimento
        # Buscamos todos los experimentos disponibles y los recorremos uno a uno
        for definition in discover_experiments():
            try:
                # Creamos el WorkflowShell con los widget del experimento
                page = create_experiment_page(definition)
            except Exception as exc:
                logger.exception("Skipping experiment '%s': %s", definition.id, exc)
                continue
            self.experiments.append(definition)
            self.pages[definition.route] = page # Guardamos todas las páginas de experimentos bajo la key de la ruta

        categories, items = build_dashboard_catalog(self.experiments)
        # Creamos el dashboard con las categorías y los items detectados
        self.dashboard = DashboardPage(categories, items)
        # Conectamos una señal del dashboard con el router. Por ejemplo, cuando el dashboard emita
        # 'route_requested.emit("experiments/eeg")', se ejecutará 'self.router.navigate("experiments/eeg")'.
        # O sea, al hacer click en un experimento, navega a esa página.
        self.dashboard.route_requested.connect(self.router.navigate)

        # Registramos la página dashboard en el router con la ruta "dashboard". Después se podrá hacer
        #'self.router.navigate("dashboard")'
        self.router.register("dashboard", self.dashboard)

        for route, page in self.pages.items():
            self.router.register(route, page) # Registramos cada página del experimento en el router
            # Conectamos la señal de dashboard_dequested de cada página del workflow con volver al dashboard
            page.dashboard_requested.connect(lambda: self.router.navigate("dashboard"))
        self.router.navigate("dashboard") # Navegamos al dashboard para empezar ahí


def _load_stylesheet() -> str:
    # Función para cargar los estilos
    path = Path(__file__).resolve().parent / "styles" / "main.qss"
    return path.read_text(encoding="utf-8").replace("${STYLE_DIR}", path.parent.as_posix())


def run() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Medusa Analyzer KEOPS") # Ponemos el nombre de la aplicación
    app.setOrganizationName("Medusa BCI")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(_load_stylesheet()) # Carga el QSS y se lo aplicamos a toda la aplicación
    # Ejecutamos toodo el constructor de la MainWidow (crear el stack, router, descubrir experimentos, crear páginas,
    # registrar rutas y navegar al dashboard.
    window = MainWindow()
    window.show()
    return app.exec()
