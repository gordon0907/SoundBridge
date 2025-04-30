from __future__ import annotations

from threading import Thread
from typing import override

import pyaudiowpatch as pyaudio

from audio_handlers import Receiver, Sender
from config import *
from control_channel import ControlChannelClient
from data_channel import DataChannel
from utils import *


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
            format=self.config.audio_dtype,
            output=True,
        )
        dummy_audio_data = bytes(self.config.chunk_size)

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
    def __init__(self, server_host: str, data_port: int, speaker_config: AudioConfig, microphone_config: AudioConfig):
        # Start data channel
        self.data_channel = DataChannel(
            is_server=False,
            server_host=server_host,
            server_port=data_port,
            sender_config=speaker_config,
            receiver_config=microphone_config,
        )

        # Initialize audio interface
        self.audio_interface = pyaudio.PyAudio()

        # Instantiate speaker and microphone
        self.speaker = Speaker(self, speaker_config)
        self.microphone = Microphone(self, microphone_config)

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
        self.data_channel.stop()


def main():
    def thread():
        while True:
            speaker_config = control_client.get_speaker_config()
            microphone_config = control_client.get_microphone_config()

            with SoundBridgeClient(SERVER_HOST, DATA_PORT, speaker_config, microphone_config):
                control_client.wait_for_stop()

            control_client.wait_for_start()

    control_client = ControlChannelClient(SERVER_HOST, CONTROL_PORT)
    Thread(target=thread, daemon=True).start()

    while input().lower() == 'm':
        control_client.toggle_microphone()


if __name__ == '__main__':
    main()
