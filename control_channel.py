import socket
from contextlib import suppress
from threading import Thread

from miscellaneous import *

TCP_TIMEOUT = 0.5
TCP_BUFFER_SIZE = 1024


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
                data: bytes = self.conn.recv(TCP_BUFFER_SIZE)
            except OSError:  # Exception on connection change
                continue

            match data:
                case b'SPEAKER_CONFIG':
                    config = self.app_server.speaker.config
                    self.conn.sendall(config.to_bytes())
                    print_("Sent SPEAKER_CONFIG to client")
                case b'MICROPHONE_CONFIG':
                    config = self.app_server.microphone.config
                    self.conn.sendall(config.to_bytes())
                    print_("Sent MICROPHONE_CONFIG to client")
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
                print_("Sent RESET to client")

        Thread(target=thread, daemon=True).start()


class ControlChannelClient:
    def __init__(self, server_host: str, control_port: int):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP
        while True:
            print_(f"Attempting TCP connection to {server_host}:{control_port}")
            try:
                self.client_socket.connect((server_host, control_port))
                break
            except ConnectionRefusedError:
                pass
        print_(f"TCP connection successful")
        self.client_socket.settimeout(TCP_TIMEOUT)

    def receive_data(self) -> bytes:
        while True:
            try:
                data = self.client_socket.recv(TCP_BUFFER_SIZE)
                break
            except TimeoutError:
                pass

        # Print message if it is not a command
        if b' ' in data:
            try:
                print_(data.decode())
            except UnicodeDecodeError:
                pass

        return data

    def get_speaker_config(self) -> AudioConfig:
        while True:
            self.client_socket.sendall(b'SPEAKER_CONFIG')
            data = self.receive_data()
            if (config := AudioConfig.from_bytes(data)) is not None:
                print_("Received SPEAKER_CONFIG from server")
                return config

    def get_microphone_config(self) -> AudioConfig:
        while True:
            self.client_socket.sendall(b'MICROPHONE_CONFIG')
            data = self.receive_data()
            if (config := AudioConfig.from_bytes(data)) is not None:
                print_("Received MICROPHONE_CONFIG from server")
                return config

    def listen_server(self):
        """ Blocks until a RESET signal is received from server. """
        while True:
            if self.receive_data() == b'RESET':
                print_("Received RESET from server")
                return

    def toggle_microphone(self):
        self.client_socket.sendall(b'TOGGLE_MICROPHONE')
        print_("Sent TOGGLE_MICROPHONE to server")
