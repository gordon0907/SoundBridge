from __future__ import annotations

import socket
import time
from multiprocessing import Event, Process
from threading import Thread
from typing import override

import pyaudio

from control_channel import ControlChannelServer
from miscellaneous import *

SERVER_PORT = 2024
CONTROL_PORT = 2025
UDP_TIMEOUT = 1.  # in seconds
UDP_READ_SIZE = 1024
FORMAT = pyaudio.paInt16  # 16-bit format
NUM_FRAMES = 32  # Number of frames per buffer


class Speaker(Thread):
    """
    Continuously receives audio data from the client and plays it on the system's default output device.
    """

    def __init__(self, app: SoundBridgeServer):
        super().__init__()
        self.app: SoundBridgeServer = app

        # Get default output device info
        self.device_info = self.app.audio_interface.get_default_output_device_info()
        self.config = AudioConfig(
            sample_rate=max(int(self.device_info['defaultSampleRate']), 48000),  # At least 48 kHz for client's WASAPI
            channels=self.device_info['maxOutputChannels'],
            audio_format=FORMAT,
            num_frames=NUM_FRAMES,
        )

        self.stream = None

    @override
    def run(self):
        # Create audio stream instance
        self.stream = self.app.audio_interface.open(
            rate=self.config.sample_rate,
            channels=self.config.channels,
            format=self.config.audio_format,
            output=True,
        )
        print_(f"{Color.GREEN}Speaker started{Color.RESET}")
        self.app.print_device_info(self)

        # Avoid audio delay after restart
        # self.app.clear_udp_buffer()

        # Reduce socket internal buffer size to decrease audio delay
        self.app.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.config.udp_buffer_size)

        while self.stream is not None:
            try:
                audio_data: bytes = self.app.receive_data()
                self.stream.write(audio_data)
            except (OSError, AttributeError):  # Includes TimeoutError
                continue
        print_(f"{Color.RED}Speaker stopped{Color.RESET}")

    def stop(self):
        """ Stop the thread and ensure it can be started again. """
        if self.is_alive():
            self.stream = None
            self.join()
            self.app.speaker = Speaker(self.app)  # Ready for the next start


class Microphone(Thread):
    """
    Continuously captures audio from the system's input device and sends it to the client.
    """

    def __init__(self, app: SoundBridgeServer):
        super().__init__()
        self.app: SoundBridgeServer = app

        # Get default input device info
        self.device_info = self.app.audio_interface.get_default_input_device_info()
        self.config = AudioConfig(
            sample_rate=int(self.device_info['defaultSampleRate']),
            channels=self.device_info['maxInputChannels'],
            audio_format=FORMAT,
            num_frames=NUM_FRAMES,
        )

        self.stream = None

    @override
    def run(self):
        # Create audio stream instance
        self.stream = self.app.audio_interface.open(
            rate=self.config.sample_rate,
            channels=self.config.channels,
            format=self.config.audio_format,
            input=True,
            frames_per_buffer=self.config.num_frames,
        )
        print_(f"{Color.GREEN}Microphone started{Color.RESET}")
        self.app.print_device_info(self)

        while self.stream is not None:
            try:
                audio_data: bytes = self.stream.read(self.config.num_frames)
                self.app.send_data(audio_data)
            except (OSError, AttributeError):  # Includes TimeoutError
                continue
        print_(f"{Color.RED}Microphone stopped{Color.RESET}")

    def stop(self):
        """ Stop the thread and ensure it can be started again. """
        if self.is_alive():
            self.stream = None
            self.join()
            self.app.microphone = Microphone(self.app)  # Ready for the next start


class SoundBridgeServer:
    def __init__(self, server_port: int, control_port: int, server_host: str = ''):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.server_socket.bind((server_host, server_port))
        self.server_socket.settimeout(UDP_TIMEOUT)
        print_(f"UDP listener started on port {server_port}")

        # Set to an invalid placeholder; will be updated with a valid address upon receiving data
        self.client_address = "192.168.0.1", server_port

        # Initialize audio interface
        self.audio_interface = pyaudio.PyAudio()

        # Detect device changes with a multiprocessing event
        self.need_reload = Event()
        self.device_monitor = Process(target=device_monitor, args=(self.need_reload,))
        self.device_monitor.daemon = True
        self.device_monitor.start()

        # Wait for the process to fully initialize
        self.need_reload.wait()
        self.need_reload.clear()

        # Auto reload if the device changes
        Thread(target=self.reload_pyaudio, daemon=True).start()

        # Instantiate speaker and microphone
        self.speaker: Speaker = Speaker(self)
        self.microphone: Microphone = Microphone(self)

        # Initialize TCP control channel server
        self.control = ControlChannelServer(self, control_port, server_host)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            traceback.print_exception(exc_type, exc_value, traceback)

        self.speaker.stop()
        self.microphone.stop()

    def send_data(self, data: bytes):
        """ Sends data to the client. """
        return self.server_socket.sendto(data, self.client_address)

    def receive_data(self) -> bytes:
        """ Receives data from the client and updates the client address. """
        data, self.client_address = self.server_socket.recvfrom(UDP_READ_SIZE)
        return data

    def clear_udp_buffer(self):
        self.server_socket.setblocking(False)
        try:
            while True:
                self.receive_data()
        except BlockingIOError:
            self.server_socket.settimeout(UDP_TIMEOUT)

    def reload_pyaudio(self):
        while self.need_reload.wait():
            is_speaker_on = self.speaker.is_alive()
            is_microphone_on = self.microphone.is_alive()

            # Completely stop device threads for safety
            self.speaker.stop()
            self.microphone.stop()
            self.audio_interface.terminate()

            self.audio_interface = pyaudio.PyAudio()
            self.speaker = Speaker(self)
            self.microphone = Microphone(self)

            self.control.notify_client()
            is_speaker_on and self.speaker.start()
            is_microphone_on and self.microphone.start()

            self.need_reload.clear()

    @staticmethod
    def print_device_info(device: Speaker | Microphone):
        class_name = device.__class__.__name__
        print_(f"<{class_name}> {device.device_info['name']} | "
               f"{device.config.sample_rate} Hz {device.config.channels} ch")


def device_monitor(signal: Event):
    """ The check must be performed in another process, as PyAudio must be terminated to detect device changes. """
    current_output_device, current_input_device = None, None

    while time.sleep(1.) or True:
        audio_interface = pyaudio.PyAudio()
        output_device = audio_interface.get_default_output_device_info()['index']
        input_device = audio_interface.get_default_input_device_info()['index']

        if output_device != current_output_device or input_device != current_input_device:
            current_output_device = output_device
            current_input_device = input_device
            signal.set()

        audio_interface.terminate()


def main():
    with SoundBridgeServer(SERVER_PORT, CONTROL_PORT) as app:
        app.speaker.start()
        app.microphone.start()
        input()


if __name__ == '__main__':
    main()
