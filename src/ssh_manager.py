
from enum import Enum, auto
from typing import Optional, Tuple
from PySide6.QtCore import QObject, QTimer, Signal
from ssh2.session import Session
from ssh2.exceptions import AuthenticationError, SessionError
import socket
import select

class SSHError(Enum):
    NoError = auto()
    SocketConnectError = auto()
    SshConnectError = auto()
    AuthError = auto()
    Unknown = auto()

class SSHManager(QObject):

    connection_lost = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent=parent)
        self.__socket = None
        self.__session = None
        self.__session
        self.__connection_check_timer = QTimer(self)

        self.__connection_check_timer.timeout.connect(self.__check_connected)

    def __check_connected(self):
        try:
            self.__session.
        except select.error:
            print("ERROR HERE!!!")

    def connect_to_robot(self, address: str, port: int, user: str, password: str,
            connect_timeout: float, operation_timeout: float) -> Tuple[SSHError, str]:
        # Disconnect first if needed
        self.disconnect_from_robot()

        # Connect socket
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.__socket.settimeout(connect_timeout)
        try:
            self.__socket.connect((address, port))
            self.__connection_check_timer.start(5000)
        except (socket.timeout, TimeoutError) as e:
            return SSHError.SocketConnectError
        self.__socket.settimeout(operation_timeout)

        # Connect SSH
        try:
            self.__session = Session()
            self.__session.handshake(self.__socket)
            self.__session.userauth_password(user, password)
        except SessionError as e:
            self.__socket.close()
            return SSHError.SshConnectError, str(e)
        except AuthenticationError as e:
            self.__socket.close()
            return SSHError.AuthError, str(e)
        except Exception as e:
            self.__socket.close()
            return SSHError.Unknown, str(e)
        
        return SSHError.NoError, ""
    
    def disconnect_from_robot(self):
        if self.__session is not None:
            self.__session.disconnect()
            self.__session = None
        if self.__socket is not None:
            self.__socket.close()
            self.__socket = None

    @property
    def is_connected(self) -> bool:
        return self.__session is not None

    def run_command(self, cmd: str) -> Tuple[int, bytes, bytes]:
        channel = self.__session.open_session()
        channel.execute(cmd)

        stdout_buffer = bytearray()
        size, data = channel.read()
        while size > 0:
            stdout_buffer.extend(data)
            size, data = channel.read()
        
        stderr_buffer = bytearray()
        size, data = channel.read_stderr()
        while size > 0:
            stderr_buffer.extend(data)
            size, data = channel.read_stderr()

        channel.close()
        exit_code = channel.get_exit_status()

        return exit_code, bytes(stdout_buffer), bytes(stderr_buffer)
    
    # TODO: SFTP stuff

