import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import web_extraction
from web_extraction import extract_article


PAGE = """<!doctype html>
<html><head>
  <title>Fallback title | Example</title>
  <meta property="og:title" content="Memory, Sleep and Learning">
</head><body>
  <header><a href="/">Home</a><a href="/about">About</a></header>
  <nav><a href="/one">One</a><a href="/two">Two</a></nav>
  <div class="cookie-banner">We use cookies. Accept?</div>
  <article>
    <h1>Memory, Sleep and Learning</h1>
    <p>Sleep stabilizes new memories and makes them easier to retrieve the next day.</p>
    <p>Deep sleep in particular is associated with the consolidation of declarative memory.</p>
    <div class="newsletter-signup"><p>Subscribe to our newsletter for more articles.</p></div>
    <aside><p>Related: ten other articles you might like.</p></aside>
  </article>
  <footer>Copyright Example</footer>
  <script>window.analytics = true;</script>
</body></html>"""


class TestArticleExtraction(unittest.TestCase):
    def test_extracts_the_article_and_drops_boilerplate(self):
        article = extract_article(PAGE, url="https://example.com/memory-sleep")
        self.assertEqual(article.title, "Memory, Sleep and Learning")
        self.assertIn("Sleep stabilizes new memories", article.text)
        self.assertIn("Deep sleep in particular", article.text)
        for noise in ("Home", "About", "cookies", "newsletter", "Related:", "Copyright", "analytics"):
            self.assertNotIn(noise, article.text)

    def test_uses_main_when_there_is_no_article(self):
        page = """<html><head><title>Main page</title></head><body>
          <nav>Navigation</nav>
          <main><p>This is the main readable paragraph with enough detail to survive extraction.</p>
          <p>A second paragraph adds more context for the reader and the card generator.</p></main>
          <footer>Footer</footer></body></html>"""
        article = extract_article(page)
        self.assertIn("main readable paragraph", article.text)
        self.assertNotIn("Navigation", article.text)

    def test_falls_back_to_body_paragraphs(self):
        page = """<html><head><title>Simple page</title></head><body>
          <p>First body paragraph with enough words to be considered readable content.</p>
          <p>Second body paragraph with additional context for the extraction fallback.</p>
        </body></html>"""
        article = extract_article(page, url="https://example.com/simple")
        self.assertEqual(article.title, "Simple page")
        self.assertIn("First body paragraph", article.text)

    def test_title_falls_back_to_the_url_slug(self):
        page = "<html><body><p>" + ("Readable body text. " * 20) + "</p></body></html>"
        article = extract_article(page, url="https://example.com/my-useful-article")
        self.assertEqual(article.title, "my useful article")

    def test_wiki_style_vector_wrappers_are_removed(self):
        page = """<html class="vector-feature-page-tools"><body class="vector-feature-main-menu">
          <div class="vector-menu">Main menu and language links</div>
          <main><p>This is the real article paragraph with enough words to be extracted cleanly.</p>
          <p>A second paragraph keeps the candidate root above the readability threshold.</p></main>
        </body></html>"""
        article = extract_article(page)
        self.assertIn("real article paragraph", article.text)
        self.assertNotIn("Main menu", article.text)

    def test_rejects_empty_html(self):
        with self.assertRaises(ValueError):
            extract_article("   ")

    def test_reports_missing_lxml(self):
        with patch.object(web_extraction, "lxml_html", None):
            with self.assertRaises(ImportError) as raised:
                extract_article("<html><body><p>" + ("Text " * 40) + "</p></body></html>")
        self.assertIn("requirements.txt", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
