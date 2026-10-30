"""Fetch card source transcripts from YouTube, podcast feeds and URLs.

Only text is downloaded; audio and video never leave the machine. YouTube
captions use ``youtube-transcript-api`` and podcast shows expose transcripts
through the Podcasting 2.0 ``<podcast:transcript>`` tag.
"""

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from transcript_formats import parse_transcript

MAX_SOURCE_BYTES = 10 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 20
USER_AGENT = "NeuralDeck/0.2 (+https://github.com/Aegean-E/NeuralDeck)"

_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YOUTUBE_HOSTS = {"youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"}
_APPLE_HOSTS = {"podcasts.apple.com", "itunes.apple.com"}
_APPLE_ID = re.compile(r"(?:^|/)id(\d+)")
_LANGUAGE_CODES = {
    "english": "en",
    "turkish": "tr",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "japanese": "ja",
    "chinese": "zh",
}
_TRANSCRIPT_TYPE_ORDER = (
    "text/plain",
    "text/vtt",
    "application/srt",
    "application/json",
    "text/html",
)


class TranscriptError(Exception):
    """A user-facing transcript failure that explains why and how to fix it."""


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    title: str
    source_url: str
    kind: str


@dataclass(frozen=True)
class PodcastTranscriptRef:
    feed_title: str
    episode_title: str
    transcript_url: str
    transcript_type: str
    language: str
    episode_url: str = ""
    episode_urls: tuple = ()


@dataclass(frozen=True)
class PodcastFeed:
    title: str
    feed_url: str
    episodes: tuple


@dataclass(frozen=True)
class ApplePodcastSource:
    collection_id: str
    episode_id: str
    feed_url: str
    episode_title: str
    page_url: str


def language_codes(language):
    """Map a UI language name to the ISO codes YouTube expects."""
    code = _LANGUAGE_CODES.get((language or "").strip().lower())
    return [code, "en"] if code and code != "en" else (["en"] if not code else [code])


def extract_youtube_video_id(value):
    """Return the 11-character video id from a YouTube URL or bare id."""
    value = (value or "").strip()
    if _YOUTUBE_ID.fullmatch(value):
        return value
    if not value:
        return None

    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]

    candidate = None
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
    elif host in _YOUTUBE_HOSTS or host.endswith(".youtube.com"):
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.path.rstrip("/") == "/watch":
            candidate = urllib.parse.parse_qs(parsed.query).get("v", [None])[0]
        elif len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
            candidate = parts[1]

    if candidate and _YOUTUBE_ID.fullmatch(candidate):
        return candidate
    return None


def _is_youtube_url(value):
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host == "youtu.be" or host in _YOUTUBE_HOSTS or host.endswith(".youtube.com")


