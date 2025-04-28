from __future__ import annotations

import socket

import pyaudiowpatch as pyaudio

from audio_handlers import *
from config import *
from control_channel import ControlChannelClient


class Speaker(Sender):
    """Continuously capture system audio and send it to the server."""

    def __init__(self, app: SoundBridgeClient, config: AudioConfig):
        # Get default loopback device info
        device_info = app.audio_interface.get_default_wasapi_loopback()

        super().__init__(app, config, device_info)

        # Helper to keep the loopback stream read always available
        self.helper_thread = Thread(target=self.helper)

    def helper(self):
        """Continuously write empty audio to the default output device to prevent loopback read blocking."""
        stream = self.app.audio_interface.open(
            rate=self.config.sample_rate,
            channels=self.config.channels,
            format=self.config.audio_format,
            output=True,
        )
        dummy_audio_data = bytes(self.config.packet_size)

        while self.run_flag:
            stream.write(dummy_audio_data, exception_on_underflow=False)

        # Clean up
        stream.stop_stream()
        stream.close()

    @override
    def run(self):
        self.helper_thread.start()
        super().run()
        self.helper_thread.join()


class Microphone(Receiver):
    """Continuously receive audio from the server and play it through the virtual cable."""

    def __init__(self, app: SoundBridgeClient, config: AudioConfig):
        # Find Virtual Audio Cable (CABLE Input) and get its device info
        for i in range(app.audio_interface.get_device_count()):
            device_info = app.audio_interface.get_device_info_by_index(i)
            if "CABLE Input" in device_info['name'] and device_info['hostApi'] == 0:  # MME
                break
        else:
            raise RuntimeError("No CABLE Input device found")

        super().__init__(app, config, device_info)


class SoundBridgeClient:
    def __init__(self, server_host: str, server_port: int, speaker_config: AudioConfig, microphone_config: AudioConfig):
        self.server_address = server_host, server_port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.client_socket.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x10)  # IPTOS_LOWDELAY
        self.client_socket.setblocking(False)

        # Initialize socket with an empty packet
        self.send_data(b'')

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
        if exc_type is not None:
            traceback.print_exception(exc_type, exc_value, traceback)

        self.speaker.stop()
        self.microphone.stop()
        self.audio_interface.terminate()
        self.client_socket.close()

    def set_receive_buffer_size(self, size: int):
        """Set socket receive buffer size in bytes."""
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, size)

    def send_data(self, data: bytes) -> int:
        """Send data to the server."""
        return self.client_socket.sendto(data, self.server_address)

    def receive_data(self, max_bytes: int) -> bytes:
        """Receive data from the server."""
        data, _ = self.client_socket.recvfrom(max_bytes)
        return data


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
    raise_process_priority()
    main()
