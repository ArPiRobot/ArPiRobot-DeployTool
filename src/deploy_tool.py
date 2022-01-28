
import socket
import re
from threading import local
import traceback
from typing import Any, Callable, List, Optional
from PySide6.QtCore import QDir, QFile, QFileInfo, QIODevice, QObject, QRegularExpression, QRegularExpressionMatch, QRunnable, QTextStream, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent, QGuiApplication, QIntValidator, QTextCursor, QRegularExpressionValidator, QValidator
from PySide6.QtWidgets import QDialog, QFileDialog, QMainWindow, QMessageBox, QProgressDialog, QTextEdit, QWidget
from paramiko.pkey import PKey
from paramiko.sftp import SFTPError
from paramiko.sftp_client import SFTPClient
from camstream_dialog import CamstreamDialog
from playstream_dialog import PlayStreamDialog
from ui_deploy_tool import Ui_DeployTool
from about_dialog import AboutDialog
from settings_dialog import SettingsDialog
from paramiko.client import SSHClient, MissingHostKeyPolicy
from paramiko.ssh_exception import SSHException
from util import settings_manager, theme_manager, WIFI_COUNTRY_CODES
from zipfile import ZipFile
import time
import os
import subprocess
import sys
import shutil
import json
import pathlib
import platform
from enum import Enum, auto



class DTProgressDialog(QProgressDialog):
    def __init__(self, parent: Optional[QWidget]):
        super().__init__(parent=parent)
        self.setCancelButton(None)
    
    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()


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
            try:
                self.task_exception.emit(e)
            except:
                pass


class AcceptMissingKeyPolicy(MissingHostKeyPolicy):
    def missing_host_key(self, client: SSHClient, hostname: str, key: PKey):
        pass


class WifiPassValidator(QRegularExpressionValidator):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRegularExpression(QRegularExpression(r"[^\x20-\x7E]+$"))


class WifiSsidValidator(QValidator):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent=parent)
    
    def validate(self, input: str, pos: int) -> object:
        if len(input) > 32:
            return QRegularExpressionValidator.Invalid
        input_bytes = list(input.encode())
        for b in input_bytes:
            # Printable ASCII range
            if b < 32 or b > 126:
                return QValidator.Invalid
            # Disallowed in printable ASCII range
            # ? " $ [ \ ] +
            if b in [63, 34, 36, 91, 93, 43]:
                return QValidator.Invalid
        return QValidator.Acceptable


class WifiPskValidator(QValidator):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent=parent)
    
    def validate(self, input: str, pos: int) -> object:
        if len(input) > 63:
            return QRegularExpressionValidator.Invalid
        input_bytes = list(input.encode())
        for b in input_bytes:
            # Printable ASCII range
            if b < 32 or b > 126:
                return QValidator.Invalid
        return QValidator.Acceptable


class WifiCountryValidator(QRegularExpressionValidator):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent=parent)
        self.setRegularExpression(QRegularExpression("[A-Z]*"))
    
    def validate(self, input: str, pos: int) -> object:
        if len(input) > 2:
            return QRegularExpressionValidator.Invalid
        return super().validate(input, pos)
        


