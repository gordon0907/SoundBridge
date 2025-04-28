from pyaudio import paInt16

# Socket Configuration
SERVER_HOST: str = "192.168.0.120"
DATA_PORT: int = 2025
CONTROL_PORT: int = 2026
SOCKET_TIMEOUT: float = 1.0  # seconds
MAX_PACKET_SIZE: int = 1024  # bytes

# Audio Configuration
AUDIO_DTYPE: int = paInt16  # 16-bit format
FRAMES_PER_CHUNK: int = 32
BUFFER_TIME: float = 0.2  # seconds
