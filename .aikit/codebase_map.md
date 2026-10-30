# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `32`
- **Total Classes**: `67`
- **Total Top-Level Functions**: `113`
- **Total Class Methods**: `330`
- **Total Source Lines**: `7591`

---

## 📦 Modules & Exported Symbols

### [`anki_addon/__init__.py`](anki_addon/__init__.py)
**Size**: `247` lines (`9787` bytes)

**Classes:**
- `class AnkiBridgeHandler`
  - Method `.log_message(format, *args)`
  - Method `._set_cors_headers()`
  - Method `.do_OPTIONS()`
  - Method `.do_GET()`
  - Method `.do_POST()`
  - Method `.add_cards_to_anki(deck_name, cards, model_name, media_files)`

**Functions:**
- `def run_server()`
- `def stop_server()`

---

### [`anki_integration.py`](anki_integration.py)
**Size**: `94` lines (`3644` bytes)

**Functions:**
- `def _get_no_proxy_opener()`
- `def check_anki_connection(port)` - *Simple check to see if the Anki add-on server is running.*
- `def get_deck_names(log_callback)` - *Fetches the list of deck names from the Anki add-on.*
- `def create_anki_deck(deck_name, qa_pairs, log_callback)` - *Sends Q&A pairs to the custom Anki Add-on running on 127.0.0.1:5005.*

---

### [`audio_transcription.py`](audio_transcription.py)
> *Optional local podcast/video transcription through faster-whisper.*

**Size**: `89` lines (`3506` bytes)

**Classes:**
- `class AudioTranscriptionError` - *A user-facing local transcription failure with a Why/Fix message.*

**Functions:**
- `def is_audio_file(file_path)` - *Return True when the path has a supported audio/video extension.*
- `def is_video_file(file_path)` - *Return True when the path has a supported video container extension.*
- `def transcribe_audio(file_path, model_size, log_callback, stop_callback)` - *Transcribe a local audio/video file and return plain text.*

---

### [`debug_anki.py`](debug_anki.py)
**Size**: `41` lines (`1724` bytes)

**Functions:**
- `def test_connection()`

---

### [`debug_llm.py`](debug_llm.py)
**Size**: `46` lines (`1724` bytes)

**Functions:**
- `def test_llm_generation()`

---

### [`document_processor.py`](document_processor.py)
**Size**: `1003` lines (`43871` bytes)

**Functions:**
- `def _extract_text_from_pdf_reader(reader, log_callback)` - *Extract text from an already opened pypdf reader.*
- `def extract_text_from_pdf(file_path, log_callback)` - *Extract text from a PDF file.*
- `def extract_text_from_pdf_bytes(data, log_callback)` - *Extract text from PDF bytes downloaded from a URL.*
- `def _extract_text_from_docx(file_path)` - *Extracts text from a .docx file.*
- `def _extract_text_from_pptx(file_path)` - *Extracts text from a .pptx file.*
- `def _extract_text_from_txt(file_path)` - *Extracts text from a .txt file.*
- `def _extract_text_from_transcript(file_path, log_callback)` - *Extracts text from WebVTT, SRT or transcript JSON files.*
- `def _extract_text_from_audio(file_path, log_callback)` - *Transcribes a local podcast or video file with optional faster-whisper.*
- `def extract_text_from_document(file_path, log_callback)` - *Extracts text from a supported document, transcript, or audio file.*
- `def check_llm_server(api_url, api_key)` - *Checks if the LLM server is reachable.*
- `def call_lm_studio(prompt, system_instruction, api_url, api_key, model, temperature, max_tokens, stop_callback, timeout)` - *Calls the local LM Studio server (OpenAI compatible API).*
- `def smart_chunk_text(text, max_chars, min_chars)` - *Splits text into chunks respecting paragraph boundaries.*
- `def _strip_trailing_commas(text)` - *Remove commas before a closing brace or bracket, ignoring quoted strings.*
- `def robust_parse_objects(text)` - *Scans the text for JSON objects and extracts them individually.*
- `def refine_generated_cards(cards, deck_names, target_language, api_url, api_key, model, temperature, log_callback, stop_callback)` - *Sends the generated cards back to the AI for a second pass to fix errors, *
- `def filter_and_process_cards(raw_data_list, deck_names, smart_deck_match, filter_yes_no)` - *Helper to clean, filter, and assign decks to a list of raw card objects.*
- `def _process_chunk_task(i, chunk, total_chunks, stop_callback, log_callback, max_tokens, system_prompt, context_window, api_url, api_key, model, temperature, ai_refinement, deck_names, target_language, filter_yes_no, smart_deck_match, pipeline_stats, failure_logger)` - *Helper function to process a single chunk in a thread.*
- `def generate_qa_pairs(text, deck_names, target_language, log_callback, api_url, api_key, model, temperature, max_tokens, prompt_style, context_window, concurrency, card_density, partial_result_callback, stop_callback, filter_yes_no, exclude_trivia, smart_deck_match, ai_refinement, deterministic_mode, pipeline_stats)` - *Generates Q&A pairs from the given text using a Local LLM.*

