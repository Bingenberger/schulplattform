import os
import pty

import pytest

from schulplattform.terminal import NoTerminal, open_tty


def test_open_tty_reads_and_writes_on_a_real_terminal():
    # Regression: open('/dev/tty', 'r+') raised "File or stream is not seekable" on real terminals.
    master, slave = pty.openpty()
    try:
        with open_tty(os.ttyname(slave)) as tty:
            tty.write("Frage: ")
            assert os.read(master, 100).startswith(b"Frage: ")
            os.write(master, "Antwort ä\n".encode())
            assert tty.readline().strip() == "Antwort ä"
    finally:
        os.close(master)
        os.close(slave)


def test_open_tty_without_terminal_names_the_cause(tmp_path):
    with pytest.raises(NoTerminal, match="Kein Terminal"):
        open_tty(tmp_path / "missing")
