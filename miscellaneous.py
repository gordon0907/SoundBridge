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
    def from_bytes(bytes_):
        return pickle.loads(bytes_)


def print_(*args, **kwargs):
    return print(f"[{datetime.now().isoformat()}]", *args, **kwargs)
