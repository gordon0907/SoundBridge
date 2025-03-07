from __future__ import annotations

import socket
from functools import cache
from threading import Thread
from typing import override

import pyaudiowpatch as pyaudio

from control_channel import ControlChannelClient
from miscellaneous import *

SERVER_HOST: str = "192.168.0.120"
SERVER_PORT: int = 2024
CONTROL_PORT: int = 2025
UDP_TIMEOUT: float = 1.  # in seconds


class Speaker(Thread):
    """Continuously captures system audio and sends it to the server."""

    def __init__(self, app: SoundBridgeClient, config: AudioConfig):
        super().__init__()
        self.app: SoundBridgeClient = app
        self.config = config

        # Get default loopback device info
        self.device_info = self.app.audio_interface.get_default_wasapi_loopback()
        self.run_flag: bool = True

    @override
    def run(self):
        # Helper stream to keep the loopback stream non-blocking
        output_stream = self.app.audio_interface.open(
            rate=self.config.sample_rate,
            channels=self.config.channels,
            format=self.config.audio_format,
            output=True,
        )
        # Dummy num_frames may need to be increased if capturing NUM_FRAMES > 32
        dummy_audio_data = self.app.generate_dummy_audio(1, self.config.channels, self.config.audio_format)

        # Create audio stream instance
        stream = self.app.audio_interface.open(
            rate=self.config.sample_rate,
            channels=self.config.channels,
            format=self.config.audio_format,
            input=True,
            input_device_index=self.device_info['index'],
            frames_per_buffer=self.config.num_frames,
        )
        print_(f"{Color.GREEN}Speaker started{Color.RESET}")
        self.app.print_device_info(self)

        while self.run_flag:
            output_stream.write(dummy_audio_data, exception_on_underflow=False)
            audio_data: bytes = stream.read(self.config.num_frames, exception_on_overflow=False)
            self.app.send_data(audio_data)

        # Clean up
        output_stream.stop_stream()
        output_stream.close()
        stream.stop_stream()
        stream.close()
        print_(f"{Color.RED}Speaker stopped{Color.RESET}")

    def stop(self):
        """Stop the thread and ensure it can be started again."""
        if self.is_alive():
            self.run_flag = False
            self.join()


class Microphone(Thread):
    """Continuously receives audio from the server and plays it through the virtual cable."""

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

        self.run_flag: bool = True

    @override
    def run(self):
        # Create audio stream instance
        stream = self.app.audio_interface.open(
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

        while self.run_flag:
            try:
                audio_data: bytes = self.app.receive_data(self.config.packet_size)
            except TimeoutError:
                continue
            stream.write(audio_data, exception_on_underflow=False)

        # Clean up
        stream.stop_stream()
        stream.close()
        print_(f"{Color.RED}Microphone stopped{Color.RESET}")

    def stop(self):
        """Stop the thread and ensure it can be started again."""
        if self.is_alive():
            self.run_flag = False
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
        """Sends data to the server."""
        return self.client_socket.sendto(data, self.server_address)

    def receive_data(self, max_bytes: int) -> bytes:
        """Receives data from the server."""
        data, _ = self.client_socket.recvfrom(max_bytes)
        return data

    @staticmethod
    def print_device_info(device: Speaker | Microphone):
        class_name = device.__class__.__name__
        print_(f"<{class_name}> {device.device_info['name']} | "
               f"{format_hz_to_khz(device.config.sample_rate)} kHz, {device.config.channels} ch")

    @staticmethod
    @cache
    def generate_dummy_audio(num_frames: int, channels: int, audio_format: int) -> bytes:
        return b'\x00' * num_frames * channels * pyaudio.get_sample_size(audio_format)


def main():
    def thread():
        while True:
            speaker_config = control_client.get_speaker_config()
            microphone_config = control_client.get_microphone_config()

            with SoundBridgeClient(SERVER_HOST, SERVER_PORT, speaker_config, microphone_config):
                control_client.wait_for_stop()

            control_client.wait_for_start()

    control_client = ControlChannelClient(SERVER_HOST, CONTROL_PORT)
    Thread(target=thread, daemon=True).start()

    while input().lower() == 'm':
        control_client.toggle_microphone()


if __name__ == '__main__':
    main()
