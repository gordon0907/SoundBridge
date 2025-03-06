from __future__ import annotations

import pickle
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property

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
        return self.num_frames * self.channels * get_sample_size(self.audio_format)

    @property
    def packet_duration(self) -> float:
        return self.num_frames / self.sample_rate  # in seconds

    @property
    def udp_buffer_size(self) -> int:
        num_bytes = int(BUFFER_TIME * self.sample_rate * self.channels * get_sample_size(self.audio_format))
        num_packets = num_bytes // self.packet_size
        # Calculate required buffer size for packets based on macOS experimental testing
        # Offset varies with `packet_size`: slot_size = 448, offset = -428, min_overhead = 32
        return max(448 * num_packets - 428, 32 + self.packet_size)

    def to_bytes(self) -> bytes:
        return pickle.dumps(self)

    @staticmethod
    def from_bytes(bytes_) -> AudioConfig | None:
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


def print_(*args, **kwargs):
    return print(f"[{datetime.now().isoformat()}]", *args, **kwargs)
