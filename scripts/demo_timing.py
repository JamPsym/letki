"""Plan readable display scenes without accelerating or truncating speech."""

import math


def scene_timing(text, step_ms, audio_seconds, delay_pixels=6):
    if not 1 <= len(text) <= 64:
        raise ValueError("Display text must contain 1..64 characters")
    if not math.isfinite(audio_seconds) or audio_seconds <= 0:
        raise ValueError("Invalid audio duration")
    if not isinstance(step_ms, int) or not 10 <= step_ms <= 500:
        raise ValueError("Scroll step must be an integer from 10 to 500 ms")
    if not isinstance(delay_pixels, int) or not 0 <= delay_pixels <= 8:
        raise ValueError("Speech lead-in must be from 0 to 8 pixels")
    # Match firmware text_columns: 2-pixel spaces, 8-pixel other glyphs.
    steps = sum(2 if character == " " else 8 for character in " " + text + " ")
    scroll_seconds = steps * step_ms / 1000
    delay_seconds = delay_pixels * step_ms / 1000
    return steps, scroll_seconds, delay_seconds, max(scroll_seconds, audio_seconds + delay_seconds)
