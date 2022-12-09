
import sys
import platform
import multiprocessing
import os
import subprocess


from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt, QFile, QIODevice, QEventLoop

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

# Fix gnome wayland things
if platform.system() == "Linux":
    # QGuiApplication.platformName() is empty until app instantiated
    # So need to create app first, but need to change things before app create
    # Logical solution is to create app, read platform, then destroy app
    # But this is impossible with PySide...
    # And multiple apps is not allowed
    # So instead, use a subprocess. Killing subprocess kills it's app
    def mp_target(argv, return_dict):
        tmp = QApplication(argv)
        return_dict['plat_name'] = QGuiApplication.platformName()
        tmp.quit()
    manager = multiprocessing.Manager()
    return_dict = manager.dict()
    p = multiprocessing.Process(target=mp_target, daemon=True, args=(sys.argv, return_dict))
    p.start()
    p.join()
    plat_name = return_dict['plat_name']
    if plat_name == "wayland" and os.environ['XDG_CURRENT_DESKTOP'].find("GNOME") != -1:
        # Running with wayland platform plugin in a gnome session
        cursor_size = int(subprocess.check_output(["gsettings", "get", "org.gnome.desktop.interface", "cursor-size"]))
        text_scale_factor = float(subprocess.check_output(["gsettings", "get", "org.gnome.desktop.interface", "text-scaling-factor"]))
        cursor_theme = subprocess.check_output(["gsettings", "get", "org.gnome.desktop.interface", "cursor-theme"]).decode()
        if 'QT_FONT_DPI' not in os.environ:
            os.environ['QT_FONT_DPI'] = str(int(text_scale_factor * 96))
        if 'XCURSOR_SIZE' not in os.environ:
            os.environ['XCURSOR_SIZE'] = str(cursor_size)
        if 'XCURSOR_THEME' not in os.environ:
            os.environ['XCURSOR_THEME'] = cursor_theme[1:-2]


# Nothing special for app creation needed. Create as usual.
if app is None:
    app = QApplication(sys.argv)

theme_manager.set_app(app)
theme_manager.apply_theme(settings_manager.theme, settings_manager.larger_fonts)

dt = DeployToolWindow()

dt.show()
app.exec()
