#!/usr/bin/env python3
"""Isolated Unix-socket integration tests. Never opens physical UART hardware."""
import concurrent.futures
import json
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
DAEMON = ROOT / "build/control/letkid"
CTL = ROOT / "build/control/letkictl"


def draft(text="CZEŚĆ", **changes):
    value = dict(text=text, font="compact", motion="scroll", speed=75,
                 brightness=75, minimum=5, pulses=2, modulation="steady", loop=True)
    value.update(changes)
    return value


class DisplayService(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="letki-service-")
        self.path = str(Path(self.temp.name) / "display.sock")
        self.log = open(Path(self.temp.name) / "service.log", "w+")
        # --simulate is mandatory: these tests must not discover a USB adapter.
        self.daemon = subprocess.Popen([str(DAEMON), "--simulate", "--socket", self.path],
                                       cwd=ROOT, stdout=self.log, stderr=self.log)
        until = time.monotonic() + 6
        while time.monotonic() < until:
            if self.daemon.poll() is not None:
                self.log.seek(0)
                self.fail("Daemon exited: " + self.log.read())
            try:
                state = self.rpc("status")
                if state.get("connected") and not state.get("busy"):
                    break
            except (OSError, ValueError):
                pass
            time.sleep(.02)
        else:
            self.fail("Simulated service did not become ready")
        self.assertTrue(state.get("simulated"), state)

    def tearDown(self):
        if self.daemon.poll() is None:
            self.daemon.terminate()
            try:
                self.daemon.wait(timeout=6)
            except subprocess.TimeoutExpired:
                self.daemon.kill()
                self.daemon.wait()
        self.log.close()
        self.temp.cleanup()

    def raw(self, payload):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(5)
            client.connect(self.path)
            client.sendall(payload + b"\n")
            data = bytearray()
            while b"\n" not in data:
                block = client.recv(65536)
                if not block:
                    break
                data.extend(block)
                if len(data) > 1024 * 1024:
                    self.fail("Unbounded service response")
        return json.loads(bytes(data).split(b"\n", 1)[0])

    def rpc(self, op, **values):
        return self.raw(json.dumps(dict(v=1, op=op, **values), ensure_ascii=False).encode())

    def ok(self, op, **values):
        response = self.rpc(op, **values)
        self.assertTrue(response.get("ok"), response)
        return response

    def idle(self, timeout=6):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            response = self.ok("status")
            if not response.get("busy"):
                self.assertFalse(response.get("last_error"), response)
                return response
            time.sleep(.01)
        self.fail("Display operation did not complete")

    def cli(self, *args, input=None, check=True):
        result = subprocess.run([str(CTL), "--socket", self.path, *args], cwd=ROOT,
                                input=input, text=True, capture_output=True, timeout=10)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result

    def test_two_clients_share_single_connection(self):
        def status(_):
            return self.rpc("status")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(status, range(12)))
        self.assertTrue(all(r.get("ok") and r.get("connected") and r.get("simulated")
                            for r in replies), replies)
        self.assertEqual(json.loads(self.cli("--start", "status").stdout)["v"], 1)
        self.ok("disconnect")
        self.assertFalse(self.idle()["connected"])
        self.ok("connect", simulate=True)
        self.assertTrue(self.idle()["connected"])

    def test_preview_and_long_text(self):
        response = self.ok("preview", draft=draft("B", motion="still", font="large", brightness=37))
        self.assertEqual(len(response["pixels"]), 320)
        self.assertTrue(set(response["pixels"]) <= {0, 37}, response)
        self.assertIn(37, response["pixels"])
        self.assertGreater(response["bytes"], 0)
        self.assertTrue(response["fits"])
        long = draft("W" * 45 + " " * 9, font="bold", motion="bounce", speed=92,
                     brightness=97, modulation="breathe", pulses=1)
        preview = self.ok("preview", draft=long)
        self.assertGreater(preview["duration_ms"], 60000)
        self.assertTrue(preview["fits"], preview)
        self.ok("text", draft=long)
        state = self.idle()
        self.assertGreater(state["applied"], 0)
        before = state["applied"]
        saved_lengths = [node["bytes"] for node in state["nodes"]]
        saved_program_bytes = state["program_bytes"]
        too_big = draft("W" * 120, font="bold")
        preview = self.ok("preview", draft=too_big)
        self.assertFalse(preview["fits"])
        self.assertFalse(self.rpc("text", draft=too_big)["ok"])
        after = self.idle()
        self.assertEqual(after["applied"], before)
        self.assertEqual(after["program_bytes"], saved_program_bytes)
        self.assertEqual([node["bytes"] for node in after["nodes"]], saved_lengths)

    def test_modulation_and_unicode_validation(self):
        a = self.ok("preview", draft=draft("ĄĆĘŁŃÓŚŹŻ", motion="still", modulation="breathe",
                                           minimum=0, brightness=100, pulses=1), position_ms=0)
        b = self.ok("preview", draft=draft("ĄĆĘŁŃÓŚŹŻ", motion="still", modulation="breathe",
                                           minimum=0, brightness=100, pulses=1), position_ms=2000)
        self.assertEqual(max(a["pixels"]), 0)
        self.assertEqual(max(b["pixels"]), 100)
        for changes in (dict(text="🙂"), dict(font="missing"), dict(motion="missing"),
                        dict(speed=-1), dict(brightness=101),
                        dict(minimum=95, brightness=30, modulation="breathe")):
            self.assertFalse(self.rpc("preview", draft=draft(**changes))["ok"], changes)

    def test_bad_protocol_requests_are_bounded_and_do_not_break_service(self):
        for payload in (b"{", b"null", b"[]", b'{"v":2,"op":"status"}',
                        b'{"v":1,"op":"missing"}', b'{"v":1,"op":"preview","draft":{"text":"\xff"}}',
                        b'{"v":1,"op":"status","padding":"' + b"x" * 131072 + b'"}'):
            response = self.raw(payload)
            self.assertFalse(response.get("ok"), response)
            self.assertTrue(response.get("error"), response)
        self.assertTrue(self.ok("status")["connected"])
        for value in ([0] * 319, [101] * 320, [0.5] * 320, [True] * 320):
            self.assertFalse(self.rpc("pixels", pixels=value)["ok"])

    def test_pixels_and_stream_lease_ownership(self):
        self.ok("text", draft=draft("KEEP ME"))
        state = self.idle()
        self.ok("pixels", pixels=[100] * 320)
        state = self.idle()
        before = state["applied"]
        self.assertEqual(state["simulation_pixels"], [100] * 320)
        lease = self.ok("stream_begin", owner="first-app", ttl_ms=3000)["lease"]
        self.assertTrue(lease)
        state = self.idle()
        self.assertTrue(state["streaming"])
        self.assertEqual(state["stream_owner"], "first-app")
        self.assertFalse(self.rpc("stream_begin", owner="other-app")["ok"])
        self.assertFalse(self.rpc("stream_frame", lease="wrong", pixels=[0] * 320)["ok"])
        self.assertFalse(self.rpc("text", draft=draft("INTERRUPT"))["ok"])
        streamed = state.get("streamed", 0)
        self.ok("stream_frame", lease=lease, pixels=[100] * 320)
        state = self.idle()
        self.assertGreater(state["streamed"], streamed)
        self.ok("stream_end", lease=lease)
        state = self.idle()
        self.assertFalse(state["streaming"])
        self.assertEqual(state["applied"], before)
        self.assertEqual(state["simulation_pixels"], [100] * 320)
        # Releasing ownership holds the last frame; it does not replace the loaded program.
        self.ok("resume")
        self.idle()

    def test_level8_stream_preserves_fine_pwm_steps(self):
        values = [0, 1, 2, 5, 10, 25, 50, 100] * 40
        lease = self.ok("stream_begin", owner="fine-pwm", format=2)["lease"]
        self.assertEqual(self.idle()["baud"], 230400)
        self.ok("stream_frame", lease=lease, pixels=values)
        self.idle()
        self.ok("stream_end", lease=lease)
        stopped = self.idle()
        self.assertEqual(stopped["simulation_pixels"], values)
        self.assertEqual(stopped["baud"], 115200)
        self.assertEqual(stopped["stream_late"], 0)
        self.assertEqual(stopped["stream_dropped"], 0)
        self.assertFalse(self.rpc("stream_begin", owner="bad", format=3)["ok"])
        self.ok("text", draft=draft("W" * 146))
        self.idle()
        self.assertFalse(self.rpc("stream_begin", owner="too-big", format=2)["ok"])
        self.assertTrue(self.idle()["connected"])

    def test_music_catalog_and_silent_companion_lifecycle(self):
        songs = self.ok("music_catalog")["songs"]
        self.assertEqual([s["id"] for s in songs], ["tubular-bells", "my-cyganie", "adagio", "lamour-toujours", "laskowski-2pac"])
        before = self.idle()["applied"]
        self.assertFalse(self.rpc("music_start", id="not-a-demo", simulate=True)["ok"])
        self.assertEqual(self.idle()["applied"], before)
        if not next(s["available"] for s in songs if s["id"] == "my-cyganie"):
            self.skipTest("Optional local music recording/player unavailable")
        # No PortAudio, SDL window or physical UART: real companion, simulated chain.
        self.ok("music_start", id="my-cyganie", simulate=True, silent=True,
                headless=True, duration_ms=100)
        until = time.monotonic() + 25
        while time.monotonic() < until:
            state = self.ok("status")
            if not state.get("music_active"):
                self.assertEqual(state.get("music_error"), "", state)
                break
            time.sleep(.05)
        else:
            self.fail("Silent companion demo did not finish")
        self.assertTrue(state["connected"] and state["simulated"])
        self.assertEqual(state["applied"], before)
        self.ok("music_start", id="my-cyganie", simulate=True, silent=True,
                headless=True, duration_ms=5000)
        self.ok("music_stop")
        until = time.monotonic() + 10
        while self.ok("status").get("music_active") and time.monotonic() < until:
            time.sleep(.05)
        self.assertFalse(self.ok("status")["music_active"])
        self.assertEqual(self.ok("status")["music_error"], "")

    def test_two_slot_stream_applies_backpressure_and_holds_last_frame(self):
        # 632 bytes leave 120 of the 752-byte arena: exactly two 48-byte GRAY4
        # slots. LEVEL8's usual two slots would not fit alongside this program.
        loaded = self.ok("text", draft=draft("W" * 146))
        self.assertGreaterEqual(loaded["bytes"], 624)
        self.assertLessEqual(loaded["bytes"], 656)
        state = self.idle()
        program_bytes = state["program_bytes"]
        applied = state["applied"]
        lease = self.ok("stream_begin", owner="two-slot-producer", ttl_ms=3000)["lease"]
        state = self.idle()
        self.assertEqual([node["slots"] for node in state["nodes"]], [2] * 5)
        first_count = state["streamed"]
        # Invalid client input must not tear down the live connection or lease.
        for invalid in (dict(pixels=[101] * 320), dict(pixels=[0] * 319),
                        dict(pixels=[0] * 320, deadline_ms=int(time.monotonic() * 1000) - 1),
                        dict(pixels=[0] * 320, deadline_ms=int(time.monotonic() * 1000) + 2000),
                        dict(pixels=[0] * 320, deadline_ms=True)):
            self.assertFalse(self.rpc("stream_frame", lease=lease, **invalid)["ok"])
            state = self.ok("status")
            self.assertTrue(state["connected"], state)
            self.assertFalse(state["last_error"], state)
            self.assertEqual(state["stream_owner"], "two-slot-producer")
        presentation_backpressure = 0
        for frame in range(16):
            level = 100 if frame == 15 else frame * 6
            until = time.monotonic() + 3
            while True:
                response = self.rpc("stream_frame", lease=lease, pixels=[level] * 320)
                if response["ok"]:
                    break
                self.assertIn("busy", response["error"].lower(), response)
                presentation_backpressure += "presenting" in response["error"]
                state = self.ok("status")
                self.assertTrue(state["connected"], state)
                self.assertFalse(state["last_error"], state)
                if time.monotonic() >= until:
                    self.fail("Two-slot stream did not recover from backpressure")
                time.sleep(.005)
        self.assertGreater(presentation_backpressure, 0,
                           "Rapid producer should fill both pending presentation slots")
        state = self.idle()
        self.assertEqual(state["streamed"], first_count + 16)
        self.ok("stream_end", lease=lease)
        state = self.idle()
        self.assertTrue(state["connected"], state)
        self.assertFalse(state["streaming"])
        self.assertEqual(state["simulation_pixels"], [100] * 320)
        self.assertEqual(state["program_bytes"], program_bytes)
        self.assertEqual(state["applied"], applied)
        for node in state["nodes"]:
            self.assertEqual(node["errors"], 0, node)
            self.assertEqual(node["drops"], 0, node)

    def test_expired_stream_can_be_claimed_by_another_app(self):
        old = self.ok("stream_begin", owner="expired-app", ttl_ms=1000)["lease"]
        self.idle()
        until = time.monotonic() + 3
        while time.monotonic() < until:
            state = self.ok("status")
            if not state.get("streaming") and not state.get("busy"):
                break
            time.sleep(.03)
        else:
            self.fail("Idle stream lease did not expire")
        self.assertFalse(self.rpc("stream_frame", lease=old, pixels=[0] * 320)["ok"])
        new = self.ok("stream_begin", owner="replacement", ttl_ms=3000)["lease"]
        self.assertNotEqual(new, old)
        self.idle()
        self.ok("stream_end", lease=new)
        self.idle()

    def test_cli_text_preview_pixels_and_stream(self):
        preview = json.loads(self.cli("preview", "ŁÓDŹ 42", "--font", "large", "--motion", "still",
                                      "--modulation", "blink", "--minimum", "0", "--brightness", "100").stdout)
        self.assertEqual(len(preview["pixels"]), 320)
        self.cli("text", "ŻÓŁĆ", "--font", "bold", "--speed", "90", "--once")
        self.idle()
        path = Path(self.temp.name) / "pixels.json"
        path.write_text(json.dumps([40] * 320))
        self.cli("pixels", str(path))
        self.idle()
        result = self.cli("stream", "pipe-app", input=json.dumps([100] * 320) + "\n" + json.dumps([0] * 320) + "\n")
        self.assertEqual(json.loads(result.stdout)["frames"], 2)
        self.assertFalse(self.idle()["streaming"])
        for arguments in (("text",), ("preview", "A", "--speed", "bad"), ("rpc", "{")):
            self.assertNotEqual(self.cli(*arguments, check=False).returncode, 0)
        rejected = self.cli("rpc", '{"v":9,"op":"status"}', check=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse(json.loads(rejected.stdout)["ok"])

    def test_cli_ctrl_c_releases_idle_stream(self):
        process = subprocess.Popen([str(CTL), "--socket", self.path, "stream", "interrupt-app"],
                                   cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            until = time.monotonic() + 4
            while time.monotonic() < until:
                state = self.ok("status")
                if state.get("streaming") and not state.get("busy"):
                    break
                time.sleep(.02)
            else:
                self.fail("CLI stream did not begin")
            process.send_signal(signal.SIGINT)
            process.wait(timeout=4)
            self.assertEqual(process.returncode, 130, process.stderr.read())
            self.assertFalse(self.idle()["streaming"])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            for handle in (process.stdin, process.stdout, process.stderr):
                handle.close()

    def test_slow_request_has_absolute_deadline_and_shutdown_is_bounded(self):
        # Each byte arrives far sooner than SO_RCVTIMEO's usual two seconds.
        # A per-read timeout alone would therefore never release this client.
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(.04)
            client.connect(self.path)
            client.sendall(b"{")
            started = time.monotonic()
            closed = False
            response = bytearray()
            while time.monotonic() - started < 3:
                try:
                    client.sendall(b" ")
                except (BrokenPipeError, ConnectionResetError):
                    closed = True
                    break
                try:
                    block = client.recv(4096)
                    if not block:
                        closed = True
                        break
                    response.extend(block)
                except (ConnectionResetError, BrokenPipeError):
                    closed = True
                    break
                except socket.timeout:
                    pass
                time.sleep(.1)
            self.assertTrue(closed, "Dripping clients must not extend the request deadline")
            self.assertLess(time.monotonic() - started, 2.8)
            if response:
                self.assertFalse(json.loads(response)["ok"])
        self.assertTrue(self.ok("status")["connected"])
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(self.path)
            client.sendall(b'{"v":1,"op":')
            time.sleep(.05)  # Let the request worker enter its incomplete read.
            started = time.monotonic()
            self.daemon.terminate()
            self.assertEqual(self.daemon.wait(timeout=3), 0)
            self.assertLess(time.monotonic() - started, 3)
        self.assertFalse(Path(self.path).exists())

    def test_single_owner_lock_and_clean_shutdown(self):
        duplicate = subprocess.run([str(DAEMON), "--simulate", "--no-connect", "--socket", self.path],
                                   cwd=ROOT, capture_output=True, timeout=3)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertTrue(self.ok("status")["connected"])
        self.daemon.terminate()
        self.assertEqual(self.daemon.wait(timeout=5), 0)
        self.assertFalse(Path(self.path).exists(), "Service must remove its socket on clean exit")


if __name__ == "__main__":
    if not DAEMON.exists() or not CTL.exists():
        raise SystemExit("Build letkid and letkictl first (make control).")
    unittest.main(verbosity=2)
