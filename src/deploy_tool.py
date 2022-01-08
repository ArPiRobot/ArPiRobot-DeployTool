
import socket
from typing import Any, Callable, List, Optional
from PySide6.QtCore import QDir, QFile, QFileInfo, QIODevice, QObject, QRunnable, QTextStream, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication, QTextCursor
from PySide6.QtWidgets import QDialog, QFileDialog, QMainWindow, QMessageBox, QProgressDialog, QTextEdit, QWidget
from paramiko.pkey import PKey
from ui_deploy_tool import Ui_DeployTool
from about_dialog import AboutDialog
from settings_dialog import SettingsDialog
from paramiko.client import SSHClient, MissingHostKeyPolicy
from paramiko.ssh_exception import SSHException
from util import settings_manager, theme_manager
from zipfile import ZipFile
import time
import os
import shutil
import traceback
from enum import Enum, auto


class WritableState(Enum):
    Unknown = auto()
    Readonly = auto()
    ReadWrite = auto()

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
    set_versions_sig = Signal(str, str, str)
    update_status_sig = Signal(float, int, int, WritableState)

    ############################################################################
    # General UI & Helper functions
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
        self.set_versions_sig.connect(self.do_set_versions)
        self.update_status_sig.connect(self.do_update_status)

        self.ui.act_settings.triggered.connect(self.open_settings)
        self.ui.act_about.triggered.connect(self.open_about)

        self.ssh_check_timer.timeout.connect(self.check_ssh_connection)

        self.ui.tabs_main.currentChanged.connect(self.tab_changed)

        self.ui.btn_install_update.clicked.connect(self.install_update_package)

        self.ui.btn_connect.clicked.connect(self.toggle_connection)

        self.ui.btn_copy_log.clicked.connect(self.copy_log)

        self.ui.btn_shutdown.clicked.connect(self.shutdown_robot)
        self.ui.btn_reboot.clicked.connect(self.reboot_robot)
        self.ui.btn_restart_program.clicked.connect(self.restart_robot_program)
        self.ui.btn_make_writable.clicked.connect(self.make_robot_writable)
        self.ui.btn_readonly.clicked.connect(self.make_robot_readonly)

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

        # Don't keep data from old connections
        self.ui.pbar_cpu_usage.setValue(0)
        self.ui.pbar_cpu_usage.setFormat(self.tr("Unknown"))
        self.ui.pbar_mem_usage.setValue(0)
        self.ui.pbar_mem_usage.setFormat(self.tr("Unknown"))
        self.ui.lbl_readonly_status.setText(self.tr("Unknown"))
        self.ui.pnl_readonly_status.setObjectName("unknown")
        self.ui.pnl_readonly_status.style().unpolish(self.ui.pnl_readonly_status)
        self.ui.pnl_readonly_status.style().polish(self.ui.pnl_readonly_status)


        # Start these tasks once connected
        # They run until disconnect
        self.populate_program_log()
        self.populate_robot_status()

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

    def do_writable_check(self) -> WritableState:
        try:
            _, stdout, _ = self.ssh.exec_command("mount | grep \"on / \"")
        except SSHException:
            print(traceback.format_exc())
            return WritableState.Unknown
        line = stdout.readline()
        if line.find("ro") > -1:
            return WritableState.Readonly
        elif line.find("rw") > -1:
            return WritableState.ReadWrite
        else:
            return WritableState.Unknown


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
        while self.ssh_connected:
            # Outter loop ensures that if this command is killed (for any reason), 
            # but SSH is still active, logging continues to work
            try:
                _, stdout, _ = self.ssh.exec_command("tail -f -n +1 /tmp/arpirobot_program.log", timeout=None)
                while self.ssh_connected:
                    line = stdout.readline()
                    if line == "":
                        # EOF, therefore connection either closed or command was terminated
                        break
                    self.append_robot_log(line)
            except SSHException:
                print(traceback.format_exc())

    def populate_program_log(self):
        task = Task(self, self.do_populate_log)
        self.start_task(task)

    def copy_log(self):
        QGuiApplication.clipboard().setText(self.ui.txt_robot_log.toPlainText())


    ############################################################################
    # Robot status tab
    ############################################################################

    def do_set_versions(self, img_ver: str, py_ver: str, tool_ver: str):
        self.ui.txt_image_version.setText(img_ver)
        self.ui.txt_python_version.setText(py_ver)
        self.ui.txt_tools_version.setText(tool_ver)

    def set_versions(self, img_ver: str, py_ver: str, tool_ver: str):
        self.set_versions_sig.emit(img_ver, py_ver, tool_ver)

    def do_update_status(self, cpu: float, mem_used: int, mem_avail: int, writable: WritableState):
        self.ui.pbar_cpu_usage.setValue(int(100.0 - cpu))
        self.ui.pbar_cpu_usage.setFormat("{0:.2f} %".format(100.0 - cpu))
        self.ui.pbar_mem_usage.setValue(mem_used)
        self.ui.pbar_mem_usage.setMaximum(mem_avail)
        self.ui.pbar_mem_usage.setFormat("%v / %m kB")
        self.ui.lbl_readonly_status.setText(self.tr(writable.name))
        self.ui.pnl_readonly_status.setObjectName(writable.name.lower())
        self.ui.pnl_readonly_status.style().unpolish(self.ui.pnl_readonly_status)
        self.ui.pnl_readonly_status.style().polish(self.ui.pnl_readonly_status)

    def update_status(self, cpu: float, mem_used: int, mem_avail: int, writable: WritableState):
        self.update_status_sig.emit(cpu, mem_used, mem_avail, writable)

    def do_populate_status(self):
        # Read versions once after connecting
        _, stdout, _ = self.ssh.exec_command("dt-getversions.sh", timeout=self.command_timeout)
        img_version = stdout.readline().strip()
        py_version = stdout.readline().strip()
        tool_version = stdout.readline().strip()
        self.set_versions(img_version, py_version, tool_version)

        # Periodically read CPU usage, memory usage, and readonly status
        while self.ssh_connected:
            try:
                _, stdout_cpu, _ = self.ssh.exec_command("dt-getidlecpu.sh", timeout=self.command_timeout)
                _, stdout_mem, _ = self.ssh.exec_command("dt-getmeminfo.sh", timeout=self.command_timeout)
                
                writable_state = self.do_writable_check()

                try:
                    cpu = float(stdout_cpu.readline())
                except:
                    cpu = 0
                
                try:
                    mem_used = int(stdout_mem.readline())
                    mem_avail = int(stdout_mem.readline())
                except:
                    mem_used = 0
                    mem_avail = 0
                
                self.update_status(cpu, mem_used, mem_avail, writable_state)
                time.sleep(1)
            except SSHException:
                pass

    def populate_robot_status(self):
        task = Task(self, self.do_populate_status)
        self.start_task(task)

    def shutdown_robot(self):
        _, stdout, _ = self.ssh.exec_command("nohup dt-shutdown.sh > /dev/null 2>&1 &")
        stdout.channel.recv_exit_status()
    
    def reboot_robot(self):
        _, stdout, _ = self.ssh.exec_command("nohup dt-reboot.sh > /dev/null 2>&1 &")
        stdout.channel.recv_exit_status()
    
    def do_restart_program(self):
        try:
            _, stdout, _ = self.ssh.exec_command("dt-stop_program.sh", timeout=10)
            stdout.channel.recv_exit_status()
        except SSHException:
            raise Exception("Failed to stop robot program.")
        self.change_progress_msg(self.tr("Starting robot program..."))
        try:
            _, stdout, _ = self.ssh.exec_command("dt-start_program.sh", timeout=10)
            stdout.channel.recv_exit_status()
        except SSHException:
            raise Exception(self.tr("Failed to stop robot program."))

    def restart_program_success(self, res: Any):
        self.hide_progress()
    
    def restart_program_fail(self, e: Exception):
        self.hide_progress()
        dialog = QMessageBox(parent=self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setText(str(e))
        dialog.setWindowTitle(self.tr("Restart Robot Program Failed"))
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.exec()


    def restart_robot_program(self):
        self.show_progress(self.tr("Restarting Robot Program"), self.tr("Stopping robot program..."))
        task = Task(self, self.do_restart_program)
        task.task_complete.connect(self.restart_program_success)
        task.task_exception.connect(self.restart_program_fail)
        self.start_task(task)

    def make_robot_writable(self):
        _, stdout, _ = self.ssh.exec_command("nohup dt-rw.sh > /dev/null 2>&1 &")
        stdout.channel.recv_exit_status()
    
    def make_robot_readonly(self):
        _, stdout, _ = self.ssh.exec_command("nohup dt-ro.sh > /dev/null 2>&1 &")
        stdout.channel.recv_exit_status()


    ############################################################################
    # Network settings tab
    ############################################################################


    ############################################################################
    # Camera streaming tab
    ############################################################################
