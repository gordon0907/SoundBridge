from __future__ import annotations

import socket
from threading import Thread
from typing import override

import pyaudiowpatch as pyaudio


class SpeakerConfig:
    SAMPLE_RATE = 48000  # 48 kHz
    CHANNELS = 2  # Stereo
    FORMAT = pyaudio.paInt16  # 16-bit format
    NUM_FRAMES = 32  # Number of frames per buffer

    # Derived Configuration
    CHUNK_SIZE = NUM_FRAMES * CHANNELS * 2
    # print(f"Speaker Chunk Size: {CHUNK_SIZE} Bytes")


class MicConfig:
    SAMPLE_RATE = 24000  # 24 kHz
    CHANNELS = 1  # Mono
    FORMAT = pyaudio.paInt16  # 16-bit format
    NUM_FRAMES = 32  # Number of frames per buffer

    # Derived Configuration
    CHUNK_SIZE = NUM_FRAMES * CHANNELS * 2
    # print(f"Microphone Chunk Size: {CHUNK_SIZE} Bytes\n")


class Speaker(Thread):
    """ Captures system audio and streams it via UDP. """

    def __init__(self, client: SoundBridgeClient):
        super().__init__()
        self.client: SoundBridgeClient = client
        self.is_running = True
        self.start()

    @override
    def run(self):
        """ Continuously captures and streams audio. """
        stream = self.client.audio_interface.open(
            format=SpeakerConfig.FORMAT,
            channels=SpeakerConfig.CHANNELS,
            rate=SpeakerConfig.SAMPLE_RATE,
            input=True,
            input_device_index=self.client.loopback_device['index'],
            frames_per_buffer=SpeakerConfig.NUM_FRAMES,
        )
        print("Speaker started.")
        try:
            while self.is_running:
                audio_data: bytes = stream.read(SpeakerConfig.NUM_FRAMES, exception_on_overflow=False)
                self.client.send_data(audio_data)
        except OSError:
            pass
        finally:
            # Ensure resource cleanup
            stream.stop_stream()
            stream.close()
            print("Speaker stopped.")


class Microphone(Thread):
    """ Receives audio data via UDP and outputs it to virtual cable. """

    def __init__(self, client: SoundBridgeClient):
        super().__init__()
        self.client: SoundBridgeClient = client
        self.is_running = True
        self.start()

    @override
    def run(self):
        """ Continuously receives and outputs to virtual cable. """
        stream = self.client.audio_interface.open(
            format=MicConfig.FORMAT,
            channels=MicConfig.CHANNELS,
            rate=MicConfig.SAMPLE_RATE,
            output=True,
            output_device_index=self.client.virtual_cable_input['index'],
        )
        print("Microphone started.")
        try:
            while self.is_running:
                audio_data: bytes = self.client.receive_data(MicConfig.CHUNK_SIZE)
                stream.write(audio_data)
        except OSError:
            pass
        finally:
            # Ensure resource cleanup
            stream.stop_stream()
            stream.close()
            print("Microphone stopped.")


class SoundBridgeClient:
    def __init__(self, server_port: int, server_host: str = "192.168.0.120"):
        self.server_address = server_host, server_port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP

        # Initialize the connection
        self.send_data(b'')

        # Initialize audio interface
        self.audio_interface, self.loopback_device, self.virtual_cable_input = None, None, None
        self.set_default_devices()
        self.print_current_devices()

        # Instantiate speaker and microphone
        self.speaker: Speaker = Speaker(self)
        self.microphone: Microphone = Microphone(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            traceback.print_exception(exc_type, exc_value, traceback)
        self.stop_device_threads()

    def send_data(self, data: bytes):
        """ Sends data to the server. """
        return self.client_socket.sendto(data, self.server_address)

    def receive_data(self, size: int) -> bytes:
        """ Receives data from the server. """
        return self.client_socket.recvfrom(size)[0]

    def set_default_devices(self):
        self.audio_interface = pyaudio.PyAudio()

        # Get the loopback device as the speaker's source
        self.loopback_device = self.audio_interface.get_default_wasapi_loopback()

        # Find Virtual Audio Cable (CABLE Input) for the microphone
        for i in range(self.audio_interface.get_device_count()):
            device_info = self.audio_interface.get_device_info_by_index(i)
            if "CABLE Input" in device_info['name'] and device_info['hostApi'] == 0:  # MME
                self.virtual_cable_input = device_info
                break

        if self.virtual_cable_input is None:
            raise RuntimeError("No CABLE Input device found.")

    def print_current_devices(self):
        print(f"\nPlaying to: {self.virtual_cable_input['name']}")
        print(f"Capturing from: {self.loopback_device['name']}")

    def stop_device_threads(self):
        """ Stops threads by closing the socket. """
        self.speaker.is_running = False
        self.microphone.is_running = False
        self.client_socket.close()
        self.audio_interface.terminate()
        self.speaker.join()
        self.microphone.join()


def main():
    with SoundBridgeClient(server_port=2025) as client:
        input("\n(Press Enter to stop)\n")


if __name__ == '__main__':
    main()
