import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from audio_transcription import (
    AudioTranscriptionError,
    is_audio_file,
    is_media_file,
    is_video_file,
    transcribe_audio,
)


def _temp_audio(suffix=".mp3"):
    handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    handle.write(b"fake audio")
    handle.close()
    return handle.name


class TestAudioTranscription(unittest.TestCase):
    def test_audio_extensions_are_recognized(self):
        for name in ("episode.mp3", "episode.M4A", "talk.wav", "video.mp4", "clip.webm", "voice.oga"):
            with self.subTest(name=name):
                self.assertTrue(is_audio_file(name))
                self.assertTrue(is_media_file(name))
        self.assertFalse(is_audio_file("document.pdf"))
        self.assertFalse(is_audio_file("transcript.vtt"))
        self.assertFalse(is_media_file("transcript.vtt"))

    def test_video_extensions_are_recognized_separately(self):
        for name in ("lecture.mp4", "clip.M4V", "talk.mkv", "clip.webm", "movie.mov", "old.avi", "talk.mpeg"):
            with self.subTest(name=name):
                self.assertTrue(is_video_file(name))
                self.assertTrue(is_audio_file(name))
        self.assertFalse(is_video_file("episode.mp3"))
        self.assertFalse(is_video_file("transcript.vtt"))

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            transcribe_audio("missing.mp3")

    def test_unsupported_extension_raises(self):
        path = _temp_audio(".pdf")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with self.assertRaises(ValueError):
            transcribe_audio(path)

    def test_missing_faster_whisper_reports_the_optional_requirements_file(self):
        path = _temp_audio()
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with patch.dict(sys.modules, {"faster_whisper": None}):
            with self.assertRaises(AudioTranscriptionError) as raised:
                transcribe_audio(path)
        self.assertIn("requirements-transcription.txt", str(raised.exception))

    def test_transcribes_segments_and_honours_stop_callback(self):
        calls = []

        class FakeSegment:
            def __init__(self, text):
                self.text = text

        class FakeInfo:
            language = "en"
            language_probability = 0.93

        class FakeModel:
            def __init__(self, *args, **kwargs):
                calls.append(("model", args, kwargs))

            def transcribe(self, path, vad_filter=True):
                calls.append(("transcribe", path, vad_filter))
                return iter([FakeSegment("First sentence."), FakeSegment("Second sentence.")]), FakeInfo()

        fake_module = types.ModuleType("faster_whisper")
        fake_module.WhisperModel = FakeModel
        path = _temp_audio()
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

        with patch.dict(sys.modules, {"faster_whisper": fake_module}):
            text = transcribe_audio(path)

        self.assertEqual(text, "First sentence. Second sentence.")
        self.assertEqual(calls[1][1], path)
        self.assertTrue(calls[1][2])

    def test_empty_speech_is_reported(self):
        class FakeSegment:
            text = ""

        class FakeInfo:
            language = "en"
            language_probability = 0.5

        class FakeModel:
            def __init__(self, *args, **kwargs):
                self.arguments = (args, kwargs)

            def transcribe(self, path, vad_filter=True):
                return iter([FakeSegment()]), FakeInfo()

        fake_module = types.ModuleType("faster_whisper")
        fake_module.WhisperModel = FakeModel
        path = _temp_audio()
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

        with patch.dict(sys.modules, {"faster_whisper": fake_module}):
            with self.assertRaises(AudioTranscriptionError) as raised:
                transcribe_audio(path)
        self.assertIn("No speech", str(raised.exception))

    def test_stop_callback_stops_before_a_result(self):
        class FakeSegment:
            def __init__(self, text):
                self.text = text

        class FakeInfo:
            language = "en"
            language_probability = 0.5

        class FakeModel:
            def __init__(self, *args, **kwargs):
                self.arguments = (args, kwargs)

            def transcribe(self, path, vad_filter=True):
                return iter([FakeSegment("Unused.")]), FakeInfo()

        fake_module = types.ModuleType("faster_whisper")
        fake_module.WhisperModel = FakeModel
        path = _temp_audio()
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

        with patch.dict(sys.modules, {"faster_whisper": fake_module}):
            with self.assertRaises(AudioTranscriptionError) as raised:
                transcribe_audio(path, stop_callback=lambda: True)
        self.assertIn("No speech", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
