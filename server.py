from __future__ import annotations

import time
from multiprocessing import Event, Process
from threading import Thread
from typing import override

import pyaudio

from audio_handlers import Receiver, Sender
from config import *
from control_channel import ControlChannelServer
from data_channel import DataChannel
from utils import *


class Speaker(Receiver):
    """Continuously receive audio data from the client and play it on the system's default output device."""

    def __init__(self, app: SoundBridgeServer):
        # Get default output device info
        device_info = app.audio_interface.get_default_output_device_info()
        config = AudioConfig(
            sample_rate=max(int(device_info['defaultSampleRate']), 48000),  # At least 48 kHz for client's WASAPI
            channels=device_info['maxOutputChannels'],
            audio_dtype=AUDIO_DTYPE,
            frames_per_chunk=FRAMES_PER_CHUNK,
        )

        super().__init__(app, config, device_info)

    @override
    def stop(self):
        """Stop the thread and ensure it can be started again."""
        super().stop()
        self.app.speaker = Speaker(self.app)  # Ready for the next start


class Microphone(Sender):
    """Continuously capture audio from the system's input device and send it to the client."""

    def __init__(self, app: SoundBridgeServer):
        # Get default input device info
        device_info = app.audio_interface.get_default_input_device_info()
        config = AudioConfig(
            sample_rate=int(device_info['defaultSampleRate']),
            channels=device_info['maxInputChannels'],
            audio_dtype=AUDIO_DTYPE,
            frames_per_chunk=FRAMES_PER_CHUNK,
        )

        super().__init__(app, config, device_info)

    @override
    def stop(self):
        """Stop the thread and ensure it can be started again."""
        super().stop()
        self.app.microphone = Microphone(self.app)  # Ready for the next start


class SoundBridgeServer:
    def __init__(self, data_port: int, control_port: int, server_host: str = "0.0.0.0"):
        # Initialize audio interface
        self.audio_interface = pyaudio.PyAudio()

        # Detect device changes with a multiprocessing event
        self.need_reload = Event()
        self.device_monitor = Process(target=device_monitor, args=(self.need_reload,))
        self.device_monitor.daemon = True
        self.device_monitor.start()

        # Wait for the process to fully initialize
        self.need_reload.wait()
        self.need_reload.clear()

        # Auto reload if the device changes
        Thread(target=self.reload_pyaudio, daemon=True).start()

        # Instantiate speaker and microphone
        self.speaker = Speaker(self)
        self.microphone = Microphone(self)

        # Start data channel
        self.data_channel = DataChannel(
            is_server=True,
            server_host=server_host,
            server_port=data_port,
            sender_config=self.microphone.config,
            receiver_config=self.speaker.config,
        )

        # Start control channel
        self.control_channel = ControlChannelServer(self, control_port, server_host)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            traceback.print_exception(exc_type, exc_value, traceback)

        self.speaker.stop()
        self.microphone.stop()
        self.audio_interface.terminate()
        self.data_channel.stop()

    def reload_pyaudio(self):
        while self.need_reload.wait():
            # Stop the client before reloading
            self.control_channel.stop_client()

            # Store device statuses
            is_speaker_on = self.speaker.is_alive()
            is_microphone_on = self.microphone.is_alive()

            # Completely stop device threads for safety
            self.speaker.stop()
            self.microphone.stop()
            self.audio_interface.terminate()

            # Reinitialize audio interface and device instances until successful
            while True:
                self.audio_interface = pyaudio.PyAudio()

                # Handle OSError raised by get_default_XXX_device_info()
                try:
                    self.speaker = Speaker(self)
                    self.microphone = Microphone(self)
                    break
                except OSError:
                    self.audio_interface.terminate()
                    continue

            # Apply updated configs to the data channel
            self.data_channel.restart(self.microphone.config, self.speaker.config)

            # Restart devices if they were previously running
            is_speaker_on and self.speaker.start()
            is_microphone_on and self.microphone.start()

            # Restart the client
            self.control_channel.start_client()

            self.need_reload.clear()


def device_monitor(signal: Event):
    """The check must be performed in another process, as PyAudio must be terminated to detect device changes."""

    def print_change(icon, old_device, new_device, channels_key):
        if old_device is not None:
            print_(f"{icon} "
                   f"{old_device['name']} ({format_hz_to_khz(old_device['defaultSampleRate'])} kHz, {old_device[channels_key]} ch) → "
                   f"{new_device['name']} ({format_hz_to_khz(new_device['defaultSampleRate'])} kHz, {new_device[channels_key]} ch)")

    current_output_device, current_input_device = None, None

    while time.sleep(1.) or True:
        audio_interface = pyaudio.PyAudio()

        try:
            output_device = audio_interface.get_default_output_device_info()
            input_device = audio_interface.get_default_input_device_info()
        except OSError:
            audio_interface.terminate()
            continue

        if output_device != current_output_device or input_device != current_input_device:
            if output_device != current_output_device:
                print_change('🔊', current_output_device, output_device, 'maxOutputChannels')
            if input_device != current_input_device:
                print_change('🎤', current_input_device, input_device, 'maxInputChannels')

            current_output_device, current_input_device = output_device, input_device
            signal.set()

        audio_interface.terminate()


def main():
    with SoundBridgeServer(DATA_PORT, CONTROL_PORT) as app:
        app.speaker.start()
        app.microphone.start()
        input()


if __name__ == '__main__':
    main()
