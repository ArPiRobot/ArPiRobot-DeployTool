
from typing import Optional
from PySide6.QtCore import QFile, QIODevice, Qt
from PySide6.QtWidgets import QDialog, QMainWindow, QWidget
from ui_deploy_tool import Ui_DeployTool
from about_dialog import AboutDialog
from settings_dialog import SettingsDialog
from util import settings_manager, theme_manager


class DeployToolWindow(QMainWindow):

    ############################################################################
    # General UI
    ############################################################################

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)

        # UI setup
        self.ui = Ui_DeployTool()
        self.ui.setupUi(self)

        # self.ui.pnl_readonly_status.setObjectName("readonly")
        # self.ui.pnl_readonly_status.style().unpolish(self.ui.pnl_readonly_status)
        # self.ui.pnl_readonly_status.style().polish(self.ui.pnl_readonly_status)

        self.ui.tabs_main.setTabEnabled(2, False)
        self.ui.tabs_main.setTabEnabled(3, False)
        self.ui.tabs_main.setTabEnabled(4, False)
        self.ui.tabs_main.setTabEnabled(5, False)

        # Append version to about label
        version_file = QFile(":/version.txt")
        if version_file.open(QIODevice.ReadOnly):
            ver = bytes(version_file.readLine()).decode().replace("\n", "").replace("\r", "")
            self.setWindowTitle(self.windowTitle() + " v" + ver)
        version_file.close()

        # Signal / Slot setup
        self.ui.act_settings.triggered.connect(self.open_settings)
        self.ui.act_about.triggered.connect(self.open_about)

    def open_settings(self):
        dialog = SettingsDialog(self)
        res = dialog.exec()
        if res == QDialog.Accepted:
            dialog.save_settings()
            theme_manager.apply_theme(settings_manager.theme, settings_manager.larger_fonts)

    def open_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    ############################################################################
    # This PC tab
    ############################################################################


    ############################################################################
    # Robot connection tab
    ############################################################################



    ############################################################################
    # Robot program tab
    ############################################################################


    ############################################################################
    # Robot program log tab
    ############################################################################


    ############################################################################
    # Robot status tab
    ############################################################################


    ############################################################################
    # Network settings tab
    ############################################################################


    ############################################################################
    # Camera streaming tab
    ############################################################################
