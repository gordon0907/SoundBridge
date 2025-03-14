import time
from threading import Thread
from typing import TYPE_CHECKING, override

from miscellaneous import *

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
            format=self.config.audio_format,
            input=True,
            input_device_index=self.device_info['index'],
            frames_per_buffer=self.config.num_frames,
        )
        print_(f"{Color.GREEN}{self.class_name} started{Color.RESET}")
        self.print_device_info()

        while self.run_flag:
            audio_data: bytes = stream.read(self.config.num_frames, exception_on_overflow=False)
            self.app.send_data(audio_data)

        # Clean up
        stream.stop_stream()
        stream.close()
        print_(f"{Color.RED}{self.class_name} stopped{Color.RESET}")

    def stop(self):
        if self.is_alive():
            self.run_flag = False
            self.join()

    def print_device_info(self):
        print_(f"<{self.class_name}> {self.device_info['name']} | "
               f"{format_hz_to_khz(self.config.sample_rate)} kHz, {self.config.channels} ch")


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
            format=self.config.audio_format,
            output=True,
            output_device_index=self.device_info['index'],
            frames_per_buffer=self.config.num_frames,
        )
        print_(f"{Color.GREEN}{self.class_name} started{Color.RESET}")
        self.print_device_info()

        # Reduce socket internal buffer size to decrease audio delay
        self.app.set_receive_buffer_size(self.config.udp_buffer_size)

        while self.run_flag:
            try:
                audio_data: bytes = self.app.receive_data(self.config.packet_size)
                stream.write(audio_data, exception_on_underflow=False)
            except BlockingIOError:
                # Allow time for the socket buffer to fill
                time.sleep(BUFFER_TIME / 2)

        # Clean up
        stream.stop_stream()
        stream.close()
        print_(f"{Color.RED}{self.class_name} stopped{Color.RESET}")

    def stop(self):
        if self.is_alive():
            self.run_flag = False
            self.join()

    def print_device_info(self):
        print_(f"<{self.class_name}> {self.device_info['name']} | "
               f"{format_hz_to_khz(self.config.sample_rate)} kHz, {self.config.channels} ch")
