#!/usr/bin/env python3
"""Small standard-library example; no serial library or firmware knowledge."""
import json
import os
import socket
import sys
import time


def request(op, **values):
    runtime = os.environ.get("XDG_RUNTIME_DIR", f"/tmp/letki-{os.getuid()}")
    default = (runtime + "/letki/display.sock" if "XDG_RUNTIME_DIR" in os.environ
               else runtime + "/display.sock")
    path = os.environ.get("LETKI_SOCKET", default)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(path)
        client.sendall(json.dumps(dict(v=1, op=op, **values)).encode() + b"\n")
        with client.makefile("rb") as reply:
            result = json.loads(reply.readline(131073))
    if not result.get("ok"):
        raise RuntimeError(result.get("error", "Display operation failed"))
    return result


def wait():
    until = time.monotonic() + 15
    while time.monotonic() < until:
        state = request("status")
        if not state["busy"]:
            if state["last_error"]:
                raise RuntimeError(state["last_error"])
            return state
        time.sleep(.03)
    raise TimeoutError("Display operation did not complete")


if __name__ == "__main__":
    # Requires an already connected service. This changes only the volatile RAM show.
    request("text", draft=dict(text=" ".join(sys.argv[1:]) or "CZEŚĆ Z PYTHONA",
                              font="large", motion="bounce", brightness=100,
                              modulation="breathe", minimum=5, pulses=2))
    print(json.dumps(wait(), indent=2))
