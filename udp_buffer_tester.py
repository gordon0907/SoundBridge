"""Run client side first."""

# Server
if __name__ == '__main__':
    import socket
    from contextlib import suppress

    PACKET_SIZE = 32 * 2 * 2
    START_SIZE = 32

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('', 2016))
    s.setblocking(False)

    s_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s_.bind(('', 2017))

    records = {}

    for buffer_size in range(START_SIZE, 2000):
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffer_size)

        # 1st iter for refreshing the buffer
        for _ in range(2):
            # Notify start
            s_.sendto(b'', ('192.168.0.110', 2016))
            # Wait for finish
            s_.recv(1)

            # Empty the buffer
            count = 0
            with suppress(BlockingIOError):
                while True:
                    s.recv(PACKET_SIZE)
                    count += 1

        records[buffer_size] = count
        if count != records.get(buffer_size - 1, 0):
            print(buffer_size, count)

# Client
if __name__ == '__main__':
    import socket

    PACKET_SIZE = 32 * 2 * 2

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('', 2016))

    while True:
        s.recv(1)
        for i in range(1000):
            s.sendto(b'\x00' * PACKET_SIZE, ('192.168.0.120', 2016))
        s.sendto(b'', ('192.168.0.120', 2017))
