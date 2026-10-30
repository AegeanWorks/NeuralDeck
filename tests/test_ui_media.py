import importlib.util
import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@unittest.skipUnless(importlib.util.find_spec("ttkbootstrap"), "ttkbootstrap is not installed")
class TestPodcastChooserShortcuts(unittest.TestCase):
    def test_single_episode_is_returned_without_opening_a_dialog(self):
        from transcript_sources import PodcastFeed, PodcastTranscriptRef
        from ui import choose_podcast_episode

        ref = PodcastTranscriptRef(
            feed_title="Show",
            episode_title="Only episode",
            transcript_url="https://example.com/one.vtt",
            transcript_type="text/vtt",
            language="en",
            episode_url="https://example.com/one",
        )
        feed = PodcastFeed(title="Show", feed_url="https://example.com/feed", episodes=(ref,))
        self.assertIs(choose_podcast_episode(None, feed), ref)

    def test_empty_feed_returns_none(self):
        from transcript_sources import PodcastFeed
        from ui import choose_podcast_episode

        feed = PodcastFeed(title="Empty", feed_url="https://example.com/feed", episodes=())
        self.assertIsNone(choose_podcast_episode(None, feed))


if __name__ == "__main__":
    unittest.main()
