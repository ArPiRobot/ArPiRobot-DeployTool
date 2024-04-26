
from ast import Tuple
from genericpath import isdir
import socket
import tarfile
from threading import local
import traceback
from typing import Any, Callable, List, Optional
from PySide6.QtCore import QDir, QFile, QFileInfo, QIODevice, QObject, QRegularExpression, QRegularExpressionMatch, QRunnable, QTextStream, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QPalette, QShowEvent, QCloseEvent, QGuiApplication, QIntValidator, QTextCursor, QRegularExpressionValidator, QValidator, QFont
from PySide6.QtWidgets import QDialog, QFileDialog, QMainWindow, QMessageBox, QProgressDialog, QApplication, QWidget
from paramiko.pkey import PKey
from paramiko.sftp import SFTPError
from paramiko.sftp_client import SFTPClient
from log_dialog import LogDialog
from ui_deploy_tool import Ui_DeployTool
from playstream_dialog import PlayStreamDialog
from about_dialog import AboutDialog
from settings_dialog import SettingsDialog
from paramiko.client import SSHClient, MissingHostKeyPolicy
from paramiko.ssh_exception import SSHException
from util import settings_manager, WIFI_COUNTRY_CODES, WIFI_COUNTRY_NAMES
from zipfile import ZipFile
import time
import os
import subprocess
import sys
import shutil
import json
import pathlib
import platform
import ctypes
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


