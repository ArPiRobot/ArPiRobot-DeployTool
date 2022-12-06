
import sys
import platform

from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtCore import Qt, QFile, QIODevice

from deploy_tool import DeployToolWindow
from util import theme_manager, settings_manager

QApplication.setAttribute(Qt.AA_DontUseNativeMenuBar)

# TODO: Stdout and Stderr redirect to log file (along with log data shown in DS log window)

try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.arpirobot.arpirobot-deploytool")
except AttributeError:
    pass

app = None

# QT 6.4 introduced experimental support for dark mode on windows
# Note that the windows them is terrible for now, but Fusion looks good
if platform.system() == "Windows":
    import winreg
    path = winreg.HKEY_CURRENT_USER
    try:
        key = winreg.OpenKeyEx(path, r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize")
        value = winreg.QueryValueEx(key, r"AppsUseLightTheme")
        if value[0] == 0:
            # TODO: When QT 6.5 released, there should be better support for this
            #       Probably a new dark / light mode API
            #       Also windowsvista theme should support dark mode
            #       Will likely also be auto detected / applied
            #       In other words, all of this is probably removed with QT 6.5
            sys.argv += ['-platform', 'windows:darkmode=2']
            app = QApplication(sys.argv)
            app.setStyle("Fusion")
        if key:
            winreg.CloseKey(key)
    except:
        pass

# Nothing special for app creation needed
if app is None:
    app = QApplication(sys.argv)

theme_manager.set_app(app)
theme_manager.apply_theme(settings_manager.theme, settings_manager.larger_fonts)

dt = DeployToolWindow()

dt.show()
app.exec()
