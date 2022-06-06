
import sys

from qtpy.QtWidgets import QApplication, QStyleFactory
from qtpy.QtCore import Qt, QFile, QIODevice

from deploy_tool import DeployToolWindow
from util import theme_manager, settings_manager

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

import qtpy
api = ""
if qtpy.PYSIDE2:
    api = "pyside2"
elif qtpy.PYSIDE6:
    api = "pyside6"
else:
    raise Exception("PyQt is not supported. Run using PySide2 or PySide6!")

if api == "pyside2":
    try:
        # Older versions of QT5 may not support this
        # Only needed on QT5. Default on QT6.
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except:
        pass

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
