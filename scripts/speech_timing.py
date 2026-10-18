"""Change speech speed in memory while preserving pitch."""


def slow_speech(audio, rate):
    if not 0.5 <= rate <= 1.25:
        raise ValueError("Speech rate must be from 0.5 to 1.25")
    if rate == 1:
        return audio
    import librosa
    return librosa.effects.time_stretch(audio, rate=rate, n_fft=1024, hop_length=256)
