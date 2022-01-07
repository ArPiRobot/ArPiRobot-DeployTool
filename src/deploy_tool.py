
from typing import Optional
from PySide6.QtCore import QFile, QIODevice, QObject, Qt
from PySide6.QtWidgets import QDialog, QMainWindow, QMessageBox, QWidget
from ui_deploy_tool import Ui_DeployTool
from about_dialog import AboutDialog
from settings_dialog import SettingsDialog
from ssh_manager import SSHManager
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

        # Append version to about label
        version_file = QFile(":/version.txt")
        if version_file.open(QIODevice.ReadOnly):
            ver = bytes(version_file.readLine()).decode().replace("\n", "").replace("\r", "")
            self.setWindowTitle(self.windowTitle() + " v" + ver)
        version_file.close()

        # Setup & initial state
        self.ssh = SSHManager(self)
        self.disable_robot_tabs()

        # Signal / Slot setup
        self.ui.act_settings.triggered.connect(self.open_settings)
        self.ui.act_about.triggered.connect(self.open_about)

        self.ui.btn_connect.clicked.connect(self.toggle_connection)

        self.ssh.connection_lost.connect(self.connection_lost)

    def open_settings(self):
        dialog = SettingsDialog(self)
        res = dialog.exec()
        if res == QDialog.Accepted:
            dialog.save_settings()
            theme_manager.apply_theme(settings_manager.theme, settings_manager.larger_fonts)

    def open_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def disable_robot_tabs(self):
        self.ui.tabs_main.setTabEnabled(2, False)
        self.ui.tabs_main.setTabEnabled(3, False)
        self.ui.tabs_main.setTabEnabled(4, False)
        self.ui.tabs_main.setTabEnabled(5, False)
    
    def enable_robot_tabs(self):
        self.ui.tabs_main.setTabEnabled(2, True)
        self.ui.tabs_main.setTabEnabled(3, True)
        self.ui.tabs_main.setTabEnabled(4, True)
        self.ui.tabs_main.setTabEnabled(5, True)


    ############################################################################
    # This PC tab
    ############################################################################


    ############################################################################
    # Robot connection tab
    ############################################################################

    def toggle_connection(self):
        if self.ssh.is_connected:
            # TODO: Disconnect
            pass
        else:
            # Connect to robot
            res = self.ssh.connect_to_robot("192.168.10.1", 22, "pi", "arpirobot", 3, 10)
            print("Res = {0}".format(res))

    def connection_lost(self):
        # TODO: Stop any running tasks, close dialogs, etc
        
        # Restore UI to valid state
        self.disable_robot_tabs()
        self.ui.tabs_main.setCurrentIndex(1)
        self.ui.btn_connect.setText(self.tr("Connect"))

        # Show dialog to user
        dialog = QMessageBox()
        dialog.setIcon(QMessageBox.Warning)
        dialog.setText("Connection to the robot was lost.")
        dialog.setWindowTitle("Disconnected")
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.exec()


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
