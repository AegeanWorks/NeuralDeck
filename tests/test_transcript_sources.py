import os
import sys
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import transcript_sources
from transcript_sources import (
    ApplePodcastSource,
    TranscriptError,
    extract_apple_podcast_ids,
    extract_youtube_video_id,
    fetch_podcast_feed,
    fetch_podcast_transcript,
    fetch_podcast_transcript_for_ref,
    fetch_transcript_from_url,
    fetch_youtube_transcript,
    language_codes,
    parse_podcast_feed,
    parse_podcast_feed_data,
    resolve_apple_podcast_url,
)


VTT = """WEBVTT

00:00:00.000 --> 00:00:03.000
Podcast transcripts become flashcards.
"""

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Learning Lab</title>
    <item>
      <title>Episode 2: Memory</title>
      <link>https://example.com/episodes/2</link>
      <guid>https://example.com/episodes/2</guid>
      <enclosure url="https://example.com/episodes/2.mp3" type="audio/mpeg"/>
      <podcast:transcript url="https://example.com/episodes/2.vtt" type="text/vtt" language="en"/>
    </item>
    <item>
      <title>Episode 1: Sleep</title>
      <link>https://example.com/episodes/1</link>
      <guid>https://example.com/episodes/1</guid>
      <podcast:transcript url="https://example.com/episodes/1.json" type="application/json" language="tr"/>
    </item>
  </channel>
