"""Readable article extraction from HTML pages.

The app already depends on lxml, so this module uses it to drop navigation,
scripts, cookie banners and other boilerplate, then keeps the main article
paragraphs. It is pure: callers fetch the page.
"""

import html
import re
import urllib.parse
from dataclasses import dataclass

try:
    from lxml import etree
    from lxml import html as lxml_html
except ImportError:  # pragma: no cover - lxml is a declared requirement
    etree = None
    lxml_html = None

_DROP_TAGS = ("script", "style", "noscript", "svg", "iframe", "form", "button", "nav", "header", "footer", "aside")
_DROP_MARKERS = re.compile(
    r"(?:^|[\s_-])(?:nav|navigation|menu|sidebar|footer|header|comment|comments|share|social|"
    r"related|cookie|cookies|banner|advert|advertisement|promo|newsletter|breadcrumb|modal|"
    r"popup|subscribe|signup|login|search|portlet|toc|mw-editsection|catlinks|printfooter|"
    r"mw-jump-link|noprint|sistersitebox|navbox|ambox|hatnote|vector-menu|vector-dropdown|"
    r"vector-toc|vector-page-toolbar|vector-main-menu|vector-pinned|vector-pinnable|"
    r"vector-sticky-header|vector-search|vector-appearance|vector-language|vector-user-menu|"
    r"vector-tab|vector-page-titlebar)(?:$|[\s_-])",
    re.IGNORECASE,
)
_CONTENT_SELECTORS = (
    "//article",
    "//main",
    "//*[@role='main']",
    "//*[@id='mw-content-text']",
    "//*[@id='main-content']",
    "//*[@id='content']",
    "//*[contains(@class,'article-body')]",
    "//*[contains(@class,'post-content')]",
    "//*[contains(@class,'entry-content')]",
    "//*[contains(@class,'story-body')]",
)
_BLOCK_XPATH = ".//p | .//li | .//blockquote | .//h1 | .//h2 | .//h3 | .//h4 | .//pre"
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class WebArticle:
    title: str
    text: str


def _normalize(value):
    return _SPACES.sub(" ", html.unescape(value or "")).strip()


def _drop_boilerplate(document):
    for node in document.xpath("//" + " | //".join(_DROP_TAGS)):
        if node.getparent() is not None:
            node.drop_tree()
    for node in document.xpath("//*[@class or @id]"):
        if node.getparent() is None or node.tag in ("html", "body"):
            continue
        marker = f"{node.get('class', '')} {node.get('id', '')}"
        if _DROP_MARKERS.search(marker):
            node.drop_tree()


def _page_title(document):
    for expression in (
        "//meta[@property='og:title']/@content",
        "//meta[@name='twitter:title']/@content",
        "//title/text()",
    ):
        values = document.xpath(expression)
        if values:
            title = _normalize(values[0])
            if title:
                return title
    return ""


def _candidate_root(document):
    candidates = []
    for selector in _CONTENT_SELECTORS:
        for node in document.xpath(selector):
            if len(_normalize(node.text_content())) >= 200 and node not in candidates:
                candidates.append(node)
    if candidates:
        return max(candidates, key=lambda node: len(_normalize(node.text_content())))
    return document.body if document.body is not None else document


def _paragraphs(root):
    nodes = root.xpath(_BLOCK_XPATH)
    if not nodes:
        nodes = [root]
    paragraphs = []
    for node in nodes:
        text = _normalize(node.text_content())
        if len(text) < 25:
            continue
        if paragraphs and text == paragraphs[-1]:
            continue
        paragraphs.append(text)
    return paragraphs


def _fallback_title(url):
    path = urllib.parse.urlparse(url).path.rstrip("/")
    if not path:
        return urllib.parse.urlparse(url).netloc
    slug = urllib.parse.unquote(path.rsplit("/", 1)[-1])
    return _normalize(slug.replace("-", " ").replace("_", " ")) or urllib.parse.urlparse(url).netloc


def extract_article(html_text, url=""):
    """Return the readable title and body text of an HTML page."""
    if lxml_html is None:
        raise ImportError("lxml is required for website extraction. Run 'pip install -r requirements.txt'.")
    if not html_text or not html_text.strip():
        raise ValueError("The page is empty.")

    try:
        document = lxml_html.fromstring(html_text)
    except (etree.ParserError, ValueError) as exc:
        raise ValueError(f"The page HTML could not be parsed: {exc}") from exc

    title = _page_title(document) or _fallback_title(url)
    _drop_boilerplate(document)
    root = _candidate_root(document)
    paragraphs = _paragraphs(root)

    if len(" ".join(paragraphs)) < 80:
        paragraphs = [_normalize(root.text_content())]
    text = "\n\n".join(paragraph for paragraph in paragraphs if paragraph)
    if len(text) < 80:
        raise ValueError("No readable article text was found on this page.")
    return WebArticle(title=title, text=text)
