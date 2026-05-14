#!/usr/bin/env python3
"""Minimal serial console with proper backspace handling for Huawei switches.
Converts DEL (0x7F) to BS (0x08) before sending to serial port."""

import sys
import os
import select
import termios
import tty
import fcntl

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 9600

    # Map baud rate
    baud_map = {
        9600: termios.B9600,
        19200: termios.B19200,
        38400: termios.B38400,
        57600: termios.B57600,
        115200: termios.B115200,
    }
    speed = baud_map.get(baud, termios.B9600)

    # Open serial port
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

    # Configure serial port: raw mode, no echo, specified baud
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0  # iflag
    attrs[1] = 0  # oflag
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL  # cflag
    attrs[3] = 0  # lflag
    attrs[4] = speed  # ispeed
    attrs[5] = speed  # ospeed
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 1
    termios.tcsetattr(fd, termios.TCSANOW, attrs)

    # Clear non-blocking on serial fd for select()
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)

    # Save stdin terminal settings
    stdin_fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(stdin_fd)

    try:
        # Set stdin to raw mode
        tty.setraw(stdin_fd)

        while True:
            ready, _, _ = select.select([stdin_fd, fd], [], [], 0.1)

            if stdin_fd in ready:
                data = os.read(stdin_fd, 1024)
                if not data:
                    break
                # Convert DEL (0x7F) to BS (0x08) for Huawei
                data = data.replace(b'\x7f', b'\x08')
                os.write(fd, data)

            if fd in ready:
                try:
                    data = os.read(fd, 4096)
                    if data:
                        os.write(sys.stdout.fileno(), data)
                        sys.stdout.flush()
                except OSError:
                    pass

    except (KeyboardInterrupt, OSError):
        pass
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
        os.close(fd)


if __name__ == "__main__":
    main()