---

### [`main.py`](main.py)
**Size**: `8` lines (`129` bytes)

**Functions:**
- `def main()`

---

### [`pipeline_utils.py`](pipeline_utils.py)
**Size**: `144` lines (`4696` bytes)

**Classes:**
- `class PipelineStats`
  - Method `.__init__()`
  - Method `.record_extraction_time(duration)`
  - Method `.record_chunking_time(duration)`
  - Method `.add_llm_time(duration)`
  - Method `.increment_chunk_count()`
  - Method `.increment_processed_chunk()`
  - Method `.increment_failed_chunk()`
  - Method `.add_generated_cards(count)`
  - Method `.add_rejected_cards(count)`
  - Method `.finish()`
  - Method `.get_summary()`
- `class FailureLogger`
  - Method `.__init__(run_id)`
  - Method `.log_failed_chunk(chunk_index, chunk_text, error)`
  - Method `.log_rejected_card(card, reason)`
  - Method `._append_to_log(filepath, entry)` - *Appends a single JSON entry as a new line (JSONL format).*
- `class CardValidator`
  - Method `.validate(card, min_len, max_len)` - *Validates a card dictionary.*
- `class ResourceGuard`
  - Method `.check_file_size(filepath)`
  - Method `.check_chunk_count(count)`

---

### [`settings_io.py`](settings_io.py)
> *Environment-aware paths and crash-safe persistence for NeuralDeck settings.*

**Size**: `378` lines (`12486` bytes)

**Functions:**
- `def application_dir(module_file, frozen, executable)` - *Return the persistent application directory, including for frozen builds.*
- `def resolve_app_path(default_name, env_var)` - *Resolve a file beside the application unless an environment variable overrides it.*
- `def ensure_parent_directory(path)` - *Create the parent directory for a file path when it does not exist yet.*
- `def quarantine_corrupt_file(path)` - *Move an unreadable state file aside so defaults never overwrite its evidence.*
- `def _report_read_error(path, exc, on_error, quarantine_on_error)`
- `def read_json_file(path, default, on_error, quarantine_on_error)` - *Read JSON from path, returning default when the file is missing, malformed or mistyped.*
- `def cleanup_stale_temp_files(path, max_age_seconds, now)` - *Remove crashed temporary siblings older than the age threshold.*
- `def _replace_once(source, target)` - *Replace target while preserving Windows ACLs and attributes when possible.*
- `def _replace_with_retries(source, target, attempts, delay)` - *Retry a replace that briefly collides with another writer.*
- `def _cross_process_lock(target)` - *Serialize writes across processes so ReplaceFileW is not used concurrently.*
- `def write_json_file(path, data, indent)` - *Write JSON atomically so a crash cannot leave a truncated settings file.*
- `def _write_json_file(path, data, indent)`
- `def parse_int_setting(raw_value, default, minimum, maximum)` - *Parse a numeric entry, clamping it to the declared range and falling back to default.*
- `def parse_float_setting(raw_value, default, minimum, maximum)` - *Parse a decimal entry, rejecting non-finite values and clamping it to the range.*
- `def normalize_config(raw)` - *Normalize persisted config values to the documented types and ranges.*
- `def normalize_session_data(data)` - *Return safe card dictionaries, or None when the session shape is unusable.*

---

### [`tests/mocks.py`](tests/mocks.py)
**Size**: `26` lines (`798` bytes)

**Classes:**
- `class MockLLM`
  - Method `.__init__(response_map)`
  - Method `.call(prompt, system_instruction, **kwargs)`
- `class MockAnki`
  - Method `.__init__()`
  - Method `.add_cards(deck_name, cards)`
  - Method `.get_decks()`

---

### [`tests/run_tests.py`](tests/run_tests.py)
**Size**: `14` lines (`364` bytes)

---

### [`tests/test_anki_addon_logic.py`](tests/test_anki_addon_logic.py)
**Size**: `133` lines (`4090` bytes)

**Classes:**
- `class MockNote`
  - Method `.__init__(col, model)`
  - Method `.__setitem__(key, value)`
  - Method `.__getitem__(key)`
- `class TestAnkiAddonLogic`
  - Method `.setUp()`
  - Method `.test_add_cards_to_anki_legacy_api()`
  - Method `.test_add_cards_to_anki_modern_api()`

---

### [`tests/test_anki_addon_media.py`](tests/test_anki_addon_media.py)
**Size**: `227` lines (`7995` bytes)

**Classes:**
- `class MockNote`
  - Method `.__init__(col, model)`
  - Method `.__setitem__(key, value)`
  - Method `.__getitem__(key)`
