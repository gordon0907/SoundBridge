from __future__ import annotations

import socket
import time
from multiprocessing import Event, Process
from threading import Thread
from typing import override

import pyaudio

from miscellaneous import *


class Speaker(Thread):
    """ Receives audio from the client and plays it on the system's output device. """

    def __init__(self, server: SoundBridgeServer):
        super().__init__()
        self.server: SoundBridgeServer = server
        output_device = self.server.audio_interface.get_default_output_device_info()
        self.config = AudioConfig(
            audio_format=self.server.FORMAT,
            channels=output_device['maxOutputChannels'],
            sample_rate=int(output_device['defaultSampleRate']),
            num_frames=self.server.NUM_FRAMES,
        )
        self.start()

    @override
    def run(self):
        """ Continuously receives audio data from the client and plays it. """
        stream = self.server.audio_interface.open(
            format=self.config.audio_format,
            channels=self.config.channels,
            rate=self.config.sample_rate,
            output=True,
        )
        print_("Speaker started.")
        try:
            while True:
                audio_data: bytes = self.server.receive_data()
                stream.write(audio_data)
        except OSError:
            pass
        finally:
            print_("Speaker stopped.")


class Microphone(Thread):
    """ Captures audio from the system's input device and streams it to the client. """

    def __init__(self, server: SoundBridgeServer):
        super().__init__()
        self.server: SoundBridgeServer = server
        input_device = self.server.audio_interface.get_default_input_device_info()
        self.config = AudioConfig(
            audio_format=self.server.FORMAT,
            channels=input_device['maxInputChannels'],
            sample_rate=int(input_device['defaultSampleRate']),
            num_frames=self.server.NUM_FRAMES,
        )
        self.start()

    @override
    def run(self):
        """ Continuously captures audio and sends it to the client. """
        stream = self.server.audio_interface.open(
            format=self.config.audio_format,
            channels=self.config.channels,
            rate=self.config.sample_rate,
            input=True,
            frames_per_buffer=self.config.num_frames,
        )
        print_("Microphone started.")
        try:
            while True:
                audio_data: bytes = stream.read(self.config.num_frames)
                self.server.send_data(audio_data)
        except OSError:
            pass
        finally:
            print_("Microphone stopped.")


class SoundBridgeServer:
    UDP_BUFFER_SIZE = 1024
    FORMAT = pyaudio.paInt16  # 16-bit format
    NUM_FRAMES = 32  # Number of frames per buffer

    def __init__(self, server_port: int, server_host: str = ''):
        self.server_address = server_host, server_port
        self.server_socket = self.init_socket()
        self.client_address = "0.0.0.0", server_port  # Set to a valid address when data is received

        # Initialize audio interface
        self.audio_interface = pyaudio.PyAudio()
        self.print_devices_name()

        # Detect device changes with a multiprocessing event
        self.has_changed = Event()
        self.device_monitor = Process(target=device_monitor, args=(self.has_changed,))
        self.device_monitor.start()

        # Wait for the process to fully initialize
        self.has_changed.wait()
        self.has_changed.clear()

        # Auto reload if the device changes
        self.is_running: bool = True
        Thread(target=self.reload).start()

        # Instantiate speaker and microphone
        self.speaker: Speaker = Speaker(self)
        self.microphone: Microphone = Microphone(self)
        self.print_devices_info()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            traceback.print_exception(exc_type, exc_value, traceback)
        self.stop_device_threads()

        # Stop reload helper thread
        self.is_running = False
        self.has_changed.set()

        self.device_monitor.terminate()

    def init_socket(self) -> socket.socket:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        server_socket.bind(self.server_address)
        return server_socket

    def send_data(self, data: bytes):
        """ Sends data to the client. """
        return self.server_socket.sendto(data, self.client_address)

    def receive_data(self) -> bytes:
        """ Receives data from the client and updates the client address. """
        data, self.client_address = self.server_socket.recvfrom(self.UDP_BUFFER_SIZE)
        return data

    def print_devices_name(self):
        print_(f"Playing to: {self.audio_interface.get_default_output_device_info()['name']}")
        print_(f"Capturing from: {self.audio_interface.get_default_input_device_info()['name']}")

    def reload(self):
        while self.has_changed.wait() and self.is_running:
            self.stop_device_threads()
            self.audio_interface.terminate()

            self.server_socket = self.init_socket()
            self.audio_interface = pyaudio.PyAudio()
            self.print_devices_name()

            self.speaker = Speaker(self)
            self.microphone = Microphone(self)
            self.print_devices_info()

            self.has_changed.clear()

    def print_devices_info(self):
        print_(f"<Speaker> Channels: {self.speaker.config.channels} | "
               f"Sample Rate: {self.speaker.config.sample_rate} kHz")
        print_(f"<Microphone> Channels: {self.microphone.config.channels} | "
               f"Sample Rate: {self.microphone.config.sample_rate} kHz")

    def stop_device_threads(self):
        """ Stops threads by closing the socket. """
        self.server_socket.close()
        self.speaker.join()
        self.microphone.join()


def device_monitor(signal: Event):
    """ The check must be performed in another process, as PyAudio must be terminated to detect device changes. """
    current_output_device, current_input_device = None, None

    while time.sleep(0.5) or True:
        audio_interface = pyaudio.PyAudio()
        output_device = audio_interface.get_default_output_device_info()
        input_device = audio_interface.get_default_input_device_info()

        if output_device != current_output_device or input_device != current_input_device:
            current_output_device = output_device
            current_input_device = input_device
            signal.set()

        audio_interface.terminate()


def main():
    with SoundBridgeServer(server_port=2025) as server:
        input()


if __name__ == '__main__':
    main()
