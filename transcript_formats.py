"""Parse transcript formats into the plain text NeuralDeck sends to the LLM.

Supported inputs are WebVTT, SubRip (SRT), Podcasting 2.0 transcript JSON,
HTML transcript pages and plain text. Network access lives in
``transcript_sources``; this module is pure and easy to test.
"""

import html
import json
import os
import re
from html.parser import HTMLParser

_TIMESTAMP_PREFIX = re.compile(
    r"^\s*(?:\[|\()?\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?(?:\]|\))?\s*"
)
_TAG = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n\s*\n")
_SKIP_TAGS = {"script", "style", "noscript", "svg", "template"}
_BLOCK_TAGS = {
    "p", "div", "br", "li", "ul", "ol", "section", "article", "header",
    "footer", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "tr",
}


class _HTMLTextExtractor(HTMLParser):
    """Collect readable text while ignoring scripts, styles and markup."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._chunks = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if not self._skip_depth and tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if not self._skip_depth and tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self._chunks.append(data)

    def get_text(self):
        return "".join(self._chunks)


def _html_to_text(text):
    parser = _HTMLTextExtractor()
    parser.feed(text)
    parser.close()
    return parser.get_text()


def _is_noise_line(line):
    upper = line.upper()
    if upper.startswith(("WEBVTT", "NOTE ", "NOTE:", "STYLE", "REGION:", "KIND:", "LANGUAGE:")):
        return True
    if upper.startswith("X-TIMESTAMP-MAP"):
        return True
    if "-->" in line and len(line) <= 120:
        return True
    if line.isdigit() and len(line) <= 4:
        return True
    return False


def _parse_timed_cues(text):
    """Shared VTT/SRT cue parser: keep the text after each timing line."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    output = []
    for block in _BLANK_LINES.split(normalized):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        cue_text = " ".join(lines[timing_index + 1:]).strip()
        if cue_text:
            output.append(cue_text)
    return "\n".join(output)


def parse_vtt(text):
    """Extract cue text from a WebVTT transcript."""
    return clean_transcript_text(_parse_timed_cues(text))


def parse_srt(text):
    """Extract cue text from a SubRip transcript."""
    return clean_transcript_text(_parse_timed_cues(text))


def _iter_segments(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("segments", "transcript", "results", "items", "captions", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return _iter_segments(value)
        if isinstance(value, str) and value.strip():
            return [value]
    return [data] if data.get("text") else []


def parse_podcast_json(text):
    """Extract text from Podcasting 2.0 JSON and similar segment lists."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Transcript JSON is malformed: {exc}") from exc

    parts = []
    for segment in _iter_segments(data):
        if isinstance(segment, str):
            parts.append(segment)
        elif isinstance(segment, dict):
            value = segment.get("text") or segment.get("body") or segment.get("transcript")
            if isinstance(value, str) and value.strip():
                parts.append(value)
    if not parts:
        raise ValueError("Transcript JSON contains no text segments.")
    return clean_transcript_text("\n".join(parts))


def _merge_overlap(previous, line):
    """Merge YouTube-style rolling captions that share a word boundary."""
    previous_words = previous.split()
    line_words = line.split()
    for size in range(min(len(previous_words), len(line_words)), 0, -1):
        if previous_words[-size:] == line_words[:size]:
            return " ".join(previous_words + line_words[size:])
    return None


def clean_transcript_text(text):
    """Normalize captions into one readable block and drop rolling duplicates."""
    if not text:
        return ""
    text = html.unescape(text)
    text = _TAG.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = []
    for raw_line in text.split("\n"):
        line = _SPACES.sub(" ", raw_line).strip()
        if not line or _is_noise_line(line):
            continue
        line = _TIMESTAMP_PREFIX.sub("", line, count=1).strip()
        if not line:
            continue
        if lines:
            previous = lines[-1]
            if line == previous:
                continue
            # YouTube-style rolling captions extend the previous line.
            if len(line) > len(previous) and line.startswith(previous):
                lines[-1] = line
                continue
            if len(previous) > len(line) and previous.startswith(line):
                continue
            merged = _merge_overlap(previous, line)
            if merged:
                lines[-1] = merged
                continue
        lines.append(line)

    return _SPACES.sub(" ", " ".join(lines)).strip()


def parse_transcript(text, hint=""):
    """Convert transcript text to plain text, sniffing the format when needed."""
    if text is None:
        raise ValueError("Transcript is empty.")
    text = text.lstrip("\ufeff")
    if not text.strip():
        raise ValueError("Transcript is empty.")

    hint = (hint or "").lower().lstrip(".")
    if hint in ("vtt", "webvtt"):
        result = parse_vtt(text)
    elif hint in ("srt", "subrip"):
        result = parse_srt(text)
    elif hint == "json":
        result = parse_podcast_json(text)
    elif hint in ("html", "htm"):
        result = clean_transcript_text(_html_to_text(text))
    else:
        stripped = text.lstrip()
        if stripped.upper().startswith("WEBVTT"):
            result = parse_vtt(text)
        elif re.match(r"^\d+\s*\n\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->", stripped):
            result = parse_srt(text)
        elif stripped.startswith(("{", "[")):
            try:
                result = parse_podcast_json(text)
            except ValueError:
                result = clean_transcript_text(text)
        elif "<p" in stripped.lower() or "<div" in stripped.lower():
            result = clean_transcript_text(_html_to_text(text))
        else:
            result = clean_transcript_text(text)

    if not result:
        raise ValueError("Transcript contains no readable text.")
    return result


def read_transcript_file(file_path):
    """Read a transcript file and return normalized plain text."""
    extension = os.path.splitext(os.fspath(file_path))[1]
    with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as handle:
        raw = handle.read()
    return parse_transcript(raw, hint=extension)