- `class TestAnkiAddonMediaHandling`
  - Method `.setUp()`
  - Method `.test_add_cards_with_media_files(mock_abspath)`
  - Method `.test_add_cards_media_path_traversal_blocked(mock_abspath)`
- `class TestAnkiAddonCORS`
  - Method `.setUp()`
  - Method `.test_cors_headers_localhost()`
  - Method `.test_cors_headers_127_0_0_1()`
  - Method `.test_cors_headers_external_rejected()`
- `class TestAnkiAddonOPTIONS`
  - Method `.setUp()`
  - Method `.test_options_returns_200()`
- `class TestAnkiAddonGET`
  - Method `.setUp()`
  - Method `.test_get_decks_success(mock_run_on_main, mock_future)`
- `class TestAnkiAddonPOST`
  - Method `.setUp()`
  - Method `.test_post_add_cards_success(mock_add_cards, mock_run_on_main, mock_future)`
  - Method `.test_post_invalid_path()`

---

### [`tests/test_anki_integration.py`](tests/test_anki_integration.py)
**Size**: `75` lines (`3206` bytes)

**Classes:**
- `class TestAnkiIntegration`
  - Method `.test_check_anki_connection_success(mock_get_opener)`
  - Method `.test_check_anki_connection_failure(mock_get_opener)`
  - Method `.test_create_anki_deck_success(mock_get_opener)`
  - Method `.test_create_anki_deck_connection_error(mock_get_opener)`
  - Method `.test_create_anki_deck_http_error(mock_get_opener)`
  - Method `.test_create_anki_deck_http_error_malformed(mock_get_opener)`

**Functions:**
- `def _opener_returning(response)`

---

### [`tests/test_anki_integration_get_deck_names.py`](tests/test_anki_integration_get_deck_names.py)
**Size**: `90` lines (`3284` bytes)

**Classes:**
- `class TestGetDeckNames`
  - Method `.test_get_deck_names_success(mock_get_opener)`
  - Method `.test_get_deck_names_empty(mock_get_opener)`
  - Method `.test_get_deck_names_with_log_callback(mock_print, mock_get_opener)`
  - Method `.test_get_deck_names_connection_error(mock_print, mock_get_opener)`
  - Method `.test_get_deck_names_http_error(mock_get_opener)`
  - Method `.test_get_deck_names_missing_decks_key(mock_get_opener)`

**Functions:**
- `def _opener_returning(response)`

---

### [`tests/test_audio_transcription.py`](tests/test_audio_transcription.py)
**Size**: `143` lines (`5127` bytes)

**Classes:**
- `class TestAudioTranscription`
  - Method `.test_audio_extensions_are_recognized()`
  - Method `.test_video_extensions_are_recognized_separately()`
  - Method `.test_missing_file_raises()`
  - Method `.test_unsupported_extension_raises()`
  - Method `.test_missing_faster_whisper_reports_the_optional_requirements_file()`
  - Method `.test_transcribes_segments_and_honours_stop_callback()`
  - Method `.test_empty_speech_is_reported()`
  - Method `.test_stop_callback_stops_before_a_result()`

**Functions:**
- `def _temp_audio(suffix)`

---

### [`tests/test_deterministic.py`](tests/test_deterministic.py)
**Size**: `83` lines (`3855` bytes)

**Classes:**
- `class TestDeterministicMode`
  - Method `.test_determinism_output_order(mock_chunk, mock_llm, mock_check)`
  - Method `.test_determinism_random_seeding(mock_chunk, mock_llm, mock_check)`
  - Method `.test_nondeterministic_behavior(mock_chunk, mock_llm, mock_check)`

---

### [`tests/test_document_processor.py`](tests/test_document_processor.py)
**Size**: `308` lines (`12258` bytes)

**Classes:**
- `class TestDocumentProcessor`
  - Method `.test_robust_parse_objects_standard()`
  - Method `.test_robust_parse_objects_markdown()`
  - Method `.test_robust_parse_objects_markdown_with_nested_code()`
  - Method `.test_robust_parse_objects_preserves_commas_before_closing_characters()`
  - Method `.test_robust_parse_objects_multiple_objects()`
  - Method `.test_robust_parse_objects_wrapper()`
  - Method `.test_robust_parse_objects_nested()`
  - Method `.test_robust_parse_objects_with_text()`
  - Method `.test_filter_and_process_cards_basic()`
  - Method `.test_filter_and_process_cards_yes_no()`
  - Method `.test_filter_and_process_cards_capitalized()`
  - Method `.test_filter_and_process_cards_whitespace()`
  - Method `.test_smart_chunk_text_strict()`
  - Method `.test_smart_chunk_text_sentences()`
  - Method `.test_extract_text_empty(mock_pypdf2, mock_open)`
  - Method `.test_extract_text_image_only(mock_pypdf2, mock_open)`
  - Method `.test_extract_text_partial_success(mock_pypdf2, mock_open)`
  - Method `.test_extract_text_success(mock_pypdf2, mock_open)`
  - Method `.test_extract_text_page_error(mock_pypdf2, mock_open)`
  - Method `.test_retry_success(mock_sleep, mock_urlopen)`
  - Method `.test_call_lm_studio_malformed_chunk(mock_urlopen)`
  - Method `.test_retry_failure(mock_sleep, mock_urlopen)`
  - Method `.test_concurrency_limit(mock_executor, mock_cpu_count, mock_as_completed, mock_check_server)`
  - Method `.test_stop_callback_stops_generation(mock_executor, mock_as_completed, mock_chunk, mock_check_server)`

