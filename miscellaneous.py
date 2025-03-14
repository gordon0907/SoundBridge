from __future__ import annotations

import pickle
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property

import psutil
from pyaudio import get_sample_size

BUFFER_TIME: float = 0.2  # in seconds


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int
    channels: int
    audio_format: int
    num_frames: int

    @cached_property
    def packet_size(self) -> int:
        """Packet size in bytes."""
        return self.num_frames * self.channels * get_sample_size(self.audio_format)

    @property
    def packet_duration(self) -> float:
        """Packet duration in seconds."""
        return self.num_frames / self.sample_rate

    @property
    def udp_buffer_size(self) -> int:
        """Calculate the required UDP buffer size for the specified BUFFER_TIME."""
        num_bytes = int(BUFFER_TIME * self.sample_rate * self.channels * get_sample_size(self.audio_format))
        num_packets = num_bytes // self.packet_size
        # Constants are derived from tests on macOS, which vary with packet_size
        # When packet_size = 128: slot_size = 448, offset = -428, min_overhead = 32
        return max(448 * num_packets - 428, 32 + self.packet_size)

    def to_bytes(self) -> bytes:
        """Serialize the object."""
        return pickle.dumps(self)

    @staticmethod
    def from_bytes(bytes_) -> AudioConfig | None:
        """Deserialize bytes into an AudioConfig, or return None on failure."""
        try:
            return pickle.loads(bytes_)
        except (pickle.UnpicklingError, EOFError):
            return None


class Color:
    RESET = '\033[0m'
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'


def format_hz_to_khz(hz: int | float) -> str:
    """Convert frequency in Hz to a smartly formatted kHz string."""
    khz: float = hz / 1000
    return f'{khz:.3f}'.rstrip('0').rstrip('.')  # Remove unnecessary trailing zeros and decimal point


def print_(*args, **kwargs):
    return print(f"[{datetime.now().isoformat()}]", *args, **kwargs)


def raise_process_priority():
    process = psutil.Process()

    if psutil.WINDOWS:
        process.nice(psutil.HIGH_PRIORITY_CLASS)
        print_("Set process priority to HIGH_PRIORITY_CLASS")
    elif psutil.MACOS:
        try:
            process.nice(-10)
            print_("Set process priority to nice -10")
        except psutil.AccessDenied:
            print_("Permission denied: Run with sudo for nice -10 process priority")
