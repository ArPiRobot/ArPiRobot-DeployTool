
import socket
from typing import Any, Callable, List, Optional
from PySide6.QtCore import QDir, QFile, QFileInfo, QIODevice, QObject, QRunnable, QTextStream, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QDialog, QFileDialog, QMainWindow, QMessageBox, QProgressDialog, QTextEdit, QWidget
from paramiko.pkey import PKey
from ui_deploy_tool import Ui_DeployTool
from about_dialog import AboutDialog
from settings_dialog import SettingsDialog
from paramiko.client import SSHClient, MissingHostKeyPolicy
from util import settings_manager, theme_manager
from zipfile import ZipFile
import time
import os
import shutil


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

    change_progress_msg_sig = Signal(str)
    append_log_sig = Signal(str)

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

        # SSH setup and initial state
        self.ssh: SSHClient = SSHClient()
        self.ssh.set_missing_host_key_policy(AcceptMissingKeyPolicy())
        self.ssh_check_timer = QTimer()
        self.ssh_connected = False

        # Populate connection fields with default information
        self.ui.txt_address.setText(settings_manager.robot_address)
        self.ui.txt_username.setText(settings_manager.robot_user)
        self.ui.txt_password.setText("arpirobot")
        self.ui.cbx_longer_timeouts.setChecked(settings_manager.longer_timeouts)

        # Progress dialog (shared between tasks)
        self.pdialog = QProgressDialog(parent=self)
        self.pdialog.cancel()
        self.pdialog.hide()

        # Active background tasks
        self.tasks: List[Task] = []

        # Signal / Slot setup
        self.change_progress_msg_sig.connect(self.do_change_progress_msg)
        self.append_log_sig.connect(self.do_append_robot_log)

        self.ui.act_settings.triggered.connect(self.open_settings)
        self.ui.act_about.triggered.connect(self.open_about)

        self.ssh_check_timer.timeout.connect(self.check_ssh_connection)

        self.ui.tabs_main.currentChanged.connect(self.tab_changed)

        self.ui.btn_install_update.clicked.connect(self.install_update_package)

        self.ui.btn_connect.clicked.connect(self.toggle_connection)

        # Startup
        self.disable_robot_tabs()
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
    
    def do_change_progress_msg(self, msg: str):
        # This can only be called from UI thread
        # Use this object's signals to trigger this if you want to update form a different thread
        self.pdialog.setLabelText(msg)
    
    def change_progress_msg(self, msg: str):
        # Can call from any thread
        self.change_progress_msg_sig.emit(msg)

    def hide_progress(self):
        self.pdialog.hide()

    def tab_changed(self, idx: int):
        if idx == 0:
            self.populate_this_pc()
        
    @property
    def command_timeout(self) -> float:
        if self.ui.cbx_longer_timeouts.isChecked():
            return 5
        else:
            return 3

    ############################################################################
    # This PC tab
    ############################################################################

    def populate_this_pc(self):
        # Load CoreLib version
        path = QDir.homePath() + "/.arpirobot/corelib/version.txt"
        if QFileInfo(path).exists():
            file = QFile(path)
            if file.open(QIODevice.ReadOnly):
                instream = QTextStream(file)
                version = instream.readLine()
                self.ui.txt_corelib_version.setText(version)
            else:
                self.ui.txt_corelib_version.setText("Unknown Version")
        else:
            self.ui.txt_corelib_version.setText("Not Installed")

    def do_update_package_installation(self, filename: str):
        with ZipFile(filename) as zfile:
            if "what.txt" in zfile.namelist():
                what = zfile.read("what.txt").strip().decode()
                dest = "{0}/.arpirobot/{1}/".format(QDir.homePath(), what)
                self.change_progress_msg("Installing update package for component '{0}'".format(what))
                
                # Delete direcotry if it exists
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                
                # Make empty directory
                os.mkdir(dest)

                # Extract zip to directory
                zfile.extractall(dest)

            else:
                raise Exception(self.tr("The selected zip file is not an ArPiRobot update package."))

    def handle_update_installed(self, res: Any):
        self.hide_progress()
        self.populate_this_pc()

    def handle_update_failure(self, e: Exception):
        self.hide_progress()
        dialog = QMessageBox(parent=self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setText(str(e))
        dialog.setWindowTitle(self.tr("Error Installing Update Package"))
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.exec()

    def install_update_package(self):
        filename = QFileDialog.getOpenFileName(self, self.tr("Open Update Package"), QDir.homePath(), self.tr("Update Packages (*.zip)"))[0]
        if filename == "":
            return

        # Perform installation of update package on background thread
        self.show_progress("Installing Update Package", "Parsing update package")
        task = Task(self, self.do_update_package_installation, filename)
        task.task_complete.connect(self.handle_update_installed)
        task.task_exception.connect(self.handle_update_failure)
        self.start_task(task)
    
    ############################################################################
    # Robot connection tab
    ############################################################################

    def do_disconnect(self):
        # Hide progress dialog if shown
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

        # Start this task once when connected
        self.populate_program_log()

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
            addr = self.ui.txt_address.text()
            user = self.ui.txt_username.text()
            pwd = self.ui.txt_password.text()

            if self.ui.cbx_longer_timeouts.isChecked():
                timeout = 8
            else:
                timeout = 3

            self.show_progress("Connecting", "Connecting to the robot at {0}".format(addr)) 


            task = Task(self, self.ssh.connect, hostname=addr, port=22, username=user, password=pwd, allow_agent=False, look_for_keys=False, timeout=timeout, auth_timeout=timeout)
            task.task_complete.connect(self.handle_connected)
            task.task_exception.connect(self.handle_connection_failure)
            self.start_task(task)

    ############################################################################
    # Robot program tab
    ############################################################################


    ############################################################################
    # Robot program log tab
    ############################################################################

    def do_append_robot_log(self, txt: str):
        self.ui.txt_robot_log.moveCursor(QTextCursor.End)
        self.ui.txt_robot_log.insertPlainText(txt)
        self.ui.txt_robot_log.moveCursor(QTextCursor.End)
    
    def append_robot_log(self, txt: str):
        self.append_log_sig.emit(txt)

    def do_populate_log(self):
        _, stdout, _ = self.ssh.exec_command("tail -f -n +1 /tmp/arpirobot_program.log", timeout=None)
        while True:
            line = stdout.readline()
            if line == "":
                # EOF, therefore connection either closed or command was terminated
                break
            self.append_robot_log(line)
        print("LOG DONE")

    def populate_program_log(self):
        task = Task(self, self.do_populate_log)
        self.start_task(task)


    ############################################################################
    # Robot status tab
    ############################################################################


    ############################################################################
    # Network settings tab
    ############################################################################


    ############################################################################
    # Camera streaming tab
    ############################################################################