---

### [`tests/test_document_processor_extra.py`](tests/test_document_processor_extra.py)
**Size**: `253` lines (`10155` bytes)

**Classes:**
- `class TestExtractTextFromDocument`
  - Method `.test_extract_docx(mock_docx)`
  - Method `.test_extract_pptx(mock_pptx)`
  - Method `.test_extract_txt(mock_txt)`
  - Method `.test_extract_pdf(mock_pdf)`
  - Method `.test_extract_vtt_transcript(mock_transcript)`
  - Method `.test_extract_srt_transcript(mock_transcript)`
  - Method `.test_extract_json_transcript(mock_transcript)`
  - Method `.test_extract_audio_transcript(mock_audio)`
  - Method `.test_extract_video_transcript(mock_audio)`
  - Method `.test_unsupported_format()`
- `class TestExtractTextFromDocx`
  - Method `.test_docx_success(mock_document)`
- `class TestExtractTextFromPptx`
  - Method `.test_pptx_success(mock_pres)`
  - Method `.test_pptx_empty(mock_pres)`
- `class TestExtractTextFromTxt`
  - Method `.test_txt_success(mock_file)`
- `class TestCheckLlmServer`
  - Method `.test_check_llm_server_success(mock_urlopen)`
  - Method `.test_check_llm_server_connection_error(mock_urlopen, mock_socket)`
  - Method `.test_check_llm_server_timeout(mock_urlopen, mock_socket)`
  - Method `.test_check_llm_server_http_error(mock_urlopen, mock_socket)`
- `class TestExtractTextFromPdfEdgeCases`
  - Method `.test_pdf_encrypted(mock_pypdf2, mock_open)`
  - Method `.test_pdf_file_not_found(mock_pypdf2, mock_open)`
- `class TestPdfBytesExtraction`
  - Method `.test_extracts_text_from_downloaded_pdf_bytes(mock_pypdf2)`
  - Method `.test_reports_an_empty_downloaded_pdf(mock_pypdf2)`
  - Method `.test_reports_a_corrupt_downloaded_pdf(mock_pypdf2)`

---

### [`tests/test_failure_isolation.py`](tests/test_failure_isolation.py)
**Size**: `73` lines (`3000` bytes)

**Classes:**
- `class TestFailureIsolation`
  - Method `.test_single_chunk_failure(mock_chunk, mock_llm, mock_check)`
  - Method `.test_malformed_json_partial(mock_chunk, mock_llm, mock_check)`

---

### [`tests/test_pipeline.py`](tests/test_pipeline.py)
**Size**: `95` lines (`3678` bytes)

**Classes:**
- `class TestFullPipeline`
  - Method `.test_full_pipeline_success(mock_anki_opener, mock_lm_studio, mock_check_server, mock_open, mock_pypdf2)`
  - Method `.test_pipeline_extraction_failure(mock_lm_studio, mock_check_server, mock_open, mock_pypdf2)`
  - Method `.test_pipeline_llm_malformed_response(mock_lm_studio, mock_check_server)`

---

### [`tests/test_pipeline_utils.py`](tests/test_pipeline_utils.py)
**Size**: `194` lines (`7642` bytes)

**Classes:**
- `class TestPipelineStats`
  - Method `.setUp()`
  - Method `.test_init()`
  - Method `.test_record_times()`
  - Method `.test_increments()`
  - Method `.test_finish(mock_time)`
  - Method `.test_get_summary()`
  - Method `.test_thread_safety()`
- `class TestCardValidator`
  - Method `.test_validate_success()`
  - Method `.test_validate_empty()`
  - Method `.test_validate_too_short()`
  - Method `.test_validate_too_long()`
  - Method `.test_validate_identical()`
- `class TestResourceGuard`
  - Method `.test_check_file_size(mock_getsize)`
  - Method `.test_check_chunk_count()`
- `class TestFailureLogger`
  - Method `.test_log_failed_chunk(mock_file)`
  - Method `.test_log_rejected_card(mock_file)`

---

### [`tests/test_settings_io.py`](tests/test_settings_io.py)
**Size**: `433` lines (`18832` bytes)

