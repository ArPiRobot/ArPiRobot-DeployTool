
import socket
from typing import Any, Callable, List, Optional
from PySide6.QtCore import QFile, QIODevice, QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtWidgets import QDialog, QMainWindow, QMessageBox, QProgressDialog, QWidget
from paramiko.pkey import PKey
from ui_deploy_tool import Ui_DeployTool
from about_dialog import AboutDialog
from settings_dialog import SettingsDialog
from paramiko.client import SSHClient, MissingHostKeyPolicy
from util import settings_manager, theme_manager


class Task(QRunnable, QObject):
    task_complete = Signal(object)
    task_exception = Signal(Exception)
    def __init__(self, parent, target: Callable, *args, **kwargs):
        QRunnable.__init__(self)
        QObject.__init__(self, parent=parent)
        self.__target = target
        self.__args = args
        self.__kwargs = kwargs

        self.setAutoDelete(True)
    
    def run(self):
        try:
            res = self.__target(*self.__args, **self.__kwargs)
            self.task_complete.emit(res)
        except Exception as e:
            self.task_exception.emit(e)


# Used to ignore ssh keys when connecting
# All robots use 192.168.10.1 as their address (unless changed)
# As such, enforcing host keys will only cause issues
class AcceptMissingKeyPolicy(MissingHostKeyPolicy):
    def missing_host_key(self, client: SSHClient, hostname: str, key: PKey):
        pass


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
        self.ssh: SSHClient = SSHClient()
        self.ssh.set_missing_host_key_policy(AcceptMissingKeyPolicy())
        self.ssh_check_timer = QTimer()
        self.ssh_connected = False
        self.disable_robot_tabs()

        # Progress dialog (shared between tasks)
        self.pdialog = QProgressDialog(parent=self)

        # Active background tasks
        self.tasks: List[Task] = []

        # Signal / Slot setup
        self.ui.act_settings.triggered.connect(self.open_settings)
        self.ui.act_about.triggered.connect(self.open_about)

        self.ssh_check_timer.timeout.connect(self.check_ssh_connection)

        self.ui.btn_connect.clicked.connect(self.toggle_connection)

        # Startup
        self.ssh_check_timer.start(1000)

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

    def start_task(self, task: Task):
        self.tasks.append(task)
        QThreadPool.globalInstance().start(task)
    
    def show_progress(self, title: str, msg: str):
        self.pdialog.hide()
        self.pdialog.setWindowModality(Qt.WindowModal)
        self.pdialog.setModal(True)
        self.pdialog.setWindowTitle(title)
        self.pdialog.setLabelText(msg)
        self.pdialog.setCancelButton(None)
        self.pdialog.setMinimum(0)
        self.pdialog.setMaximum(0)
        self.pdialog.setValue(0)
        self.pdialog.show()

    def hide_progress(self):
        self.pdialog.hide()

    ############################################################################
    # This PC tab
    ############################################################################


    ############################################################################
    # Robot connection tab
    ############################################################################

    def do_disconnect(self):
        # TODO: Stop any running tasks, close dialogs, etc
        self.hide_progress()

        # Disconnect from robot
        self.ssh.close()
        self.ssh_connected = False

        # Restore UI to valid state
        self.disable_robot_tabs()
        self.ui.tabs_main.setCurrentIndex(1)
        self.ui.btn_connect.setText(self.tr("Connect"))

    def handle_connected(self, res: Any):
        self.enable_robot_tabs()
        self.ui.btn_connect.setText(self.tr("Disconnect"))
        self.ssh_connected = True
        self.hide_progress()

    def handle_connection_failure(self, e: Exception):
        self.hide_progress()
        dialog = QMessageBox(parent=self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowTitle("Connect Failed!")
        dialog.setStandardButtons(QMessageBox.Ok)
        if isinstance(e, socket.timeout):
            dialog.setText("Unable to connect to the robot.")
        else:
            dialog.setText("Unknown error occurred while attempting to connect to the robot. {0}" \
                .format(str(e)))
        dialog.exec()

    def check_ssh_connection(self):
        if self.ssh_connected and not self.ssh.get_transport().is_active():
            # Connection lost
            self.do_disconnect()
            dialog = QMessageBox(parent=self)
            dialog.setIcon(QMessageBox.Warning)
            dialog.setText("Connection to the robot was lost.")
            dialog.setWindowTitle("Disconnected")
            dialog.setStandardButtons(QMessageBox.Ok)
            dialog.exec()

    def toggle_connection(self):
        if self.ssh_connected:
            # Disconnect from robot
            self.do_disconnect()
        else:
            # Connect to robot
            self.show_progress("Connecting", "Connecting to the robot...")            
            task = Task(self, self.ssh.connect, hostname="192.168.10.1", port=22, username="pi", password="arpirobot", allow_agent=False, look_for_keys=False, timeout=3, auth_timeout=3)
            task.task_complete.connect(self.handle_connected)
            task.task_exception.connect(self.handle_connection_failure)
            self.start_task(task)

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
