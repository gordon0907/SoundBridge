import socket
import time
from collections import deque
from io import BytesIO
from threading import Thread

from config import *
from utils import *


class DataChannel:
    def __init__(
            self,
            is_server: bool,
            server_host: str,
            server_port: int,
            sender_config: AudioConfig,
            receiver_config: AudioConfig,
    ):
        # --- 1. Set Up Socket ---
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x10)  # IPTOS_LOWDELAY
        self.socket.settimeout(SOCKET_TIMEOUT)

        self.is_server = is_server
        if is_server:
            self.socket.bind((server_host, server_port))
            print_(f"UDP data channel listening on port {server_port}")
            self.dst_address = '', 0  # To be set on data receipt
        else:
            self.socket.bind(("0.0.0.0", 0))  # Prevent OSError on recvfrom before sendto
            self.dst_address = server_host, server_port

        # --- 2. Initialize and Set Up Buffer and Parameters ---
        self.tx_buffer = self.rx_buffer = deque([b''])
        self.tx_chunk_size = self.rx_chunk_size = 0
        self.tx_chunks_per_pkt = self.rx_chunks_per_pkt = 0
        self.tx_pkt_duration = self.rx_pkt_duration = 0.

        self.setup(sender_config, receiver_config)

        # --- 3. Initialize and Start Thread ---
        self.run_flag: bool = False
        self.sender_thread = self.receiver_thread = Thread()

        self.start()

    def setup(self, sender_config: AudioConfig, receiver_config: AudioConfig):
        """Set up buffers and parameters with the given configurations."""
        self.tx_buffer = deque(maxlen=int(BUFFER_TIME / sender_config.chunk_duration))
        self.rx_buffer = deque(maxlen=int(BUFFER_TIME / receiver_config.chunk_duration))

        self.tx_chunk_size = sender_config.chunk_size
        self.rx_chunk_size = receiver_config.chunk_size

        self.tx_chunks_per_pkt = MAX_PACKET_SIZE // self.tx_chunk_size
        self.rx_chunks_per_pkt = MAX_PACKET_SIZE // self.rx_chunk_size

        self.tx_pkt_duration = sender_config.chunk_duration * self.tx_chunks_per_pkt
        self.rx_pkt_duration = receiver_config.chunk_duration * self.rx_chunks_per_pkt

    def start(self):
        """Start the sender and receiver loop threads."""
        self.run_flag = True

        self.sender_thread = Thread(target=self.__sender)
        self.receiver_thread = Thread(target=self.__receiver)

        self.sender_thread.start()
        self.receiver_thread.start()

    def stop(self):
        """Stop the sender and receiver loop threads."""
        self.run_flag = False
        self.sender_thread.join()
        self.receiver_thread.join()

    def __sender(self):
        while self.run_flag:
            # Wait for enough chunks
            if len(self.tx_buffer) < self.tx_chunks_per_pkt:
                time.sleep(self.tx_pkt_duration)
                continue

            # Send packet
            payload = b''.join(self.tx_buffer.popleft() for _ in range(self.tx_chunks_per_pkt))
            try:
                self.socket.sendto(payload, self.dst_address)
            except OSError:
                pass

    def __receiver(self):
        while self.run_flag:
            try:
                payload, sender_address = self.socket.recvfrom(MAX_PACKET_SIZE)
            except TimeoutError:
                continue

            # Set destination as latest sender (server-side)
            if self.is_server:
                self.dst_address = sender_address

            # Append chunks to buffer
            payload_stream = BytesIO(payload)
            while chunk := payload_stream.read(self.rx_chunk_size):
                self.rx_buffer.append(chunk)

    def put_chunk(self, chunk: bytes) -> None:
        self.tx_buffer.append(chunk)

    def get_chunk(self) -> bytes | None:
        try:
            return self.rx_buffer.popleft()
        except IndexError:
            return None
