import os
import sys
import tempfile
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from transcript_formats import (
    clean_transcript_text,
    parse_podcast_json,
    parse_srt,
    parse_transcript,
    parse_vtt,
    read_transcript_file,
)


VTT_SAMPLE = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.500 align:start position:0%
Hello and welcome to the show.

00:00:02.500 --> 00:00:05.000
Today we discuss <c.colored>memory</c> and sleep.
"""

SRT_SAMPLE = """1
00:00:00,000 --> 00:00:02,500
Hello and welcome to the show.

2
00:00:02,500 --> 00:00:05,000
Today we discuss memory and sleep.
"""


class TestTranscriptFormats(unittest.TestCase):
    def test_parse_vtt_strips_headers_timings_and_tags(self):
        text = parse_vtt(VTT_SAMPLE)
        self.assertIn("Hello and welcome to the show.", text)
        self.assertIn("Today we discuss memory and sleep.", text)
        self.assertNotIn("WEBVTT", text)
        self.assertNotIn("-->", text)
        self.assertNotIn("<c.", text)

    def test_parse_srt_strips_cue_numbers(self):
        text = parse_srt(SRT_SAMPLE)
        self.assertEqual(
            text,
            "Hello and welcome to the show. Today we discuss memory and sleep.",
        )
        self.assertNotIn("00:00:00", text)

    def test_parse_podcast_json_segments(self):
        payload = """
        {"version": "1.0.0", "segments": [
            {"startTime": 0, "text": "First point."},
            {"startTime": 2, "text": "Second point."}
        ]}
        """
        self.assertEqual(parse_podcast_json(payload), "First point. Second point.")

    def test_parse_podcast_json_accepts_a_plain_text_field(self):
        self.assertEqual(parse_podcast_json('{"text": "One block."}'), "One block.")

    def test_parse_podcast_json_accepts_a_string_transcript_field(self):
        self.assertEqual(parse_podcast_json('{"transcript": "One block."}'), "One block.")

    def test_parse_podcast_json_rejects_empty_segments(self):
        with self.assertRaises(ValueError):
            parse_podcast_json('{"segments": []}')

    def test_clean_transcript_removes_rolling_duplicates(self):
        text = clean_transcript_text("hello everyone\nhello everyone welcome\nwelcome to the show")
        self.assertEqual(text, "hello everyone welcome to the show")

    def test_clean_transcript_removes_timestamp_prefixes(self):
        text = clean_transcript_text("[00:12:34] The main idea.\n(00:12:40) A detail.")
        self.assertEqual(text, "The main idea. A detail.")

    def test_plain_text_is_normalized(self):
        text = parse_transcript("  Line one.\n\n  Line two.  ")
        self.assertEqual(text, "Line one. Line two.")

    def test_html_transcript_is_rendered_as_text(self):
        html = "<html><body><nav>Menu</nav><p>Real content.</p><script>ignore()</script></body></html>"
        text = parse_transcript(html)
        self.assertIn("Real content.", text)
        self.assertNotIn("ignore()", text)

    def test_format_is_sniffed_without_a_hint(self):
        self.assertIn("Hello and welcome", parse_transcript(VTT_SAMPLE))
        self.assertIn("Hello and welcome", parse_transcript(SRT_SAMPLE))

    def test_empty_transcript_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_transcript("   \n\n ")

    def test_read_transcript_file_uses_its_extension_hint(self):
        with tempfile.NamedTemporaryFile("w", suffix=".vtt", delete=False, encoding="utf-8") as handle:
            handle.write(VTT_SAMPLE)
            path = handle.name
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

        self.assertIn("Hello and welcome", read_transcript_file(path))


if __name__ == "__main__":
    unittest.main()
