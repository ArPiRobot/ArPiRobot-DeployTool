
import sys

from qtpy.QtWidgets import QApplication, QStyleFactory
from qtpy.QtCore import Qt, QFile, QIODevice

from deploy_tool import DeployToolWindow
from util import theme_manager, settings_manager

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
QApplication.setAttribute(Qt.AA_DontUseNativeMenuBar)

# TODO: Stdout and Stderr redirect to log file (along with log data shown in DS log window)

try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.arpirobot.arpirobot-deploytool")
except AttributeError:
    pass

app = QApplication(sys.argv)
theme_manager.set_app(app)
theme_manager.apply_theme(settings_manager.theme, settings_manager.larger_fonts)

dt = DeployToolWindow()

dt.show()
app.exec_()
