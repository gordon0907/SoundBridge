import socket
import time
from contextlib import suppress
from threading import Thread

from config import *
from utils import *


class ControlChannelServer:
    def __init__(self, app_server, server_host: str, server_port: int):
        self.app_server = app_server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.server_socket.bind((server_host, server_port))
        print_(f"UDP control channel listening on port {server_port}")

        # Set to an invalid placeholder; will be updated with a valid address upon receiving data
        self.client_address = '', 0

        Thread(target=self._request_handler, daemon=True).start()

    def stop_client(self):
        self._send_client_with_retries(b'STOP')

    def start_client(self):
        self._send_client_with_retries(b'START')

    def _send_client_with_retries(self, data: bytes, interval: float = 0.1, attempts: int = 3):
        """Send data to the client with multiple best-effort attempts."""
        with suppress(OSError):
            for i in reversed(range(attempts)):
                self.server_socket.sendto(data, self.client_address)
                if i > 0:
                    time.sleep(interval)
            print_(f"{Color.CYAN}Sent {data.decode()} to client{Color.RESET}")

    def _request_handler(self):
        while True:
            previous_client_address = self.client_address
            command, self.client_address = self.server_socket.recvfrom(MAX_PACKET_SIZE)

            match command:
                case b'SPEAKER_CONFIG' | b'MICROPHONE_CONFIG':
                    config = (
                        self.app_server.speaker.config
                        if command == b'SPEAKER_CONFIG'
                        else self.app_server.microphone.config
                    )
                    self.server_socket.sendto(command[:1] + config.to_bytes(), self.client_address)
                    print_(f"{Color.CYAN}Sent {command.decode()} to client{Color.RESET}")
                case b'TOGGLE_MICROPHONE':
                    if self.app_server.microphone.is_alive():
                        self.app_server.microphone.stop()
                    else:
                        self.app_server.microphone.start()
                    self.server_socket.sendto(b'MIC ON' if self.app_server.microphone.is_alive() else b'MIC OFF',
                                              self.client_address)
                case b'HEARTBEAT':
                    pass
                case _:
                    # Revert client address on unknown command
                    self.client_address = previous_client_address


class ControlChannelClient:
    def __init__(self, server_host: str, server_port: int):
        self.server_address = server_host, server_port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.client_socket.settimeout(SOCKET_TIMEOUT)

        Thread(target=self._heartbeat, daemon=True).start()

    def get_speaker_config(self) -> AudioConfig:
        return self._get_audio_config(b'SPEAKER_CONFIG')

    def get_microphone_config(self) -> AudioConfig:
        return self._get_audio_config(b'MICROPHONE_CONFIG')

    def toggle_microphone(self):
        self.client_socket.sendto(b'TOGGLE_MICROPHONE', self.server_address)
        print_(f"{Color.CYAN}Sent TOGGLE_MICROPHONE to server{Color.RESET}")

    def wait_for_stop(self):
        self._wait_for_command(b'STOP')

    def wait_for_start(self):
        self._wait_for_command(b'START')

    def _get_audio_config(self, command: bytes) -> AudioConfig:
        while True:
            self.client_socket.sendto(command, self.server_address)
            data = self._receive_data()

            prefix_byte, config_bytes = data[:1], data[1:]
            config: AudioConfig | None = AudioConfig.from_bytes(config_bytes)

            if prefix_byte == command[:1] and config is not None:
                print_(f"{Color.YELLOW}Received {command.decode()} from server{Color.RESET}")
                return config

    def _wait_for_command(self, expected_command: bytes):
        """Block until the expected command is received from the server."""
        while True:
            if self._receive_data() == expected_command:
                print_(f"{Color.YELLOW}Received {expected_command.decode()} from server{Color.RESET}")
                return

    def _receive_data(self) -> bytes:
        """Return received data or empty bytes if a timeout occurs."""
        try:
            data, _ = self.client_socket.recvfrom(MAX_PACKET_SIZE)
        except TimeoutError:
            return b''

        # Handle specific notification messages
        if data in (b'MIC ON', b'MIC OFF'):
            print_(f"{Color.MAGENTA}{data.decode()}{Color.RESET}")

        return data

    def _heartbeat(self, interval: float = 60.):
        """Periodically send packets to prevent Windows Firewall timeouts that block traffic."""
        while time.sleep(interval) or True:
            self.client_socket.sendto(b'HEARTBEAT', self.server_address)