**Classes:**
- `class TestApplicationDir`
  - Method `.test_source_checkout_uses_the_module_directory()`
  - Method `.test_frozen_build_uses_the_executable_directory()`
  - Method `.test_frozen_build_falls_back_when_no_executable_is_available()`
- `class TestResolveAppPath`
  - Method `.test_defaults_to_the_application_directory()`
  - Method `.test_honours_an_absolute_environment_override()`
  - Method `.test_resolves_a_relative_override_against_the_application_directory()`
  - Method `.test_an_empty_override_falls_back_to_the_default()`
- `class TestQuarantineCorruptFile`
  - Method `.setUp()`
  - Method `.test_moves_a_corrupt_file_and_preserves_its_content()`
  - Method `.test_returns_none_when_the_file_is_missing()`
  - Method `.test_read_quarantines_malformed_input_when_requested()`
  - Method `.test_read_keeps_a_valid_file_when_quarantine_is_requested()`
- `class TestCleanupStaleTempFiles`
  - Method `.setUp()`
  - Method `.test_removes_only_old_matching_temp_files()`
  - Method `.test_returns_zero_when_the_parent_does_not_exist()`
- `class TestReadJsonFile`
  - Method `.setUp()`
  - Method `.test_returns_the_default_when_the_file_is_missing()`
  - Method `.test_returns_the_default_when_the_file_is_malformed()`
  - Method `.test_returns_the_default_when_the_json_type_does_not_match()`
  - Method `.test_returns_parsed_content_for_a_matching_type()`
  - Method `.test_a_transient_open_error_does_not_quarantine_a_valid_file()`
- `class TestNormalizeConfig`
  - Method `.test_wrong_types_fall_back_to_documented_defaults()`
  - Method `.test_numeric_strings_are_parsed_and_clamped()`
  - Method `.test_density_is_restricted_and_deck_names_are_strings()`
  - Method `.test_unknown_keys_are_preserved()`
- `class TestNormalizeSessionData`
  - Method `.test_valid_cards_are_normalized()`
  - Method `.test_optional_fields_get_safe_defaults()`
  - Method `.test_non_list_or_non_object_entries_are_rejected()`
- `class TestWriteJsonFile`
  - Method `.setUp()`
  - Method `._leftovers()`
  - Method `.test_creates_parent_directories_and_round_trips()`
  - Method `.test_leaves_no_temporary_file_behind()`
  - Method `.test_replaces_existing_content_in_one_step()`
  - Method `.test_honours_the_requested_indent()`
  - Method `.test_rejects_a_directory_target_without_leaving_temporary_files()`
  - Method `.test_preserves_an_existing_restrictive_mode()`
  - Method `.test_preserves_windows_file_attributes()`
  - Method `.test_removes_the_temp_file_when_serialization_fails()`
  - Method `.test_recovers_from_a_transient_replace_failure()`
  - Method `.test_failed_replace_retries_and_keeps_the_old_file()`
  - Method `.test_concurrent_writers_do_not_share_a_temp_file()`
- `class TestEnsureParentDirectory`
  - Method `.test_creates_a_nested_parent_directory()`
- `class TestParseIntSetting`
  - Method `.test_parses_valid_integers()`
  - Method `.test_accepts_surrounding_whitespace()`
  - Method `.test_returns_the_default_for_blank_or_invalid_input()`
  - Method `.test_clamps_to_the_declared_range()`
  - Method `.test_keeps_in_range_values_untouched()`
- `class TestParseFloatSetting`
  - Method `.test_parses_valid_floats()`
  - Method `.test_accepts_surrounding_whitespace()`
  - Method `.test_returns_the_default_for_blank_or_invalid_input()`
  - Method `.test_clamps_to_the_declared_range()`
  - Method `.test_rejects_non_finite_values()`
- `class TestExampleConfig`
  - Method `.test_example_config_matches_the_documented_defaults()`
  - Method `.test_runtime_requirements_are_pinned()`

---

### [`tests/test_transcript_formats.py`](tests/test_transcript_formats.py)
**Size**: `111` lines (`3803` bytes)

**Classes:**
- `class TestTranscriptFormats`
  - Method `.test_parse_vtt_strips_headers_timings_and_tags()`
  - Method `.test_parse_srt_strips_cue_numbers()`
  - Method `.test_parse_podcast_json_segments()`
  - Method `.test_parse_podcast_json_accepts_a_plain_text_field()`
  - Method `.test_parse_podcast_json_accepts_a_string_transcript_field()`
  - Method `.test_parse_podcast_json_rejects_empty_segments()`
  - Method `.test_clean_transcript_removes_rolling_duplicates()`
  - Method `.test_clean_transcript_removes_timestamp_prefixes()`
  - Method `.test_plain_text_is_normalized()`
  - Method `.test_html_transcript_is_rendered_as_text()`
  - Method `.test_format_is_sniffed_without_a_hint()`
  - Method `.test_empty_transcript_is_rejected()`
  - Method `.test_read_transcript_file_uses_its_extension_hint()`