def _fetch_url_bytes(url, max_bytes=MAX_SOURCE_BYTES, timeout=FETCH_TIMEOUT_SECONDS):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise TranscriptError(
            "The transcript URL is not a valid http(s) address.\n"
            "Why: only web URLs can be imported.\n"
            "Fix: paste a YouTube, podcast RSS or transcript URL that starts with http:// or https://."
        )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xml,text/plain,*/*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(max_bytes + 1)
            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            charset = response.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as exc:
        raise TranscriptError(
            f"The transcript source returned HTTP {exc.code}.\n"
            "Why: the link is private, expired or blocked for this client.\n"
            "Fix: open the link in a browser, then download the transcript file and load it locally."
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TranscriptError(
            f"Could not download the transcript source: {exc}\n"
            "Why: the server is unreachable or the connection timed out.\n"
            "Fix: check your connection and the URL, then try again."
        ) from exc

    if len(data) > max_bytes:
        raise TranscriptError(
            f"The transcript source is larger than {max_bytes // (1024 * 1024)} MB.\n"
            "Why: NeuralDeck bounds downloads to protect memory.\n"
            "Fix: download a smaller transcript or split the source."
        )
    return data, content_type, charset


def _decode(data, charset):
    try:
        return data.decode(charset or "utf-8", errors="replace")
    except LookupError:
        return data.decode("utf-8", errors="replace")


def extract_apple_podcast_ids(value):
    """Return (collection_id, episode_id) from an Apple Podcasts URL."""
    value = (value or "").strip()
    if not value:
        return None
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in _APPLE_HOSTS:
        return None
    match = _APPLE_ID.search(parsed.path)
    if not match:
        return None
    episode_id = urllib.parse.parse_qs(parsed.query).get("i", [""])[0]
    if episode_id and not episode_id.isdigit():
        episode_id = ""
    return match.group(1), episode_id


def _fetch_json(url, max_bytes=1024 * 1024):
    data, _, charset = _fetch_url_bytes(url, max_bytes=max_bytes)
    try:
        return json.loads(_decode(data, charset))
    except ValueError as exc:
        raise TranscriptError(
            "The podcast directory returned an unreadable response.\n"
            "Why: the lookup API did not return valid JSON.\n"
            "Fix: try the show's RSS feed URL directly."
        ) from exc


def _apple_page_title(url):
    """Read the episode title from Apple's Open Graph metadata."""
    data, _, charset = _fetch_url_bytes(url, max_bytes=2 * 1024 * 1024)
    page = _decode(data, charset)
    patterns = (
        r'<meta[^>]+(?:property|name)=["\']og:title["\'][^>]*content=["\']([^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']og:title["\']',
        r"<title>(.*?)</title>",
    )
    for pattern in patterns:
        match = re.search(pattern, page, re.IGNORECASE | re.DOTALL)
        if match:
            title = html.unescape(match.group(1)).strip()
            if title:
                return re.split(r"\s+-\s+Apple Podcasts$", title, flags=re.IGNORECASE)[0].strip()
    return ""


def resolve_apple_podcast_url(url):
    """Resolve an Apple Podcasts show or episode URL to its RSS feed."""
    ids = extract_apple_podcast_ids(url)
    if not ids:
        return None
    collection_id, episode_id = ids
    lookup_url = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode(
        {"id": collection_id, "entity": "podcast"}
    )
    payload = _fetch_json(lookup_url)
    results = payload.get("results") if isinstance(payload, dict) else None
    feed_url = next(
        (result.get("feedUrl") for result in (results or []) if result.get("feedUrl")),
        "",
    )
    if not feed_url:
        raise TranscriptError(
            "Apple Podcasts did not return an RSS feed for this show.\n"
            "Why: the show may be unavailable, region-locked or no longer published.\n"
            "Fix: open the show in a podcast app and copy its RSS feed address."
        )

    episode_title = ""
    if episode_id:
        try:
            episode_title = _apple_page_title(url)
        except TranscriptError:
            # The feed still supports browsing; only the automatic episode match is lost.
            episode_title = ""
    return ApplePodcastSource(
        collection_id=collection_id,
        episode_id=episode_id,
        feed_url=feed_url,
        episode_title=episode_title,
        page_url=url,
    )


def _normalized_title(value):
    return re.sub(r"\W+", " ", html.unescape(value or "").casefold()).strip()


def _find_episode_by_title(feed, title):
    wanted = _normalized_title(title)
    if not wanted:
        return None
    for ref in feed.episodes:
        if _normalized_title(ref.episode_title) == wanted:
            return ref
    for ref in feed.episodes:
        candidate = _normalized_title(ref.episode_title)
        if candidate and (wanted in candidate or candidate in wanted):
            return ref
    return None


def _select_feed_episode(feed, language="English"):
    newest = feed.episodes[0]
    code = language_codes(language)[0]
    if newest.language and newest.language != code:
        for ref in feed.episodes:
            if ref.language == code:
                return ref
    return newest


def _load_youtube_transcript_api():
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, YouTubeTranscriptApiException
    except ImportError as exc:
        raise TranscriptError(
            "YouTube transcript support is not installed.\n"
            "Why: the youtube-transcript-api package is missing from this Python environment.\n"
            "Fix: run `pip install -r requirements.txt` and restart NeuralDeck."
        ) from exc
    return YouTubeTranscriptApi, YouTubeTranscriptApiException


def _youtube_error_message(video_id, exc):
    name = type(exc).__name__
    reasons = {
        "TranscriptsDisabled": "The uploader disabled captions for this video.",
        "NoTranscriptFound": "This video has no caption track in the requested languages.",
        "VideoUnavailable": "YouTube reports the video as unavailable or private.",
        "VideoUnplayable": "YouTube refused to serve this video.",
        "AgeRestricted": "The video is age-restricted, so captions cannot be fetched anonymously.",
        "InvalidVideoId": "The video id is not valid.",
        "RequestBlocked": "YouTube blocked the transcript request from this network.",
        "IpBlocked": "YouTube blocked this IP address.",
        "PoTokenRequired": "YouTube now requires a proof-of-origin token for this video.",
    }
    detail = reasons.get(name, f"YouTube returned {name}: {exc}")
    return (
        f"Could not fetch captions for YouTube video {video_id}.\n"
        f"Why: {detail}\n"
        "Fix: open the video in a browser and upload its .vtt/.srt transcript file, "
        "or try a video whose captions are public."
    )


def fetch_youtube_transcript(url_or_id, language="English", log_callback=None):
    """Download the best available caption track for a YouTube video."""
    video_id = extract_youtube_video_id(url_or_id)
    if not video_id:
        if _is_youtube_url(url_or_id):
            raise TranscriptError(
                "The YouTube link does not point to a single video.\n"
                "Why: channel, playlist and search links have no caption track of their own.\n"
                "Fix: paste a watch, shorts, live or youtu.be video link."
            )
        raise TranscriptError(
            "This is not a recognizable YouTube video link.\n"
            "Why: NeuralDeck needs the 11-character video id or a watch/shorts/youtu.be URL.\n"
            "Fix: copy the video address from the browser and try again."
        )

    api_class, api_error = _load_youtube_transcript_api()
    if log_callback:
        log_callback(f"Fetching YouTube captions for {video_id}...")

    try:
        api = api_class()
        transcript_list = api.list(video_id)
        try:
            transcript = transcript_list.find_transcript(language_codes(language))
        except api_error:
            available = list(transcript_list)
            if not available:
                raise
            # Fall back to any manual or generated track; the LLM can still
            # produce cards in the requested language from foreign captions.
            transcript = available[0]
        fetched = transcript.fetch()
        raw_text = " ".join(getattr(snippet, "text", "") for snippet in fetched)
        if not raw_text.strip():
            raise TranscriptError(
                f"YouTube returned an empty caption track for video {video_id}.\n"
                "Why: the track exists but contains no speech.\n"
                "Fix: try another video or load a transcript file."
            )
        text = parse_transcript(raw_text)
    except api_error as exc:
        raise TranscriptError(_youtube_error_message(video_id, exc)) from exc
    except TranscriptError:
        raise
    except Exception as exc:
        raise TranscriptError(
            f"Could not fetch captions for YouTube video {video_id}: {exc}\n"
            "Why: the caption endpoint returned an unexpected response.\n"
            "Fix: download the transcript file manually and load it locally."
        ) from exc

    if not text:
        raise TranscriptError(
            f"YouTube returned an empty caption track for video {video_id}.\n"
            "Why: the track exists but contains no speech.\n"
            "Fix: try another video or load a transcript file."
        )

    language_name = getattr(transcript, "language", None) or "unknown"
    if log_callback:
        log_callback(f"YouTube captions found ({language_name}, {len(text)} characters).")
    return TranscriptResult(
        text=text,
        title=f"YouTube video {video_id}",
        source_url=f"https://www.youtube.com/watch?v={video_id}",
        kind="youtube",
    )


def _local_name(tag):
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _child(element, name):
    for child in element:
        if _local_name(child.tag) == name:
            return child
    return None


def _text_of(element, name):
    child = _child(element, name)
    return (child.text or "").strip() if child is not None else ""


def _normalized_url(value):
    return (value or "").strip().rstrip("/")


def _choose_transcript(transcripts, language):
    if not transcripts:
        return None
    code = language_codes(language)[0]
    matching = [entry for entry in transcripts if entry["language"] == code]
    candidates = matching or transcripts
    return min(
        candidates,
        key=lambda entry: _TRANSCRIPT_TYPE_ORDER.index(entry["type"])
        if entry["type"] in _TRANSCRIPT_TYPE_ORDER
        else len(_TRANSCRIPT_TYPE_ORDER),
    )


def _transcript_ref(item, feed_title, language="English"):
    transcripts = []
    for element in item.iter():
        if _local_name(element.tag) != "transcript":
            continue
        url = (element.get("url") or "").strip()
        if url:
            transcripts.append(
                {
                    "url": url,
                    "type": (element.get("type") or "").strip().lower(),
                    "language": (element.get("language") or "").strip().lower(),
                }
            )
    preferred = _choose_transcript(transcripts, language)
    if preferred is None:
        return None

    episode_title = _text_of(item, "title") or "Untitled episode"
    enclosure = _child(item, "enclosure")
    episode_urls = tuple(
        value for value in (
            _text_of(item, "link"),
            _text_of(item, "guid"),
            (enclosure.get("url") or "").strip() if enclosure is not None else "",
        ) if value
    )
    return PodcastTranscriptRef(
        feed_title=feed_title,
        episode_title=episode_title,
        transcript_url=preferred["url"],
        transcript_type=preferred["type"],
        language=preferred["language"],
        episode_url=episode_urls[0] if episode_urls else "",
        episode_urls=episode_urls,
    )


def _parse_feed_items(xml_text, language):
    try:
        root = ET.fromstring(xml_text)
    except (ET.ParseError, DefusedXmlException, ValueError) as exc:
        raise TranscriptError(
            "The podcast feed could not be parsed.\n"
            "Why: the URL did not return valid RSS/XML.\n"
            "Fix: paste the show's RSS feed URL, not its web page."
        ) from exc

    channel = next((child for child in root.iter() if _local_name(child.tag) == "channel"), None)
    if channel is None:
        raise TranscriptError(
            "The podcast feed has no channel element.\n"
            "Why: this is not an RSS podcast feed.\n"
            "Fix: copy the RSS feed address from the podcast app and try again."
        )

    feed_title = _text_of(channel, "title") or "Podcast"
    items = [child for child in channel if _local_name(child.tag) == "item"]
    if not items:
        raise TranscriptError(
            f"The podcast feed '{feed_title}' contains no episodes.\n"
            "Why: the feed is empty or still being generated.\n"
            "Fix: try again later or use another feed."
        )

    refs = [ref for ref in (_transcript_ref(item, feed_title, language) for item in items) if ref is not None]
    if not refs:
        raise TranscriptError(
            f"No Podcasting 2.0 transcript is published in '{feed_title}'.\n"
            "Why: the show does not link a <podcast:transcript> file for its episodes.\n"
            "Fix: choose an episode with a transcript, or download the audio and use "
            "local transcription (requirements-transcription.txt)."
        )
    return feed_title, refs


def parse_podcast_feed_data(xml_text, feed_url="", language="English"):
    """Parse a Podcasting 2.0 feed into its transcribed episodes."""
    feed_title, refs = _parse_feed_items(xml_text, language)
    return PodcastFeed(title=feed_title, feed_url=feed_url, episodes=tuple(refs))


def parse_podcast_feed(xml_text, feed_url="", episode_url=None, language="English"):
    """Find a Podcasting 2.0 transcript link in an RSS feed."""
    feed = parse_podcast_feed_data(xml_text, feed_url=feed_url, language=language)

    if episode_url:
        wanted = _normalized_url(episode_url)
        for ref in feed.episodes:
            urls = ref.episode_urls or ((ref.episode_url,) if ref.episode_url else ())
            if wanted in {_normalized_url(value) for value in urls}:
                return ref
        raise TranscriptError(
            "The requested episode has no transcript in this feed.\n"
            "Why: either the episode URL does not match an item, or that item has no transcript.\n"
            "Fix: omit the episode URL to use the newest transcribed episode, or pick another feed."
        )

    return _select_feed_episode(feed, language)


def _hint_from_type(content_type):
    if "vtt" in content_type:
        return "vtt"
    if "srt" in content_type or "subrip" in content_type:
        return "srt"
    if "json" in content_type:
        return "json"
    if "html" in content_type:
        return "html"
    if content_type.startswith("text/plain"):
        return "plain"
    return ""


def _hint_from_url(url):
    path = urllib.parse.urlparse(url).path.lower()
    for extension in (".vtt", ".srt", ".json"):
        if path.endswith(extension):
            return extension.lstrip(".")
    return ""


def _transcript_from_ref(ref, log_callback=None):
    if log_callback:
        log_callback(f"Downloading podcast transcript for '{ref.episode_title}'...")
    data, content_type, charset = _fetch_url_bytes(ref.transcript_url)
    raw = _decode(data, charset)
    hint = _hint_from_type(ref.transcript_type) or _hint_from_type(content_type) or _hint_from_url(ref.transcript_url)
    try:
        text = parse_transcript(raw, hint=hint)
    except ValueError as exc:
        raise TranscriptError(
            f"The podcast transcript for '{ref.episode_title}' is unreadable.\n"
            f"Why: {exc}\n"
            "Fix: download the transcript file and load it locally, or try another episode."
        ) from exc
    if log_callback:
        log_callback(f"Podcast transcript ready ({len(text)} characters).")
    title = f"{ref.feed_title}: {ref.episode_title}" if ref.feed_title else ref.episode_title
    return TranscriptResult(
        text=text,
        title=title,
        source_url=ref.transcript_url,
        kind="podcast",
    )


def fetch_podcast_feed(feed_url, language="English", log_callback=None):
    """Download and parse a feed into its transcribed episodes."""
    if extract_apple_podcast_ids(feed_url):
        source = resolve_apple_podcast_url(feed_url)
        feed_url = source.feed_url
        if log_callback:
            log_callback("Resolved the Apple Podcasts page to its RSS feed.")
    if log_callback:
        log_callback("Downloading podcast feed...")
    data, _, _ = _fetch_url_bytes(feed_url)
    feed = parse_podcast_feed_data(data, feed_url=feed_url, language=language)
    if log_callback:
        log_callback(f"Found {len(feed.episodes)} transcribed episode(s) in '{feed.title}'.")
    return feed


def fetch_podcast_transcript_for_ref(ref, log_callback=None):
    """Download the transcript already selected from a podcast feed."""
    return _transcript_from_ref(ref, log_callback=log_callback)


def fetch_podcast_transcript(feed_url, episode_url=None, language="English", log_callback=None):
    """Download a transcript linked from a Podcasting 2.0 RSS feed."""
    if log_callback:
        log_callback("Downloading podcast feed...")
    data, _, _ = _fetch_url_bytes(feed_url)
    ref = parse_podcast_feed(data, feed_url=feed_url, episode_url=episode_url, language=language)
    return _transcript_from_ref(ref, log_callback=log_callback)


def _looks_like_feed(url, content_type, text):
    if content_type in ("application/rss+xml", "application/atom+xml", "application/xml", "text/xml"):
        return True
    if urllib.parse.urlparse(url).path.lower().endswith((".rss", ".xml")):
        return True
    return text.lstrip("\ufeff \t\r\n").startswith(("<?xml", "<rss", "<feed"))


def fetch_transcript_from_url(url, language="English", log_callback=None):
    """Fetch a transcript from a YouTube link, podcast feed or transcript URL."""
    url = (url or "").strip()
    if not url:
        raise TranscriptError(
            "No transcript URL was provided.\n"
            "Why: the import field was empty.\n"
            "Fix: paste a YouTube video, podcast RSS feed or transcript link."
        )

    if extract_youtube_video_id(url):
        return fetch_youtube_transcript(url, language=language, log_callback=log_callback)
    if _is_youtube_url(url):
        # Let the YouTube path produce the precise "not a single video" error.
        return fetch_youtube_transcript(url, language=language, log_callback=log_callback)

    if extract_apple_podcast_ids(url):
        source = resolve_apple_podcast_url(url)
        feed = fetch_podcast_feed(source.feed_url, language=language, log_callback=log_callback)
        ref = _find_episode_by_title(feed, source.episode_title)
        if ref is None and source.episode_id:
            if source.episode_title:
                raise TranscriptError(
                    f"The Apple Podcasts episode '{source.episode_title}' has no published transcript.\n"
                    "Why: it did not match any transcribed episode in the show's RSS feed.\n"
                    "Fix: use Browse Podcast to pick another episode, or transcribe the audio locally."
                )
            raise TranscriptError(
                "Could not identify which Apple Podcasts episode this link points to.\n"
                "Why: the episode page did not expose a readable title.\n"
                "Fix: use Browse Podcast with the show URL, or paste the RSS feed URL."
            )
        if ref is None:
            ref = _select_feed_episode(feed, language)
        return fetch_podcast_transcript_for_ref(ref, log_callback=log_callback)

    data, content_type, charset = _fetch_url_bytes(url)
    raw = _decode(data, charset)

    if _looks_like_feed(url, content_type, raw):
        ref = parse_podcast_feed(data, feed_url=url, language=language)
        return _transcript_from_ref(ref, log_callback=log_callback)

    if content_type.startswith("audio/") or content_type.startswith("video/"):
        raise TranscriptError(
            "The URL points to audio or video, not a text transcript.\n"
            "Why: NeuralDeck does not download media from the web.\n"
            "Fix: download the episode and select the audio file for local transcription, "
            "or use the podcast RSS feed URL."
        )

    hint = _hint_from_type(content_type) or _hint_from_url(url)
    try:
        text = parse_transcript(raw, hint=hint)
    except ValueError as exc:
        raise TranscriptError(
            f"The URL did not return a readable transcript: {exc}\n"
            "Why: the page may need a browser login or contain only navigation text.\n"
            "Fix: download the .vtt/.srt/.txt transcript and load it locally."
        ) from exc

    filename = urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/", 1)[-1])
    title = filename or urllib.parse.urlparse(url).netloc
    if log_callback:
        log_callback(f"Transcript ready ({len(text)} characters).")
    return TranscriptResult(text=text, title=title, source_url=url, kind="web")
