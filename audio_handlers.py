import time
from threading import Thread
from typing import TYPE_CHECKING, override

from config import *
from utils import *

if TYPE_CHECKING:
    from client import SoundBridgeClient  # noqa
    from server import SoundBridgeServer  # noqa


class Sender(Thread):
    def __init__(self, app: 'SoundBridgeServer | SoundBridgeClient', config: AudioConfig, device_info):
        super().__init__()
        self.app = app
        self.config = config
        self.device_info = device_info

        self.class_name: str = self.__class__.__name__  # Child class name: 'Speaker' or 'Microphone'
        self.run_flag: bool = True

    @override
    def run(self):
        # Create audio stream instance
        stream = self.app.audio_interface.open(
            rate=self.config.sample_rate,
            channels=self.config.channels,
            format=self.config.audio_dtype,
            input=True,
            input_device_index=self.device_info['index'],
            frames_per_buffer=self.config.frames_per_chunk,
        )
        print_(f"{Color.GREEN}{self.class_name} started{Color.RESET}")
        print_device_info(self)

        while self.run_flag:
            audio_chunk: bytes = stream.read(self.config.frames_per_chunk, exception_on_overflow=False)
            self.app.data_channel.put_chunk(audio_chunk)

        # Clean up
        stream.stop_stream()
        stream.close()
        print_(f"{Color.RED}{self.class_name} stopped{Color.RESET}")

    def stop(self):
        if self.is_alive():
            self.run_flag = False
            self.join()


class Receiver(Thread):
    def __init__(self, app: 'SoundBridgeServer | SoundBridgeClient', config: AudioConfig, device_info):
        super().__init__()
        self.app = app
        self.config = config
        self.device_info = device_info

        self.class_name: str = self.__class__.__name__  # Child class name: 'Speaker' or 'Microphone'
        self.run_flag: bool = True

    @override
    def run(self):
        # Create audio stream instance
        stream = self.app.audio_interface.open(
            rate=self.config.sample_rate,
            channels=self.config.channels,
            format=self.config.audio_dtype,
            output=True,
            output_device_index=self.device_info['index'],
            frames_per_buffer=self.config.frames_per_chunk,
        )
        print_(f"{Color.GREEN}{self.class_name} started{Color.RESET}")
        print_device_info(self)

        while self.run_flag:
            if (audio_chunk := self.app.data_channel.get_chunk()) is not None:
                stream.write(audio_chunk, exception_on_underflow=False)
            else:
                # Allow time for the buffer to fill
                time.sleep(BUFFER_TIME / 2)

        # Clean up
        stream.stop_stream()
        stream.close()
        print_(f"{Color.RED}{self.class_name} stopped{Color.RESET}")

    def stop(self):
        if self.is_alive():
            self.run_flag = False
            self.join()


def print_device_info(streamer: Sender | Receiver):
    print_(f"<{streamer.class_name}> {streamer.device_info['name']} | "
           f"{format_hz_to_khz(streamer.config.sample_rate)} kHz, {streamer.config.channels} ch")