---

### [`tests/test_transcript_sources.py`](tests/test_transcript_sources.py)
**Size**: `628` lines (`28707` bytes)

**Classes:**
- `class _FakeTranscript`
  - Method `.__init__(text)`
  - Method `.fetch()`
- `class _FakeTranscriptList`
  - Method `.__init__(transcript, error)`
  - Method `.find_transcript(codes)`
  - Method `.__iter__()`
- `class TestYouTubeIds`
  - Method `.test_accepts_common_youtube_urls_and_bare_ids()`
  - Method `.test_rejects_channels_playlists_and_other_sites()`
  - Method `.test_language_codes_map_names_and_keep_english_fallback()`
- `class TestYouTubeTranscript`
  - Method `.test_fetches_the_requested_track_and_uses_oembed_metadata()`
  - Method `.test_oembed_failure_is_ignored()`
  - Method `.test_oembed_uses_a_short_bounded_request()`
  - Method `.test_youtube_metadata_failure_falls_back_to_the_video_id()`
  - Method `.test_falls_back_to_any_available_track()`
  - Method `.test_disabled_captions_get_an_actionable_error()`
  - Method `.test_missing_library_reports_the_install_command()`
  - Method `.test_channel_url_is_rejected_before_network_access()`
- `class TestPodcastFeed`
  - Method `.test_finds_the_newest_episode_with_a_transcript()`
  - Method `.test_prefers_the_requested_language()`
  - Method `.test_matches_an_explicit_episode_url()`
  - Method `.test_unknown_episode_url_is_reported()`
  - Method `.test_feed_data_lists_every_transcribed_episode_in_order()`
  - Method `.test_episodes_without_transcripts_are_omitted_from_the_browser()`
  - Method `.test_fetch_podcast_feed_downloads_the_feed_once()`
  - Method `.test_fetch_podcast_transcript_for_ref_downloads_only_the_transcript()`
  - Method `.test_feed_without_transcript_tags_is_reported()`
  - Method `.test_invalid_xml_is_reported()`
  - Method `.test_fetch_podcast_transcript_downloads_feed_and_cue_file()`
- `class TestApplePodcasts`
  - Method `.test_show_and_episode_urls_are_recognized()`
  - Method `.test_resolve_show_url_uses_the_itunes_feed()`
  - Method `.test_resolve_episode_url_reads_the_page_title()`
  - Method `.test_apple_page_title_reads_open_graph_metadata()`
  - Method `.test_apple_show_url_uses_the_newest_transcribed_episode()`
  - Method `.test_apple_episode_url_matches_the_transcript_by_title()`
  - Method `.test_short_episode_numbers_do_not_match_by_prefix()`
  - Method `.test_apple_episode_without_a_transcript_is_reported()`
  - Method `.test_apple_episode_without_a_title_is_reported()`
  - Method `.test_fetch_podcast_feed_resolves_an_apple_show_url()`
- `class TestDirectTranscriptUrls`
  - Method `.test_direct_vtt_url_is_parsed()`
  - Method `.test_rss_url_is_detected_from_content_type()`
  - Method `.test_youtube_url_is_dispatched_without_downloading_a_page()`
  - Method `.test_pdf_url_is_extracted_with_pypdf2()`
  - Method `.test_pdf_is_detected_from_magic_bytes()`
  - Method `.test_website_url_extracts_the_article_not_the_navigation()`
  - Method `.test_website_without_readable_text_is_reported()`
  - Method `.test_video_url_is_downloaded_and_transcribed()`
  - Method `.test_audio_url_is_downloaded_and_transcribed()`
  - Method `.test_missing_media_transcription_package_is_reported()`
  - Method `.test_media_download_limit_is_enforced()`
  - Method `.test_media_url_returning_html_is_rejected()`
  - Method `.test_audio_content_type_without_a_media_extension_is_rejected()`
  - Method `.test_empty_url_is_rejected()`
  - Method `.test_http_error_is_wrapped()`
  - Method `.test_oversized_download_is_refused()`

**Functions:**
- `def _fake_youtube_api(transcript_list)`

---

### [`tests/test_ui_media.py`](tests/test_ui_media.py)
**Size**: `35` lines (`1283` bytes)

**Classes:**
- `class TestPodcastChooserShortcuts`
  - Method `.test_single_episode_is_returned_without_opening_a_dialog()`
  - Method `.test_empty_feed_returns_none()`

---

### [`tests/test_ui_themes.py`](tests/test_ui_themes.py)
**Size**: `21` lines (`553` bytes)

**Classes:**
- `class TestThemeAllowlist`
  - Method `.test_allowlist_matches_the_installed_ttkbootstrap_themes()`

---

