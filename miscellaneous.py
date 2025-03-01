from __future__ import annotations

import pickle
from datetime import datetime


class AudioConfig:
    def __init__(self, audio_format: int, channels: int, sample_rate: int, num_frames: int):
        self.audio_format = audio_format
        self.channels = channels
        self.sample_rate = sample_rate
        self.num_frames = num_frames

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
