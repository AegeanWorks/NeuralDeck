# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.

<!-- Entry format:
### ADR-NNN: <decision in one line>
- **Date**: YYYY-MM-DD
- **Status**: Accepted
- **Context**: <what forced the decision>
- **Decision**: <what was decided>
- **Consequences**: <what follows, including what it costs>
-->

### ADR-001: Adopt the AIKit project workflow and gate hygiene
- **Date**: 2026-10-20
- **Status**: Accepted
- **Context**: NeuralDeck is now tracked as an AIKit project, so its Phase 4 gates (tests, hygiene, guidelines, secrets) must pass before each commit without changing production behaviour.
- **Decision**: Keep `.aikit/` project memory in the repository except transient lock, backup and temp files; annotate deliberate silent fallbacks inline with `hygiene: allow <reason>` instead of reshaping UI error paths; maintain the README cold-start quick reference and a complete top-level tree.
- **Consequences**: Commits require `python aikit.py check NeuralDeck`; deliberate fallbacks carry an explicit reason; runtime JSONL logs and the session cache stay untracked.

### ADR-002: Resolve settings beside the app and persist them atomically
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: The README promised `NEURALDECK_CONFIG` and `NEURALDECK_LOG` overrides, but the code read and wrote `config.json`, `session_cache.json` and `session.log` relative to the current working directory, so launching NeuralDeck from another folder could create new files or lose saved settings. Plain `json.dump` writes could also leave a truncated file after a crash, Generate read context window and concurrency from the last saved config rather than the values visible in the Settings tab, and empty numeric fields raised `TclError`.
- **Decision**: Add `settings_io.py` as the single place that resolves the config and log paths. The default directory is the source module's directory, or the executable's directory in a frozen (`sys.frozen`) build, so a PyInstaller one-file executable does not write into its temporary extraction directory. `NEURALDECK_CONFIG` and `NEURALDECK_LOG` override the paths. JSON is read with a typed fallback and an optional error callback; it is written while holding an in-process lock and a hidden lock-file sibling across processes, through a unique `tempfile.mkstemp` sibling, flushed with `fsync`, and moved with `ReplaceFileW` on Windows NTFS where supported (preserving ACLs and attributes), with an `os.replace` fallback and bounded retries for transient sharing violations on unsupported filesystems. Existing POSIX modes are preserved and new files start at `0600`; the log parent directory is created before FileHandler. Config keeps its four-space indentation while the session keeps two. The session cache lives beside the resolved config file. Malformed or wrong-shaped config and session files are quarantined as `.corrupt_<timestamp>` siblings before defaults are used; a file that cannot be read because of an I/O error is left in place and blocks saving over it until it is removed or the application restarts. Stale temporary siblings older than one day are removed at startup. Config values are normalized to documented types and ranges before the UI uses them, session entries are validated before restoration, and failed config writes are logged while an explicit Settings save reports the failure in a dialog. The UI reads live context window, concurrency, max-token and temperature values on Generate and clamps invalid entries to bounded defaults.
- **Consequences**: The documented environment variables now work, including nested log paths; user data stays with the application regardless of the launch directory and survives a frozen one-file build; an abrupt process termination during a write cannot leave a truncated target; concurrent writers use distinct temp files; a restrictive POSIX mode and Windows NTFS ACLs are not loosened; unsupported filesystems fall back without that metadata guarantee. Generate uses the values the user sees. Deliberately malformed numeric input is corrected silently to the declared default or range instead of raising `TclError`, and an unreadable session cache is logged and preserved for inspection instead of disappearing silently.

### ADR-003: Keep personal configuration out of version control
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: The tracked `config.json` mixed application defaults with personal deck names, language and an API-key field. Every settings save dirtied the repository, and a user-customized key could be committed by accident.
- **Decision**: Untrack `config.json`, ignore it, and commit `config.example.json` with the documented defaults and an empty `selected_decks` list. A fresh checkout may copy the example, while the UI creates `config.json` on the first save if it is absent.
- **Consequences**: Personal settings no longer appear in commits or on the remote; the default configuration remains documented and testable; an existing local `config.json` keeps working because untracking does not delete the working file.

### ADR-004: Import media transcripts instead of downloading media
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: Users want cards from YouTube videos and podcasts, but NeuralDeck is a local, privacy-first desktop app. YouTube exposes caption tracks, many podcasts publish Podcasting 2.0 `<podcast:transcript>` files, and some episodes have neither.
- **Decision**: Add `transcript_sources.py`, `transcript_formats.py` and `audio_transcription.py`. YouTube captions are fetched with the pinned `youtube-transcript-api` package; podcast feeds are parsed with `defusedxml` and only the linked transcript text is downloaded; direct `.vtt`/`.srt`/`.json`/HTML/plain transcript URLs are accepted. Local audio/video files can be transcribed through optional `faster-whisper`, installed from `requirements-transcription.txt`, which never uploads the audio. Downloads are limited to 10 MB with a 20-second timeout, and every unsupported source returns a Why/Fix message instead of silently degrading.
- **Consequences**: URL imports make a network request to the host the user names and need `youtube-transcript-api`/`defusedxml` at runtime. Audio transcription is opt-in, downloads a model on first use, and is not bundled in the base install. YouTube can still block caption requests; the documented fallback is a local transcript file or local audio transcription.

