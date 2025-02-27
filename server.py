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


class SoundBridgeServer:
    class Speaker(Thread):
        def __init__(self, server):
            super().__init__()
            self.server = server

        @override
        def run(self):
            stream = self.server.audio_interface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                output=True,
                output_device_index=self.server.output_device['index'],
            )
            print("Speaker started.")
            try:
                while True:
                    audio_data: bytes = self.server.receive_data()
                    stream.write(audio_data)
            except OSError:
                print("Speaker stopped.")
            finally:
                # Ensure resource cleanup
                stream.stop_stream()
                stream.close()

    class Microphone(Thread):
        """ Receives audio data via UDP and outputs it to virtual cable. """

        def __init__(self, server):
            super().__init__()
            self.server = server

        @override
        def run(self):
            """ Continuously receives and outputs to virtual cable. """
            stream = self.server.audio_interface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=self.server.input_device['index'],
            )
            print("Microphone started.")
            try:
                while True:
                    audio_data: bytes = stream.read(NUM_FRAMES, exception_on_overflow=False)
                    self.server.send_data(audio_data)
            except OSError:
                print("Microphone stopped.")
            finally:
                # Ensure resource cleanup
                stream.stop_stream()
                stream.close()

    def __init__(self, server_port: int, server_host: str = ''):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.server_socket.bind((server_host, server_port))
        self.client_address = None

        # Initialize audio interface
        self.audio_interface = pyaudio.PyAudio()
        self.output_device = self.audio_interface.get_default_output_device_info()
        self.input_device = self.audio_interface.get_default_input_device_info()

        # Initialize speaker and microphone threads
        self.speaker = self.Speaker(self)
        self.microphone = self.Microphone(self)

    def send_data(self, data: bytes):
        """ Sends audio data to the server. """
        return self.client_address and self.server_socket.sendto(data, self.client_address)

    def receive_data(self) -> bytes:
        """ Receives audio data from the server. """
        data, self.client_address = self.server_socket.recvfrom(CHUNK_SIZE)
        return data

    def close(self):
        """ Stop threads by closing the socket connection. """
        self.server_socket.close()


def main():
    client = SoundBridgeServer(server_port=2025)

    client.speaker.start()
    client.microphone.start()
    input("\n(Press Enter to stop)\n")

    client.close()


if __name__ == '__main__':
    main()
