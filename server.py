import socket
from threading import Thread
from typing import override

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


class SoundBridgeServer:
    class Speaker(Thread):
        """ Receives audio from the client and plays it on the system's output device. """

        def __init__(self, server):
            super().__init__()
            self.server = server

        @override
        def run(self):
            """ Continuously receives audio data from the client and plays it. """
            stream = self.server.audio_interface.open(
                format=SpeakerConfig.FORMAT,
                channels=SpeakerConfig.CHANNELS,
                rate=SpeakerConfig.SAMPLE_RATE,
                output=True,
                output_device_index=self.server.output_device['index'],
            )
            print("Speaker started.")
            try:
                while True:
                    audio_data: bytes = self.server.receive_data(SpeakerConfig.CHUNK_SIZE)
                    stream.write(audio_data)
            except OSError:
                print("Speaker stopped.")
            finally:
                # Ensure resource cleanup
                stream.stop_stream()
                stream.close()

    class Microphone(Thread):
        """ Captures audio from the system's input device and streams it to the client. """

        def __init__(self, server):
            super().__init__()
            self.server = server

        @override
        def run(self):
            """ Continuously captures audio and sends it to the client. """
            stream = self.server.audio_interface.open(
                format=MicConfig.FORMAT,
                channels=MicConfig.CHANNELS,
                rate=MicConfig.SAMPLE_RATE,
                input=True,
                input_device_index=self.server.input_device['index'],
                frames_per_buffer=MicConfig.NUM_FRAMES,
            )
            print("Microphone started.")
            try:
                while True:
                    audio_data: bytes = stream.read(MicConfig.NUM_FRAMES, exception_on_overflow=False)
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
        self.client_address = None  # Set dynamically when data is received

        # Initialize audio interface
        self.audio_interface = pyaudio.PyAudio()
        self.output_device = self.audio_interface.get_default_output_device_info()
        self.input_device = self.audio_interface.get_default_input_device_info()

        # Initialize speaker and microphone threads
        self.speaker = self.Speaker(self)
        self.microphone = self.Microphone(self)

    def send_data(self, data: bytes):
        """ Sends audio data to the client. """
        if self.client_address:
            return self.server_socket.sendto(data, self.client_address)

    def receive_data(self, size: int) -> bytes:
        """ Receives audio data from the client and updates the client address. """
        data, self.client_address = self.server_socket.recvfrom(size)
        return data

    def close(self):
        """ Stops threads by closing the socket. """
        self.server_socket.close()


def main():
    server = SoundBridgeServer(server_port=2025)

    server.speaker.start()
    server.microphone.start()
    input("\n(Press Enter to stop)\n")

    server.close()


if __name__ == '__main__':
    main()
