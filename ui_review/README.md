# NeuralDeck UI improvement — before / after evidence

Captured live from the running Tk application with `PrintWindow`
(`scratch/nd_capture.py`, kept in the AIKit workspace scratch area).
Baseline: commit `dcf2152`, theme `darkly`, window ~1216x839.

## Change 1 — Theme-consistent text areas

| Before | After |
|---|---|
| `01_before_generator.png` | `01_after_generator.png` |
| `02_before_settings.png` | `02_after_settings.png` |

**Before (analysis).** The `darkly` ttk theme styled the Notebook, buttons and
labelframes, but the three Tk `Text`/`ScrolledText` widgets were never themed:
the Generator log console and the Settings custom-prompt editor both rendered
as bright white rectangles with black text and light scrollbars. This broke the
dark visual language, pulled attention away from the workflow, and made the log
hard to scan. The transcript-preview dialog had the same defect.

**After (analysis).** All text areas now derive their palette from the active
ttkbootstrap theme (`themed_text_options()`): dark input background, theme
foreground, themed selection and caret colours, and a subtle themed border. The
log also uses a monospace font (`Consolas 9`), which suits timestamped/technical
output. The two tabs now look like one coherent application, and switching the
theme at runtime repaints the text widgets (`apply_theme` was extended).

## Change 2 — Onboarding empty state in the Review pane

| Before | After |
|---|---|
| `01_after_generator.png` (blank review area) | `03_after_empty_state.png` |

**Before (analysis).** The top "Review & Source Comparison" panel occupied
roughly a third of the window but was an empty dark rectangle on first run.
There was no indication that generated cards appear there, or what to do next —
a common first-run drop-off point.

