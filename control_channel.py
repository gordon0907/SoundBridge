import socket
from contextlib import suppress
from threading import Thread

from miscellaneous import *

TCP_TIMEOUT = 1.
TCP_READ_SIZE = 1024


class ControlChannelServer:
    def __init__(self, app_server, control_port: int, server_host: str = ''):
        self.app_server = app_server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP
        self.server_socket.bind((server_host, control_port))
        self.server_socket.listen()  # No pending client queue
        print_(f"TCP listener started on port {control_port}")

        self.conn, self.addr = None, None
        Thread(target=self.connection_handler, daemon=True).start()

        # Instantiate `request_handler` thread
        self.request_handler_thread = Thread(target=self.request_handler, daemon=True)

    def connection_handler(self):
        while True:
            conn, addr = self.server_socket.accept()

            # Maintain only one connection at a time
            if self.conn is not None:
                self.conn.close()
                print_(f"Closed TCP connection with {self.addr[0]}:{self.addr[1]}")
            self.conn, self.addr = conn, addr
            print_(f"TCP Connected with {self.addr[0]}:{self.addr[1]}")

            if not self.request_handler_thread.is_alive():
                self.request_handler_thread.start()

    def request_handler(self):
        while True:
            try:
                data: bytes = self.conn.recv(TCP_READ_SIZE)
            except OSError:  # Exception on connection change
                continue

            match data:
                case b'SPEAKER_CONFIG':
                    config = self.app_server.speaker.config
                    self.conn.sendall(config.to_bytes())
                    print_(f"{Color.CYAN}Sent SPEAKER_CONFIG to client{Color.RESET}")
                case b'MICROPHONE_CONFIG':
                    config = self.app_server.microphone.config
                    self.conn.sendall(config.to_bytes())
                    print_(f"{Color.CYAN}Sent MICROPHONE_CONFIG to client{Color.RESET}")
                case b'TOGGLE_MICROPHONE':
                    if self.app_server.microphone.is_alive():
                        self.app_server.microphone.stop()
                    else:
                        self.app_server.microphone.start()
                    self.conn.sendall(b'MIC ON' if self.app_server.microphone.is_alive() else b'MIC OFF')

    def notify_client(self):
        def thread():
            # Best effort, regardless of failure
            with suppress(Exception):
                self.conn.sendall(b'RESET')
                print_(f"{Color.CYAN}Sent RESET to client{Color.RESET}")

        Thread(target=thread, daemon=True).start()


class ControlChannelClient:
    def __init__(self, server_host: str, control_port: int):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP
        while True:
            print_(f"Attempting TCP connection to {server_host}:{control_port}")
            with suppress(ConnectionRefusedError):
                self.client_socket.connect((server_host, control_port))
                break
        print_(f"TCP connection successful")
        self.client_socket.settimeout(TCP_TIMEOUT)  # Avoid blocking if expected data is not received

    def receive_data(self) -> bytes:
        """ Return received data or empty bytes if a timeout occurs. """
        try:
            data = self.client_socket.recv(TCP_READ_SIZE)
        except TimeoutError:
            return b''

        # Print message if it is not a command
        if b' ' in data:
            with suppress(UnicodeDecodeError):
                print_(f"{Color.MAGENTA}{data.decode()}{Color.RESET}")

        return data

    def get_speaker_config(self) -> AudioConfig:
        while True:
            self.client_socket.sendall(b'SPEAKER_CONFIG')
            data = self.receive_data()
            if (config := AudioConfig.from_bytes(data)) is not None:
                print_(f"{Color.YELLOW}Received SPEAKER_CONFIG from server{Color.RESET}")
                return config

    def get_microphone_config(self) -> AudioConfig:
        while True:
            self.client_socket.sendall(b'MICROPHONE_CONFIG')
            data = self.receive_data()
            if (config := AudioConfig.from_bytes(data)) is not None:
                print_(f"{Color.YELLOW}Received MICROPHONE_CONFIG from server{Color.RESET}")
                return config

    def listen_server(self):
        """ Blocks until a RESET signal is received from server. """
        while True:
            if self.receive_data() == b'RESET':
                print_(f"{Color.YELLOW}Received RESET from server{Color.RESET}")
                return

    def toggle_microphone(self):
        self.client_socket.sendall(b'TOGGLE_MICROPHONE')
        print_(f"{Color.CYAN}Sent TOGGLE_MICROPHONE to server{Color.RESET}")
