
import sys
import platform
import multiprocessing
import os
import subprocess


from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtCore import Qt

from deploy_tool import DeployToolWindow

QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar)

# TODO: Stdout and Stderr redirect to log file (along with log data shown in DS log window)

try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("io.github.arpirobot.DeployTool") # type: ignore
except AttributeError:
    pass

app = None

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
        text_scale_factor = float(subprocess.check_output(["gsettings", "get", "org.gnome.desktop.interface", "text-scaling-factor"]))
        if 'QT_FONT_DPI' not in os.environ:
            os.environ['QT_FONT_DPI'] = str(int(text_scale_factor * 96))



app = QApplication(sys.argv)
app.setStyle("fusion")

# This method of associating desktop file with window works on both X11 and wayland
# See: https://bugreports.qt.io/browse/QTBUG-117772?jql=text%20~%20%22wmclass%22
app.setDesktopFileName("io.github.arpirobot.DeployTool")
app.setApplicationName("io.github.arpirobot.DeployTool")

# Theme fixes (only needed for dark theme; light always works properly)
if app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
    if platform.system() == "Windows":
        # Somehow, this fixes checkboxes being blue on windows dark theme.
        # Not really sure why, but it does.
        p = app.palette()
        for cg in [QPalette.ColorGroup.Active, QPalette.ColorGroup.Current, QPalette.ColorGroup.Disabled, QPalette.ColorGroup.Inactive]:
            p.setColor(cg, QPalette.ColorRole.Base, p.color(cg, QPalette.ColorRole.Base))
        app.setPalette(p)

dt = DeployToolWindow()

dt.show()
app.exec()