</rss>
"""


def _fake_youtube_api(transcript_list):
    class FakeApi:
        def list(self, video_id):
            return transcript_list

    return FakeApi


class _FakeTranscript:
    language = "English"

    def __init__(self, text):
        self.text = text

    def fetch(self):
        snippet = MagicMock()
        snippet.text = self.text
        return [snippet]


class _FakeTranscriptList:
    def __init__(self, transcript=None, error=None):
        self.transcript = transcript
        self.error = error

    def find_transcript(self, codes):
        if self.error:
            raise self.error
        return self.transcript

    def __iter__(self):
        return iter([self.transcript] if self.transcript else [])


class TestYouTubeIds(unittest.TestCase):
    def test_accepts_common_youtube_urls_and_bare_ids(self):
        expected = "dQw4w9WgXcQ"
        values = [
            "dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?app=desktop&v=dQw4w9WgXcQ&t=30",
            "https://youtu.be/dQw4w9WgXcQ?si=abc",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube.com/live/dQw4w9WgXcQ",
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(extract_youtube_video_id(value), expected)

    def test_rejects_channels_playlists_and_other_sites(self):
        for value in (
            "https://www.youtube.com/@somechannel",
            "https://www.youtube.com/playlist?list=PL123",
            "https://example.com/watch?v=dQw4w9WgXcQ",
            "",
        ):
            with self.subTest(value=value):
                self.assertIsNone(extract_youtube_video_id(value))

    def test_language_codes_map_names_and_keep_english_fallback(self):
        self.assertEqual(language_codes("Turkish"), ["tr", "en"])
        self.assertEqual(language_codes("English"), ["en"])
        self.assertEqual(language_codes("Klingon"), ["en"])


class TestYouTubeTranscript(unittest.TestCase):
    def test_fetches_the_requested_track_and_uses_oembed_metadata(self):
        fake_list = _FakeTranscriptList(transcript=_FakeTranscript("Hello from captions."))
        with patch.object(
            transcript_sources,
            "_load_youtube_transcript_api",
            return_value=(_fake_youtube_api(fake_list), RuntimeError),
        ), patch.object(
            transcript_sources,
            "_youtube_metadata",
            return_value={"title": "Memory and Sleep", "author_name": "Neuro Channel"},
        ):
            result = fetch_youtube_transcript("dQw4w9WgXcQ", language="Turkish")

        self.assertEqual(result.kind, "youtube")
        self.assertEqual(result.text, "Hello from captions.")
        self.assertEqual(result.title, "Memory and Sleep — Neuro Channel")
        self.assertEqual(result.source_url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_oembed_failure_is_ignored(self):
        with patch.object(transcript_sources, "_fetch_json", side_effect=TranscriptError("offline")):
            self.assertEqual(transcript_sources._youtube_metadata("dQw4w9WgXcQ"), {})

    def test_oembed_uses_a_short_bounded_request(self):
        with patch.object(transcript_sources, "_fetch_json", return_value={}) as fetch:
            transcript_sources._youtube_metadata("dQw4w9WgXcQ")
        self.assertEqual(fetch.call_args.kwargs["timeout"], 5)
        self.assertEqual(fetch.call_args.kwargs["max_bytes"], 256 * 1024)

    def test_youtube_metadata_failure_falls_back_to_the_video_id(self):
        fake_list = _FakeTranscriptList(transcript=_FakeTranscript("Hello from captions."))
        with patch.object(
            transcript_sources,
            "_load_youtube_transcript_api",
            return_value=(_fake_youtube_api(fake_list), RuntimeError),
        ), patch.object(transcript_sources, "_youtube_metadata", return_value={}):
            result = fetch_youtube_transcript("dQw4w9WgXcQ")

        self.assertEqual(result.title, "YouTube video dQw4w9WgXcQ")

    def test_falls_back_to_any_available_track(self):
        class NoTranscriptFound(Exception):
            pass

        fake_list = _FakeTranscriptList(
            transcript=_FakeTranscript("Fallback captions."),
            error=NoTranscriptFound("missing tr"),
        )
        with patch.object(
            transcript_sources,
            "_load_youtube_transcript_api",
            return_value=(_fake_youtube_api(fake_list), NoTranscriptFound),
        ), patch.object(transcript_sources, "_youtube_metadata", return_value={}):
            result = fetch_youtube_transcript("dQw4w9WgXcQ", language="Turkish")
        self.assertEqual(result.text, "Fallback captions.")

    def test_disabled_captions_get_an_actionable_error(self):
        TranscriptsDisabled = type("TranscriptsDisabled", (Exception,), {})
        fake_list = _FakeTranscriptList(error=TranscriptsDisabled("off"))
        with patch.object(
            transcript_sources,
            "_load_youtube_transcript_api",
            return_value=(_fake_youtube_api(fake_list), TranscriptsDisabled),
        ):
            with self.assertRaises(TranscriptError) as raised:
                fetch_youtube_transcript("dQw4w9WgXcQ")

        message = str(raised.exception)
        self.assertIn("disabled captions", message)
        self.assertIn("Why:", message)
        self.assertIn("Fix:", message)

    def test_missing_library_reports_the_install_command(self):
        with patch.dict(sys.modules, {"youtube_transcript_api": None}):
            with self.assertRaises(TranscriptError) as raised:
                fetch_youtube_transcript("dQw4w9WgXcQ")
        self.assertIn("pip install -r requirements.txt", str(raised.exception))

    def test_channel_url_is_rejected_before_network_access(self):
        with self.assertRaises(TranscriptError) as raised:
            fetch_youtube_transcript("https://www.youtube.com/@somechannel")
        self.assertIn("single video", str(raised.exception))


class TestPodcastFeed(unittest.TestCase):
    def test_finds_the_newest_episode_with_a_transcript(self):
        ref = parse_podcast_feed(FEED)
        self.assertEqual(ref.feed_title, "Learning Lab")
        self.assertEqual(ref.episode_title, "Episode 2: Memory")
        self.assertEqual(ref.transcript_url, "https://example.com/episodes/2.vtt")
        self.assertEqual(ref.transcript_type, "text/vtt")

    def test_prefers_the_requested_language(self):
        ref = parse_podcast_feed(FEED, language="Turkish")
        self.assertEqual(ref.episode_title, "Episode 1: Sleep")
        self.assertEqual(ref.language, "tr")

    def test_matches_an_explicit_episode_url(self):
        ref = parse_podcast_feed(FEED, episode_url="https://example.com/episodes/1/")
        self.assertEqual(ref.episode_title, "Episode 1: Sleep")

    def test_unknown_episode_url_is_reported(self):
        with self.assertRaises(TranscriptError) as raised:
            parse_podcast_feed(FEED, episode_url="https://example.com/episodes/99")
        self.assertIn("no transcript", str(raised.exception))

    def test_feed_data_lists_every_transcribed_episode_in_order(self):
        feed = parse_podcast_feed_data(FEED, feed_url="https://example.com/feed.xml")
        self.assertEqual(feed.title, "Learning Lab")
        self.assertEqual(feed.feed_url, "https://example.com/feed.xml")
        self.assertEqual(len(feed.episodes), 2)
        self.assertEqual(
            [episode.episode_title for episode in feed.episodes],
            ["Episode 2: Memory", "Episode 1: Sleep"],
        )
        self.assertEqual(feed.episodes[0].episode_url, "https://example.com/episodes/2")
        self.assertIn("https://example.com/episodes/2", feed.episodes[0].episode_urls)

    def test_episodes_without_transcripts_are_omitted_from_the_browser(self):
        feed_xml = """<rss xmlns:podcast="https://podcastindex.org/namespace/1.0">
          <channel><title>Mixed Show</title>
            <item><title>No transcript</title><link>https://example.com/0</link></item>
            <item><title>Transcribed</title><link>https://example.com/1</link>
              <podcast:transcript url="https://example.com/1.vtt" type="text/vtt" language="en"/>
            </item>
          </channel></rss>"""
        feed = parse_podcast_feed_data(feed_xml)
        self.assertEqual([episode.episode_title for episode in feed.episodes], ["Transcribed"])

    def test_fetch_podcast_feed_downloads_the_feed_once(self):
        with patch.object(
            transcript_sources,
            "_fetch_url_bytes",
            return_value=(FEED.encode("utf-8"), "application/rss+xml", "utf-8"),
        ) as mocked:
            feed = fetch_podcast_feed("https://example.com/feed.xml")
        self.assertEqual(len(feed.episodes), 2)
        mocked.assert_called_once()

    def test_fetch_podcast_transcript_for_ref_downloads_only_the_transcript(self):
        ref = parse_podcast_feed(FEED)
        with patch.object(
            transcript_sources,
            "_fetch_url_bytes",
            return_value=(VTT.encode("utf-8"), "text/vtt", "utf-8"),
        ) as mocked:
            result = fetch_podcast_transcript_for_ref(ref)
        self.assertEqual(result.kind, "podcast")
        self.assertEqual(result.title, "Learning Lab: Episode 2: Memory")
        self.assertIn("become flashcards", result.text)
        mocked.assert_called_once_with(ref.transcript_url)

    def test_feed_without_transcript_tags_is_reported(self):
        feed = "<rss><channel><title>No Transcripts</title><item><title>One</title></item></channel></rss>"
        with self.assertRaises(TranscriptError) as raised:
            parse_podcast_feed(feed)
        self.assertIn("No Podcasting 2.0 transcript", str(raised.exception))
        self.assertIn("requirements-transcription.txt", str(raised.exception))

    def test_invalid_xml_is_reported(self):
        with self.assertRaises(TranscriptError) as raised:
            parse_podcast_feed("<rss><channel>")
        self.assertIn("could not be parsed", str(raised.exception))

    def test_fetch_podcast_transcript_downloads_feed_and_cue_file(self):
        responses = [
            (FEED.encode("utf-8"), "application/rss+xml", "utf-8"),
            (VTT.encode("utf-8"), "text/vtt", "utf-8"),
        ]
        with patch.object(transcript_sources, "_fetch_url_bytes", side_effect=responses):
            result = fetch_podcast_transcript("https://example.com/feed.xml")

        self.assertEqual(result.kind, "podcast")
        self.assertEqual(result.title, "Learning Lab: Episode 2: Memory")
        self.assertIn("Podcast transcripts become flashcards.", result.text)


class TestApplePodcasts(unittest.TestCase):
    def test_show_and_episode_urls_are_recognized(self):
        self.assertEqual(
            extract_apple_podcast_ids(
                "https://podcasts.apple.com/us/podcast/podcasting-2-0/id1584274529"
            ),
            ("1584274529", ""),
        )
        self.assertEqual(
            extract_apple_podcast_ids(
                "https://podcasts.apple.com/us/podcast/podcasting-2-0/id1584274529?i=1000797833454"
            ),
            ("1584274529", "1000797833454"),
        )
        self.assertEqual(
            extract_apple_podcast_ids(
                "itunes.apple.com/us/podcast/show/id123?i=456"
            ),
            ("123", "456"),
        )
        self.assertIsNone(extract_apple_podcast_ids("https://example.com/podcast/id123"))
        self.assertIsNone(extract_apple_podcast_ids("https://podcasts.apple.com/us/podcast/show"))

    def test_resolve_show_url_uses_the_itunes_feed(self):
        with patch.object(
            transcript_sources,
            "_fetch_json",
            return_value={"results": [{"feedUrl": "https://example.com/feed.xml"}]},
        ) as lookup:
            source = resolve_apple_podcast_url(
                "https://podcasts.apple.com/us/podcast/show/id1584274529"
            )
        self.assertEqual(source.feed_url, "https://example.com/feed.xml")
        self.assertEqual(source.collection_id, "1584274529")
        self.assertEqual(source.episode_id, "")
        self.assertEqual(source.episode_title, "")
        lookup.assert_called_once()

    def test_resolve_episode_url_reads_the_page_title(self):
        with patch.object(
            transcript_sources,
            "_fetch_json",
            return_value={"results": [{"feedUrl": "https://example.com/feed.xml"}]},
        ), patch.object(
            transcript_sources,
            "_apple_page_title",
            return_value='Episode 276: "Jackleg leechers"',
        ):
            source = resolve_apple_podcast_url(
                "https://podcasts.apple.com/us/podcast/show/id1584274529?i=1000797833454"
            )
        self.assertEqual(source.episode_id, "1000797833454")
        self.assertEqual(source.episode_title, 'Episode 276: "Jackleg leechers"')

    def test_apple_page_title_reads_open_graph_metadata(self):
        page = '<html><head><meta property="og:title" content="Episode 1: &quot;Sleep&quot;"></head></html>'
        with patch.object(
            transcript_sources,
            "_fetch_url_bytes",
            return_value=(page.encode("utf-8"), "text/html", "utf-8"),
        ):
            title = transcript_sources._apple_page_title("https://podcasts.apple.com/episode")
        self.assertEqual(title, 'Episode 1: "Sleep"')

    def test_apple_show_url_uses_the_newest_transcribed_episode(self):
        source = ApplePodcastSource("1584274529", "", "https://example.com/feed.xml", "", "https://apple")
        feed = parse_podcast_feed_data(FEED)
        expected = transcript_sources.TranscriptResult("text", "title", "url", "podcast")
        with patch.object(transcript_sources, "resolve_apple_podcast_url", return_value=source), \
             patch.object(transcript_sources, "fetch_podcast_feed", return_value=feed), \
             patch.object(transcript_sources, "fetch_podcast_transcript_for_ref", return_value=expected) as fetch:
            result = fetch_transcript_from_url("https://podcasts.apple.com/us/podcast/show/id1584274529")
        self.assertIs(result, expected)
        self.assertEqual(fetch.call_args.args[0].episode_title, "Episode 2: Memory")

    def test_apple_episode_url_matches_the_transcript_by_title(self):
        source = ApplePodcastSource(
            "1584274529", "1000797833454", "https://example.com/feed.xml",
            "Episode 1: Sleep", "https://apple",
        )
        feed = parse_podcast_feed_data(FEED)
        expected = transcript_sources.TranscriptResult("text", "title", "url", "podcast")
        with patch.object(transcript_sources, "resolve_apple_podcast_url", return_value=source), \
             patch.object(transcript_sources, "fetch_podcast_feed", return_value=feed), \
             patch.object(transcript_sources, "fetch_podcast_transcript_for_ref", return_value=expected) as fetch:
            fetch_transcript_from_url("https://podcasts.apple.com/us/podcast/show/id1584274529?i=1000797833454")
        self.assertEqual(fetch.call_args.args[0].episode_title, "Episode 1: Sleep")

    def test_short_episode_numbers_do_not_match_by_prefix(self):
        feed = parse_podcast_feed_data(FEED)
        self.assertIsNone(transcript_sources._find_episode_by_title(feed, "Episode 1"))
        self.assertIsNone(transcript_sources._find_episode_by_title(feed, "Episode"))
        self.assertEqual(
            transcript_sources._find_episode_by_title(feed, "Episode 1: Sleep").episode_title,
            "Episode 1: Sleep",
        )

    def test_apple_episode_without_a_transcript_is_reported(self):
        source = ApplePodcastSource(
            "1584274529", "1000797833454", "https://example.com/feed.xml",
            "Untranscribed episode", "https://apple",
        )
        feed = parse_podcast_feed_data(FEED)
        with patch.object(transcript_sources, "resolve_apple_podcast_url", return_value=source), \
             patch.object(transcript_sources, "fetch_podcast_feed", return_value=feed):
            with self.assertRaises(TranscriptError) as raised:
                fetch_transcript_from_url("https://podcasts.apple.com/us/podcast/show/id1584274529?i=1")
        self.assertIn("no published transcript", str(raised.exception))

    def test_apple_episode_without_a_title_is_reported(self):
        source = ApplePodcastSource(
            "1584274529", "1000797833454", "https://example.com/feed.xml", "", "https://apple",
        )
        feed = parse_podcast_feed_data(FEED)
        with patch.object(transcript_sources, "resolve_apple_podcast_url", return_value=source), \
             patch.object(transcript_sources, "fetch_podcast_feed", return_value=feed):
            with self.assertRaises(TranscriptError) as raised:
                fetch_transcript_from_url("https://podcasts.apple.com/us/podcast/show/id1584274529?i=1")
        self.assertIn("Could not identify", str(raised.exception))

    def test_fetch_podcast_feed_resolves_an_apple_show_url(self):
        source = ApplePodcastSource("1584274529", "", "https://example.com/feed.xml", "", "https://apple")
        with patch.object(transcript_sources, "resolve_apple_podcast_url", return_value=source), \
             patch.object(
                 transcript_sources,
                 "_fetch_url_bytes",
                 return_value=(FEED.encode("utf-8"), "application/rss+xml", "utf-8"),
             ) as fetch:
            feed = fetch_podcast_feed("https://podcasts.apple.com/us/podcast/show/id1584274529")
        self.assertEqual(feed.feed_url, "https://example.com/feed.xml")
        fetch.assert_called_once_with("https://example.com/feed.xml")


class TestDirectTranscriptUrls(unittest.TestCase):
    def test_direct_vtt_url_is_parsed(self):
        with patch.object(
            transcript_sources,
            "_fetch_url_bytes",
            return_value=(VTT.encode("utf-8"), "text/vtt", "utf-8"),
        ):
            result = fetch_transcript_from_url("https://example.com/captions.vtt")
        self.assertEqual(result.kind, "web")
        self.assertEqual(result.title, "captions.vtt")
        self.assertIn("become flashcards", result.text)

    def test_rss_url_is_detected_from_content_type(self):
        responses = [
            (FEED.encode("utf-8"), "application/rss+xml", "utf-8"),
            (VTT.encode("utf-8"), "text/vtt", "utf-8"),
        ]
        with patch.object(transcript_sources, "_fetch_url_bytes", side_effect=responses):
            result = fetch_transcript_from_url("https://example.com/feed")
        self.assertEqual(result.kind, "podcast")

    def test_youtube_url_is_dispatched_without_downloading_a_page(self):
        expected = transcript_sources.TranscriptResult("text", "YouTube", "url", "youtube")
        with patch.object(transcript_sources, "fetch_youtube_transcript", return_value=expected) as mocked:
            result = fetch_transcript_from_url("https://youtu.be/dQw4w9WgXcQ", language="Turkish")
        self.assertIs(result, expected)
        mocked.assert_called_once()

    def test_pdf_url_is_extracted_with_pypdf2(self):
        with patch.object(
            transcript_sources,
            "_fetch_url_bytes",
            return_value=(b"%PDF-1.7 fake", "application/pdf", "utf-8"),
        ), patch(
            "document_processor.extract_text_from_pdf_bytes",
            return_value="Extracted PDF study text.",
        ):
            result = fetch_transcript_from_url("https://example.com/paper.pdf")
        self.assertEqual(result.kind, "pdf")
        self.assertEqual(result.title, "paper.pdf")
        self.assertIn("PDF study text", result.text)

    def test_pdf_is_detected_from_magic_bytes(self):
        with patch.object(
            transcript_sources,
            "_fetch_url_bytes",
            return_value=(b"%PDF-1.7 fake", "application/octet-stream", "utf-8"),
        ), patch(
            "document_processor.extract_text_from_pdf_bytes",
            return_value="Extracted PDF study text.",
        ):
            result = fetch_transcript_from_url("https://example.com/download")
        self.assertEqual(result.kind, "pdf")

    def test_website_url_extracts_the_article_not_the_navigation(self):
        page = """<html><head><title>Memory and Sleep</title></head><body>
          <nav>Home About Contact</nav>
          <article><p>Sleep stabilizes new memories and improves next-day recall.</p>
          <p>Deep sleep supports declarative memory consolidation in particular.</p></article>
          <footer>Copyright Example</footer></body></html>"""
        with patch.object(
            transcript_sources,
            "_fetch_url_bytes",
            return_value=(page.encode("utf-8"), "text/html", "utf-8"),
        ):
            result = fetch_transcript_from_url("https://example.com/article")
        self.assertEqual(result.kind, "web")
        self.assertEqual(result.title, "Memory and Sleep")
        self.assertIn("Sleep stabilizes", result.text)
        self.assertNotIn("Home About", result.text)

    def test_website_without_readable_text_is_reported(self):
        page = "<html><body><script>onlyApp()</script></body></html>"
        with patch.object(
            transcript_sources,
            "_fetch_url_bytes",
            return_value=(page.encode("utf-8"), "text/html", "utf-8"),
        ):
            with self.assertRaises(TranscriptError) as raised:
                fetch_transcript_from_url("https://example.com/empty")
        self.assertIn("readable article text", str(raised.exception))

    def test_audio_url_is_rejected_with_a_local_path_suggestion(self):
        with patch.object(
            transcript_sources,
            "_fetch_url_bytes",
            return_value=(b"ID3", "audio/mpeg", "utf-8"),
        ):
            with self.assertRaises(TranscriptError) as raised:
                fetch_transcript_from_url("https://example.com/episode.mp3")
        self.assertIn("local transcription", str(raised.exception))

    def test_empty_url_is_rejected(self):
        with self.assertRaises(TranscriptError):
            fetch_transcript_from_url("  ")

    def test_http_error_is_wrapped(self):
        error = urllib.error.HTTPError(
            "https://example.com/feed", 404, "Not Found", {}, None
        )
        with patch.object(transcript_sources.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(TranscriptError) as raised:
                fetch_transcript_from_url("https://example.com/feed")
        self.assertIn("HTTP 404", str(raised.exception))

    def test_oversized_download_is_refused(self):
        headers = MagicMock()
        headers.get.return_value = "text/plain"
        headers.get_content_charset.return_value = "utf-8"
        response = MagicMock()
        response.read.return_value = b"123456789"
        response.headers = headers
        response.__enter__.return_value = response
        response.__exit__.return_value = None

        with patch.object(transcript_sources.urllib.request, "urlopen", return_value=response):
            with self.assertRaises(TranscriptError) as raised:
                transcript_sources._fetch_url_bytes("https://example.com/feed", max_bytes=4)
        self.assertIn("larger than", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