### [`tests/test_web_extraction.py`](tests/test_web_extraction.py)
**Size**: `87` lines (`4093` bytes)

**Classes:**
- `class TestArticleExtraction`
  - Method `.test_extracts_the_article_and_drops_boilerplate()`
  - Method `.test_uses_main_when_there_is_no_article()`
  - Method `.test_falls_back_to_body_paragraphs()`
  - Method `.test_title_falls_back_to_the_url_slug()`
  - Method `.test_wiki_style_vector_wrappers_are_removed()`
  - Method `.test_rejects_empty_html()`
  - Method `.test_reports_missing_lxml()`

---

### [`transcript_formats.py`](transcript_formats.py)
> *Parse transcript formats into the plain text NeuralDeck sends to the LLM.*

**Size**: `228` lines (`7625` bytes)

**Classes:**
- `class _HTMLTextExtractor` - *Collect readable text while ignoring scripts, styles and markup.*
  - Method `.__init__()`
  - Method `.handle_starttag(tag, attrs)`
  - Method `.handle_endtag(tag)`
  - Method `.handle_data(data)`
  - Method `.get_text()`

**Functions:**
- `def _html_to_text(text)`
- `def _is_noise_line(line)`
- `def _parse_timed_cues(text)` - *Shared VTT/SRT cue parser: keep the text after each timing line.*
- `def parse_vtt(text)` - *Extract cue text from a WebVTT transcript.*
- `def parse_srt(text)` - *Extract cue text from a SubRip transcript.*
- `def _iter_segments(data)`
- `def parse_podcast_json(text)` - *Extract text from Podcasting 2.0 JSON and similar segment lists.*
- `def _merge_overlap(previous, line)` - *Merge YouTube-style rolling captions that share a word boundary.*
- `def clean_transcript_text(text)` - *Normalize captions into one readable block and drop rolling duplicates.*
- `def parse_transcript(text, hint)` - *Convert transcript text to plain text, sniffing the format when needed.*
- `def read_transcript_file(file_path)` - *Read a transcript file and return normalized plain text.*

---

### [`transcript_sources.py`](transcript_sources.py)
> *Fetch card source transcripts from YouTube, podcast feeds and URLs.*

**Size**: `917` lines (`35266` bytes)

**Classes:**
- `class TranscriptError` - *A user-facing transcript failure that explains why and how to fix it.*
- `class TranscriptResult`
- `class PodcastTranscriptRef`
- `class PodcastFeed`
- `class ApplePodcastSource`

**Functions:**
- `def language_codes(language)` - *Map a UI language name to the ISO codes YouTube expects.*
- `def extract_youtube_video_id(value)` - *Return the 11-character video id from a YouTube URL or bare id.*
- `def _is_youtube_url(value)`
- `def _fetch_url_bytes(url, max_bytes, timeout)`
- `def _decode(data, charset)`
- `def extract_apple_podcast_ids(value)` - *Return (collection_id, episode_id) from an Apple Podcasts URL.*
- `def _fetch_json(url, max_bytes, timeout)`
- `def _youtube_metadata(video_id)` - *Read the public title and channel through YouTube's oEmbed endpoint.*
- `def _apple_page_title(url)` - *Read the episode title from Apple's Open Graph metadata.*
- `def resolve_apple_podcast_url(url)` - *Resolve an Apple Podcasts show or episode URL to its RSS feed.*
- `def _normalized_title(value)`
- `def _titles_overlap(left, right)` - *Allow a long-title prefix, but never a short episode number.*
- `def _find_episode_by_title(feed, title)`
- `def _select_feed_episode(feed, language)`
- `def _load_youtube_transcript_api()`
- `def _youtube_error_message(video_id, exc)`
- `def fetch_youtube_transcript(url_or_id, language, log_callback)` - *Download the best available caption track for a YouTube video.*
- `def _local_name(tag)`
- `def _child(element, name)`
- `def _text_of(element, name)`
- `def _normalized_url(value)`
- `def _choose_transcript(transcripts, language)`
- `def _transcript_ref(item, feed_title, language)`
- `def _parse_feed_items(xml_text, language)`
- `def parse_podcast_feed_data(xml_text, feed_url, language)` - *Parse a Podcasting 2.0 feed into its transcribed episodes.*
- `def parse_podcast_feed(xml_text, feed_url, episode_url, language)` - *Find a Podcasting 2.0 transcript link in an RSS feed.*
- `def _hint_from_type(content_type)`
- `def _hint_from_url(url)`
- `def _transcript_from_ref(ref, log_callback)`
- `def fetch_podcast_feed(feed_url, language, log_callback)` - *Download and parse a feed into its transcribed episodes.*
- `def fetch_podcast_transcript_for_ref(ref, log_callback)` - *Download the transcript already selected from a podcast feed.*
- `def fetch_podcast_transcript(feed_url, episode_url, language, log_callback)` - *Download a transcript linked from a Podcasting 2.0 RSS feed.*
- `def _looks_like_feed(url, content_type, text)`
- `def _looks_like_pdf(url, content_type, data)`
- `def _looks_like_html(url, content_type, text)`
- `def _url_filename(url)`
- `def _looks_like_media_url(url)`
- `def _remove_temp(path)`
- `def _download_media_to_temp(url, log_callback, max_bytes)` - *Stream a bounded audio/video URL to a temporary local file.*
- `def _media_transcript(url, log_callback)`
- `def _pdf_transcript(data, url, log_callback)`
- `def _web_transcript(raw, url, log_callback)`
- `def fetch_transcript_from_url(url, language, log_callback)` - *Fetch a transcript from a YouTube link, podcast feed or transcript URL.*

