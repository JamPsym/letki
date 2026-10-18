"""Exercise the native C renderer through the same socket API used by agents."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(os.environ.get("LETKI_RENDERER", ROOT / "build/renderer/letki-renderer"))


class NativeRendererTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="letki-renderer-")
        self.path = str(Path(self.temp.name) / "control.sock")
        self.process = subprocess.Popen(
            [str(BIN), "--headless", "--manual", "--socket", self.path],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        deadline = time.monotonic() + 3
        while not Path(self.path).exists():
            if self.process.poll() is not None:
                self.fail(self.process.communicate())
            if time.monotonic() > deadline:
                self.fail("Renderer socket was not created")
            time.sleep(.01)

    def tearDown(self):
        self.process.terminate()
        stdout, stderr = self.process.communicate(timeout=3)
        self.assertEqual(self.process.returncode, 0, (stdout, stderr))
        self.assertFalse(Path(self.path).exists(), "Owned socket must be removed on exit")
        self.temp.cleanup()

    def command(self, text, valid=True):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(self.path)
            client.sendall((text + "\n").encode())
            data = bytearray()
            while chunk := client.recv(65536):
                data.extend(chunk)
        result = json.loads(data)
        self.assertEqual(result["ok"], valid, text)
        return result

    @staticmethod
    def balls(state):
        pixels = []
        for tile in state["tiles"]:
            columns = bytes.fromhex(tile["columns"])
            for x, column in enumerate(columns):
                for y in range(8):
                    if x == 7 and y == 0:  # Reserved transport indicator.
                        continue
                    if column & (1 << y):
                        pixels.append((tile["index"] * 8 + x, y))
        return pixels

    def test_general_levels_are_row_major_and_invalid_input_preserves_pixels(self):
        self.command("boards 5")
        pixels=bytearray(64);pixels[2*8+3]=70
        state=self.command("levels 2 "+pixels.hex())
        self.assertEqual(state["tiles"][2]["levels"],pixels.hex())
        self.assertEqual(bytes.fromhex(state["tiles"][2]["columns"])[3],1<<2)
        self.command("levels 2 "+(bytes([101])*64).hex(),False)
        self.assertEqual(self.command("status")["tiles"][2]["levels"],pixels.hex())

    def test_full_trajectories_for_one_through_five_boards(self):
        for boards in range(1, 6):
            state = self.command(f"boards {boards}")
            self.assertEqual(self.balls(state), [])
            visited = set()
            old = None
            # Include wrapping the entire trajectory, not just the first seam.
            for _ in range(state["phase_count"] + 2):
                state = self.command("step")
                self.assertTrue(all(t["alive"] for t in state["tiles"]))
                self.assertTrue(all(t["phase"] == state["tiles"][0]["phase"] for t in state["tiles"]))
                pixels = self.balls(state)
                self.assertEqual(len(pixels), 1)
                x, y = pixels[0]
                self.assertTrue(0 <= x < boards * 8 and 0 <= y < 8)
                if old:
                    self.assertEqual(abs(x - old[0]), 1)
                    self.assertEqual(abs(y - old[1]), 1)
                old = x, y
                visited.add(x)
            self.assertEqual(visited, set(range(boards * 8)))

    def test_loss_timeout_retry_and_pause(self):
        self.command("boards 5")
        good = self.command("step 10")
        self.command("link 2 down")
        failed = self.command("step")
        self.assertEqual(failed["tiles"][0]["phase"], good["tiles"][0]["phase"])
        self.assertFalse(failed["tiles"][0]["alive"])
        self.assertEqual(failed["tiles"][2]["accepted"], good["tiles"][2]["accepted"])
        expired = self.command("advance 1500")
        self.assertTrue(all(not t["alive"] for t in expired["tiles"][2:]))
        self.command("link 2 up")
        recovered = self.command("step")
        self.assertTrue(all(t["alive"] for t in recovered["tiles"]))
        self.assertEqual(recovered["tiles"][0]["phase"], (good["tiles"][0]["phase"] + 1) % recovered["phase_count"])
        self.command("pause")
        held = self.command("step")
        exchanged = self.command("step 20")
        self.assertEqual(exchanged["tiles"][0]["phase"], held["tiles"][0]["phase"])
        self.assertEqual(exchanged["tiles"][0]["accepted"], held["tiles"][0]["accepted"] + 20)
        self.assertTrue(all(t["alive"] for t in exchanged["tiles"]))
        self.command("resume")
        self.command("step")
        advanced = self.command("step")
        self.assertNotEqual(advanced["tiles"][0]["phase"], held["tiles"][0]["phase"])

    def test_crc_and_external_frames(self):
        self.command("step 3")
        before = self.command("status")
        self.command("corrupt 1")
        damaged = self.command("step")
        self.assertEqual(damaged["tiles"][0]["phase"], before["tiles"][0]["phase"])
        self.assertEqual(damaged["tiles"][1]["phase"], before["tiles"][1]["phase"])
        self.assertGreater(damaged["tiles"][1]["failed"], 0)
        self.command("mode external")
        # Real firmware protocol: A5, little-endian phase, CRC-8/0x07.
        packet = bytearray([0xA5, 9, 0])
        crc = 0
        for byte in packet:
            crc ^= byte
            for _ in range(8):
                crc = ((crc << 1) ^ (7 if crc & 128 else 0)) & 255
        packet.append(crc)
        state = self.command(f"packet 1 {packet.hex()}")
        self.assertEqual(state["tiles"][1]["phase"], 9)
        self.assertFalse(state["tiles"][0]["alive"])
        before = self.command("status")
        packet[-1] ^= 1
        self.command(f"packet 1 {packet.hex()}", valid=False)
        self.assertEqual(self.command("status"), before)
        self.assertFalse(self.command("advance 1500")["tiles"][1]["alive"])
        self.command("frame 0 0102040810204080")
        frame = self.command("status")
        self.assertEqual(frame["tiles"][0]["columns"], "0102040810204080")
        self.assertTrue(frame["tiles"][0]["raw"])

    def test_validation_maximum_strip_cli_and_snapshot(self):
        before = self.command("status")
        for command in ("boards 0", "boards 257", "boards -1", "step 10001", "advance 99999999999999999999",
                        "speed 49", "receive 0 210", "frame 0 0000", "link 9 down", "link 0 nope",
                        "step 2 extra", "mode unknown", "" ):
            self.command(command, valid=False)
            self.assertEqual(self.command("status"), before)
        maximum = self.command("boards 256")
        self.assertEqual(len(maximum["tiles"]), 256)
        self.assertLess(maximum["phase_count"], 32768)
        self.command("step 10")
        png = Path(self.temp.name) / "strip test.png"
        self.command(f"snapshot {png}")
        self.assertEqual(png.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        cli = subprocess.run([str(BIN), "--socket", self.path, "ctl", "status"], capture_output=True, text=True, timeout=3)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout)["boards"], 256)
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o700)

    def test_stalled_client_duplicate_instance_and_realtime(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stalled:
            stalled.connect(self.path)
            stalled.sendall(b"sta")
            duplicate = subprocess.run([str(BIN), "--headless", "--socket", self.path], capture_output=True, text=True, timeout=3)
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertTrue(Path(self.path).exists())
            self.command("run")
            time.sleep(.25)
            state = self.command("stop")
            self.assertGreaterEqual(state["tiles"][0]["accepted"], 2)
            self.assertFalse(state["running"])
            self.assertTrue(self.command("status")["ok"])

    def test_five_tile_pwm_show(self):
        self.command("boards 5")
        state=self.command("demo pwm")
        self.assertEqual(state["demo"],"pwm")
        self.assertEqual(state["interval_ms"],40)
        self.assertEqual(len(state["tiles"]),5)
        self.command("pwm audio on")
        state=self.command("pwm seek 32000")
        self.assertTrue(state["pwm_audio"])
        self.assertFalse(state["running"])
        self.assertEqual(state["pwm_tick"],800)
        self.assertEqual(state["pwm_scene"],"Daisy chain")
        self.command("pwm seek 0")
        self.command("pwm audio off")
        scenes=set()
        for _ in range(6):
            state=self.command("step 160")
            scenes.add(state["pwm_scene"])
            values=[v for t in state["tiles"] for v in bytes.fromhex(t["levels"])]
            self.assertEqual(len(values),320)
            self.assertTrue(all(v<=100 for v in values))
            self.assertGreaterEqual(len(set(values)),8)
        self.assertEqual(len(scenes),6)
        self.command("pause")
        before=self.command("status")
        after=self.command("step 25")
        self.assertEqual(before["pwm_tick"],after["pwm_tick"])
        self.assertEqual([t["levels"] for t in before["tiles"]],[t["levels"] for t in after["tiles"]])
        self.command("resume")
        self.command("pwm scene ladder")
        state=self.command("status")
        self.assertFalse(state["pwm_auto"])
        self.assertEqual(state["pwm_scene"],"Light ladder")
        self.command("pwm brightness 0")
        self.assertEqual(self.command("status")["pwm_brightness_pct"],0)
        for command in ("pwm scene bad","pwm brightness 101","pwm brightness -1"):
            self.command(command,valid=False)
        self.assertEqual(self.command("status")["pwm_brightness_pct"],0)
        self.command("pwm brightness 75")
        self.command("boards 3")
        state=self.command("status")
        self.assertEqual(state["demo"],"pwm")
        self.assertEqual(state["pwm_brightness_pct"],75)
        self.command("snapshot "+str(Path(self.temp.name)/"pwm.png"))
        self.command("demo text")
        self.assertEqual(self.command("status")["demo"],"text")

    def test_five_tile_falling_text_and_pulse(self):
        self.command("boards 5")
        self.command("demo text")
        self.command("uart t LETKI DZIAŁA PIĘĆ PŁYTEK RAZEM")
        self.command("uart m fall")
        self.command("uart b 40")
        levels=set()
        lines=set()
        frames=set()
        for _ in range(96):
            state=self.command("step")
            self.assertEqual(state["text_mode"],"fall")
            self.assertTrue(state["pulse"])
            self.assertLessEqual(state["effective_brightness_pct"],40)
            levels.add(state["effective_brightness_pct"])
            lines.add(state["text_line"])
            frames.add(tuple(t["columns"] for t in state["tiles"]))
        self.assertGreater(len(levels),8)
        self.assertGreater(len(lines),1)
        self.assertGreater(len(frames),10)
        self.command("uart p")
        held=self.command("step")
        later=self.command("step 20")
        for key in ("text_line","text_offset","effective_brightness_pct"):
            self.assertEqual(held[key],later[key])
        self.command("uart e off")
        self.assertEqual(self.command("step")["effective_brightness_pct"],40)

    def test_standard_text_preview_uses_firmware_commands(self):
        self.command("boards 2")
        initial=self.command("demo text")
        self.assertEqual(initial["text_mode"],"bounce")
        offsets=set()
        previous=None
        for _ in range(120):
            state=self.command("step")
            offsets.add(state["text_offset"])
            self.assertTrue(all(t["alive"] for t in state["tiles"]))
            if previous is not None:
                self.assertLessEqual(abs(state["text_offset"]-previous),1)
            previous=state["text_offset"]
        self.assertEqual(min(offsets),0)
        self.assertGreater(max(offsets),16)
        state=self.command("uart m scroll")
        self.assertEqual(state["uart_reply"],"OK mode updated\r\n")
        self.command("step 12")
        self.command("uart p")
        held=self.command("step")
        self.assertEqual(self.command("step 20")["text_offset"],held["text_offset"])
        self.command("uart r")
        self.command("uart v 50")
        self.assertEqual(self.command("status")["interval_ms"],50)
        state=self.command("uart t zażółć gęślą jaźń")
        self.assertEqual(state["uart_reply"],"OK text updated\r\n")
        self.command("step 3")
        self.command("uart b 25")
        self.assertEqual(self.command("step")["brightness_pct"],25)
        before=self.command("status")
        self.command("uart m wrong",valid=False)
        after=self.command("status")
        self.assertEqual(after["text_mode"],before["text_mode"])
        self.assertEqual(after["text_offset"],before["text_offset"])
        self.command("uart ping test-token")
        self.assertEqual(self.command("status")["uart_reply"],"PONG test-token\r\n")
        self.command("uart g 01020408102040800102040810204080")
        frame=self.command("step")
        self.assertEqual([t["columns"] for t in frame["tiles"]],["0102040810204080"]*2)


if __name__ == "__main__":
    unittest.main()