### ADR-005: Browse podcast episodes before downloading a transcript
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: A feed can publish transcripts for many episodes. Picking the newest one silently is safe but not predictable, and users could not inspect imported text before spending LLM time.
- **Decision**: Keep one pure feed parser that returns a `PodcastFeed` of `PodcastTranscriptRef` records (including the episode's link, GUID and enclosure URLs). `fetch_podcast_feed` downloads the feed once for the chooser, and `fetch_podcast_transcript_for_ref` downloads only the selected transcript. The UI shows a modal episode table, then a read-only transcript preview capped at 50,000 characters. The existing `parse_podcast_feed`/`fetch_podcast_transcript` behavior stays available for callers that want the newest episode.
- **Consequences**: Episode selection adds no dependency and avoids re-downloading the feed when the chosen transcript is fetched. The feed is parsed on a worker thread and the chooser runs on the UI thread. A feed with one transcribed episode skips the chooser. Transcripts remain in memory only.

### ADR-006: Resolve Apple Podcasts links through iTunes lookup and RSS
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: Users usually have Apple Podcasts links, while NeuralDeck needs an RSS feed and a Podcasting 2.0 transcript. Apple does not expose a transcript API in that lookup response.
- **Decision**: Parse `/id<collection>` and `?i=<episode>` from Apple Podcasts URLs, resolve the show's `feedUrl` through `https://itunes.apple.com/lookup`, and read an episode page's Open Graph title to match the feed item. Reuse the existing feed parser and download only the matched transcript. A show URL opens the normal episode chooser; an episode URL matches by normalized title and fails with a Why/Fix message when the episode has no transcript or no readable title.
- **Consequences**: Apple show links work without scraping the show page, and episode links work only when Apple exposes its title metadata and the feed publishes a transcript for that episode. The page fetch is bounded to 2 MB and is skipped for show URLs. No new dependency or credential is introduced.

### ADR-007: Extract PDF bytes and readable web articles through the URL importer
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: Local PDFs already worked, but a PDF link or a normal article URL either failed or passed raw HTML with navigation, cookie banners and scripts into the LLM. PyPDF2 and lxml were already declared dependencies.
- **Decision**: Detect PDFs by content type, `.pdf` path or `%PDF-` magic before decoding, and reuse the existing PyPDF2 page loop through `extract_text_from_pdf_bytes`. Extract HTML pages with a small lxml-based `web_extraction` module: drop scripts/nav/header/footer/aside and class/id boilerplate, prefer `<article>`/`<main>`, keep readable paragraphs, and fall back to the existing transcript parser when article extraction is thin. URL downloads stay bounded at 10 MB and use the existing worker thread.
- **Consequences**: PDF and article links can be pasted into the same import box; scanned PDFs still need OCR, paywalled or script-only pages can still fail with a Why/Fix message. No new dependency or persisted state is added.

### ADR-008: Stream direct media URLs to a temporary file for local transcription
- **Date**: 2026-10-30
- **Status**: Accepted
- **Context**: Direct video and audio URLs (lecture recordings, podcast MP3s) are common study sources, but the normal URL reader decodes responses as text and caps them at 10 MB. Transcribing from memory is not viable for media.
- **Decision**: Detect media extensions in the URL path before the normal fetch, stream the response to a `mkstemp` file in 1 MB chunks, cap it at 300 MB, reject HTML/JSON/XML responses, and call the optional local faster-whisper adapter. Delete the temporary file in a `finally` block whether transcription succeeds or fails. The resulting card source is labeled `video` or `audio`.
- **Consequences**: Direct media imports need the optional `requirements-transcription.txt` package and a first-run model download; a 300 MB cap bounds disk and time, and the temporary file is removed after one attempt. Player pages and non-extension media URLs still need the local-file path or a written transcript.

## Licensing migration (agpl-final)

- New versions use the Aegean License 1.1 (AL-1.1); versions up to and including `agpl-final` remain under GNU AGPL-3.0.
- Rights holder: AegeanWorks; commercial use under ACL-1.0.
- Counsel review of the 1.1 texts remains pending.

## License notice cleanup (2026-10-26)

- The license-history notes were removed from README.md and COMMERCIAL.md: the project is offered only under the Aegean License 1.1 (AL-1.1), with commercial use under ACL-1.0.
