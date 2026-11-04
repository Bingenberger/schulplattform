"""Controlling-terminal access for interactive console prompts.

open('/dev/tty', 'r+') fails on real terminals ("File or stream is not seekable"):
text mode with '+' needs a seekable buffered stream. An unbuffered raw handle
wrapped in a line-buffered text layer needs no seeking.
"""
import io


class NoTerminal(RuntimeError):
    pass


def open_tty(path="/dev/tty"):
    try:
        raw = open(path, "r+b", buffering=0)
    except OSError:
        raise NoTerminal("Kein Terminal verfügbar: dieser Schritt fragt interaktiv und braucht eine echte "
                         "Terminal-Sitzung (z. B. 'ssh -t root@server'), keinen Aufruf über Pipe/Skript.") from None
    return io.TextIOWrapper(raw, encoding="utf-8", line_buffering=True, write_through=True)
