from __future__ import annotations

import socket
from contextlib import suppress

import pyaudiowpatch as pyaudio


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
    """ Captures system audio and streams it via UDP. """

    def __init__(self, client: SoundBridgeClient):
        self.client: SoundBridgeClient = client
        self.stream = None

    # noinspection PyUnusedLocal
    def callback(self, in_data, frame_count, time_info, status):
        self.client.send_data(in_data)
        return in_data, pyaudio.paContinue

    def start(self):
        """ Restarts the stream if it is already active. """
        if self.stream is None:
            self.stream = self.client.audio_interface.open(
                format=SpeakerConfig.FORMAT,
                channels=SpeakerConfig.CHANNELS,
                rate=SpeakerConfig.SAMPLE_RATE,
                input=True,
                input_device_index=self.client.loopback_device['index'],
                frames_per_buffer=SpeakerConfig.NUM_FRAMES,
                stream_callback=self.callback,
            )
            print("Speaker started.")
        else:
            self.stop()
            self.start()

    def stop(self):
        self.client.stop_device(self)


class Microphone:
    """ Receives audio data via UDP and outputs it to virtual cable. """

    def __init__(self, client: SoundBridgeClient):
        self.client: SoundBridgeClient = client
        self.stream = None

    # noinspection PyUnusedLocal
    def callback(self, in_data, frame_count, time_info, status):
        out_data: bytes = self.client.receive_data(MicConfig.CHUNK_SIZE)
        return out_data, pyaudio.paContinue

    def start(self):
        """ Restarts the stream if it is already active. """
        if self.stream is None:
            self.stream = self.client.audio_interface.open(
                format=MicConfig.FORMAT,
                channels=MicConfig.CHANNELS,
                rate=MicConfig.SAMPLE_RATE,
                output=True,
                output_device_index=self.client.virtual_cable_input['index'],
                frames_per_buffer=MicConfig.NUM_FRAMES,
                stream_callback=self.callback,
            )
            print("Microphone started.")
        else:
            self.stop()
            self.start()

    def stop(self):
        self.client.stop_device(self)


class SoundBridgeClient:
    def __init__(self, server_port: int, server_host: str = "192.168.0.120"):
        self.server_address = (server_host, server_port)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP

        # Initialize the connection
        self.send_data(b'')

        # Initialize audio interface
        self.audio_interface = pyaudio.PyAudio()

        # Get the loopback device as the speaker's source
        self.loopback_device = self.audio_interface.get_default_wasapi_loopback()
        print(f"Capturing from: {self.loopback_device['name']}")

        # Find Virtual Audio Cable (CABLE Input) for the microphone
        self.virtual_cable_input = None
        for i in range(self.audio_interface.get_device_count()):
            device_info = self.audio_interface.get_device_info_by_index(i)
            if "CABLE Input" in device_info['name'] and device_info['hostApi'] == 0:  # MME
                self.virtual_cable_input = device_info
                break
        if self.virtual_cable_input is None:
            raise RuntimeError("No CABLE Input device found.")
        else:
            print(f"Playing to: {self.virtual_cable_input['name']}")

        # Instantiate speaker and microphone
        self.speaker: Speaker = Speaker(self)
        self.microphone: Microphone = Microphone(self)

    def __del__(self):
        self.audio_interface.terminate()
        self.client_socket.close()

    def send_data(self, data: bytes):
        """ Sends data to the server. """
        return self.client_socket.sendto(data, self.server_address)

    def receive_data(self, size: int) -> bytes:
        """ Receives data from the server. """
        return self.client_socket.recvfrom(size)[0]

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
    client = SoundBridgeClient(server_port=2025)
    print()

    client.speaker.start()
    client.microphone.start()
    input("\n(Press Enter to stop)\n")

    client.speaker.stop()
    client.microphone.stop()


if __name__ == '__main__':
    main()