class DeployToolWindow(QMainWindow):

    change_progress_msg_sig = Signal(str)
    append_log_sig = Signal(str)
    set_versions_sig = Signal(str, str)
    update_status_sig = Signal(float, int, int, WritableState)
    update_net_info_sig = Signal(str, str, str, str, str, str)
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

        # Populate country codes in combo box
        self.ui.cbx_wifi_country.addItems(WIFI_COUNTRY_NAMES)

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

        # Store channels allowed for wifi
        self.channels_24 = []
        self.channels_50 = []

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
        self.ui.btn_install_sysroot.clicked.connect(self.install_sysroot_package)

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

        self.ui.cbx_wifi_band.currentIndexChanged.connect(self.wifi_band_changed)
        self.ui.cbx_wifi_country.currentIndexChanged.connect(self.wifi_country_changed)

        self.ui.btn_launch_player.clicked.connect(self.play_stream)

        # Startup
        self.disable_robot_tabs()
        self.ssh_check_timer.start(1000)

        # Load last used connection settings
        self.ui.txt_address.setText(settings_manager.robot_address)
        self.ui.txt_username.setText(settings_manager.robot_user)
        self.ui.cbx_longer_timeouts.setChecked(settings_manager.longer_timeouts)

        self.__on_color_change()
        self.__set_font_size()

    def __on_color_change(self):
        pass

    def __set_font_size(self):
        size = QFont().pointSizeF()
        if settings_manager.larger_fonts:
            size *= 1.2
        app = QApplication.instance()
        app.setStyleSheet("{0}\n{1}".format(app.styleSheet(), "*{{font-size: {0}pt}}".format(size)))

    def showEvent(self, event: QShowEvent):
        # TODO: Debug properly.
        # For some reason the "This PC" tab is not shown on Windows as of QT 6.5
        # May affect other OSes too (untested)
        # This is a workaround
        self.ui.tabs_main.setTabVisible(0, False)
        self.ui.tabs_main.setTabVisible(0, True)
        self.ui.tabs_main.setCurrentIndex(0)
        self.ui.tabs_main.setCurrentIndex(1)

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
            self.__set_font_size()

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

    def handle_populate_this_pc_exec(self, e):
        self.hide_progress()
        print("EXCEPTION")
        print(e)
        traceback.print_exc()

    def populate_this_pc(self):
        self.show_progress("Searching", "Searching for Tools...")
        task = Task(self, self.do_populate_this_pc)
        task.task_complete.connect(self.hide_progress)
        task.task_exception.connect(self.handle_populate_this_pc_exec)
        self.start_task(task)

    # Copied from cpython shutil source
    # https://github.com/python/cpython/blob/main/Lib/shutil.py
    # Adapted too return all instances of the command in the path
    # Instead of just the first one found
    # Mimics behavior of Linux "which -a"
    def which_all(self, cmd, mode=os.F_OK | os.X_OK, path=None):
        # Check that a given file can be accessed with the correct mode.
        # Additionally check that `file` is not a directory, as on Windows
        # directories pass the os.access check.
        def _access_check(fn, mode):
            return (os.path.exists(fn) and os.access(fn, mode)
                    and not os.path.isdir(fn))
        """Given a command, mode, and a PATH string, return the path which
        conforms to the given mode on the PATH, or None if there is no such
        file.
        `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
        of os.environ.get("PATH"), or can be overridden with a custom search
        path.
        """
        # If we're given a path with a directory part, look it up directly rather
        # than referring to PATH directories. This includes checking relative to the
        # current directory, e.g. ./script
        if os.path.dirname(cmd):
            if _access_check(cmd, mode):
                return cmd
            return None

        use_bytes = isinstance(cmd, bytes)

        if path is None:
            path = os.environ.get("PATH", None)
            if path is None:
                try:
                    path = os.confstr("CS_PATH")
                except (AttributeError, ValueError):
                    # os.confstr() or CS_PATH is not available
                    path = os.defpath
            # bpo-35755: Don't use os.defpath if the PATH environment variable is
            # set to an empty string

        # PATH='' doesn't match, whereas PATH=':' looks in the current directory
        if not path:
            return None

        if use_bytes:
            path = os.fsencode(path)
            path = path.split(os.fsencode(os.pathsep))
        else:
            path = os.fsdecode(path)
            path = path.split(os.pathsep)

        if sys.platform == "win32":
            # The current directory takes precedence on Windows.
            curdir = os.curdir
            if use_bytes:
                curdir = os.fsencode(curdir)
            if curdir not in path:
                path.insert(0, curdir)

            # PATHEXT is necessary to check on Windows.
            pathext_source = os.getenv("PATHEXT") or ".COM;.EXE;.BAT;.CMD;.VBS;.JS;.WS;.MSC"
            pathext = [ext for ext in pathext_source.split(os.pathsep) if ext]

            if use_bytes:
                pathext = [os.fsencode(ext) for ext in pathext]
            # See if the given file matches any of the expected path extensions.
            # This will allow us to short circuit when given "python.exe".
            # If it does match, only test that one, otherwise we have to try
            # others.
            if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
                files = [cmd]
            else:
                files = [cmd + ext for ext in pathext]
        else:
            # On other platforms you don't have things like PATHEXT to tell you
            # what file suffixes are executable, so just pass on cmd as-is.
            files = [cmd]

        seen = set()
        found = []
        for dir in path:
            normdir = os.path.normcase(dir)
            if not normdir in seen:
                seen.add(normdir)
                for thefile in files:
                    name = os.path.join(dir, thefile)
                    if _access_check(name, mode):
                        found.append(name)
        return found

    def do_populate_this_pc(self):
        # Show then hide too fast causes issues on Ubuntu 22.04 
        # (and likely other systems using XCB backend)
        time.sleep(0.1)

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
        
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        else:
            startupinfo = None
        
        # LLVM Version
        if shutil.which('clang') is None:
            self.ui.txt_llvm_version.setText(self.tr("Not Installed"))
        else:
            cmd = subprocess.Popen(["clang", "--version"], startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # First line of output is clang version [VERSION]
            # However, sometimes it's got a system vendor name eg: Ubuntu clang version [VERSION]
            # So just find the first digit and go from there
            line = cmd.stdout.readline().decode().strip()
            if line.lower().find("apple clang") != -1:
                # Check where brew installs llvm clang on mac
                if os.path.exists("/usr/local/opt/llvm/bin/clang"):
                    cmd = subprocess.Popen(["/usr/local/opt/llvm/bin/clang", "--version"], startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    line = cmd.stdout.readline().decode().strip()
                    pos = 0
                    for i in range(len(line)):
                        c = line[i]
                        if c.isdigit():
                            pos = i
                            break
                    self.ui.txt_llvm_version.setText(line[pos:])
                else:
                    self.ui.txt_llvm_version.setText(self.tr("Only found Apple Clang, requires LLVM Clang"))
            else:
                pos = 0
                for i in range(len(line)):
                    c = line[i]
                    if c.isdigit():
                        pos = i
                        break
                self.ui.txt_llvm_version.setText(line[pos:])

        # Load cmake version
        if shutil.which('cmake') is None:
            self.ui.txt_cmake_version.setText(self.tr("Not Installed"))
        else:
            cmd = subprocess.Popen(["cmake", "--version"], startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # First line of output is cmake version [VERSION]
            self.ui.txt_cmake_version.setText(cmd.stdout.readline().decode()[14:].strip())

        # Load ninja version
        if shutil.which('ninja') is None:
            self.ui.txt_ninja_version.setText(self.tr("Not Installed"))
        else:
            cmd = subprocess.Popen(["ninja", "--version"], startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # First line of output is [VERSION]
            self.ui.txt_ninja_version.setText(cmd.stdout.readline().decode().strip())
        
        # Load pkgconfig version
        if shutil.which('pkg-config') is None:
            self.ui.txt_pkgconfig_version.setText(self.tr("Not Installed"))
        else:
            cmd = subprocess.Popen(["pkg-config", "--version"], startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.ui.txt_pkgconfig_version.setText(cmd.stdout.readline().decode().strip())
        
        # Check for installed sysroots
        found_sysroots = []
        path = QDir.homePath() + "/.arpirobot/sysroot/"
        if os.path.exists(path):
            for f in os.listdir(path):
                if os.path.isdir("{0}/{1}".format(path, f)) and not f.startswith("."):
                    verfile = "{0}/{1}/version.txt".format(path, f)
                    if os.path.isfile(verfile):
                        try:
                            with open(verfile, 'r') as verfileobj:
                                version = verfileobj.readline().replace("\r", "").replace("\n", "")
                        except:
                            version = "unknown"
                    else:
                        version = "unknown"
                    found_sysroots.append("{} ({})".format(f, version))
        if len(found_sysroots) == 0:
            self.ui.txt_sysroot.setText("No sysroots installed.")
        else:
            self.ui.txt_sysroot.setText(", ".join(found_sysroots))

        # Find any python interpreters in path. List versions
        versions = []
        interpreters: List[str] = []
        python_exe_names = ["python", "python3"]
        for i in range(20):
            python_exe_names.append("python3.{0}".format(i))
            python_exe_names.append("python3{0}".format(i))
        for name in python_exe_names:
            interpreters.extend(self.which_all(name))
        for interpreter in interpreters:
            cmd = subprocess.Popen([interpreter.replace("\r", "").replace("\n", ""), "--version"], startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Output: Python [VERSION]
            versions.append(cmd.stdout.readline().decode()[7:].strip())
        # Remove duplicate version numbers
        versions = list(dict.fromkeys(versions))
        if len(versions) == 0:
            self.ui.txt_pc_python_version.setText("Not Installed")
        else:
            v_str = versions[0]
            for v in versions[1:]:
                if v != "":
                    v_str = "{0}, {1}".format(v_str, v)
            self.ui.txt_pc_python_version.setText(v_str)

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
        # No longer needed. Extension generates env file
        # try:
        #     self.set_pythonpath()
        # except:
        #     print(traceback.format_exc())
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
        if platform.system() == "Linux":
            if not os.path.exists(home + "/.config/environment.d/"):
                os.mkdir(home + "/.config/environment.d/")
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
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        else:
            startupinfo = None
        subprocess.call(cmd, startupinfo=startupinfo)

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

    def do_install_sysroot_package(self, filename: str):
        # Find what.txt to verify this is a sysroot package and to determine where to extract it
        with tarfile.open(filename) as tf:
            if "what.txt" in tf.getnames():
                # Construct destination
                what = tf.extractfile("what.txt").readline().strip().decode()
                final_path = QDir.homePath() + "/.arpirobot/{0}".format(what)

                # Delete old sysroot if installed
                if os.path.exists(final_path):
                    shutil.rmtree(final_path)
                
                # Extract sysroot
                tf.extractall(path=final_path)

                # The sysroot will use symlinks. Windows supports symlinks
                # and tarfile.extractall will create them, as long as running as admin
                # (or if the user has developer mode enabled, but it is assumed most users don't)
                # However, the slashes will be forward slashes, which breaks things.\
                # So we loop over and fix all symlinks to use backslashes...
                # https://github.com/python/cpython/issues/57911
                if platform.system() == "Windows":
                    for root, dirs, files in os.walk(final_path):
                        for file in dirs + files:
                            file_path = os.path.join(root, file)
                            if os.path.islink(file_path):
                                # Python can handle forward slash, so this resolves the correct link path
                                target_path = os.path.realpath(file_path)

                                # Convert to relative path and ensure all backlashes
                                # Also make sure all start with .\ or ..\ (this is what 7zip does when it extracts tar symlinks)
                                new_target_path = os.path.relpath(target_path, os.path.dirname(file_path))
                                new_target_path = new_target_path.replace("/", "\\")

                                # Then re-create the link with correct relative paths
                                os.remove(file_path)
                                os.symlink(new_target_path, file_path, os.path.isdir(target_path))
                
                
                # Allow all sysroot binaries to execute on macos
                if platform.system() == "Darwin":
                    os.system("zsh -c 'chmod -R +x {}'".format(final_path))
                    os.system("zsh -c 'xattr -dr {}'".format(final_path))

                # Allow all sysroot binaries to execute on linux
                if platform.system() == "Linux":
                    os.system("sh -c 'chmod -R +x {}'".format(final_path))
            else:
                raise Exception("Not a valid sysroot archive.")

    def convert_formats(self, formats) -> str:
        fmt_str = ""
        for f in formats:
            if f[0] == "gztar":
                fmt_str = "{0} *.{1}".format(fmt_str, "tar.gz")
                fmt_str = "{0} *.{1}".format(fmt_str, "tgz")
            if f[0] == "bztar":
                fmt_str = "{0} *.{1}".format(fmt_str, "tar.bz")
                fmt_str = "{0} *.{1}".format(fmt_str, "tbz")
            if f[0] == "xztar":
                fmt_str = "{0} *.{1}".format(fmt_str, "tar.xz")
                fmt_str = "{0} *.{1}".format(fmt_str, "txz")
            fmt_str = "{0} *.{1}".format(fmt_str, f[0])
        return fmt_str

    def handle_sysroot_success(self, res):
         self.hide_progress()
         self.populate_this_pc()

    def handle_sysroot_failure(self, e):
        self.hide_progress()
        print(e)
        dialog = QMessageBox(parent=self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setText(self.tr("Make sure the archive exists, is a known format, and is not corrupted."))
        dialog.setWindowTitle(self.tr("Error Installing Sysroot"))
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.exec()

    def install_sysroot_package(self):
        # Making symlinks requires admin on windows
        if platform.system() == "Windows":
            try:
                if ctypes.windll.shell32.IsUserAnAdmin() != 1:
                    dialog = QMessageBox(parent=self)
                    dialog.setIcon(QMessageBox.Warning)
                    dialog.setText(self.tr("DeployTool must be run as admin to install sysroot."))
                    dialog.setWindowTitle(self.tr("Error Installing Sysroot"))
                    dialog.setStandardButtons(QMessageBox.Ok)
                    dialog.exec()
                    return
            except:
                print("UNABLE TO CHECK ADMIN STATUS")
        
        fmt_str = self.convert_formats(shutil.get_archive_formats())
        filename = QFileDialog.getOpenFileName(self, self.tr("Open Update Package"), QDir.homePath(), self.tr("Archives (") + fmt_str + ")")[0]
        if filename == "":
            return

        # Perform installation of update package on background thread
        self.show_progress("Installing Sysroot", "Extracting sysroot package")
        task = Task(self, self.do_install_sysroot_package, filename)
        task.task_complete.connect(self.handle_sysroot_success)
        task.task_exception.connect(self.handle_sysroot_failure)
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

    def handle_ssh_disconnect(self):
        self.do_disconnect()
        dialog = QMessageBox(parent=self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setText("Connection to the robot was lost.")
        dialog.setWindowTitle("Disconnected")
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.exec()

    def check_ssh_connection(self):
        if self.ssh_connected:
            if not self.ssh.get_transport().is_active():
                self.handle_ssh_disconnect()
            else:
                # is_active doesn't always work (eg change WiFi network on Linux)
                try:
                    _, stdout, _ = self.ssh.exec_command("true", timeout=3)
                    stdout.channel.recv_exit_status()
                except:
                    # Timed out (or failed to even open session). Disconnected.
                    self.handle_ssh_disconnect()
                

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
        line = stdout.readline().strip()
        opts_list = []
        try:
            spos = line.index("(")
            line = line[spos+1:-1]
            opts_list = line.split(",")
            if "ro" in opts_list:
                return WritableState.Readonly
            elif "rw" in opts_list:
                return WritableState.ReadWrite
            else:
                return WritableState.Unknown
        except:
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

    def do_set_versions(self, img_ver: str, py_ver: str):
        self.ui.txt_image_version.setText(img_ver)
        self.ui.txt_python_version.setText(py_ver)

    def set_versions(self, img_ver: str, py_ver: str):
        self.set_versions_sig.emit(img_ver, py_ver)

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
        self.set_versions(img_version, py_version)

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

    def parse_valid_channels(self):
        _, stdout_caps, _ = self.ssh.exec_command("dt-wifi_caps.py", timeout=self.command_timeout)
        for line in stdout_caps.readlines():
            if line.startswith("2.4GHz: "):
                self.channels_24 = eval(line.strip()[8:])
            if line.startswith("5.0GHz: "):
                self.channels_50 = eval(line.strip()[8:])
            if line.startswith("2.4GHz Disabled: "):
                channels_24_disabled = eval(line.strip()[17:])
                for channel in channels_24_disabled:
                    if channel in self.channels_24:
                        self.channels_24.remove(channel)
            if line.startswith("5.0GHz Disabled: "):
                channels_50_disabled = eval(line.strip()[17:])
                for channel in channels_50_disabled:
                    if channel in self.channels_50:
                        self.channels_50.remove(channel)

    def do_change_country_code(self):
        code = WIFI_COUNTRY_CODES[self.ui.cbx_wifi_country.currentIndex()]
        _, stdout_regdom, _ = self.ssh.exec_command("dt-wifi_regdom.sh {}".format(code), timeout=self.command_timeout)
        stdout_regdom.channel.recv_exit_status()

        # Valid channels can change with country code
        self.parse_valid_channels()

        # If valid channels for the band change, need to rebuild channel options in UI
        self.wifi_band_changed(self.ui.cbx_wifi_band.currentIndex())
    
    def wifi_country_changed_done(self, arg):
        self.hide_progress()

    def wifi_country_changed(self, index: int):
        self.show_progress(self.tr("Changing Country"), self.tr("Changing wifi country code..."))
        task = Task(self, self.do_change_country_code)
        task.task_complete.connect(self.wifi_country_changed_done)
        task.task_exception.connect(self.wifi_country_changed_done)
        self.start_task(task)

    def wifi_band_changed(self, index: int):
        if index == 0:
            self.ui.cbx_wifi_channel.clear()
            self.ui.cbx_wifi_channel.addItem("Auto (Not Recommended)")
            self.ui.cbx_wifi_channel.addItems(self.channels_24)
        elif index == 1:
            self.ui.cbx_wifi_channel.clear()
            self.ui.cbx_wifi_channel.addItem("Auto (Not Recommended)")
            self.ui.cbx_wifi_channel.addItems(self.channels_50)

    def do_update_network_info(self, hostname: str, ssid: str, password: str, country: str, channel: str, band: str):
        self.ui.cbx_wifi_band.clear()
        if len(self.channels_24) != 0:
            self.ui.cbx_wifi_band.addItem("2.4GHz")
        if len(self.channels_50) != 0:
            self.ui.cbx_wifi_band.addItem("5.0GHz")
        
        self.ui.cbx_wifi_channel.clear()

        if channel == "0":
            channel = "Auto (Not Recommended)"

        self.ui.txt_hostname.setText(hostname)
        self.ui.txt_wifi_ssid.setText(ssid)
        self.ui.txt_wifi_pass.setText(password)
        if band == "g":
            self.ui.cbx_wifi_band.setCurrentIndex(0)
            self.ui.cbx_wifi_channel.addItem("Auto (Not Recommended)")
            self.ui.cbx_wifi_channel.addItems(self.channels_24)
        elif band == "a":
            self.ui.cbx_wifi_band.setCurrentIndex(1)
            self.ui.cbx_wifi_channel.addItem("Auto (Not Recommended)")
            self.ui.cbx_wifi_channel.addItems(self.channels_50)
        
        idx = 0
        if country in WIFI_COUNTRY_CODES:
            idx = WIFI_COUNTRY_CODES.index(country)
        self.ui.cbx_wifi_country.setCurrentIndex(idx)

        self.ui.cbx_wifi_channel.setCurrentText(channel)

    def update_network_info(self, hostname: str, ssid: str, password: str, country: str, channel: str, band: str):
        self.update_net_info_sig.emit(hostname, ssid, password, country, channel, band)

    def do_populate_network_settings(self):
        _, stdout_host, _ = self.ssh.exec_command("dt-hostname.sh", timeout=self.command_timeout)
        _, stdout_ap, _ = self.ssh.exec_command("dt-wifi_ap.sh", timeout=self.command_timeout)
        _, stdout_regdom, _ = self.ssh.exec_command("dt-wifi_regdom.sh", timeout=self.command_timeout)

        hostname = stdout_host.readline().strip()

        ssid = stdout_ap.readline().strip()
        password = stdout_ap.readline().strip()
        channel = stdout_ap.readline().strip()
        band = stdout_ap.readline().strip()

        country = stdout_regdom.readline().strip()

        self.parse_valid_channels()
        
        self.update_network_info(hostname, ssid, password, country, channel, band)

    def populate_network_settings(self):
        self.show_progress(self.tr("Loading"), self.tr("Loading info from robot..."))
        task = Task(self, self.do_populate_network_settings)
        task.task_complete.connect(lambda res: self.hide_progress())
        task.task_exception.connect(lambda e: self.hide_progress())
        self.start_task(task)
    
    def do_apply_network_settings(self, ssid: str, psk: str, channel: int, band: str):
        # dt-wifi_ap.sh handles writable check and making rw if needed
        # This is necessary because DT may drop comms due to network changes
        # Thus nohup is used to run the script
        # But as a result, the deploy tool doesn't know when the changes are actually applied
        # And may make ro too soon
        # orig_state = self.do_writable_check()
        # if orig_state != WritableState.ReadWrite:
        #     self.make_robot_writable()

        _, stdout, _ = self.ssh.exec_command("nohup dt-wifi_ap.sh '{0}' '{1}' '{2}' '{3}' > /dev/null 2>&1".format(ssid, psk, channel, band),
                timeout=self.command_timeout)
        stdout.channel.recv_exit_status()

        # if orig_state == WritableState.Readonly:
        #     self.make_robot_readonly()

    def apply_network_settings(self):
        ssid = self.ui.txt_wifi_ssid.text()
        psk = self.ui.txt_wifi_pass.text()
        channel = self.ui.cbx_wifi_channel.currentText()
        if channel == "Auto (Not Recommended)":
            channel = 0
        else:
            channel = int(channel)
        # country = WIFI_COUNTRY_CODES[self.ui.cbx_wifi_country.currentIndex()]
        
        band_idx = self.ui.cbx_wifi_band.currentIndex()
        bands = ["g", "a"]   # 2.4, 5.0
        band = bands[band_idx]
        
        if len(ssid) < 2:
            dialog = QMessageBox(parent=self)
            dialog.setIcon(QMessageBox.Warning)
            dialog.setText(self.tr("SSID must be at least 2 characters in length."))
            dialog.setWindowTitle(self.tr("WiFi Settings Invalid"))
            dialog.setStandardButtons(QMessageBox.Ok)
            dialog.exec()
            return
        
        if len(psk) < 8:
            dialog = QMessageBox(parent=self)
            dialog.setIcon(QMessageBox.Warning)
            dialog.setText(self.tr("Password must be at least 8 characters in length."))
            dialog.setWindowTitle(self.tr("WiFi Settings Invalid"))
            dialog.setStandardButtons(QMessageBox.Ok)
            dialog.exec()
            return

        self.show_progress(self.tr("Applying Network Settings"), self.tr("Applying network setting changes on robot..."))
        task = Task(self, self.do_apply_network_settings, ssid, psk, channel, band)
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
    
    def play_stream(self):
        # Check to make sure player is installed
        player = self.ui.cbx_video_player.currentText()
        stream = self.ui.txt_stream_key.text()
        robot_ip = self.ui.txt_address.text()

        # Make sure player is in PATH
        path = shutil.which(player)
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
            dialog.setText(self.tr("No stream key. Enter a stream key to play a stream."))
            dialog.setWindowTitle(self.tr("Cannot Play Stream"))
            dialog.setStandardButtons(QMessageBox.Ok)
            dialog.exec()
            return

        # Construct player command
        rtsp_url = "rtsp://{0}:8554/{1}".format(robot_ip, stream)
        cmd = []
        if player == "mpv":
            cmd = ["mpv", "--no-cache", "--untimed", "--profile=low-latency", "--osc=no", "--hwdec=auto", rtsp_url]
        elif player == "mplayer":
            cmd = ["mplayer", "-benchmark", "-nocache", rtsp_url]
        elif player == "ffplay":
            cmd = ["ffplay", "-probesize", "32", "-fflags", "nobuffer", "-flags", "low_delay", "-framedrop", 
                        "-sync", "ext", rtsp_url]
        print(" ".join(cmd))

        # Launch player
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        else:
            startupinfo = None
        try:
            p = subprocess.Popen(cmd, startupinfo=startupinfo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            dialog = QMessageBox(parent=self)
            dialog.setIcon(QMessageBox.Warning)
            dialog.setText(str(e))
            dialog.setWindowTitle(self.tr("Failed to Launch Video Player"))
            dialog.setStandardButtons(QMessageBox.Ok)
            dialog.exec()
            return
        pdialog = PlayStreamDialog("Playing Stream", "Playing stream '{0}' using {1}...".format(stream, player), p, self)
        self.camstreams.append(pdialog)
        pdialog.finished.connect(lambda res: self.camstreams.remove(pdialog))
        pdialog.show()
