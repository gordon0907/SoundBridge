import socket
from threading import Thread
from typing import override

import pyaudiowpatch as pyaudio

# Audio Configuration
SAMPLE_RATE = 48000  # 48 kHz
CHANNELS = 2  # Stereo
FORMAT = pyaudio.paInt16  # 16-bit format
NUM_FRAMES = 32  # Number of frames per buffer

# Derived Configuration
CHUNK_SIZE = NUM_FRAMES * CHANNELS * 2
print(f"{CHUNK_SIZE = } bytes")


class SoundBridgeClient:
    class Speaker(Thread):
        """ Captures system audio and streams it via UDP. """

        def __init__(self, outer):
            super().__init__()
            self.outer = outer

        @override
        def run(self):
            """ Continuously captures and streams audio. """
            stream = self.outer.audio_interface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=self.outer.loopback_device["index"],
                frames_per_buffer=NUM_FRAMES,
            )
            try:
                while True:
                    audio_data: bytes = stream.read(NUM_FRAMES, exception_on_overflow=False)
                    self.outer.send_data(audio_data)
            except OSError:
                print("Speaker stopped")
            finally:
                # Ensure cleanup of resources
                stream.stop_stream()
                stream.close()

    class Microphone(Thread):
        def __init__(self, outer):
            super().__init__()
            self.outer = outer

        @override
        def run(self):
            stream = self.outer.audio_interface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                output=True,
                output_device_index=self.outer.virtual_cable_input['index'],
            )
            # Initialize the connection
            self.outer.send_data(b'')
            try:
                while True:
                    data, _ = self.outer.recv_data()
                    stream.write(data)
            except OSError:
                print("Microphone stopped")
            finally:
                # Ensure cleanup of resources
                stream.stop_stream()
                stream.close()

    def __init__(self, server_port: int, server_host: str = "192.168.0.120"):
        self.server_address = (server_host, server_port)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP

        # Initialize audio interface
        self.audio_interface = pyaudio.PyAudio()
        self.loopback_device = self.audio_interface.get_default_wasapi_loopback()
        print(f"Capturing from: {self.loopback_device['name']}")
        for i in range(self.audio_interface.get_device_count()):
            device_info = self.audio_interface.get_device_info_by_index(i)
            if 'CABLE Input' in device_info['name'] and device_info['hostApi'] == 2:  # WASAPI
                self.virtual_cable_input = device_info
                break
        else:
            raise RuntimeError(f"No CABLE Input device found")

        self.speaker = self.Speaker(self)
        self.microphone = self.Microphone(self)

    def __del__(self):
        self.audio_interface.terminate()

    def send_data(self, data: bytes):
        return self.client_socket.sendto(data, self.server_address)

    def recv_data(self) -> bytes:
        return self.client_socket.recvfrom(CHUNK_SIZE)[0]

    def close(self):
        """ Stop threads by closing the socket """
        self.client_socket.close()


def main():
    client = SoundBridgeClient(server_port=2025)
    client.speaker.start()
    client.microphone.start()
    input("\n(Press Enter to stop)")

    client.close()


if __name__ == '__main__':
    main()
