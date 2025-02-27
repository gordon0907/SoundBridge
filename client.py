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

        def __init__(self, client):
            super().__init__()
            self.client = client

        @override
        def run(self):
            """ Continuously captures and streams audio. """
            stream = self.client.audio_interface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=self.client.loopback_device['index'],
                frames_per_buffer=NUM_FRAMES,
            )
            try:
                while True:
                    audio_data: bytes = stream.read(NUM_FRAMES, exception_on_overflow=False)
                    self.client.send_data(audio_data)
            except OSError:
                print("Speaker stopped.")
            finally:
                # Ensure resource cleanup
                stream.stop_stream()
                stream.close()

    class Microphone(Thread):
        """ Receives audio data via UDP and outputs it to virtual cable. """

        def __init__(self, client):
            super().__init__()
            self.client = client

        @override
        def run(self):
            """ Continuously receives and outputs to virtual cable. """
            stream = self.client.audio_interface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                output=True,
                output_device_index=self.client.virtual_cable_input['index'],
            )
            # Initialize the connection
            self.client.send_data(b'')
            try:
                while True:
                    audio_data: bytes = self.client.receive_data()
                    stream.write(audio_data)
            except OSError:
                print("Microphone stopped.")
            finally:
                # Ensure resource cleanup
                stream.stop_stream()
                stream.close()

    def __init__(self, server_port: int, server_host: str = "192.168.0.120"):
        self.server_address = (server_host, server_port)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP

        # Initialize audio interface
        self.audio_interface = pyaudio.PyAudio()

        # Get the loopback device as the speaker's source
        self.loopback_device = self.audio_interface.get_default_wasapi_loopback()
        print(f"Capturing from: {self.loopback_device['name']}")

        # Find Virtual Audio Cable (CABLE Input) for the microphone
        self.virtual_cable_input = None
        for i in range(self.audio_interface.get_device_count()):
            device_info = self.audio_interface.get_device_info_by_index(i)
            if "CABLE Input" in device_info['name'] and device_info['hostApi'] == 2:  # WASAPI
                self.virtual_cable_input = device_info
                break
        if self.virtual_cable_input is None:
            raise RuntimeError("No CABLE Input device found.")

        # Initialize speaker and microphone threads
        self.speaker = self.Speaker(self)
        self.microphone = self.Microphone(self)

    def send_data(self, data: bytes):
        """ Sends audio data to the server. """
        return self.client_socket.sendto(data, self.server_address)

    def receive_data(self) -> bytes:
        """ Receives audio data from the server. """
        return self.client_socket.recvfrom(CHUNK_SIZE)[0]

    def close(self):
        """ Stops threads by closing the socket. """
        self.client_socket.close()


def main():
    client = SoundBridgeClient(server_port=2025)

    client.speaker.start()
    client.microphone.start()
    input("\n(Press Enter to stop)\n")

    client.close()


if __name__ == '__main__':
    main()
