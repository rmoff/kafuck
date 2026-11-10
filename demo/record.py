#!/usr/bin/env python3
"""Types the Kafuck demo into a real shell, at human speed.

Record it with:

    asciinema rec --headless --window-size 90x30 --idle-time-limit 2 \\
        -f asciicast-v2 --overwrite -c "python3 demo/record.py" demo/kafuck.cast
"""

import fcntl
import os
import pty
import random
import struct
import sys
import termios
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT = [
    ("type", "# Kafuck: Kafka, rewritten in Brainfuck"),
    ("type", "./kafuck"),
    ("pause", 2.0),
    ("type", "Phello"),
    ("type", "Pworld"),
    ("type", "Pis this production-ready? 🚀"),
    ("pause", 0.8),
    ("type", "C0"),
    ("pause", 1.2),
    ("type", "C2"),
    ("pause", 1.2),
    ("keys", "\x04"),
    ("pause", 2.5),
    ("type", "clear"),
    ("type", "# but is it fast?"),
    ("type", "python3 bench/bench.py"),
    ("pause", 4.0),
]

last_output = time.monotonic()


def relay(fd):
    global last_output
    while True:
        try:
            data = os.read(fd, 4096)
        except OSError:
            return
        if not data:
            return
        last_output = time.monotonic()
        os.write(sys.stdout.fileno(), data)


def wait_quiet(seconds=0.4):
    while time.monotonic() - last_output < seconds:
        time.sleep(0.05)


def type_line(fd, text):
    wait_quiet()
    for ch in text:
        os.write(fd, ch.encode())
        time.sleep(random.uniform(0.04, 0.09))
    time.sleep(0.3)
    os.write(fd, b"\r")
    time.sleep(0.2)


def window_size():
    try:
        return fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b"\0" * 8)
    except OSError:
        return struct.pack("HHHH", 30, 90, 0, 0)


def main():
    random.seed(4)
    size = window_size()
    pid, fd = pty.fork()
    if pid == 0:
        fcntl.ioctl(0, termios.TIOCSWINSZ, size)
        os.chdir(ROOT)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/"),
            "TERM": "xterm-256color",
            "LANG": "en_US.UTF-8",
            "PS1": "\\[\\e[1;32m\\]$\\[\\e[0m\\] ",
            "BASH_SILENCE_DEPRECATION_WARNING": "1",
        }
        os.execvpe("bash", ["bash", "--norc", "--noprofile"], env)

    reader = threading.Thread(target=relay, args=(fd,), daemon=True)
    reader.start()
    time.sleep(0.8)

    for step, arg in SCRIPT:
        if step == "type":
            type_line(fd, arg)
        elif step == "keys":
            wait_quiet()
            os.write(fd, arg.encode())
        elif step == "pause":
            wait_quiet()
            time.sleep(arg)

    wait_quiet()
    os.write(fd, b"exit\r")
    os.waitpid(pid, 0)
    reader.join(timeout=1)


if __name__ == "__main__":
    main()
