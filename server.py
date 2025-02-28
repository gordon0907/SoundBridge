from __future__ import annotations

import socket
from contextlib import suppress

import pyaudio


class SpeakerConfig:
    SAMPLE_RATE = 48000  # 48 kHz
    CHANNELS = 2  # Stereo
    FORMAT = pyaudio.paInt16  # 16-bit format
    NUM_FRAMES = 32  # Number of frames per buffer

    # Derived Configuration
    CHUNK_SIZE = NUM_FRAMES * CHANNELS * 2
    print(f"Speaker Chunk Size: {CHUNK_SIZE} Bytes")


class MicConfig:
    SAMPLE_RATE = 24000  # 24 kHz
    CHANNELS = 1  # Mono
    FORMAT = pyaudio.paInt16  # 16-bit format
    NUM_FRAMES = 32  # Number of frames per buffer

    # Derived Configuration
    CHUNK_SIZE = NUM_FRAMES * CHANNELS * 2
    print(f"Microphone Chunk Size: {CHUNK_SIZE} Bytes")


class Speaker:
    """ Receives audio from the client and plays it on the system's output device. """

    def __init__(self, server: SoundBridgeServer):
        self.server: SoundBridgeServer = server
        self.stream = None

    # noinspection PyUnusedLocal
    def callback(self, in_data, frame_count, time_info, status):
        out_data: bytes = self.server.receive_data(SpeakerConfig.CHUNK_SIZE)
        return out_data, pyaudio.paContinue

    def start(self):
        """ Restarts the stream if it is already active. """
        if self.stream is None:
            self.stream = self.server.audio_interface.open(
                format=SpeakerConfig.FORMAT,
                channels=SpeakerConfig.CHANNELS,
                rate=SpeakerConfig.SAMPLE_RATE,
                output=True,
                output_device_index=self.server.output_device['index'],
                frames_per_buffer=SpeakerConfig.NUM_FRAMES,
                stream_callback=self.callback,
            )
            print("Speaker started.")
        else:
            self.stop()
            self.start()

    def stop(self):
        self.server.stop_device(self)


class Microphone:
    """ Captures audio from the system's input device and streams it to the client. """

    def __init__(self, server: SoundBridgeServer):
        self.server: SoundBridgeServer = server
        self.stream = None

    # noinspection PyUnusedLocal
    def callback(self, in_data, frame_count, time_info, status):
        self.server.send_data(in_data)
        return in_data, pyaudio.paContinue

    def start(self):
        """ Restarts the stream if it is already active. """
        if self.stream is None:
            self.stream = self.server.audio_interface.open(
                format=MicConfig.FORMAT,
                channels=MicConfig.CHANNELS,
                rate=MicConfig.SAMPLE_RATE,
                input=True,
                input_device_index=self.server.input_device['index'],
                frames_per_buffer=MicConfig.NUM_FRAMES,
                stream_callback=self.callback,
            )
            print("Microphone started.")
        else:
            self.stop()
            self.start()

    def stop(self):
        self.server.stop_device(self)


class SoundBridgeServer:
    def __init__(self, server_port: int, server_host: str = ''):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.server_socket.bind((server_host, server_port))
        self.client_address = None  # Set dynamically when data is received

        # Initialize audio interface
        self.audio_interface = pyaudio.PyAudio()
        self.output_device = self.audio_interface.get_default_output_device_info()
        self.input_device = self.audio_interface.get_default_input_device_info()

        print(f"Playing to: {self.output_device['name']}")
        print(f"Capturing from: {self.input_device['name']}")

        # Instantiate speaker and microphone
        self.speaker: Speaker = Speaker(self)
        self.microphone: Microphone = Microphone(self)

    def __del__(self):
        self.audio_interface.terminate()
        self.server_socket.close()

    def send_data(self, data: bytes):
        """ Sends data to the client. """
        if self.client_address:
            return self.server_socket.sendto(data, self.client_address)

    def receive_data(self, size: int) -> bytes:
        """ Receives data from the client and updates the client address. """
        data, self.client_address = self.server_socket.recvfrom(size)
        return data

    @staticmethod
    def stop_device(instance: Speaker | Microphone):
        if instance.stream is not None:
            with suppress(OSError):
                instance.stream.stop_stream()
            instance.stream.close()
            instance.stream = None
            print(f"{instance.__class__.__name__} stopped.")


def main():
    print()
    server = SoundBridgeServer(server_port=2025)
    print()

    server.speaker.start()
    server.microphone.start()
    input("\n(Press Enter to stop)\n")

    server.speaker.stop()
    server.microphone.stop()


if __name__ == '__main__':
    main()