**After (analysis).** A centred placeholder (brain icon, "No cards to review
yet", and a two-line hint pointing at the input controls) now explains the next
action. It is removed as soon as the first card is added and returns when the
last card is deleted, so it never competes with real content. Verified in
`05_verify_card_added.png`: adding a manual card hides the placeholder and
enables the sync button.

## Change 3 — Live status bar

| Before | After |
|---|---|
| `03_after_empty_state.png` (no status feedback) | `04_after_status_bar.png` |

**Before (analysis).** The only feedback about state was buried in the log:
connection failures and card counts had to be read from four lines of small
text. The Settings pane also clipped its "Save Settings" button at the original
1200x800 window size.

**After (analysis).** A status strip at the bottom of the Generator tab shows
`Ready / Generating…`, `N cards · N approved`, and the live Anki connection
state. Counts update immediately when cards are added, removed or approved
(including Check All / Uncheck All), and the connection label follows the deck
fetch result. Window height grew to 1200x850, which also reveals the previously
clipped "Save Settings" button in the Settings tab.

## Cross-theme verification

`06_verify_light_theme.png` proves the theme fix is dynamic: after switching to
the light `litera` theme at runtime, the log console flips to a white background
with dark text while the rest of the UI follows the light palette. The status
bar remains legible.

## Change 4 — Clearer action hierarchy and deck guidance

| Before | After |
|---|---|
| `07_before_hierarchy_generator.png` | `07_after_hierarchy_generator.png` |

**Before (analysis).** "Select Document / Media" — the first step in every
workflow — used a thin `primary-outline` style and read as disabled next to the
solid green "Generate Cards". The "Available Decks" panel was an empty area with
one lone checkbox and no explanation of what ticking (or not ticking) does.

**After (analysis).** The source-selection button is now a filled `primary`
button, establishing a clear entry point, while "Import URL / Media" and
"Browse Podcast" remain outline-styled secondary actions. A one-line hint in
the deck panel explains that ticking restricts decks and leaving all unticked
lets the AI choose from every deck. The file label also moved off the legacy
Helvetica font to Segoe UI for consistency.

## Change 5 — Masked API key with reveal toggle

| Before | After |
|---|---|
| `08_before_key_masking.png` | `08_after_key_masking.png` |
| Reveal proof: `09_verify_key_revealed.png` | |

**Before (analysis).** The API key was displayed in plain text in Settings,
readable at a glance by anyone near the screen, even though it is a credential.

**After (analysis).** The field is masked by default and paired with a
`Show` / `Hide` button. The stored value is untouched. A live harness confirmed
the toggle: `show='•'` / button `Show` → `show=''` / button `Hide`, and the
revealed screenshot shows the real value. This is both a privacy and a UI
clarity improvement.

## Change 6 — Colour-coded status indicators

| Before | After |
|---|---|
| `10_after_status_colors.png` (status text) | same file, coloured state |

**Before (analysis).** Status text was uniformly neutral, so a failed Anki
connection was easy to miss among the labels.

**After (analysis).** `_refresh_status()` now pulls semantic colours from the
theme palette: green for `Ready`, amber for `Generating…`, green for
`Anki: connected`, red for `Anki: not connected`, blue while checking. Colours
re-apply on theme changes. The screenshot shows green "● Ready" alongside red
"Anki: not connected" — the state is now readable at a glance.

## Change 7 — Always-visible Save Settings footer

| Before | After |
|---|---|
| `11_before_save_footer.png` | `11_after_save_footer.png` |

**Before (analysis).** "Save Settings" lived at the bottom of the scrollable
settings form. At the default window size it was clipped by the lower window
edge — only the top half of the button was visible, forcing the user to scroll
just to save.

**After (analysis).** The button moved into a fixed footer packed to the bottom
of the Settings tab, separated from the scrolling form by a themed divider and
labelled "Saved to config.json". It is now fully visible and reachable at any
scroll position. The command wiring is unchanged; only the layout moved.

## Change 8 — Card-dependent bulk controls

| Before | After | Enabled proof |
|---|---|---|
| `12_before_bulk_controls.png` | `12_after_bulk_controls.png` | `13_verify_bulk_enabled.png` |

**Before (analysis).** With zero cards, the deck combo and "Move Selected"
were still styled as active, and "Clear All" was still a red clickable link —
inviting actions that could do nothing. "Check All" / "Uncheck All" used a grey
`secondary-outline` style, so they looked disabled even when cards existed.

**After (analysis).** All card-dependent controls now follow the card count via
`_sync_review_placeholder()`: Check All, Uncheck All, Move Selected and the bulk
deck combo are disabled while the review pane is empty and switch to normal /
readonly as soon as the first card arrives. Clear All stays available for a
blocked session so a corrupt cache can still be discarded. Check All / Uncheck
All moved to `info-outline` so their enabled state actually reads as enabled.
A live harness confirmed the transition:
`{check_all: disabled, move_selected: disabled, bulk_combo: disabled, clear_all: disabled}`
→ `{check_all: normal, move_selected: normal, bulk_combo: readonly, clear_all: normal}`.

## Change 9 — Labelled console with Clear control

| Before | After | Cleared proof |
|---|---|---|
| `14_before_log_control.png` | `14_after_log_control.png` | `15_verify_log_cleared.png` |

**Before (analysis).** The log console was an unlabelled text area. During long
generation sessions it accumulated output with no in-app way to clear the view,
so old runs mixed with new ones.

**After (analysis).** The console now has an "Activity Log" header with a
`Clear` button. `clear_log()` temporarily enables the read-only Text widget,
deletes its contents and restores the disabled state; the file handler still
writes the full history to `session.log`, so nothing is lost. A live harness
invoked the actual button: log length 180 → 0 characters, widget state remained
`disabled` afterwards.

## Change 10 — Informative source box

| Before | After |
|---|---|
| `16_before_source_box.png` | `16_after_source_box.png` |

**Before (analysis).** The source box showed only "No file selected". Nothing
indicated which formats were accepted or that a URL could be pasted instead,
so first-time users had to discover both by trial and error or by reading the
README.

**After (analysis).** The box now uses a two-line hierarchy: a bold status line
(`No file selected` / the chosen source) plus a smaller hint listing the
supported inputs — PDF, Word, PowerPoint, text, VTT/SRT, audio/video — and
pointing to the URL import below. The file label widget and its tooltip are
unchanged, so existing file/URL selection logic still updates it normally.

## Change 11 — Legible Clear button

| Before | After |
|---|---|
| `17_before_clear_button.png` | `17_after_clear_button.png` |

**Before (analysis).** The Activity Log's `Clear` button used the
`secondary-outline` bootstyle, which renders as faint grey text in the `darkly`
theme. It was almost invisible and read as disabled, even though clicking it
worked — the same affordance problem previously fixed for the review toolbar.

**After (analysis).** Switching it to `info-outline` gives it a blue outline
consistent with the other enabled secondary actions ("Import URL / Media",
"Check All"). Its command is unchanged; a live `.invoke()` still takes the
console from 180 characters to 0 while leaving the widget read-only.

## Change 12 — Unsaved-changes indicator in Settings

| Before | After (saved) | After (edited) |
|---|---|---|
| `18_before_dirty_indicator.png` | `18_after_saved_state.png` | `19_verify_unsaved_state.png` |

**Before (analysis).** The Settings footer showed a static "Saved to config.json"
label even after edits, so there was no warning that clicking away would discard
changes made since the last save.

**After (analysis).** The footer label is now stateful and colour-coded: green
"● Saved to config.json" when clean, amber "● Unsaved changes" after any edit.
Every setting variable carries a write trace, and the custom-prompt text area
uses a guarded `<<Modified>>` handler (it only resets the flag when set, avoiding
a virtual-event loop). `save_settings_ui()` clears the flag on both successful
save paths. A live harness confirmed:
`Saved to config.json / dirty=False` → `Unsaved changes / dirty=True` after a
model-name edit, and the prompt edit kept it dirty.

## Change 13 — Self-explanatory card rows

| Before | After | Empty-card proof |
|---|---|---|
| `20_before_card_rows.png` | `20_after_card_rows.png` | `21_verify_placeholders.png` |

**Before (analysis).** A review row showed two visually identical entry boxes.
Only their vertical order identified which was the question and which the
answer — ambiguous when scanning a long list. The source-context button used a
`❝` glyph that rendered as a tiny unreadable mark, and a manually added blank
card had no guidance for what to type.

**After (analysis).** Each row now has bold `Q` / `A` markers beside the two
fields, placeholder text ("Question — what do you want to ask?" / "Answer — the
ideal response") for empty manual cards, and a word-labelled `Source` button
instead of the cryptic glyph. The widgets, `get_data()` keys and callbacks are
unchanged — only column positions, labels and placeholders moved. Screenshots
show both a filled generated-style card and a blank manual card.

## Change 14 — Progress indicator for generation

| Before | After (idle) | After (busy) |
|---|---|---|
| `22_before_progress.png` | `22_after_progress_idle.png` | `23_verify_processing.png` |

**Before (analysis).** The status bar's amber "Generating…" text was the only
sign that a long LLM run was active. With a slow local model, users could not
tell whether the app was working or stuck.

**After (analysis).** An indeterminate `Progressbar` sits in the status bar.
`_refresh_status()` starts it when `processing` becomes true and stops it when
processing finishes, using a `_progress_running` guard so repeated refreshes do
not restart the animation. The busy screenshot shows the moving segment beside
"● Generating…"; the idle screenshot shows an inert trough. A live harness
confirmed `IDLE running=False` → `BUSY running=True` → `STOPPED running=False`.

## Change 15 — All / None deck shortcuts

| Before | After |
|---|---|
| `24_before_deck_shortcuts.png` | `24_after_deck_shortcuts.png` |

**Before (analysis).** Selecting which decks the AI may assign cards to meant
ticking each checkbox individually. With a real Anki collection of many decks,
that is tedious; leaving everything unticked is also a meaningful "let the AI
choose from all decks" state that was hard to reach quickly.

**After (analysis).** The "Available Decks" panel now has `All` and `None`
buttons above the deck list. `_set_all_decks()` sets every discovered deck
variable and calls the existing `save_deck_selection()`, so bulk selection is
persisted exactly like manual ticking. A live harness confirmed
`{'Default': False}` → `{'Default': True}` → `{'Default': False}`. The temporary
`config.json` written by that harness was removed afterwards to keep the
workspace in its original state.

## Change 16 — Contextual counts in section headers

| Before | After | Idle proof |
|---|---|---|
| `25_before_header_counts.png` | `25_after_header_counts.png` | `26_verify_idle_header.png` |

**Before (analysis).** Both main section titles were static: "Review & Source
Comparison" and "Available Decks". With many cards or decks, the user had to
scan the list (or read the status bar) to know how many were present.

**After (analysis).** The review header appends the card count
("Review & Source Comparison — 1 card") and reverts to the plain title when the
list is empty; the deck header shows "Available Decks (1)". The review title is
updated by the existing `_sync_review_placeholder()` hook (so it stays correct
on add/remove/clear/restore), and the deck title is set where the deck list is
built. Screenshots verify both the populated and empty states.

## Change 17 — Keyboard shortcuts for primary actions

| Before | After |
|---|---|
| `27_before_shortcuts.png` | `27_after_shortcuts.png` |

**Before (analysis).** The two actions used every session — choosing a source
and generating cards — were mouse-only, with no visible hint that a faster
keyboard path existed.

**After (analysis).** The buttons now advertise `(Ctrl+O)` and `(Ctrl+Enter)`,
and the toplevel binds those keys to guarded handlers. The guards check the
button state, `processing` and `preview_loading`, so shortcuts never fire while
the app is busy; they are bound on the toplevel so they also work while typing
in an entry or the prompt editor. A live harness confirmed both bindings exist,
that disabled buttons produce no calls (`WHILE_DISABLED []`), and that enabled
buttons dispatch (`WHILE_ENABLED ['generate', 'select']`).

## Change 18 — Copy log for diagnostics

| Before | After |
|---|---|
| `28_before_copy_log.png` | `28_after_copy_log.png` |

**Before (analysis).** The Activity Log had only a Clear button. The project's
contribution guide asks users to include logs when reporting issues, but there
was no way to get the console text out of the app except manual selection.

**After (analysis).** A `Copy` button now sits beside `Clear` in the log header.
`copy_log()` places the on-screen console text on the system clipboard and adds
a confirmation line to the log; it is a no-op when the console is empty. A live
harness invoked the real button and confirmed the clipboard contained exactly
the console text (`EXPECTED_LEN 180 COPIED_LEN 180 MATCH True`).

## Change 19 — Reset settings to defaults

| Before | After |
|---|---|
| `29_before_reset.png` | `29_after_reset.png` |

**Before (analysis).** Once settings had been customized, there was no way to
get back to the shipped configuration short of editing `config.json` by hand or
reinstalling.

**After (analysis).** A `Reset` button sits beside `Save Settings` in the fixed
footer. It asks for confirmation, then restores every field from the tracked
`config.example.json`, re-applies the theme, clears the dirty indicator and
persists the result. A live harness changed model/temperature/prompt and then
reset:
`BEFORE totally-custom-model 0.99 dirty=True` →
`AFTER local-model 0.7 dirty=False`, `PROMPT ''`. The `config.json` written by
that harness was removed afterwards to restore the original workspace state.

## Change 20 — Contextual source-ready hint

| Before | After |
|---|---|
| `30_before_source_ready.png` | `30_after_source_ready.png` |

**Before (analysis).** After selecting a file or importing a URL, the source
box kept showing the generic format list ("PDF · Word · … — or paste a URL
below"). The useful information — that a source is loaded and what to do next —
was missing at the exact moment it mattered.

**After (analysis).** The subtitle is now stateful. With no source it keeps the
format help; once a file is chosen or a transcript imported, it turns green and
reads "Source ready — preview it, then press Ctrl+Enter to generate." Both
selection paths call the same `_set_source_hint()` helper, so local files and
URL imports stay consistent. Screenshots were taken with a simulated file
pick (`filedialog.askopenfilename` patched in a scratch harness).

## Change 21 — Retry Anki connection

| Before | After |
|---|---|
| `31_before_retry.png` | `31_after_retry.png` |

**Before (analysis).** The Anki bridge was contacted only once at startup. If
the user launched Anki later — a common workflow — the deck list stayed empty
and the status stayed red until the whole app was restarted.

**After (analysis).** A `Retry` button now sits beside the connection label in
the status bar. It disables itself while the check runs, sets the status to
"checking", re-runs the existing deck-fetch thread, and is re-enabled when the
deck list is rebuilt. A live harness with a deliberately slow fake fetch showed
the full lifecycle: `connected / normal` → `checking / disabled` →
`connected / normal`, with `available_decks` updated to the new values.

## Change 22 — Selected-deck count

| Before | After |
|---|---|
| `32_before_deck_count.png` | `32_after_deck_count.png` |

**Before (analysis).** With several decks, the All/None shortcuts left no
indication of how many decks were actually selected. Because zero selected has
the special meaning "let the AI choose from every deck", the user had to inspect
each checkbox to know what would happen.

**After (analysis).** A label beside All/None now reads `All decks` when nothing
is ticked (the special auto mode) or `N selected` otherwise. It is refreshed by
`save_deck_selection()` and after the deck list is rebuilt, so manual ticks and
bulk shortcuts agree. A live harness confirmed:
`All decks` → `1 selected` (All) → `All decks` (None). The temporary config file
written by that harness was removed afterwards.

## Change 23 — Card Density on the Generator tab

| Before | After |
|---|---|
| `33_before_generator_density.png` | `33_after_generator_density.png` |

**Before (analysis).** Card Density — one of the most frequently adjusted knobs
for a given document — lived only in the Settings tab, so tuning it required a
tab switch during every generation run.

**After (analysis).** A `Card Density` combobox now sits beside Card Language in
Input Configuration. It shares a single `StringVar` with the Settings control,
so changing it in either place updates both, and `start_processing()` already
read that same variable. Selecting a value writes it to `config.json`. The
extra row reduced the review panel's height, so the empty-state icon, heading
and padding were tightened to keep the guidance fully visible. A live harness
confirmed `Medium` → `High`, with the combobox and config both following and a
config save issued.

## Change 24 — Offline notice in the deck panel

| Before | After |
|---|---|
| `34_before_deck_warning.png` | `34_after_deck_warning.png` |

**Before (analysis).** When the Anki bridge was unreachable, the deck panel
silently fell back to a single local "Default" deck. The red status-bar label
was easy to miss, and nothing in the panel explained why only one deck existed.

**After (analysis).** An amber line — "Anki offline — using local 'Default'
deck." — appears in the Available Decks panel whenever the fetch reports a
disconnected bridge, and is removed once decks load. Harness verification:
with a failing bridge, `STATUS disconnected WARNING_SHOWN True`; after a
successful fetch, `STATUS connected … WARNING_SHOWN False`. An initial attempt
to position the notice with `pack(before=…)` raised a TclError against the
ScrolledFrame wrapper; that was caught in verification and replaced with a
plain pack, after which the update path completed cleanly.

## Change 25 — Focus the new manual card's question

| Before | After |
|---|---|
| `35_before_card_focus.png` | `35_after_card_focus.png` |

**Before (analysis).** Clicking "Add Manual Card" created a blank row but left
keyboard focus on the button, so the user had to click into the question field
before typing — an extra step on a workflow whose whole purpose is typing.

**After (analysis).** `add_manual_card()` now calls `focus_set()` on the new
row's question entry. The after screenshot shows the focus highlight and caret
in the Q field, and a live harness confirmed the focused widget is the
`CardReviewRow` entry (`focus= …!cardreviewrow.!entry`). Generated cards and
restored sessions are unaffected; only the manual-authoring path changed.

## Change 26 — Numbered review cards

| Before | After |
|---|---|
| `36_before_card_indices.png` | `36_after_card_indices.png` |

**Before (analysis).** A long review list was a stack of identical-looking
rows. Referring to a specific card ("the third one") required counting from the
top, and there was no stable position marker.

**After (analysis).** Each row now shows a bold `#N` position marker before the
Q/A fields. `_refresh_card_indices()` runs from the existing card-change hook,
so numbering stays correct after additions, removals, bulk clear and session
restore. A live harness confirmed `BEFORE ['#1', '#2', '#3']` →
`AFTER ['#1', '#2']` after removing the middle card. The row grid was shifted by
one column to make room; no callbacks or data keys changed.

## Change 27 — Active model in the status bar

| Before | After |
|---|---|
| `37_before_model_status.png` | `37_after_model_status.png` |

**Before (analysis).** The configured model name was only visible on the
Settings tab, so a user confirming which model a run would use had to switch
tabs mid-workflow.

**After (analysis).** The status bar now includes `Model: local-model`. It is
driven by the same `model_var` as Settings, with a write trace so edits show up
immediately, and is initialized when Settings finishes building so it never
shows a stale placeholder. A live harness confirmed:
`BEFORE Model: local-model` → `AFTER Model: llama3-8b`.

## Change 28 — Save button reflects unsaved state

| Before | After |
|---|---|
| `38_before_save_button.png` | `38_after_save_button.png` |

**Before (analysis).** The footer warned "● Unsaved changes" in amber, but the
action button stayed green and read "Save Settings" — the label didn't tell the
user what the button would do at that moment.

**After (analysis).** `_refresh_settings_status()` now also restyles the button:
it becomes amber and reads "Save Changes" while dirty, then returns to green
"Save Settings" after a successful save or reset. Harness verification:
`BUTTON Save Changes warning.TButton` after an edit, and
`BUTTON Save Settings primary.TButton` after reset. The command wiring is
unchanged.

## Change 29 — Confirm quitting with unsaved settings

| Before | After |
|---|---|
| `39_before_quit_guard.png` (dirty state, no protection) | `39_after_quit_guard.png` (confirmation dialog) |

**Before (analysis).** Closing the window while Settings were dirty silently
discarded those edits; the unsaved-changes label had no effect on quit.

**After (analysis).** `on_close()` now asks "You have unsaved settings changes.
Quit without saving them?" when the dirty flag is set. Cancelling aborts the
close; confirming proceeds with the existing session save/shutdown path. A live
harness verified `NO_ANSWER destroyed=False`, `YES_ANSWER destroyed=True`, and
`CLEAN destroyed=True` (no prompt when nothing is unsaved). The dialog
screenshot was captured from the running app with `PrintWindow` on the
messagebox window.

## Change 30 — Generation summary in the review area

| Before | After |
|---|---|
| `40_before_run_summary.png` | `40_after_run_summary.png` |

**Before (analysis).** The pipeline's timing and card/chunk statistics were
written only to the log console, which users scroll away from while reviewing
the generated cards.

**After (analysis).** A dedicated header above the review list now shows the
completed run's summary — duration, chunks processed/failed and cards
generated/rejected — using the exact `PipelineStats.get_summary()` text.
`show_generation_summary()` is called from the pipeline's completion callback;
the label is cleared at the start of the next run via `clear_review_area()`.
An initial attempt packed the label after the ScrolledFrame and it was hidden
below the cards; a dedicated header frame fixed the order. Harness verification:
`SHOWN True`, `CLEARED False`.

## Change 31 — Custom prompt character count

| Before | After |
|---|---|
| `41_before_prompt_count.png` | `41_after_prompt_count.png` |

**Before (analysis).** The custom prompt editor gave no indication of how much
instruction text had been entered, which matters when tuning prompts for a
local model with a limited context window.

**After (analysis).** A small right-aligned `N characters` label sits under the
prompt editor and updates on every edit through the existing `<<Modified>>`
handler, with singular/plural handling and thousands separators. It is
initialized from the stored value and refreshed after Reset. Live harness:
typing "Focus on mechanisms." produced `COUNT 20 characters`, visible in the
after screenshot.

## Change 32 — Test LLM connection

| Before | After |
|---|---|
| `42_before_llm_test.png` | `42_after_llm_test.png` |

**Before (analysis).** Users could only discover a wrong API URL, key or server
state by starting a full generation run and waiting for it to fail.

**After (analysis).** A `Test Connection` button in AI Server Configuration
calls the existing `check_llm_server()` probe on a daemon thread, so the UI
stays responsive. It disables itself and reads "Testing…" while probing, then
restores and reports success or failure via a dialog plus a log line. A live
harness confirmed both paths:
- success → `normal / Test Connection / Connected to LLM server at …`
- failure → `normal / Test Connection / Could not reach LLM server: refused`

## Change 33 — Optional timestamps in the Activity Log

| Before | After |
|---|---|
| `43_before_timestamp_toggle.png` | `43_after_timestamp_toggle.png` |

**Before (analysis).** The on-screen log formatter showed messages only; the
file handler had timestamps, but users diagnosing a problem in the app could
not see when each event happened.

**After (analysis).** A `Time: Off / Time: On` button in the log header swaps
the UI handler's formatter between `%(message)s` and `[%(asctime)s] %(message)s`
with a compact `%H:%M:%S` date format. The button recolours to show the active
state. A live harness confirmed the console tail gained
`[10:59:49] Timestamped diagnostic line.` and that toggling back restored
`Time: Off`. The file handler and log content are unchanged.

## Change 34 — Approval progress in the review header

| Before | After |
|---|---|
| `44_before_approved_header.png` | `44_after_approved_header.png` |

**Before (analysis).** The review header showed only the card count, so the
user had to look down at the status bar (or count toggles) to know how many
cards were approved for sync.

**After (analysis).** The header now reads e.g.
"Review & Source Comparison — 3 cards · 1 approved". To keep it live, the
per-row approve callback and Check All / Uncheck All now route through
`_sync_review_placeholder()` (which already refreshes the header, status bar
and indices) rather than only `_refresh_status()`. Live harness:
`3 cards · 3 approved` → `3 cards · 2 approved` after a single toggle →
`3 cards · 3 approved` after Check All.

## Change 35 — Persistent review scrollbar

| Before | After |
|---|---|
| `45_before_review_scrollbar.png` | `45_after_review_scrollbar.png` |

**Before (analysis).** The review `ScrolledFrame` used `autohide=True`, so with
more cards than fit, the last row was simply cut off with no visible affordance
that the area scrolled.

**After (analysis).** `autohide=False` keeps a vertical scrollbar visible in
the review panel, making scrollability obvious and the hidden cards reachable.
A live harness walked the review container's widget tree and found
`SCROLLBARS 1 MAPPED [True]`. An initial verification attempt queried
`cget("autohide")`, which is not a readable Tk option; the check was rewritten
to inspect the actual mapped scrollbar instead.

## Change 36 — Session restoration note

| Before | After |
|---|---|
| `46_before_restore_note.png` | `46_after_restore_note.png` |

**Before (analysis).** Cards restored from `session_cache.json` appeared in the
review list with no explanation of where they came from; the only clue was a
line buried in the log.

**After (analysis).** Restoring a session now shows "Restored N cards from the
previous session." in the summary header above the list, reusing the same area
that displays post-generation statistics. It is cleared when a new generation
starts. To capture this, a temporary `session_cache.json` was written with plain
UTF-8 — an earlier PowerShell write added a BOM and demonstrated the app's
existing quarantine path — and both the seed file and the quarantined copy were
removed afterwards.

## Change 37 — Approved count on the Sync button

| Before | After |
|---|---|
| `47_before_sync_count.png` | `47_after_sync_count.png` |

**Before (analysis).** "Sync Approved to Anki" gave no hint how many cards that
would send; the user had to read the status bar or count approvals first.

**After (analysis).** `_refresh_status()` now sets the button label to
"Sync Approved to Anki (N)" while any cards are approved, reverting to the
plain label when none are. Live harness:
`Sync Approved to Anki (3)` → `Sync Approved to Anki (2)` after unchecking one
card. The command wiring and enable/disable logic are unchanged.

## Change 38 — Self-explanatory disabled Preview button

| Before | After | Source-selected proof |
|---|---|---|
| `48_before_preview_hint.png` | `48_after_preview_hint.png` | `49_verify_preview_hint_cleared.png` |

**Before (analysis).** "Preview Transcript" was disabled on a fresh launch with
no visible explanation, leaving users to wonder whether the feature was broken.

**After (analysis).** While no source is loaded the button reads
"Preview Transcript (select a source first)". Once a local file is chosen or a
URL transcript is imported, the label returns to "Preview Transcript". A live
harness confirmed
`BEFORE Preview Transcript (select a source first) disabled` →
`AFTER Preview Transcript disabled` after `select_file()`. The enable/disable
logic itself is unchanged.

## Change 39 — Persistent deck-list scrollbar

| Before | After |
|---|---|
| `50_before_deck_scrollbar.png` | `50_after_deck_scrollbar.png` |

**Before (analysis).** The Available Decks `ScrolledFrame` also used
`autohide=True`. With a large Anki collection, decks past the visible area were
silently clipped with no visible scrollbar.

**After (analysis).** `autohide=False` keeps the deck panel's scrollbar present,
consistent with the review panel (Change 35). Screenshots used a harness with a
fake 25-deck collection; the after image shows the scrollbar track on the panel
right edge. A widget-tree check found `SCROLLBARS 1 MAPPED [True]`.

## Change 40 — LLM connection state in the status bar

| Before | After |
|---|---|
| `51_before_llm_status.png` | `51_after_llm_status.png` |

**Before (analysis).** The "Test Connection" result appeared only in a
transient dialog and a log line; once dismissed, the app gave no indication of
whether the configured LLM endpoint was reachable.

**After (analysis).** The status bar now shows `LLM: —` initially, then
`LLM: online` (green) or `LLM: offline` (red) after a probe. Editing the API
URL, key or model invalidates the result back to unknown, since the probe no
longer describes the current configuration. Live harness:
`LLM: —` → `LLM: online` → `LLM: offline` → `LLM: —` after an API URL edit.
The harness initially blocked on the real messagebox; patching it in the
scratch harness resolved that.

## Change 41 — Stronger section headers

| Before | After |
|---|---|
| `52_before_bold_headers.png` | `52_after_bold_headers.png` |

**Before (analysis).** The Settings section titles ("Appearance", "AI Server
Configuration", "Model Parameters", …) used the default labelframe font and
blended into the form, making the panel harder to scan.

**After (analysis).** A single `TLabelframe.Label` style configure gives all
section titles a bold 9pt Segoe UI face. It is re-applied in `apply_theme()` so
switching themes does not drop the override. A live harness confirmed
`INITIAL {Segoe UI} 9 bold` and `AFTER_THEME {Segoe UI} 9 bold`. No individual
widget was given a hardcoded colour.

## Change 42 — Log line-wrap toggle

| Before | After (wrapped) | After (unwrapped) |
|---|---|---|
| `53_before_wrap_toggle.png` | `53_after_wrap_on.png` | `54_verify_wrap_off.png` |

**Before (analysis).** Long diagnostic lines were always wrapped at the
console width, which can obscure the structure of URLs or stack traces; there
was no way to see them as single lines.

**After (analysis).** A `Wrap: On / Off` button in the log header switches the
Text widget between `wrap="word"` and `wrap="none"`, and the console was
initialized with `wrap="word"` explicitly. Live harness with a deliberately
long line: `WRAPPED word Wrap: On` → `UNWRAPPED none Wrap: Off`, with screenshots
showing the line wrapping to two rows versus extending past the visible edge
with a horizontal scrollbar. An initial implementation checked only for
`"word"` while ScrolledText's default was `"char"`, producing a mismatched
label; the check now treats any mode other than `"none"` as wrapping.

## Change 43 — Minimum window size

| Before | After |
|---|---|
| `55_before_min_size.png` | `55_after_min_size.png` |

**Before (analysis).** The window could be resized down to 600x400, where the
entire review panel disappeared and the deck hint text was clipped — a layout
that made the app hard to use after an accidental resize.

**After (analysis).** `minsize(1120, 820)` clamps resizing so the review pane,
its empty-state guidance and both input panels stay visible. A live harness
requested `600x400`; the actual geometry reported `1120x820`, and the screenshot
shows the complete empty state. Two earlier candidates (960x680 and 1100x760)
were tested and rejected because the empty-state heading was still clipped.

## Change 44 — Filter the deck list

| Before | After |
|---|---|
| `56_before_deck_filter.png` | `56_after_deck_filter.png` |

**Before (analysis).** With a large Anki collection, finding a specific deck in
the scrollable list meant visually scanning every row — the All/None shortcuts
help with bulk selection but not with locating one deck.

**After (analysis).** A "Filter decks…" entry above the list narrows it as the
user types, case-insensitively, without rebuilding the list or changing any
selection state. `self.deck_rows` maps deck names to their checkbox widgets so
rows can simply be packed/unpacked. A live harness with 25 decks confirmed
`ALL 25` → `FILTERED ['Deck 20' … 'Deck 25']` for the query "deck 2" →
`RESTORED 25` on clearing.

## Change 45 — Phase-aware generation status

| Before | After |
|---|---|
| `57_before_phase_status.png` | `57_after_phase_status.png` |

**Before (analysis).** During a run the status label said only "Generating…"
for the whole pipeline, so a slow extraction or a hung LLM looked identical.

**After (analysis).** `set_generation_phase()` drives the busy label through
"Starting…", "Extracting text…", "Generating cards…" and "Finalizing…", set
from the pipeline callback points, then cleared by `_finish_processing()` back
to "Ready". The amber colour and indeterminate progress bar remain. Live
harness: `Starting…` → `Extracting text…` → `Generating cards…` →
`Finalizing…` → `Ready`. Two harness runs initially hung on printing the `●`
character through the Windows console encoding; switching to ASCII-safe output
resolved that.

## Change 46 — No-match feedback for deck filtering

| Before | After |
|---|---|
| `58_before_no_match.png` | `58_after_no_match.png` |

**Before (analysis).** Typing a filter with no matching decks left an empty
list while the selection label still said "All decks" — misleading and with no
hint that the filter was the cause.

**After (analysis).** When a non-empty filter hides every row, the deck-status
label switches to an amber "No matching decks" and returns to the normal
selection count as soon as the filter matches again or is cleared. Live harness:
`ALL 25 All decks` → `RESTORED 25 All decks` → `NOMATCH No matching decks`.

## Change 47 — Filter the review cards

| Before | After |
|---|---|
| `59_before_card_filter.png` | `59_after_card_filter.png` |

**Before (analysis).** With many generated cards there was no way to focus on
a subset; the review list had to be scrolled and scanned manually.

**After (analysis).** A "Filter cards…" entry in the review header narrows the
list by question or answer text. `_filter_cards()` packs/unpacks the row frames
without touching card data, and is called from the existing card-change hook so
new or restored cards respect an active filter. Live harness:
`ALL 3` → `FILTERED 1 Question 2` → `RESTORED 3`.

## Change 48 — Card filter match count

| Before | After |
|---|---|
| `60_before_filter_count.png` | `60_after_filter_count.png` |

**Before (analysis).** With the card filter active, the reduced list gave no
indication of how many cards were hidden by the filter versus genuinely absent.

**After (analysis).** A small `shown/total` counter sits beside the filter
entry, e.g. `1/3`, and clears when the filter is emptied. It is updated by the
existing `_filter_cards()` pass. Live harness:
`FILTERED 1 Question 2 COUNT 1/3` → `RESTORED 3 COUNT ''`.

## Change 49 — Clear buttons on both filters

| Before | After |
|---|---|
| `61_before_clear_filters.png` | `61_after_clear_filters.png` |

**Before (analysis).** Clearing a filter required selecting its text and
deleting it manually; the small × affordance users expect from search fields
was missing on both the card and deck filters.

**After (analysis).** Each filter entry now has a × button that empties its
variable and re-runs the corresponding filter pass. A live harness confirmed
`BEFORE 2 Deck 3` → `AFTER '' ''`. No filtering semantics changed.

## Change 50 — No-match feedback and Escape-to-clear for card filter

| Before | After |
|---|---|
| `62_before_no_card_matches.png` | `62_after_no_card_matches.png` |

**Before (analysis).** A card filter with no hits showed only "0/3" in neutral
text, which could be read as a display glitch, and clearing both filters
required two separate clicks.

**After (analysis).** When the card filter matches nothing, its counter turns
amber and reads "No matches"; Escape now clears both the card and deck filters
in one action. Live harness: `BEFORE 2 Deck 3` → `ESCAPE '' ''`.

## Change 51 — Approved-only review filter

| Before | After |
|---|---|
| `63_before_approved_only.png` | `63_after_approved_only.png` |

**Before (analysis).** Before syncing, there was no way to hide unapproved
cards and review only what would actually be sent to Anki.

**After (analysis).** An `Approved` toggle beside the card filter limits the
review list to approved cards; it composes with the text filter, updates the
`shown/total` counter, and Escape clears it along with both text filters. Live
harness: `ALL 3` → `APPROVED_ONLY 2 2/3` → `RESTORED 3 ''`.

## Change 52 — Collapsible Activity Log

| Before | After |
|---|---|
| `64_before_log_collapse.png` | `64_after_log_collapse.png` |

**Before (analysis).** The console always occupied a fixed strip at the bottom,
even when the user wanted maximum room to review a long list of cards.

**After (analysis).** A `Hide / Show` button in the log header collapses just
the Text widget, leaving the header and its controls in place and giving the
review area more vertical space. Live harness:
`BEFORE True Hide` → `COLLAPSED False Show` → `RESTORED True Hide`. Logging
continues to the file handler while collapsed.

## Change 53 — Error lines highlighted in the log

| Before | After |
|---|---|
| `65_before_log_levels.png` | `65_after_log_levels.png` |

**Before (analysis).** All console lines shared one colour, so a "Critical
Error" was no more visible than an informational message in a busy log.

**After (analysis).** `TextWidgetHandler` now passes the record's level to
`append_log()` and applies a themed `error` text tag to ERROR and above,
coloured with the active theme's `danger` colour. Live harness:
`ERROR_TAG_RANGES 2 COLOR #e74c3c` (one tagged line). Info lines remain
untagged, and the file handler is unchanged.

## Change 54 — Automatic LLM status at startup

| Before | During | After |
|---|---|---|
| `66_before_auto_llm.png` | `66_during_auto_llm.png` | `66_after_auto_llm.png` |

**Before (analysis).** The LLM indicator stayed at "—" until the user manually
pressed Test Connection, giving no startup information about endpoint health.

**After (analysis).** A daemon thread probes the configured endpoint once at
startup. The status reads blue "LLM: checking…" while the probe runs (it can
take up to ~10 s with timeouts), then green "LLM: online" or red
"LLM: offline". Editing the endpoint/key still invalidates it back to unknown.
Live harness: `LLM_STATUS offline LLM: offline` after the real probe; a
patched instant probe confirmed `STATUS online LLM: online`.

## Change 55 — LLM result shown in Settings

| Before | After | Failure proof |
|---|---|---|
| `67_before_settings_llm_status.png` | `67_after_settings_llm_status.png` | `68_verify_settings_llm_fail.png` |

**Before (analysis).** The connection result was only in the status bar on the
Generator tab and in a transient dialog, so while editing the endpoint on the
Settings tab the user had no local feedback.

**After (analysis).** A coloured label next to "Test Connection" mirrors the
LLM state: green "Connected", red "Not connected", blue "Checking…", empty
when invalidated by an edit. It is driven centrally from `_refresh_status()`,
so startup probe, manual test and config edits stay consistent. Live captures:
`RESULT Connected` and `RESULT Not connected`.

## Change 56 — Log follow (auto-scroll) toggle

| Before | After |
|---|---|
| `69_before_log_follow.png` | `69_after_log_follow.png` |

**Before (analysis).** New log lines always jumped the console to the bottom,
so reading an earlier section while a run was still logging was impossible.

**After (analysis).** A `Follow: On / Off` button in the log header controls
whether `TextWidgetHandler` calls `see("end")` after each append. With Follow
off, new lines accumulate while the user's scroll position stays put; the
button recolours to show state. Live captures show the latest lines with Follow
on and the first lines with Follow off after logging 30 lines.

## Change 57 — Active source in the status bar

| Before | After |
|---|---|
| `70_before_source_status.png` | `70_after_source_status.png` |

**Before (analysis).** After choosing a file or importing a URL, the status
bar gave no indication which source was active; the user had to look back at
the source box on the Generator tab.

**After (analysis).** The status bar now shows "Source: <name>" (truncated at
30 characters), or "Source: none" when empty. It is derived centrally in
`_refresh_status()` from `loaded_source_title` / `selected_file_path`, with
refreshes added to the file-selection and URL-import paths so it updates
immediately.

## Change 58 — Warning lines highlighted in the log

| Before | After |
|---|---|
| `71_before_warning_color.png` | `71_after_warning_color.png` |

**Before (analysis).** After error lines were coloured, WARNING lines still
looked like ordinary info, so rejected cards / degraded runs were easy to miss.

**After (analysis).** `TextWidgetHandler.append_log()` now tags WARNING and
above with a themed `warning` colour (amber) in addition to the existing red
`error` tag. Live harness:
`WARNING_TAG_RANGES 2 COLOR #f39c12`, `ERROR_TAG_RANGES 2 COLOR #e74c3c`.
Info lines remain neutral.

## Change 59 — Clear the selected source

| Before | After | Cleared proof |
|---|---|---|
| `72_before_clear_source.png` | `72_after_clear_source.png` | `73_verify_source_cleared.png` |

**Before (analysis).** Once a file or URL was selected there was no in-app way
to deselect it; switching sources meant opening another file, and a stale
selection could be sent to the LLM by accident.

**After (analysis).** A small × button at the right of the source box clears
the file/URL state, resets the label, icon, source hint, Preview button and
status-bar source field, while leaving reviewed cards untouched. Live harness:
`BEFORE lecture-notes.pdf | Source: lecture-notes.pdf` →
`AFTER No file selected | Source: none | disabled`.

## Change 60 — Keyboard shortcuts help button

| Before | After |
|---|---|
| `74_before_help_button.png` | `74_after_help_button.png` |

**Before (analysis).** Shortcuts were advertised on button labels and worked,
but there was no single place to discover them all.

**After (analysis).** A `?` button at the right end of the status bar opens a
"Keyboard Shortcuts" dialog listing Ctrl+O, Ctrl+Enter and Escape. Live harness
captured the dialog content verbatim.

## Change 61 — Pending review filter

| Before | After |
|---|---|
| `75_before_pending_filter.png` | `75_after_pending_filter.png` |

**Before (analysis).** The Approved filter could isolate what would be sent to
Anki, but there was no way to focus on the cards still needing review.

**After (analysis).** A `Pending` toggle beside `Approved` shows only
unapproved cards. The two are mutually exclusive, compose with the text
filter, update the `shown/total` counter, and are both cleared by Escape. Live
harness: `PENDING False True 2/3` → `APPROVED True False 1/3` →
`CLEARED False False ''`.

## Change 62 — Copy cards to clipboard

| Before | After |
|---|---|
| `76_before_copy_cards.png` | `76_after_copy_cards.png` |

**Before (analysis).** Reviewed cards could only be exported by syncing to
Anki; there was no lightweight way to copy the Q/A text elsewhere.

**After (analysis).** A `Copy Cards` button in the review toolbar copies the
currently visible cards as `Q: … / A: …` blocks, so it respects text and
Approved/Pending filters. Live harness: `ALL_COPIED blocks= 3`, then after
filtering `FILTERED blocks= 1 q2= True`. Two harness attempts hung because row
visibility was checked before an event-loop update; adding `update()` fixed it.

## Change 63 — Bulk approval respects filters

| Before | After |
|---|---|
| `77_before_bulk_visibility.png` | `77_after_bulk_visibility.png` |

**Before (analysis).** With a card filter active, Check All / Uncheck All still
changed hidden rows too — approving cards the user could not see and might not
intend to sync.

**After (analysis).** `toggle_all_approvals()` now iterates only mapped (visible)
rows, so bulk actions match what is on screen. Live harness with three cards
filtered to "Question 2": `APPROVED [True, True, True]` →
`APPROVED [False, True, False]`. The screenshots were taken after clearing the
filter, making the difference visible in the approval toggles and the header
count (3 approved → 1 approved).

## Change 64 — Bulk deck move respects filters

| Before | After |
|---|---|
| `78_before_bulk_move_scope.png` | `78_after_bulk_move_scope.png` |

**Before (analysis).** "Move Selected" applied the chosen deck to every
approved card, including rows hidden by a filter — the confirmation count and
log could claim more cards than the user could see.

**After (analysis).** `bulk_assign_deck()` now selects only approved *and*
mapped (visible) rows. Live harness with three approved cards filtered to
"Question 2": `DECKS ['TargetDeck', 'TargetDeck', 'TargetDeck']` →
`DECKS ['Default', 'TargetDeck', 'Default']`, and the log line changed from
"Moved 3 cards" to "Moved 1 cards". This matches the bulk-approval fix in
Change 63.

## Change 65 — Ctrl+P for transcript preview

| Before | After |
|---|---|
| `79_before_preview_shortcut.png` | `79_after_preview_shortcut.png` |

**Before (analysis).** Preview was mouse-only despite being one of the more
frequent actions after loading a source.

**After (analysis).** Ctrl+P now opens the transcript preview when the button
is enabled, and the enabled button label shows "(Ctrl+P)". The handler guards
on processing/preview state, and the `?` shortcuts dialog lists the new
binding. Live harness: `BINDING True`, `DISABLED []`, `ENABLED ['preview']`.

## Change 66 — Copy Cards follows card count

| Before | After |
|---|---|
| `80_before_copy_button_state.png` | `80_after_copy_button_state.png` |

**Before (analysis).** "Copy Cards" looked available with no cards and silently
did nothing when clicked, unlike the other bulk controls which disable
themselves in that state.

**After (analysis).** It is now part of the card-count state group and uses the
same `info-outline` treatment as the other enabled bulk actions. Live harness:
`EMPTY disabled` → `WITH_CARD normal` → `CLEARED disabled`. A first harness
attempt blocked on Clear All's confirmation dialog; patching it in the scratch
harness resolved that.

## Change 67 — Errors-only log view

| Before | After |
|---|---|
| `81_before_errors_only.png` | `81_after_errors_only.png` |

**Before (analysis).** A long run mixed routine info and warning lines with the
few errors that actually needed attention, with no way to isolate them.

**After (analysis).** All appended lines now carry an `info`, `warning` or
`error` tag, and an `Errors: Off / On` button elides the first two when
enabled, leaving only red error lines. Live harness:
`BEFORE 0 ''` → `ON 1 1 Errors: On` → `OFF 0 0 Errors: Off`. The underlying log
and clipboard copy are unaffected.

## Change 68 — Clear All confirmation shows the count

| Before | After |
|---|---|
| `82_before_clear_confirm.png` | `82_after_clear_confirm.png` |

**Before (analysis).** The confirmation read "Clear all generated cards?" and
gave no hint of how much work would be discarded.

**After (analysis).** It now states the exact count with correct pluralisation,
e.g. "Clear all 3 generated cards?". The blocked-session wording is unchanged.
Both dialog screenshots were captured from the running app via `PrintWindow`
on the messagebox window.

## Change 69 — Copy button in transcript preview

| Before | After |
|---|---|
| `83_before_preview_copy.png` | `83_after_preview_copy.png` |

**Before (analysis).** The transcript preview dialog could only be read and
closed; copying the text for use elsewhere meant selecting it manually.

**After (analysis).** A `Copy` button beside `Close` copies the full preview
text to the clipboard. Live harness:
`COPIED ['This is the transcript text.'] MATCH True`. An initial capture of the
after dialog showed a blank white viewer — a transient PrintWindow repaint
artifact; recapturing showed the normal dark viewer with both buttons.

## Change 70 — Larger notebook tabs

| Before | After |
|---|---|
| `84_before_tab_style.png` | `84_after_tab_style.png` |

**Before (analysis).** The "Generator" / "Settings" tabs used the small default
font and padding, making the two main navigation targets easy to overlook.

**After (analysis).** A `TNotebook.Tab` style gives them a bold 10pt Segoe UI
font with more horizontal padding; it is re-applied in `apply_theme()` so theme
switches keep it. Live harness: `INITIAL {Segoe UI} 10 bold` and
`AFTER_THEME {Segoe UI} 10 bold`.

## Change 71 — Optional log clear on generation start

| Before | After |
|---|---|
| `85_before_clear_on_run.png` | `85_after_clear_on_run.png` |

**Before (analysis).** Log lines from earlier runs accumulated alongside the
current run, making it harder to follow a fresh generation.

**After (analysis).** A "Clear on run" toggle in the log header empties the
on-screen console at the start of each generation (file logging continues).
Live harness with an "old log line" present and a patched pipeline:
`OLD_LINE_GONE True` after `start_processing()`.

## Change 72 — Card filters reset on a new run

| Before | After |
|---|---|
| `86_before_filter_reset.png` | `86_after_filter_reset.png` |

**Before (analysis).** A text/Approved/Pending filter from a previous review
session persisted into the next generation, so new cards that didn't match the
stale filter were invisible after a run.

**After (analysis).** `start_processing()` clears card filters before starting,
so every new card is visible. Live harness: `BEFORE 2 True` →
`AFTER '' False`. The screenshots show the filter entry populated with a 1/3
count versus cleared with the full list visible. Deck filters are left intact.

## Change 73 — Working state on the Generate button and title

| Before | After |
|---|---|
| `87_before_working_state.png` | `87_after_working_state.png` |

**Before (analysis).** During a run the Generate button kept its normal label
(only disabled), which was easy to miss when returning to the window.

**After (analysis).** While processing, the button reads "Working…" and the
window title carries the current phase ("NeuralDeck — Extracting text…",
etc.). Both are restored by `_finish_processing()`. Live harness:
`INITIAL NeuralDeck / Generate Cards (Ctrl+Enter)` →
`PHASE NeuralDeck — Extracting text…` →
`DONE NeuralDeck / Generate Cards (Ctrl+Enter)`. The after screenshot shows
the "Working…" button and enabled Stop Processing control.

## Change 74 — Copy log respects Errors-only

| Before | After |
|---|---|
| `88_before_copy_scope.png` | `88_after_copy_scope.png` |

**Before (analysis).** With Errors-only enabled, the console showed only errors
but the Copy button still placed hidden info/warning lines on the clipboard —
surprising when pasting into a bug report.

**After (analysis).** `copy_log()` extracts only the `error` tag ranges when
Errors-only is active; otherwise it copies everything as before. Live harness:
`HAS_INFO True HAS_ERROR True` → `HAS_INFO False HAS_ERROR True`. The
screenshots show the Errors-only view in both cases; the behaviour difference
is in the clipboard content verified by the harness.

## Change 75 — Card count on the Generator tab

| Before | After |
|---|---|
| `89_before_tab_count.png` | `89_after_tab_count.png` |

**Before (analysis).** The tab label was static, so switching away and back
gave no hint how many cards were in the current review session.

**After (analysis).** The tab reads `Generator (N)` while cards exist and
reverts to `Generator` when empty. It is updated by the existing card-change
hook, so adds, removals, generation and restore all stay in sync. Live harness:
`EMPTY Generator` → `ONE Generator (1)` → `TWO Generator (2)` →
`CLEARED Generator`.

## Change 76 — Copy button on each card row

| Before | After |
|---|---|
| `90_before_row_copy.png` | `90_after_row_copy.png` |

**Before (analysis).** The toolbar could copy all visible cards, but there was
no way to copy a single card without selecting text manually.

**After (analysis).** Each review row now has a `Copy` button that places just
that card's Q/A on the clipboard. Live harness:
`ROW_COPY 'Q: Question 2\nA: Answer 2' has_q2= True has_q1= False`.

## Change 77 — Enable local-file Preview

| Before | After |
|---|---|
| `91_before_local_preview.png` | `91_after_local_preview.png` |

**Before (analysis).** The source box explicitly said "Source ready — preview
it…" but selecting a local file left the Preview button disabled, making that
instruction false. The README promises early extraction of local files.

**After (analysis).** `select_file()` now enables Preview immediately —
`preview_transcript()` already extracts local files on demand — and the button
uses `info-outline` so its enabled state is visually obvious. Live harness:
`PREVIEW_STATE disabled` → `PREVIEW_STATE normal` with the same file selected.

## Change 78 — Preview stays enabled after a busy cycle

| Before | After |
|---|---|
| `92_before_preview_busy_fix.png` | `92_after_preview_busy_fix.png` |

**Before (analysis).** After any preview busy/reset cycle (e.g. `_set_preview_busy(False)`
following a failed URL import), Preview was disabled again even with a local
file selected, because the enable condition only checked extracted text.

**After (analysis).** The condition now also considers `selected_file_path`,
so a chosen file keeps Preview available. Live harness:
`AFTER_SELECT normal` → `AFTER_BUSY_CYCLE disabled` → `AFTER_BUSY_CYCLE normal`.

## Change 79 — Source Clear button follows the source state

| Before | After |
|---|---|
| `93_before_source_clear_state.png` | `93_after_source_clear_state.png` |

**Before (analysis).** The × button in the source box was always enabled, even
with no source loaded, where clicking it did nothing.

**After (analysis).** `_refresh_status()` now enables it only when a file or
imported title is present. Live harness:
`EMPTY disabled` → `WITH_SOURCE normal` → `CLEARED disabled`. The screenshots
show the no-source and source-loaded states of the box.

## Change 80 — Find in log

| Before | After |
|---|---|
| `94_before_log_search.png` | `94_after_log_search.png` |

**Before (analysis).** Long logs had to be scanned visually; there was no way
to locate a term or error code.

**After (analysis).** A "Find in log…" entry in the log header highlights every
case-insensitive match with the theme's warning colour, and clearing the field
removes the highlights. Live harness: `WITH_QUERY 1` → `CLEARED 0`; the
screenshot shows "ERROR" highlighted in the console.

## Change 81 — Live log search highlighting

| Before | After |
|---|---|
| `95_before_live_search.png` | `95_after_live_search.png` |

**Before (analysis).** With a search term active, lines appended afterwards
were not highlighted, so a live run gradually lost its visual matches.

**After (analysis).** `TextWidgetHandler.append_log()` re-runs `_search_log()`
whenever a query is active, so new matches are highlighted immediately. Live
harness: `BEFORE 1` → `AFTER 2` matches; the screenshots show only the first
"error" highlighted before and both highlighted after.

## Change 82 — Log search match counter

| Before | After |
|---|---|
| `96_before_match_counter.png` | `96_after_match_counter.png` |

**Before (analysis).** The search box highlighted matches but gave no count,
so a user couldn't tell whether a term occurred once or many times without
scanning the log.

**After (analysis).** An amber `N matches` label beside the search field shows
the count (with singular/plural handling) and clears with the query. Live
harness: `MATCHES '1 match'` → `CLEARED ''`; the screenshot shows "2 matches".

## Change 83 — Source hint recolors on theme switch

| Before | After |
|---|---|
| `97_before_hint_theme.png` | `97_after_hint_theme.png` |

**Before (analysis).** The green "Source ready…" hint kept the dark theme's
success colour after switching to a light theme, where the palette uses a
different green.

**After (analysis).** `apply_theme()` now re-applies `_set_source_hint()` so the
hint uses the active theme's success colour. Live harness:
`DARK #00bc8c` → `LIGHT #02b875` (expected `#02b875`). The colour change is
subtle in the screenshots; the harness values are the precise evidence.

## Change 84 — Unsaved marker on the Settings tab

| Before | After |
|---|---|
| `98_before_settings_tab_marker.png` | `98_after_settings_tab_marker.png` |

**Before (analysis).** Unsaved changes were only visible in the Settings
footer, so switching to another tab hid the warning entirely.

**After (analysis).** The tab label reads `Settings •` while the form is dirty
and reverts to `Settings` after a save or reset, driven by
`_refresh_settings_status()`. Live harness: `CLEAN Settings` →
`DIRTY Settings •` → `RESET Settings`. Any config file written by the harness
was removed afterwards.

## Change 85 — Clear button for log search

| Before | After |
|---|---|
| `99_before_search_clear.png` | `99_after_search_clear.png` |

**Before (analysis).** Clearing a log search required selecting the query text
and deleting it; every other filter in the app had a × affordance.

**After (analysis).** A × button beside the match counter empties the query and
removes highlights/count in one click. Live harness:
`BEFORE 'error' 2 '2 matches'` → `AFTER '' 0 ''`.

## Change 86 — Ctrl+F focuses log search

| Before | After |
|---|---|
| `100_before_find_shortcut.png` | `100_after_find_shortcut.png` |

**Before (analysis).** The log search field had to be clicked with the mouse;
no keyboard route existed despite the app's other shortcuts.

**After (analysis).** Ctrl+F focuses and selects the contents of the Find field,
and the `?` shortcuts dialog lists it. Live harness:
`BINDING True`, `CALLS ['focus', 'select']`. The screenshot shows the focused
search field with an active match.

## Change 87 — Offline deck warning recolors on theme switch

| Before | After |
|---|---|
| `101_before_deckwarn_theme.png` | `101_after_deckwarn_theme.png` |

**Before (analysis).** The amber "Anki offline" label kept the dark theme's
warning colour after switching to a light theme.

**After (analysis).** `apply_theme()` now re-colors `deck_warning` from the
active theme palette. Live harness: `DARK #f39c12` → `LIGHT #f0ad4e`
(expected `#f0ad4e`). The change is subtle in screenshots; the harness values
are the precise evidence.

## Change 88 — Enter jumps to the first log search match

| Before | After |
|---|---|
| `102_before_search_jump.png` | `102_after_search_jump.png` |

**Before (analysis).** Search highlighted matches but offered no way to jump to
one in a long, scrolled log.

**After (analysis).** Pressing Enter in the Find field scrolls the console to
the first highlighted match. Live harness: `BINDING True`, view position
`BEFORE 0.886` (bottom) → `AFTER 0.0` (match at top); the after screenshot shows
the highlighted "NEEDLE" line in view. An initial capture was scrolled back by
late Anki log lines, so the capture harness disables Follow for this check.

## Verification

- `python -m py_compile ui.py` — clean
- `python -m pytest tests -q` — 224 passed, 1 skipped, 24 subtests passed
- `update_knowledge_base.py --check --workspace …/NeuralDeck` — codebase map fresh
- Live harnesses: card add + approval updates status text; theme switch repaints
  text widgets; API-key toggle rounds-trips `show` and button label; bulk
  controls transition disabled → enabled with the card count; Clear button
  empties the console via a real `.invoke()`; Settings indicator flips on edits;
  progress animation starts/stops with processing state; deck shortcuts flip
  every deck variable; keyboard shortcuts dispatch only when enabled; Copy log
  matches the console text on the clipboard; Reset restores shipped defaults;
  Retry re-runs the Anki fetch and re-enables itself; deck count follows
  selection; Generator density persists and stays in sync with Settings;
  offline notice appears only while disconnected; manual card focuses Q; card
  indices renumber after removal; status-bar model follows the Settings field;
  Save button label/style follows the dirty flag; quit guard honours both
  answers; run summary shows and clears; prompt count follows edits; LLM test
  reports success and failure; timestamp toggle changes the log formatter;
  approval progress updates in the header; review scrollbar stays visible;
  restored sessions are labelled; Sync button shows the approved count;
  Preview button explains its disabled state; deck scrollbar stays visible;
  LLM state is shown and invalidated on config edits; section headers stay bold
  across themes; log wrap toggles between word and none; window resizing is
  clamped to a usable minimum; deck list filters and restores; generation
  status names the current phase. All screenshots above were captured from the
  running process with `PrintWindow`.
