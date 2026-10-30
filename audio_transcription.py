"""Optional local podcast/video transcription through faster-whisper.

Audio is decoded and transcribed on the local machine. The model is downloaded
on first use, then cached by faster-whisper. The base application works without
this optional dependency; only audio files need it.
"""

import os

SUPPORTED_AUDIO_EXTENSIONS = {
    ".mp3", ".m4a", ".wav", ".ogg", ".oga", ".flac", ".aac", ".wma",
    ".mp4", ".mkv", ".webm", ".mov",
}


class AudioTranscriptionError(Exception):
    """A user-facing local transcription failure with a Why/Fix message."""


def is_audio_file(file_path):
    """Return True when the path has a supported audio/video extension."""
    extension = os.path.splitext(os.fspath(file_path))[1].lower()
    return extension in SUPPORTED_AUDIO_EXTENSIONS


def transcribe_audio(file_path, model_size="base", log_callback=None, stop_callback=None):
    """Transcribe a local audio/video file and return plain text."""
    path = os.fspath(file_path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Audio file not found: {path}")
    if not is_audio_file(path):
        raise ValueError(f"Unsupported audio file type: {os.path.splitext(path)[1]}")

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise AudioTranscriptionError(
            "Local audio transcription is not installed.\n"
            "Why: the optional faster-whisper package is missing.\n"
            "Fix: run `pip install -r requirements-transcription.txt` and restart NeuralDeck, "
            "or select a .vtt/.srt transcript file instead."
        ) from exc

    if log_callback:
        log_callback(
            f"Loading local Whisper model '{model_size}' (the first run downloads it)..."
        )

    try:
        model = WhisperModel(model_size, device="auto", compute_type="int8")
        segments, info = model.transcribe(path, vad_filter=True)
        parts = []
        for segment in segments:
            if stop_callback and stop_callback():
                break
            text = (getattr(segment, "text", "") or "").strip()
            if text:
                parts.append(text)
    except AudioTranscriptionError:
        raise
    except Exception as exc:
        raise AudioTranscriptionError(
            f"Audio transcription failed: {exc}\n"
            "Why: the local Whisper model could not decode or process this file.\n"
            "Fix: check that the file plays locally, try a smaller model or convert it to .wav/.mp3."
        ) from exc

    result = " ".join(parts).strip()
    if not result:
        raise AudioTranscriptionError(
            "No speech was detected in the audio file.\n"
            "Why: the file may be silent, music-only or in an unsupported codec.\n"
            "Fix: try another episode or load a written transcript."
        )

    if log_callback:
        detected = getattr(info, "language", None) or "unknown"
        probability = getattr(info, "language_probability", None)
        suffix = f" ({detected}, {probability:.0%})" if isinstance(probability, float) else f" ({detected})"
        log_callback(f"Transcribed {len(result)} characters locally{suffix}.")
    return result
