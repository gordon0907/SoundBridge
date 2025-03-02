from __future__ import annotations

import socket
from threading import Thread
from typing import override

import numpy as np
import pyaudiowpatch as pyaudio

from control_channel import ControlChannelClient
from miscellaneous import *

SERVER_HOST = "192.168.0.120"
SERVER_PORT = 2024
CONTROL_PORT = 2025
UDP_TIMEOUT = 1.  # in seconds
UDP_READ_SIZE = 1024


class Speaker(Thread):
    """
    Continuously captures system audio and sends it to the server.
    """

    def __init__(self, app: SoundBridgeClient, config: AudioConfig):
        super().__init__()
        self.app: SoundBridgeClient = app
        self.config = config

        # Get default loopback device info
        self.device_info = self.app.audio_interface.get_default_wasapi_loopback()
        self.stream = None

    @override
    def run(self):
        stream = self.app.audio_interface.open(
            rate=self.config.sample_rate,
            channels=self.config.channels,
            format=self.config.audio_format,
            output=True,
        )  # Helper stream to keep the loopback stream awake
        dummy_audio_data = np.zeros((1, self.config.channels)).tobytes()

        self.stream = self.app.audio_interface.open(
            rate=self.config.sample_rate,
            channels=self.config.channels,
            format=self.config.audio_format,
            input=True,
            input_device_index=self.device_info['index'],
            frames_per_buffer=self.config.num_frames,
        )
        print_(f"{Color.GREEN}Speaker started{Color.RESET}")
        self.app.print_device_info(self)

        while self.stream is not None:
            try:
                stream.write(dummy_audio_data, exception_on_underflow=False)
                audio_data: bytes = self.stream.read(self.config.num_frames, exception_on_overflow=False)
                self.app.send_data(audio_data)
            except (OSError, AttributeError):  # Includes TimeoutError
                continue
        print_(f"{Color.RED}Speaker stopped{Color.RESET}")

    def stop(self):
        """ Stop the thread and ensure it can be started again. """
        if self.is_alive():
            self.stream = None
            self.join()


class Microphone(Thread):
    """
    Continuously receives audio from the server and plays it through the virtual cable.
    """

    def __init__(self, app: SoundBridgeClient, config: AudioConfig):
        super().__init__()
        self.app: SoundBridgeClient = app
        self.config = config

        # Find Virtual Audio Cable (CABLE Input) and get its device info
        for i in range(self.app.audio_interface.get_device_count()):
            device_info = self.app.audio_interface.get_device_info_by_index(i)
            if "CABLE Input" in device_info['name'] and device_info['hostApi'] == 0:  # MME
                self.device_info = device_info
                break
        else:
            raise RuntimeError("No CABLE Input device found")

        self.stream = None

    @override
    def run(self):
        # Create audio stream instance
        self.stream = self.app.audio_interface.open(
            rate=self.config.sample_rate,
            channels=self.config.channels,
            format=self.config.audio_format,
            output=True,
            output_device_index=self.device_info['index'],
            frames_per_buffer=self.config.num_frames,
        )
        print_(f"{Color.GREEN}Microphone started{Color.RESET}")
        self.app.print_device_info(self)

        # Reduce socket internal buffer size to decrease audio delay
        self.app.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.config.udp_buffer_size)

        while self.stream is not None:
            try:
                audio_data: bytes = self.app.receive_data()
                self.stream.write(audio_data, exception_on_underflow=False)
            except (OSError, AttributeError):  # Includes TimeoutError
                continue
        print_(f"{Color.RED}Microphone stopped{Color.RESET}")

    def stop(self):
        """ Stop the thread and ensure it can be started again. """
        if self.is_alive():
            self.stream = None
            self.join()


class SoundBridgeClient:
    def __init__(self, server_host: str, server_port: int, speaker_config: AudioConfig, microphone_config: AudioConfig):
        self.server_address = server_host, server_port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.client_socket.settimeout(UDP_TIMEOUT)

        # Initialize audio interface
        self.audio_interface = pyaudio.PyAudio()

        # Instantiate speaker and microphone
        self.speaker: Speaker = Speaker(self, speaker_config)
        self.microphone: Microphone = Microphone(self, microphone_config)

        # Start speaker and microphone
        self.speaker.start()
        self.microphone.start()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            traceback.print_exception(exc_type, exc_value, traceback)

        self.speaker.stop()
        self.microphone.stop()
        self.audio_interface.terminate()
        self.client_socket.close()

    def send_data(self, data: bytes):
        """ Sends data to the server. """
        return self.client_socket.sendto(data, self.server_address)

    def receive_data(self) -> bytes:
        """ Receives data from the server. """
        data = self.client_socket.recvfrom(UDP_READ_SIZE)[0]
        return data

    @staticmethod
    def print_device_info(device: Speaker | Microphone):
        class_name = device.__class__.__name__
        print_(f"<{class_name}> {device.device_info['name']} | "
               f"{device.config.sample_rate} Hz {device.config.channels} ch")


def main():
    def thread():
        while True:
            speaker_config = control_client.get_speaker_config()
            microphone_config = control_client.get_microphone_config()

            with SoundBridgeClient(SERVER_HOST, SERVER_PORT, speaker_config, microphone_config):
                control_client.listen_server()

    control_client = ControlChannelClient(SERVER_HOST, CONTROL_PORT)
    Thread(target=thread, daemon=True).start()

    while input().lower() == 'm':
        control_client.toggle_microphone()


if __name__ == '__main__':
    main()
