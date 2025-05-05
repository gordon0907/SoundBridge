from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import cached_property

import psutil
from pyaudio import get_sample_size


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int
    channels: int
    audio_dtype: int
    frames_per_chunk: int

    @cached_property
    def chunk_size(self) -> int:
        """Chunk size in bytes."""
        return self.frames_per_chunk * self.channels * get_sample_size(self.audio_dtype)

    @cached_property
    def chunk_duration(self) -> float:
        """Chunk duration in seconds."""
        return self.frames_per_chunk / self.sample_rate

    def to_bytes(self) -> bytes:
        """Serialize the instance to JSON bytes."""
        return json.dumps(self._to_dict()).encode()

    @staticmethod
    def from_bytes(data: bytes) -> AudioConfig | None:
        """Deserialize JSON bytes to AudioConfig, or None on failure."""
        try:
            obj = json.loads(data)
        except ValueError:
            return None

        if not (
                isinstance(obj, dict)
                and all(isinstance(k, str) and isinstance(v, int) for k, v in obj.items())
        ):
            return None

        try:
            return AudioConfig._from_dict(obj)
        except TypeError:
            return None

    def _to_dict(self) -> dict[str, int]:
        """Convert the instance to a dict."""
        return asdict(self)

    @staticmethod
    def _from_dict(data: dict[str, int]) -> AudioConfig:
        """Create an AudioConfig from a dict."""
        return AudioConfig(**data)


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
