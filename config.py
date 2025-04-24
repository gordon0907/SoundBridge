import pyaudio

# Global config
SERVER_PORT: int = 2025
CONTROL_PORT: int = 2026

# Server config
FORMAT: int = pyaudio.paInt16  # 16-bit format
NUM_FRAMES: int = 32  # Number of frames per buffer

# Client config
SERVER_HOST: str = "192.168.0.120"