---

### [`ui.py`](ui.py)
**Size**: `1228` lines (`55526` bytes)

**Classes:**
- `class TextWidgetHandler` - *Custom logging handler that writes to a Tkinter ScrolledText widget thread-safely.*
  - Method `.__init__(text_widget, root)`
  - Method `.emit(record)`
  - Method `.append_log(msg)`
- `class CardReviewRow` - *A row representing a single generated card for review.*
  - Method `.__init__(parent, question, answer, assigned_deck, available_decks, quote, on_remove)`
  - Method `.get_data()`
  - Method `.show_source()`
  - Method `.remove_row()`
- `class AnkiGeneratorUI`
  - Method `.__init__()`
  - Method `.setup_logging()`
  - Method `.setup_main_tab()`
  - Method `.setup_settings_tab()`
  - Method `.load_config()`
  - Method `._read_int(var, default, minimum, maximum)` - *Read a numeric Tk variable without letting an empty field crash the UI.*
  - Method `._read_float(var, default, minimum, maximum)` - *Read a decimal Tk variable without letting an empty field crash the UI.*
  - Method `.save_settings_ui()`
  - Method `.save_config()`
  - Method `.apply_theme(event)`
  - Method `.fetch_decks()`
  - Method `._fetch_decks_thread()`
  - Method `.update_deck_list_ui()`
  - Method `.save_deck_selection()`
  - Method `.select_file()`
  - Method `.import_media_url()` - *Fetch a transcript, article or PDF from a URL.*
  - Method `._import_media_url_worker(url, language)`
  - Method `.browse_podcast()` - *List a feed's transcribed episodes and fetch the chosen one.*
  - Method `._browse_podcast_worker(url, language)`
  - Method `._choose_podcast_episode(feed)`
  - Method `._fetch_podcast_episode_worker(selected)`
  - Method `._handle_import_error(exc)`
  - Method `._set_import_busy(busy)`
  - Method `._apply_imported_transcript(result)`
  - Method `._reset_import_controls()`
  - Method `.preview_transcript()` - *Show the text that will be sent to the LLM, extracting it if needed.*
  - Method `._preview_file_worker(file_path)`
  - Method `._preview_ready(file_path, text)`
  - Method `._preview_failed(exc)`
  - Method `._set_preview_busy(busy)`
  - Method `.start_processing()`
  - Method `.run_process(file_path, target_lang, api_url, api_key, model, temperature, max_tokens, prompt_style, deck_names, context_window, concurrency, card_density, filter_yes_no, exclude_trivia, smart_deck_match, ai_refinement, deterministic_mode, preloaded_text)`
  - Method `._finish_processing()`
  - Method `.clear_review_area()`
  - Method `.add_manual_card()` - *Adds a blank card row for manual authoring.*
  - Method `.append_cards_to_review(new_cards)`
  - Method `.remove_card_row(row)`
  - Method `.save_session()` - *Saves the current state of generated cards to a JSON file.*
  - Method `.load_session()` - *Restores cards from the session cache file.*
  - Method `.stop_processing()`
  - Method `.on_close()` - *Handle window closing event to ensure all threads are killed.*
  - Method `.clear_all_cards()`
  - Method `.toggle_all_approvals(state)`
  - Method `.bulk_assign_deck()` - *Assigns the selected deck to all checked cards.*
  - Method `.sync_to_anki()`

**Functions:**
- `def choose_podcast_episode(parent, feed)` - *Show the feed's transcribed episodes and return the chosen reference.*
- `def show_text_preview(parent, title, text)` - *Display a read-only transcript preview without modifying the source.*

---

### [`web_extraction.py`](web_extraction.py)
> *Readable article extraction from HTML pages.*

**Size**: `139` lines (`4832` bytes)

**Classes:**
- `class WebArticle`

**Functions:**
- `def _normalize(value)`
- `def _drop_boilerplate(document)`
- `def _page_title(document)`
- `def _candidate_root(document)`
- `def _paragraphs(root)`
- `def _fallback_title(url)`
- `def extract_article(html_text, url)` - *Return the readable title and body text of an HTML page.*

---