class DeployToolWindow(QMainWindow):

    change_progress_msg_sig = Signal(str)
    append_log_sig = Signal(str)
    set_versions_sig = Signal(str, str, str)
    update_status_sig = Signal(float, int, int, WritableState)
    update_net_info_sig = Signal(str, str, str, str, str)
    clear_robot_log_sig = Signal()

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

        self.ui.txt_wifi_ssid.setValidator(WifiSsidValidator(self))
        self.ui.txt_wifi_pass.setValidator(WifiPskValidator(self))
        self.ui.txt_wifi_country.setValidator(WifiCountryValidator(self))
        self.ui.txt_wifi_channel.setValidator(QIntValidator(1, 14, self))

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
        self.pdialog = DTProgressDialog(parent=self)
        self.pdialog.cancel()
        self.pdialog.hide()

        # Active background tasks
        self.tasks: List[Task] = []

        # Active dialogs for playing streams
        self.camstreams: List[PlayStreamDialog] = []

        # Signal / Slot setup
        self.change_progress_msg_sig.connect(self.do_change_progress_msg)
        self.append_log_sig.connect(self.do_append_robot_log)
        self.set_versions_sig.connect(self.do_set_versions)
        self.update_status_sig.connect(self.do_update_status)
        self.update_net_info_sig.connect(self.do_update_network_info)
        self.clear_robot_log_sig.connect(self.do_clear_robot_log)

        self.ui.act_settings.triggered.connect(self.open_settings)
        self.ui.act_about.triggered.connect(self.open_about)

        self.ssh_check_timer.timeout.connect(self.check_ssh_connection)

        self.ui.tabs_main.currentChanged.connect(self.tab_changed)

        self.ui.btn_install_update.clicked.connect(self.install_update_package)

        self.ui.btn_connect.clicked.connect(self.toggle_connection)

        self.ui.btn_proj_browse.clicked.connect(self.choose_proj_folder)
        self.ui.btn_proj_deploy.clicked.connect(self.deploy_program)

        self.ui.btn_copy_log.clicked.connect(self.copy_log)

        self.ui.btn_shutdown.clicked.connect(self.shutdown_robot)
        self.ui.btn_reboot.clicked.connect(self.reboot_robot)
        self.ui.btn_restart_program.clicked.connect(self.restart_robot_program)
        self.ui.btn_make_writable.clicked.connect(self.make_robot_writable)
        self.ui.btn_readonly.clicked.connect(self.make_robot_readonly)

        self.ui.btn_wifi_apply.clicked.connect(self.apply_network_settings)
        self.ui.btn_change_hostname.clicked.connect(self.apply_hostname)

        self.ui.btn_new_camstream.clicked.connect(self.new_camstream)
        self.ui.btn_delete_camstream.clicked.connect(self.delete_camstream)
        self.ui.btn_edit_camstream.clicked.connect(self.edit_camstream)
        self.ui.combox_camstream_player.currentTextChanged.connect(self.change_player_download_link)
        self.ui.btn_play_camstream.clicked.connect(self.play_stream)
        self.ui.btn_camstream_start.clicked.connect(self.start_camstream)
        self.ui.btn_camstream_stop.clicked.connect(self.stop_camstream)
        self.ui.btn_rtsp_start.clicked.connect(self.start_rtsp)
        self.ui.btn_rtsp_stop.clicked.connect(self.stop_rtsp)
        self.ui.cbx_camstream_boot.clicked.connect(self.enable_camstream_changed)
        self.ui.cbx_enable_rtsp.clicked.connect(self.enable_rtsp_changed)

        # Startup
        self.disable_robot_tabs()
        self.ssh_check_timer.start(1000)

        # Load last used connection settings
        self.ui.txt_address.setText(settings_manager.robot_address)
        self.ui.txt_username.setText(settings_manager.robot_user)
        self.ui.cbx_longer_timeouts.setChecked(settings_manager.longer_timeouts)

    def closeEvent(self, event: QCloseEvent):
        self.ssh_connected = False
        self.ssh.close()

        # Save last used connection settings
        settings_manager.robot_address = self.ui.txt_address.text()
        settings_manager.robot_user = self.ui.txt_username.text()
        settings_manager.longer_timeouts = self.ui.cbx_longer_timeouts.isChecked()

        return super().closeEvent(event)

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
        self.ui.tabs_main.setTabEnabled(6, False)

        # Robot disconnected. Can edit these now
        self.ui.txt_address.setEnabled(True)
        self.ui.txt_username.setEnabled(True)
        self.ui.txt_password.setEnabled(True)
    
    def enable_robot_tabs(self):
        self.ui.tabs_main.setTabEnabled(2, True)
        self.ui.tabs_main.setTabEnabled(3, True)
        self.ui.tabs_main.setTabEnabled(4, True)
        self.ui.tabs_main.setTabEnabled(5, True)
        self.ui.tabs_main.setTabEnabled(6, True)

        # While conencted to robot don't allow editing these
        self.ui.txt_address.setEnabled(False)
        self.ui.txt_username.setEnabled(False)
        self.ui.txt_password.setEnabled(False)

    def start_task(self, task: Task):
        self.tasks.append(task)
        QThreadPool.globalInstance().start(task)
    
    def show_progress(self, title: str, msg: str):
        self.pdialog.hide()
        self.pdialog.setWindowModality(Qt.WindowModal)
        self.pdialog.setModal(True)
        self.pdialog.setWindowTitle(title)
        self.pdialog.setLabelText(msg)
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
        elif idx == 2:
            self.populate_program_tab()
        elif idx == 5:
            self.populate_network_settings()
        elif idx == 6:
            self.populate_streams()
        
    @property
    def command_timeout(self) -> float:
        if self.ui.cbx_longer_timeouts.isChecked():
            return 5
        else:
            return 3

    ############################################################################
    # SFTP Functions
    ############################################################################
    def sftp_upload_file(self, sftp: SFTPClient, local_file: str, remote_dest: str):
        # Note: remote_dest is a directory and must exist
        sftp.put(local_file, "{0}/{1}".format(remote_dest, os.path.basename(local_file)))

    def sftp_mkdir_recursive(self, sftp: SFTPClient, remote_directory: str):
        remote_directory.replace("\\", "/")
        if remote_directory == '/':
            sftp.chdir('/')
            return
        if remote_directory == '':
            return
        try:
            sftp.chdir(remote_directory)
        except IOError:
            dirname, basename = os.path.split(remote_directory.rstrip('/'))
            self.sftp_mkdir_recursive(sftp, dirname)
            sftp.mkdir(basename)
            sftp.chdir(basename)
            return True

    def sftp_upload_directory(self, sftp: SFTPClient, local_dir: str, remote_dest: str):
        # Note: remote_dest is a directory and must exist
        # The local directory is recursively uploaded to the remote location

        # Use only forward slashes. Remove trailing slash as it messes up os.path.basename
        local_dir = local_dir.replace("\\", "/").rstrip("/")

        remote_dest = "{0}/{1}".format(remote_dest, os.path.basename(local_dir))

        # Copy each item in this directory recursively
        for root, dirs, files in os.walk(local_dir):
            for file in files:
                local_file = "{0}/{1}".format(root, file).replace("\\", "/")
                remote_file = local_file.replace(local_dir, remote_dest)
                self.sftp_mkdir_recursive(sftp, os.path.dirname(remote_file))
                sftp.put(local_file, remote_file)
            for dir in dirs:
                local_file = os.path.join(root, dir).replace("\\", "/")
                remote_file = local_file.replace(local_dir, remote_dest)
                self.sftp_upload_directory(sftp, local_file, os.path.dirname(remote_file))   

    def sftp_list_directory(self, sftp: SFTPClient, remote_dir: str) -> List[str]:
        dirs = sftp.listdir(remote_dir)
        dirs.sort()
        return dirs

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
        try:
            self.set_pythonpath()
        except:
            print(traceback.format_exc())
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
    
    def set_pythonpath(self):
        if platform.system() == "Windows":
            self.add_var_windows("PYTHONPATH", QDir.homePath().rstrip("/\\") + "\\.arpirobot\\corelib\\python_bindings")
        else:
            home = os.environ["HOME"].rstrip("/")
            path = home + "/.arpirobot/corelib/python_bindings"
            self.add_var_to_profile(home + "/.bashrc", "PYTHONPATH", path)
            self.add_var_to_profile(home + "/.zshrc", "PYTHONPATH", path)
            self.add_var_to_profile(home + "/.profile", "PYTHONPATH", path)
            self.add_var_to_config(home + "/.config/environment.d/deploy-tool.conf", "PYTHONPATH", path)

    def add_var_windows(self, var: str, value: str):
        value = value.replace("/", "\\")
        if var in os.environ:
            existing = os.environ[var]
        else:
            existing = ""
        parts = existing.split(";")
        for part in parts:
            if pathlib.Path(part) == pathlib.Path(value):
                # Already set
                return
        if existing == "":
            cmd = "cmd /s /c \"setx {0} \"{1}\"".format(var, value)
        else:
            cmd = "cmd /s /c \"setx {0} \"{1};%{0}%\"".format(var, value)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.call(cmd, startupinfo=si)

    def add_var_to_profile(self, filename: str, var: str, value: str):
        if os.path.isdir(filename):
            return
        if not os.path.exists(filename):
            return
        with open(filename, "r") as fp:
            line = fp.readline()
            while line != "":
                if line.startswith("export {0}".format(var)):
                    pos = line.find("=")
                    if pos > -1:
                        parts = line[pos+1:].split(":")
                        for part in parts:
                            if pathlib.Path(part) == pathlib.Path(value):
                                # Don't need to add anything. Already exists
                                return
                line = fp.readline()
        
        with open(filename, "a") as fp:
            fp.write("export {0}={1}:${0}\n".format(var, value))
    
    def add_var_to_config(self, filename: str, var: str, value: str):
        if os.path.isdir(filename):
            return
        if not os.path.exists(filename):
            if not os.path.exists(os.path.dirname(filename)):
                return
        if os.path.exists(filename):
            with open(filename, "r") as fp:
                line = fp.readline()
                while line != "":
                    if line.startswith("{0}".format(var)):
                        pos = line.find("=")
                        if pos > -1:
                            parts = line[pos+1:].split(":")
                            for part in parts:
                                if pathlib.Path(part) == pathlib.Path(value):
                                    # Don't need to add anything. Already exists
                                    return
                    line = fp.readline()
        with open(filename, "a") as fp:
            fp.write("{0}={1}:${0}\n".format(var, value))

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

    def populate_program_tab(self):
        self.ui.txt_proj_folder.setText(settings_manager.last_proj_folder)
        self.validate_proj_folder()

    def validate_proj_folder(self):
        valid = os.path.exists(settings_manager.last_proj_folder) and os.path.isdir(settings_manager.last_proj_folder)
        if valid:
            valid = os.path.exists(os.path.join(settings_manager.last_proj_folder, "arpirobot-proj.json"))
        self.ui.btn_proj_deploy.setEnabled(valid)
    
    def choose_proj_folder(self):
        if settings_manager.last_proj_folder != "" and os.path.exists(settings_manager.last_proj_folder):
            start_dir = settings_manager.last_proj_folder
        else:
            start_dir = QDir.homePath()
        folder = QFileDialog.getExistingDirectory(self, self.tr("Open Project Folder"), start_dir)
        if(folder != ""):
            settings_manager.last_proj_folder = folder
            self.ui.txt_proj_folder.setText(folder)
            self.validate_proj_folder()

    def do_writable_check(self) -> WritableState:
        try:
            _, stdout, _ = self.ssh.exec_command("mount | grep \"on / \"")
        except SSHException:
            return WritableState.Unknown
        line = stdout.readline()
        if line.find("ro") > -1:
            return WritableState.Readonly
        elif line.find("rw") > -1:
            return WritableState.ReadWrite
        else:
            return WritableState.Unknown

    def custom_glob(self, expression: str, base_path: str, old_dt_compat: bool) -> List[str]:
        # Old deploy tool treated src/** as src/**/* would be treated (more or less)
        if old_dt_compat and expression.endswith("**"):
            expression = "{0}/*".format(expression)

        matches = []
        base_path_obj = pathlib.Path(base_path)
        for match in base_path_obj.glob(expression):
            matches.append(str(match))
        return matches

    def do_deploy_program(self, proj_folder: str):

        self.change_progress_msg(self.tr("Ensuring robot filesystem is writable..."))
        orig_state = self.do_writable_check()
        if(orig_state != WritableState.ReadWrite):
            self.make_robot_writable()
        
        self.change_progress_msg(self.tr("Stopping old robot program..."))
        _, stdout, _ = self.ssh.exec_command("dt-stop_program.sh", timeout=self.command_timeout)
        res = stdout.channel.recv_exit_status()
        if res != 0:
            raise Exception(self.tr("Failed to stop old program."))

        # Clear log when program is redeployed
        self.clear_robot_log()
        time.sleep(0.1)

        self.change_progress_msg(self.tr("Deleting old project..."))
        _, stdout, _ = self.ssh.exec_command("dt-delete_program.sh", timeout=self.command_timeout)
        res = stdout.channel.recv_exit_status()
        if res != 0:
            raise Exception(self.tr("Failed to delete old program."))

        self.change_progress_msg(self.tr("Uploading new project to robot..."))

        # Do Deploy
        sftp = self.ssh.open_sftp()
    
        # Make sure project file is of a known version
        all_files: List[str] = []
        try:
            with open(os.path.join(proj_folder, "arpirobot-proj.json")) as fp:
                proj_file = json.load(fp)
        except:
            raise Exception(self.tr("Unable to open project file."))
        
        if "version" not in proj_file:
            raise Exception(self.tr("Invalid project version. Update the deploy tool and try again."))
        elif proj_file["version"] == 2 or proj_file["version"] == 1:
            if "deployFiles" not in proj_file or "coreLibFiles" not in proj_file:
                raise Exception("Project file is invalid. Make sure all required sections exist")
            
            old_dt_compat = proj_file["version"] == 1

            for expression in proj_file["deployFiles"]:
                all_files.extend(self.custom_glob(expression, proj_folder, old_dt_compat))
            for expression in proj_file["coreLibFiles"]:
                all_files.extend(self.custom_glob(expression, os.path.join(QDir.homePath(), ".arpirobot", "corelib"), old_dt_compat))

        else:
            raise Exception(self.tr("Invalid project version. Update the deploy tool and try again."))

        # Make empty directory to upload to exists
        _, stdout, _ = self.ssh.exec_command("rm -rf /tmp/robot_proj/;mkdir -p /tmp/robot_proj")
        res = stdout.channel.recv_exit_status()

        # Upload each item to the remote directory using sftp
        try:
            for file in all_files:               
                if not os.path.isdir(file):
                    self.sftp_upload_file(sftp, file, "/tmp/robot_proj/")
                else:
                    self.sftp_upload_directory(sftp, file, "/tmp/robot_proj/")
        except SFTPError as e:
            print(str(e))
            raise Exception(self.tr("Unable to copy files to the robot."))

        sftp.close()

        _, stdout, _ = self.ssh.exec_command("dt-update_program.sh /tmp/robot_proj", timeout=self.command_timeout)
        res = stdout.channel.recv_exit_status()
        if res != 0:
            raise Exception(self.tr("Unable to update program on the robot."))

        self.change_progress_msg("Starting new robot program...")
        _, stdout, _ = self.ssh.exec_command("dt-start_program.sh", timeout=self.command_timeout)
        res = stdout.channel.recv_exit_status()

        if res != 0:
            raise Exception(self.tr("Failed to start new program on robot."))

        self.change_progress_msg("Restoring filesystem state...")
        # Restore readonly status
        if(orig_state == WritableState.Readonly):
            self.make_robot_readonly()

    def deploy_complete(self, res: Any):
        self.hide_progress()
    
    def deploy_failed(self, e: Exception):
        self.hide_progress()
        dialog = QMessageBox(parent=self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setText(str(e))
        dialog.setWindowTitle(self.tr("Deploy Program Failed"))
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.exec()

    def deploy_program(self):
        self.show_progress(self.tr("Deploying Program"), self.tr("Preparing to deploy program to robot..."))
        task = Task(self, self.do_deploy_program, self.ui.txt_proj_folder.text())
        task.task_complete.connect(self.deploy_complete)
        task.task_exception.connect(self.deploy_failed)
        self.start_task(task)


    ############################################################################
    # Robot program log tab
    ############################################################################

    def do_clear_robot_log(self):
        self.ui.txt_robot_log.clear()

    def clear_robot_log(self):
        self.clear_robot_log_sig.emit()

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
                pass

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
        _, stdout, _ = self.ssh.exec_command("nohup dt-shutdown.sh > /dev/null 2>&1 &", timeout=self.command_timeout)
        stdout.channel.recv_exit_status()
    
    def reboot_robot(self):
        _, stdout, _ = self.ssh.exec_command("nohup dt-reboot.sh > /dev/null 2>&1 &", timeout=self.command_timeout)
        stdout.channel.recv_exit_status()
    
    def do_restart_program(self):
        try:
            _, stdout, _ = self.ssh.exec_command("dt-stop_program.sh", timeout=10)
            stdout.channel.recv_exit_status()
        except SSHException:
            raise Exception("Failed to stop robot program.")

        # Clear log when program restarts 
        self.clear_robot_log()
        time.sleep(0.1)
        
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
        _, stdout, _ = self.ssh.exec_command("nohup dt-rw.sh > /dev/null 2>&1 &", timeout=self.command_timeout)
        stdout.channel.recv_exit_status()
    
    def make_robot_readonly(self):
        _, stdout, _ = self.ssh.exec_command("nohup dt-ro.sh > /dev/null 2>&1 &", timeout=self.command_timeout)
        stdout.channel.recv_exit_status()


    ############################################################################
    # Network settings tab
    ############################################################################

    def do_update_network_info(self, hostname: str, ssid: str, password: str, country: str, channel: str):
        self.ui.txt_hostname.setText(hostname)
        self.ui.txt_wifi_ssid.setText(ssid)
        self.ui.txt_wifi_pass.setText(password)
        self.ui.txt_wifi_country.setText(country)
        self.ui.txt_wifi_channel.setText(channel)

    def update_network_info(self, hostname: str, ssid: str, password: str, country: str, channel: str):
        self.update_net_info_sig.emit(hostname, ssid, password, country, channel)

    def do_populate_network_settings(self):
        _, stdout_host, _ = self.ssh.exec_command("dt-hostname.sh", timeout=self.command_timeout)
        _, stdout_ap, _ = self.ssh.exec_command("dt-wifi_ap.sh", timeout=self.command_timeout)

        hostname = stdout_host.readline().strip()

        ssid = stdout_ap.readline().strip()
        password = stdout_ap.readline().strip()
        country = stdout_ap.readline().strip()
        channel = stdout_ap.readline().strip()

        self.update_network_info(hostname, ssid, password, country, channel)

    def populate_network_settings(self):
        self.show_progress(self.tr("Loading"), self.tr("Loading info from robot..."))
        task = Task(self, self.do_populate_network_settings)
        task.task_complete.connect(lambda res: self.hide_progress())
        task.task_exception.connect(lambda e: self.hide_progress())
        self.start_task(task)
    
    def do_apply_network_settings(self, ssid: str, psk: str, country: str, channel: int):
        orig_state = self.do_writable_check()
        if orig_state != WritableState.ReadWrite:
            self.make_robot_writable()

        _, stdout, _ = self.ssh.exec_command("nohup dt-wifi_ap.sh '{0}' '{1}' '{2}' '{3}'  > /dev/null 2>&1".format(ssid, psk, country, channel),
                timeout=self.command_timeout)
        stdout.channel.recv_exit_status()

        if orig_state == WritableState.Readonly:
            self.make_robot_readonly()

    def apply_network_settings(self):
        ssid = self.ui.txt_wifi_ssid.text()
        psk = self.ui.txt_wifi_pass.text()
        country = self.ui.txt_wifi_country.text()

        try:
            channel = int(self.ui.txt_wifi_channel.text())
            if channel < 1 or channel > 14:
                raise Exception()
        except:
            dialog = QMessageBox(parent=self)
            dialog.setIcon(QMessageBox.Warning)
            dialog.setText(self.tr("Wifi channel invalid! Channel must be a number between 1 and 14."))
            dialog.setWindowTitle(self.tr("WiFi Settings Invalid"))
            dialog.setStandardButtons(QMessageBox.Ok)
            dialog.exec()
        
        if len(ssid) < 2:
            dialog = QMessageBox(parent=self)
            dialog.setIcon(QMessageBox.Warning)
            dialog.setText(self.tr("SSID must be at least 2 characters in length."))
            dialog.setWindowTitle(self.tr("WiFi Settings Invalid"))
            dialog.setStandardButtons(QMessageBox.Ok)
            dialog.exec()
        
        if len(psk) < 8:
            dialog = QMessageBox(parent=self)
            dialog.setIcon(QMessageBox.Warning)
            dialog.setText(self.tr("Password must be at least 8 characters in length."))
            dialog.setWindowTitle(self.tr("WiFi Settings Invalid"))
            dialog.setStandardButtons(QMessageBox.Ok)
            dialog.exec()
        
        if len(country) < 2 or country not in WIFI_COUNTRY_CODES:
            dialog = QMessageBox(parent=self)
            dialog.setIcon(QMessageBox.Warning)
            dialog.setText(self.tr("Country code must be a valid two letter country code."))
            dialog.setWindowTitle(self.tr("WiFi Settings Invalid"))
            dialog.setStandardButtons(QMessageBox.Ok)
            dialog.exec()
        
        self.show_progress(self.tr("Applying Network Settings"), self.tr("Applying network setting changes on robot..."))
        task = Task(self, self.do_apply_network_settings, ssid, psk, country, channel)
        task.task_complete.connect(lambda res: self.hide_progress())
        task.task_exception.connect(lambda e: self.hide_progress())
        self.start_task(task)

    def post_apply_reboot(self):
        self.hide_progress()
        dialog = QMessageBox(parent=self)
        dialog.setIcon(QMessageBox.Question)
        dialog.setText(self.tr("The hostname was successfully changed, however a reboot is necessary for changes to take effect. Reboot now?"))
        dialog.setWindowTitle(self.tr("Hostname Changed"))
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        res = dialog.exec()
        if res == QMessageBox.Yes:
            self.reboot_robot()

    def do_apply_hostname(self, hostname: str):
        orig_state = self.do_writable_check()
        if orig_state != WritableState.ReadWrite:
            self.make_robot_writable()
        
        _, stdout, _ = self.ssh.exec_command("nohup dt-hostname.sh '{0}' > /dev/null 2>&1".format(hostname),timeout=self.command_timeout)
        stdout.channel.recv_exit_status()

        if orig_state == WritableState.Readonly:
            self.make_robot_readonly()

    def apply_hostname(self):
        self.show_progress(self.tr("Changing Hostname"), self.tr("Changing robot hostname..."))
        task = Task(self, self.do_apply_hostname, self.ui.txt_hostname.text())
        task.task_exception.connect(self.hide_progress)
        task.task_complete.connect(self.post_apply_reboot)
        self.start_task(task)


    ############################################################################
    # Camera streaming tab
    ############################################################################
    
    def write_camstream_config(self, name: str, config: str):
        orig_state = self.do_writable_check()
        if orig_state != WritableState.ReadWrite:
            self.make_robot_writable()
        
        sftp = None
        try:
            sftp = self.ssh.open_sftp()
            with sftp.open("/home/pi/camstream/{0}.txt".format(name), "w") as file:
                file.write(config.encode())
            sftp.close()
        except (SSHException, SFTPError):
            if sftp is not None:
                sftp.close()
        
        if orig_state == WritableState.Readonly:
            self.make_robot_readonly()

    def new_camstream(self):
        dialog = CamstreamDialog(self)
        res = dialog.exec()
        if res == QDialog.Accepted:
            name = dialog.get_config_name()
            config = dialog.to_config()
            self.write_camstream_config(name, config)
            self.populate_streams()
    
    def delete_camstream(self):
        dialog = QMessageBox(parent=self)
        dialog.setIcon(QMessageBox.Question)
        dialog.setText(self.tr("Are you sure you want to delete '{0}'?".format(self.ui.combox_stream_source.currentText())))
        dialog.setWindowTitle(self.tr("Confirm Delete"))
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        res = dialog.exec()
        if res == QMessageBox.Yes:
            orig_state = self.do_writable_check()
            if orig_state != WritableState.ReadWrite:
                self.make_robot_writable()

            sftp = None
            try:
                sftp = self.ssh.open_sftp()
                sftp.remove("/home/pi/camstream/{0}.txt".format(self.ui.combox_stream_source.currentText()))
                sftp.close()
            except (SSHException, SFTPError):
                if sftp is not None:
                    sftp.close()

            if orig_state == WritableState.Readonly:
                self.make_robot_readonly()

            self.populate_streams()
    
    def edit_camstream(self):
        if self.ui.combox_stream_source.currentText() != "":
            sftp = None
            try:
                sftp = self.ssh.open_sftp()
                with sftp.open("/home/pi/camstream/{0}.txt".format(self.ui.combox_stream_source.currentText()), "r") as file:
                    config = file.read().decode()
                dialog = CamstreamDialog(self)
                dialog.set_config_name(self.ui.combox_stream_source.currentText())
                dialog.disable_edit_config_name()
                dialog.from_config(config)
                res = dialog.exec()
                if res == QDialog.Accepted:
                    name = dialog.get_config_name()
                    new_config = dialog.to_config()
                    self.write_camstream_config(name, new_config)
                sftp.close()
            except (SSHException, SFTPError):
                if sftp is not None:
                    sftp.close()
                dialog = QMessageBox(parent=self)
                dialog.setIcon(QMessageBox.Warning)
                dialog.setTextFormat(Qt.RichText)
                dialog.setText(self.tr("Error reading config file for the selected stream!"))
                dialog.setWindowTitle(self.tr("SFTP Error"))
                dialog.setStandardButtons(QMessageBox.Ok)
                dialog.exec()
    
    def change_player_download_link(self, text: str):
        if text == self.tr("ffplay"):
            self.ui.lbl_camstream_download.setText("<a href=\"https://ffmpeg.org/\">Download Player</a>")
        elif text == self.tr("mpv"):
            self.ui.lbl_camstream_download.setText("<a href=\"https://mpv.io/\">Download Player</a>")
        elif text == self.tr("mplayer"):
            self.ui.lbl_camstream_download.setText("<a href=\"http://www.mplayerhq.hu/design7/news.html\">Download Player</a>")

    def do_populate_streams(self):
        # Load list of streams from the remote device
        sftp = None
        try:
            sftp = self.ssh.open_sftp()
            paths = self.sftp_list_directory(sftp, "/home/pi/camstream/")
            sftp.close()
        except (SSHException, SFTPError):
            paths = []
            if sftp is not None:
                sftp.close()

        streams = []
        for entry in paths:
            if entry.endswith(".txt"):
                streams.append(entry.removesuffix(".txt"))

        # Clear old items
        self.ui.combox_stream_source.clear()
        
        # Add items
        for stream in streams:
            self.ui.combox_stream_source.addItem(stream)
        
        # Check if services are running
        _, stdout, _ = self.ssh.exec_command("sudo systemctl is-enabled camstream.service")
        stdout.channel.recv_exit_status()
        data = stdout.read().decode().strip().lower()
        self.ui.cbx_camstream_boot.setChecked(data == "enabled")

        _, stdout, _ = self.ssh.exec_command("sudo systemctl is-enabled rtsp-simple-server.service")
        stdout.channel.recv_exit_status()
        data = stdout.read().decode().strip().lower()
        self.ui.cbx_enable_rtsp.setChecked(data == "enabled")

    def populate_streams(self):
        self.show_progress(self.tr("Loading"), self.tr("Loading info from robot..."))
        task = Task(self, self.do_populate_streams)
        task.task_complete.connect(lambda res: self.hide_progress())
        task.task_exception.connect(lambda e: self.hide_progress())
        self.start_task(task)

    def start_camstream(self):
        _, stdout, _ = self.ssh.exec_command("sudo systemctl start camstream.service")
        stdout.channel.recv_exit_status()

    def stop_camstream(self):
        _, stdout, _ = self.ssh.exec_command("sudo systemctl stop camstream.service")
        stdout.channel.recv_exit_status()

    def start_rtsp(self):
        _, stdout, _ = self.ssh.exec_command("sudo systemctl start rtsp-simple-server.service")
        stdout.channel.recv_exit_status()

    def stop_rtsp(self):
        _, stdout, _ = self.ssh.exec_command("sudo systemctl stop rtsp-simple-server.service")
        stdout.channel.recv_exit_status()

    def do_enable_camstream_changed(self, state: int):
        if state == Qt.Checked:
            _, stdout, _ = self.ssh.exec_command("sudo systemctl enable camstream.service")
            stdout.channel.recv_exit_status()
        else:
            _, stdout, _ = self.ssh.exec_command("sudo systemctl disable camstream.service")
            stdout.channel.recv_exit_status()

    def enable_camstream_changed(self, checked: bool):
        self.show_progress(self.tr("Modifying system services"), self.tr("Changing boot services..."))
        task = Task(self, self.do_enable_camstream_changed, self.ui.cbx_camstream_boot.checkState())
        task.task_complete.connect(lambda res: self.hide_progress())
        task.task_exception.connect(lambda e: self.hide_progress())
        self.start_task(task)
    
    def do_enable_rtsp_changed(self, state: int):
        if state == Qt.Checked:
            _, stdout, _ = self.ssh.exec_command("sudo systemctl enable rtsp-simple-server.service")
            stdout.channel.recv_exit_status()
        else:
            _, stdout, _ = self.ssh.exec_command("sudo systemctl disable rtsp-simple-server.service")
            stdout.channel.recv_exit_status()
    
    def enable_rtsp_changed(self, checked: bool):
        self.show_progress(self.tr("Modifying system services"), self.tr("Changing boot services..."))
        task = Task(self, self.do_enable_rtsp_changed, self.ui.cbx_enable_rtsp.checkState())
        task.task_complete.connect(lambda res: self.hide_progress())
        task.task_exception.connect(lambda e: self.hide_progress())
        self.start_task(task)

    def play_stream(self):
        # Check to make sure player is installed
        player = self.ui.combox_camstream_player.currentText()
        stream = self.ui.combox_stream_source.currentText()
        path = shutil.which(player)

        # Make sure player is in PATH
        if path == "" or path == None:
            dialog = QMessageBox(parent=self)
            dialog.setIcon(QMessageBox.Warning)
            dialog.setTextFormat(Qt.RichText)
            dialog.setText(self.tr("<p>The selected player was not found on your system. Download and install the player and make sure the command is in your system path. You will need to restart the deploy tool after chaning the path environment variable.</p><p>You can also use the system package manager (on Linux) or a third party one (<a href=\"https://scoop.sh/\">scoop</a> or <a href=\"https://chocolatey.org/\">chocolatey</a> on Windows or <a href=\"https://brew.sh\">homebrew</a> on macOS) to install the packages. Typically the packages are named ffmpeg (includes ffplay), mpv, and mplayer respectively.</p>"))
            dialog.setWindowTitle(self.tr("Player not found"))
            dialog.setStandardButtons(QMessageBox.Ok)
            dialog.exec()
            return
        
        # Make sure a stream is selected
        if stream == "":
            dialog = QMessageBox(parent=self)
            dialog.setIcon(QMessageBox.Warning)
            dialog.setText(self.tr("No steam was selected. Select a stream before playing it."))
            dialog.setWindowTitle(self.tr("Cannot Play Stream"))
            dialog.setStandardButtons(QMessageBox.Ok)
            dialog.exec()
            return

        sftp = None
        try:
            sftp = self.ssh.open_sftp()
            with sftp.open("/home/pi/camstream/{0}.txt".format(stream), "r") as file:
                selected_config = file.read().decode()
            sftp.close()
        except (SSHException, SFTPError):
            if sftp is not None:
                sftp.close()

        # Parse selected config to determine arguments for the playback script
        selected_config = re.sub("\s", " ", selected_config)
        items = selected_config.split(" ")

        netmode = "rtsp"
        port = ""
        rtsp_key = "stream"
        format = "h264"
        framerate = 30
        for i in range(len(items)):
            if items[i] == "--netmode":
                netmode = items[i+1]
            elif items[i] == "--port":
                port = items[i+1]
            elif items[i] == "--rtspkey":
                rtsp_key = items[i+1]
            elif items[i] == "--format":
                format = items[i+1]
            elif items[i] == "--framerate":
                try:
                    framerate = int(items[i+1])
                except:
                    pass
        
        # Double framerate for playback if enabled
        if self.ui.cbx_camstream_2fr.isChecked():
            framerate *= 2

        # Determine address from netmode setting
        if netmode == "rtsp":
            address = self.ui.txt_address.text()
            if port == "":
                port = "8554"
        elif netmode == "tcp":
            address = self.ui.txt_address.text()
            if port == "":
                port = "5008"
        elif netmode == "udp":
            address = "127.0.0.1"
            if port == "":
                port = "5008"
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        cmd = self.construct_play_command(address, netmode, port, rtsp_key, player, framerate, format)
        print(cmd)
        p = subprocess.Popen(cmd, startupinfo=startupinfo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pdialog = PlayStreamDialog("Playing Stream", "Playing stream '{0}' using {1}...".format(stream, player), p, self)
        self.camstreams.append(pdialog)
        pdialog.finished.connect(lambda res: self.camstreams.remove(pdialog))
        pdialog.open()
    
    def construct_play_command(self, address, netmode, port, rtspkey, player, framerate, format):
        if address == "auto":
            if netmode == "udp":
                address = "127.0.0.1"
            else:
                address = "192.168.10.1"
        
        if port == 0:
            if netmode == "rtsp":
                port = 8554
            else:
                port = 5008

        if netmode == "tcp":
            url = "tcp://{0}:{1}".format(address, port)
        elif netmode == "udp":
            url = "udp://{0}:{1}".format(address, port)
        elif netmode == "rtsp":
            url = "rtsp://{0}:{1}/{2}".format(address, port, rtspkey)
        else:
            print("ERROR: Unknown netmode.")

        if player == "auto":
            if shutil.which("ffplay") is not None:
                player = "ffplay"
            elif shutil.which("mpv") is not None:
                player = "mpv"
            elif shutil.which("mplayer") is not None:
                player = "mplayer"
            else:
                print("ERROR: No player found. Install either ffplay, mpv, or mplayer and make sure it is in your PATH.")

        if player == "ffplay":
            if not shutil.which("ffplay"):
                print("ERROR: ffplay not found. Install ffmpeg and ensure ffplay is in your PATH.")
            
            if netmode != "rtsp":
                cmd = "ffplay -probesize 32 -framerate {fps} -fflags nobuffer -flags low_delay -framedrop -sync ext {url}".format(fps=framerate, url=url)
            else:
                # Cannot use -framerate with rtsp
                cmd = "ffplay -probesize 32 -fflags nobuffer -flags low_delay -framedrop -sync ext {url}".format(url=url)
                    
        if player == "mpv":
            if not shutil.which("mpv"):
                print("ERROR: mpv not found. Install mpv and ensure it is in your PATH.")
            
            # MPV cannot reliably detect MJPEG and rejects the stream by default
            # Using --demuxer-lavf-probescore=10 fixes this
            if format == "h264":
                extra = ""
            else:
                extra = "--demuxer-lavf-probescore=10"

            cmd = "mpv --no-cache --untimed --profile=low-latency --no-correct-pts --fps={fps} --osc=no {extra} {url}".format(fps=framerate, url=url, extra=extra)
        
        if player == "mplayer":
            if not shutil.which("mplayer"):
                print("ERROR: mplayer not found. Install mplayer and ensure it is in your PATH.")
            if url.startswith("tcp") or url.startswith("udp"):
                url = "ffmpeg://{0}".format(url)
            
            if format == "auto":
                print("ERROR: mplayer cannot auto detect format. Specify a format using --format")
            elif format == "mjpeg":
                cmd = "mplayer -benchmark -nocache -fps {fps} -demuxer lavf {url}".format(fps=framerate, url=url)
            elif format == "h264":
                cmd = "mplayer -benchmark -nocache -fps {fps} -demuxer h264es {url}".format(fps=framerate, url=url)
            else:
                print("ERROR: Unknown format specified.")
        return cmd
        
        
