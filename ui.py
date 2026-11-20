import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledFrame
from ttkbootstrap.widgets import ToolTip
from tkinter import TclError, filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
import threading
import os
import time
import logging
from audio_transcription import is_audio_file, is_video_file
from document_processor import check_llm_server, extract_text_from_document, generate_qa_pairs
from transcript_sources import (
    MAX_MEDIA_BYTES,
    fetch_podcast_feed,
    fetch_podcast_transcript_for_ref,
    fetch_transcript_from_url,
)
from anki_integration import create_anki_deck, get_deck_names, check_anki_connection
from pipeline_utils import PipelineStats, ResourceGuard
from settings_io import (
    cleanup_stale_temp_files,
    ensure_parent_directory,
    normalize_config,
    normalize_session_data,
    parse_float_setting,
    parse_int_setting,
    quarantine_corrupt_file,
    read_json_file,
    resolve_app_path,
    write_json_file,
)

CONFIG_FILE = resolve_app_path("config.json", "NEURALDECK_CONFIG")
SESSION_FILE = CONFIG_FILE.parent / "session_cache.json"
LOG_FILE = resolve_app_path("session.log", "NEURALDECK_LOG")
THEMES = (
    "cerculean", "cosmo", "cyborg", "darkly", "flatly", "journal", "litera", "lumen",
    "minty", "morph", "pulse", "sandstone", "simplex", "solar", "superhero", "united",
    "vapor", "yeti",
)

LOG_FONT = ("Consolas", 9)


def themed_text_options(style=None):
    """Tk Text colours taken from the active ttkbootstrap theme.

    Tkinter's Text/ScrolledText widgets are not themed by ttkbootstrap, so left
    untouched they render as a bright white box inside a dark application. This
    maps the theme palette onto the Text widget options, keeping the console,
    prompt editor and transcript preview visually consistent with every theme.
    """
    style = style or ttk.Style()
    colors = style.colors or {}
    bg = colors.get("inputbg") or colors.get("bg") or "#ffffff"
    fg = colors.get("inputfg") or colors.get("fg") or "#000000"
    return {
        "background": bg,
        "foreground": fg,
        "insertbackground": fg,
        "selectbackground": colors.get("selectbg") or colors.get("primary") or bg,
        "selectforeground": colors.get("selectfg") or fg,
        "highlightbackground": colors.get("border") or bg,
        "highlightcolor": colors.get("primary") or fg,
        "highlightthickness": 1,
    }


class TextWidgetHandler(logging.Handler):
    """Custom logging handler that writes to a Tkinter ScrolledText widget thread-safely."""
    def __init__(self, text_widget, root):
        super().__init__()
        self.text_widget = text_widget
        self.root = root

    def emit(self, record):
        msg = self.format(record)
        self.root.after(0, self.append_log, msg, record.levelno)

    def append_log(self, msg, level=logging.INFO):
        try:
            self.text_widget.config(state='normal')
            tag = "info"
            color_key = None
            if level >= logging.ERROR:
                tag, color_key = "error", "danger"
            elif level >= logging.WARNING:
                tag, color_key = "warning", "warning"
            style = getattr(self.root, "style", None)
            colors = style.colors if style is not None else {}
            if color_key:
                self.text_widget.tag_configure(
                    tag, foreground=colors.get(color_key) or colors.get("fg")
                )
            self.text_widget.insert("end", msg + "\n", tag)
            search_var = getattr(self.root, "log_search_var", None)
            if search_var is not None and search_var.get().strip():
                self.root._search_log()
            # Limit to approx 50000 characters
            text = self.text_widget.get("1.0", "end")
            if len(text) > 50000:
                excess = len(text) - 50000
                self.text_widget.delete("1.0", f"1.0+{excess}c")
            if getattr(self.root, "log_autoscroll", True):
                self.text_widget.see("end")
            self.text_widget.config(state='disabled')
        except Exception:  # hygiene: allow widget teardown must not break logging
            pass

class CardReviewRow(ttk.Frame):
    """A row representing a single generated card for review."""
    def __init__(self, parent, question, answer, assigned_deck, available_decks, quote="", on_remove=None, on_approve=None, index=0):
        super().__init__(parent)
        self.quote = quote
        self.on_remove = on_remove
        self.on_approve = on_approve
        self.pack(fill=X, pady=5, padx=5)
        
        # Layout columns
        self.columnconfigure(3, weight=1) # Question/Answer area stretches
        
        # Checkbox for approval
        self.approved_var = ttk.BooleanVar(value=False)
        self.checkbox = ttk.Checkbutton(self, text="Approve", variable=self.approved_var,
                                        bootstyle="round-toggle", command=self._on_approve)
        self.checkbox.grid(row=0, column=0, rowspan=2, padx=10, sticky="ns")

        # Position in the review list; refreshed whenever cards are added/removed.
        self.index_label = ttk.Label(self, text=f"#{index}" if index else "#",
                                     font=("Segoe UI", 9, "bold"), width=3)
        self.index_label.grid(row=0, column=1, rowspan=2, padx=(0, 2))

        # Explicit Q / A markers make the two identical-looking fields
        # unmistakable, especially in a long list of cards.
        ttk.Label(self, text="Q", font=("Segoe UI", 9, "bold"), width=2).grid(row=0, column=2, sticky=E)
        ttk.Label(self, text="A", font=("Segoe UI", 9, "bold"), width=2).grid(row=1, column=2, sticky=E)

        # Inputs — placeholders guide manual cards that start empty.
        self.q_entry = ttk.Entry(self, placeholder="Question — what do you want to ask?")
        self.q_entry.insert(0, question)
        self.q_entry.grid(row=0, column=3, sticky=EW, padx=5, pady=2)
        
        self.a_entry = ttk.Entry(self, placeholder="Answer — the ideal response")
        self.a_entry.insert(0, answer)
        self.a_entry.grid(row=1, column=3, sticky=EW, padx=5, pady=2)
        
        # Deck Selection
        self.deck_var = ttk.StringVar(value=assigned_deck)
        # Use a local copy to avoid polluting the global available_decks list with generated names
        deck_options = list(available_decks)
        if assigned_deck and assigned_deck not in deck_options:
            deck_options.append(assigned_deck)
            
        self.deck_dropdown = ttk.Combobox(self, textvariable=self.deck_var, values=deck_options, width=20, state="readonly")
        self.deck_dropdown.grid(row=0, column=4, rowspan=2, padx=10)
        self.deck_dropdown.bind('<Button-1>', lambda e: self.deck_dropdown.event_generate('<Down>'))

        # Source context button — a word reads more clearly than a quote glyph.
        btn_state = "normal" if self.quote else "disabled"
        btn_style = "info-outline" if self.quote else "secondary-outline"
        
        self.quote_btn = ttk.Button(self, text="Source", command=self.show_source,
                                    bootstyle=btn_style, width=7, state=btn_state)
        self.quote_btn.grid(row=0, column=5, rowspan=2, padx=2)
        
        if self.quote:
            ToolTip(self.quote_btn, text=f"Source: {self.quote[:100]}...")

        # Per-card copy — handy when only one card needs to be reused.
        self.copy_btn = ttk.Button(self, text="Copy", command=self._copy_card,
                                   bootstyle="secondary-outline", width=5)
        self.copy_btn.grid(row=0, column=6, rowspan=2, padx=(0, 3))

        # Remove Button
        self.remove_btn = ttk.Button(self, text="🗑", command=self.remove_row, bootstyle="danger-outline", width=3)
        self.remove_btn.grid(row=0, column=7, rowspan=2, padx=5)

    def get_data(self):
        return {
            "question": self.q_entry.get(),
            "answer": self.a_entry.get(),
            "deck": self.deck_var.get(),
            "approved": self.approved_var.get()
        }

    def show_source(self):
        messagebox.showinfo("Source Context", self.quote)

    def remove_row(self):
        if self.on_remove:
            self.on_remove(self)

    def _on_approve(self):
        if self.on_approve:
            self.on_approve()

    def _copy_card(self):
        root = self.winfo_toplevel()
        root.clipboard_clear()
        root.clipboard_append(
            f"Q: {self.q_entry.get().strip()}\nA: {self.a_entry.get().strip()}"
        )

def choose_podcast_episode(parent, feed):
    """Show the feed's transcribed episodes and return the chosen reference."""
    if not feed.episodes:
        return None
    if len(feed.episodes) == 1:
        return feed.episodes[0]

    dialog = ttk.Toplevel(parent)
    dialog.title("Select Podcast Episode")
    dialog.geometry("760x420")
    dialog.minsize(500, 280)
    dialog.transient(parent)

    ttk.Label(
        dialog,
        text=f"{feed.title} — {len(feed.episodes)} transcribed episode(s)",
        font=("Helvetica", 10, "bold"),
        padding=10,
    ).pack(anchor=W)

    table_frame = ttk.Frame(dialog, padding=(10, 0, 10, 0))
    table_frame.pack(fill=BOTH, expand=True)
    tree = ttk.Treeview(
        table_frame,
        columns=("language", "format"),
        show="tree headings",
        selectmode="browse",
    )
    tree.heading("#0", text="Episode")
    tree.heading("language", text="Language")
    tree.heading("format", text="Format")
    tree.column("#0", width=510)
    tree.column("language", width=90, anchor="center")
    tree.column("format", width=130, anchor="center")
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.pack(side=RIGHT, fill="y")

    for index, ref in enumerate(feed.episodes):
        tree.insert(
            "",
            "end",
            iid=str(index),
            text=ref.episode_title,
            values=(ref.language or "?", ref.transcript_type or "?"),
        )

    result = {"ref": None}

    def confirm(event=None):
        selection = tree.selection()
        if not selection:
            return
        result["ref"] = feed.episodes[int(selection[0])]
        dialog.destroy()

    buttons = ttk.Frame(dialog, padding=10)
    buttons.pack(fill=X)
    ttk.Button(buttons, text="Use Selected", command=confirm, bootstyle="success").pack(side=RIGHT, padx=(5, 0))
    ttk.Button(buttons, text="Cancel", command=dialog.destroy, bootstyle="secondary-outline").pack(side=RIGHT)

    tree.bind("<Double-1>", confirm)
    tree.bind("<Return>", confirm)
    dialog.bind("<Escape>", lambda event: dialog.destroy())
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    tree.focus_set()
    if feed.episodes:
        tree.selection_set("0")
        tree.focus("0")
    dialog.grab_set()
    dialog.wait_window()
    return result["ref"]


def show_text_preview(parent, title, text):
    """Display a read-only transcript preview without modifying the source."""
    dialog = ttk.Toplevel(parent)
    dialog.title(f"Transcript Preview - {title}")
    dialog.geometry("900x600")
    dialog.minsize(500, 300)
    dialog.transient(parent)

    frame = ttk.Frame(dialog, padding=10)
    frame.pack(fill=BOTH, expand=True)
    ttk.Label(frame, text=title, font=("Helvetica", 10, "bold")).pack(anchor=W)
    ttk.Label(frame, text=f"{len(text):,} characters").pack(anchor=W, pady=(0, 5))

    viewer = ScrolledText(frame, wrap="word", font=("Segoe UI", 9))
    viewer.configure(**themed_text_options())
    preview = text if len(text) <= 50000 else text[:50000] + "\n\n[... preview truncated to 50,000 characters ...]"
    viewer.insert("1.0", preview)
    viewer.config(state="disabled")
    viewer.pack(fill=BOTH, expand=True)

    preview_actions = ttk.Frame(frame)
    preview_actions.pack(fill=X, pady=(8, 0))
    ttk.Button(preview_actions, text="Copy", bootstyle="info-outline",
               command=lambda: (dialog.clipboard_clear(),
                                dialog.clipboard_append(viewer.get("1.0", "end-1c")))
               ).pack(side=RIGHT, padx=(0, 6))
    ttk.Button(preview_actions, text="Close", command=dialog.destroy,
               bootstyle="secondary").pack(side=RIGHT)
    dialog.bind("<Escape>", lambda event: dialog.destroy())
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.grab_set()
    dialog.wait_window()


class AnkiGeneratorUI(ttk.Window):
    def __init__(self):
        for state_file in (CONFIG_FILE, SESSION_FILE, LOG_FILE):
            cleanup_stale_temp_files(state_file)
        self.load_config()
        theme = self.config.get("theme", "darkly")
        if theme == "cerulean":
            theme = "cerculean"
        if theme not in THEMES:
            theme = "darkly"
        self.config["theme"] = theme
        super().__init__(themename=theme)

        # Slightly stronger section titles improve scanability without adding
        # any hardcoded colours or fonts to the individual form widgets.
        self.style.configure("TLabelframe.Label", font=("Segoe UI", 9, "bold"))
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(12, 6))

        self.title("NeuralDeck")
        self.geometry("1200x850")
        self.minsize(1120, 820)  # keep the review pane and both input panels usable

        # Data
        self.anki_status = "checking"
        self._progress_running = False
        self._log_timestamps = False
        self.log_autoscroll = True
        self.errors_only = False
        self.llm_status = "checking"
        self.generation_phase = ""
        # Shared by the Generator quick control and the Settings panel so both
        # stay in sync without duplicating state.
        self.density_var = ttk.StringVar(value=self.config.get("card_density", "Medium"))
        self.selected_file_path = None
        self.loaded_source_text = None
        self.loaded_source_title = None
        self.processing = False
        self.preview_loading = False
        self.available_decks = []
        self.deck_vars = {}
        self.deck_checkboxes = []
        self.deck_rows = {}
        self.card_rows = []
        self.source_text = ""
        self.stop_requested = False
        self._session_loaded = False
        self.session_write_blocked = False
        
        # Tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=True)
        
        self.main_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.main_tab, text="Generator")
        self.notebook.add(self.settings_tab, text="Settings")
        
        self.setup_main_tab()
        self.setup_logging()
        self.setup_settings_tab()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Keyboard shortcuts for the two actions used every session. Bound on
        # the toplevel so they also work while typing in an entry or the prompt.
        self.bind("<Control-o>", self._shortcut_select)
        self.bind("<Control-Return>", self._shortcut_generate)
        self.bind("<Escape>", self._clear_filters)
        self.bind("<Control-p>", self._shortcut_preview)
        self.bind("<Control-f>", self._shortcut_find)

        # Initial Fetch
        self.fetch_decks()
        self._llm_startup_check()

    def setup_logging(self):
        self.logger = logging.getLogger("NeuralDeck")
        level = logging.DEBUG if self.config.get("debug_mode", False) else logging.INFO
        self.logger.setLevel(level)
        # Prevent adding handlers multiple times if re-initialized
        if not self.logger.handlers:
            # File Handler
            try:
                ensure_parent_directory(LOG_FILE)
                file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
                file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="[%Y-%m-%d %H:%M:%S]"))
                self.logger.addHandler(file_handler)
            except Exception:  # hygiene: allow read-only session.log must not stop the UI
                pass

            # UI Handler
            text_handler = TextWidgetHandler(self.log_area, self)
            text_handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(text_handler)
            self.ui_log_handler = text_handler
            self.log_area.tag_configure("info", elide=False)

    def setup_main_tab(self):
        self.main_tab.columnconfigure(0, weight=1)
        self.main_tab.rowconfigure(0, weight=1) # Review area expands (now at top)
        
        # 1. Review Area (Scrollable) - Moved to Top
        self.review_container = ttk.Labelframe(self.main_tab, text="Review & Source Comparison")
        self.review_container.grid(row=0, column=0, sticky=NSEW, padx=20, pady=(20, 10))
        
        # Review Toolbar (Select All / None)
        toolbar = ttk.Frame(self.review_container)
        toolbar.pack(fill=X, padx=5, pady=2)

        self.check_all_btn = ttk.Button(toolbar, text="Check All", command=lambda: self.toggle_all_approvals(True),
                                        bootstyle="info-outline", width=10)
        self.check_all_btn.pack(side=LEFT, padx=2)
        self.uncheck_all_btn = ttk.Button(toolbar, text="Uncheck All", command=lambda: self.toggle_all_approvals(False),
                                          bootstyle="info-outline", width=12)
        self.uncheck_all_btn.pack(side=LEFT, padx=2)

        ttk.Button(toolbar, text="Add Manual Card", command=self.add_manual_card, 
                   bootstyle="info-outline").pack(side=LEFT, padx=(10, 0))
        self.copy_cards_btn = ttk.Button(toolbar, text="Copy Cards", command=self.copy_cards,
                                         bootstyle="info-outline")
        self.copy_cards_btn.pack(side=LEFT, padx=(4, 0))

        # Clear All stays available for a blocked session so the cached file
        # can still be discarded even when no cards were restored.
        self.clear_all_btn = ttk.Button(toolbar, text="Clear All", command=self.clear_all_cards,
                                        bootstyle="danger-link")
        self.clear_all_btn.pack(side=RIGHT, padx=5)

        # Bulk move
        bulk_deck_frame = ttk.Frame(toolbar)
        bulk_deck_frame.pack(side=RIGHT, padx=10)
        self.bulk_deck_var = ttk.StringVar()
        self.bulk_deck_combo = ttk.Combobox(bulk_deck_frame, textvariable=self.bulk_deck_var, values=self.available_decks, state="readonly", width=20)
        self.bulk_deck_combo.pack(side=LEFT, padx=(10, 5))
        self.move_selected_btn = ttk.Button(bulk_deck_frame, text="Move Selected", command=self.bulk_assign_deck,
                                            bootstyle="primary-outline")
        self.move_selected_btn.pack(side=LEFT)

        # Header above the scroll area; holds the run summary when present.
        self.review_header = ttk.Frame(self.review_container)
        self.review_header.pack(fill=X)
        self.summary_label = ttk.Label(self.review_header, font=("Segoe UI", 9),
                                       anchor=W, justify=LEFT)
        card_filter_frame = ttk.Frame(self.review_header)
        card_filter_frame.pack(side=RIGHT)
        self.approved_only_var = ttk.BooleanVar(value=False)
        ttk.Checkbutton(card_filter_frame, text="Approved", variable=self.approved_only_var,
                        command=self._on_approved_filter,
                        bootstyle="round-toggle").pack(side=LEFT, padx=(0, 6))
        self.pending_only_var = ttk.BooleanVar(value=False)
        ttk.Checkbutton(card_filter_frame, text="Pending", variable=self.pending_only_var,
                        command=self._on_pending_filter,
                        bootstyle="round-toggle").pack(side=LEFT, padx=(0, 8))
        self.card_filter_count = ttk.Label(card_filter_frame, text="", font=("Segoe UI", 8))
        self.card_filter_count.pack(side=LEFT, padx=(0, 6))
        self.card_filter_var = ttk.StringVar()
        self.card_filter = ttk.Entry(card_filter_frame, textvariable=self.card_filter_var,
                                     placeholder="Filter cards…", width=20)
        self.card_filter.pack(side=LEFT)
        self.card_filter.bind("<KeyRelease>", self._filter_cards)
        ttk.Button(card_filter_frame, text="×", width=2, bootstyle="secondary-outline",
                   command=self._clear_card_filter).pack(side=LEFT, padx=(3, 0))

        # Review Area (Single Pane) — persistent scrollbar makes long lists
        # obviously scrollable instead of silently clipping the last cards.
        self.review_frame = ScrolledFrame(self.review_container, autohide=False)
        self.review_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # First-run guidance: the review pane starts empty, so explain the next
        # step instead of presenting a featureless dark rectangle.
        self.review_placeholder = ttk.Frame(self.review_frame)
        ttk.Label(self.review_placeholder, text="🧠", font=("Segoe UI Emoji", 30)).pack()
        ttk.Label(self.review_placeholder, text="No cards to review yet",
                  font=("Segoe UI", 14, "bold")).pack(pady=(6, 2))
        ttk.Label(
            self.review_placeholder,
            text="Select a document, transcript or URL on the left,\nthen press Generate Cards to create your first cards.",
            font=("Segoe UI", 10), justify="center",
        ).pack()
        self._sync_review_placeholder()

        # 2. Input & Decks - Moved to Middle
        top_frame = ttk.Frame(self.main_tab)
        top_frame.grid(row=1, column=0, sticky=EW, padx=20, pady=10)
        top_frame.columnconfigure(0, weight=1)
        top_frame.columnconfigure(1, weight=1)

        # Left Panel (Input Configuration)
        left_panel = ttk.Labelframe(top_frame, text="Input Configuration", padding=15)
        left_panel.grid(row=0, column=0, sticky=NSEW, padx=(0, 10))
        left_panel.columnconfigure(0, weight=1)

        # File Info Box
        self.file_box = ttk.Frame(left_panel, padding=10, relief=RIDGE, borderwidth=1)
        self.file_box.pack(fill=X, pady=(0, 10))
        
        self.emoji_label = ttk.Label(self.file_box, text="📎", font=("Segoe UI Emoji", 24), anchor="center")
        self.emoji_label.pack(side=LEFT, padx=10)

        file_text = ttk.Frame(self.file_box)
        file_text.pack(side=LEFT, fill=X, expand=True)

        self.file_label = ttk.Label(file_text, text="No file selected",
                                    font=("Segoe UI", 10, "bold"), anchor="w")
        self.file_label.pack(anchor=W)
        self.source_hint = ttk.Label(
            file_text,
            text="PDF · Word · PowerPoint · text · VTT/SRT · audio/video — or paste a URL below",
            font=("Segoe UI", 8), anchor="w",
        )
        self.source_hint.pack(anchor=W, pady=(2, 0))
        self.clear_source_btn = ttk.Button(self.file_box, text="×", width=2,
                                           command=self.clear_source,
                                           bootstyle="secondary-outline")
        self.clear_source_btn.pack(side=RIGHT)

        # Select Document Button — the first, primary step, so give it a filled
        # button; the URL/podcast actions below stay secondary (outline).
        self.select_btn = ttk.Button(left_panel, text="Select Document / Media  (Ctrl+O)", command=self.select_file, bootstyle="primary")
        self.select_btn.pack(fill=X, pady=(0, 5))

        # Import a YouTube or podcast transcript URL
        import_row = ttk.Frame(left_panel)
        import_row.pack(fill=X, pady=(0, 5))
        self.import_btn = ttk.Button(import_row, text="Import URL / Media", command=self.import_media_url, bootstyle="info-outline")
        self.import_btn.pack(side=LEFT, fill=X, expand=True, padx=(0, 3))
        self.browse_btn = ttk.Button(import_row, text="Browse Podcast", command=self.browse_podcast, bootstyle="info-outline")
        self.browse_btn.pack(side=LEFT, fill=X, expand=True, padx=(3, 0))

        # Preview the text that will be sent to the LLM
        self.preview_btn = ttk.Button(left_panel, text="Preview Transcript (select a source first)",
                                      command=self.preview_transcript, bootstyle="info-outline", state="disabled")
        self.preview_btn.pack(fill=X, pady=(0, 10))

        # Language Selection
        lang_frame = ttk.Frame(left_panel)
        lang_frame.pack(fill=X, pady=(0, 10))
        
        ttk.Label(lang_frame, text="Card Language:").pack(side=LEFT)
        
        langs = ["English", "Turkish", "Spanish", "French", "German", "Japanese", "Chinese"]
        self.lang_var = ttk.StringVar(value=self.config.get("language", "English"))
        self.lang_combo = ttk.Combobox(lang_frame, textvariable=self.lang_var, values=langs, state="readonly")
        self.lang_combo.pack(side=RIGHT, fill=X, expand=True, padx=(10, 0))
        self.lang_combo.bind("<<ComboboxSelected>>", lambda e: self.save_config())

        # Density quick control — the variable is shared with Settings.
        density_frame = ttk.Frame(left_panel)
        density_frame.pack(fill=X, pady=(0, 10))
        ttk.Label(density_frame, text="Card Density:").pack(side=LEFT)
        self.gen_density_combo = ttk.Combobox(
            density_frame, textvariable=self.density_var,
            values=["Low", "Medium", "High"], state="readonly", width=12,
        )
        self.gen_density_combo.pack(side=RIGHT, padx=(10, 0))
        self.gen_density_combo.bind("<<ComboboxSelected>>", self._on_generator_density_changed)

        # Generate Button
        self.generate_btn = ttk.Button(left_panel, text="Generate Cards  (Ctrl+Enter)", command=self.start_processing, bootstyle="success")
        self.generate_btn.pack(fill=X)

        # Right Panel (Deck List)
        self.deck_frame = ttk.Labelframe(top_frame, text="Available Decks", padding=5)
        self.deck_frame.grid(row=0, column=1, sticky=NSEW)
        deck_frame = self.deck_frame

        ttk.Label(
            deck_frame,
            text="Tick the decks the AI may assign cards to. Leave all unticked to allow every deck.",
            font=("Segoe UI", 9), wraplength=430, justify=LEFT,
        ).pack(anchor=W, padx=5, pady=(2, 6))

        deck_filter_frame = ttk.Frame(deck_frame)
        deck_filter_frame.pack(fill=X, padx=5, pady=(0, 6))
        self.deck_search_var = ttk.StringVar()
        self.deck_search = ttk.Entry(deck_filter_frame, textvariable=self.deck_search_var,
                                     placeholder="Filter decks…")
        self.deck_search.pack(side=LEFT, fill=X, expand=True)
        self.deck_search.bind("<KeyRelease>", self._filter_decks)
        ttk.Button(deck_filter_frame, text="×", width=2, bootstyle="secondary-outline",
                   command=self._clear_deck_filter).pack(side=LEFT, padx=(4, 0))

        deck_actions = ttk.Frame(deck_frame)
        deck_actions.pack(fill=X, padx=5, pady=(0, 6))
        ttk.Button(deck_actions, text="All", width=5, bootstyle="info-outline",
                   command=lambda: self._set_all_decks(True)).pack(side=LEFT, padx=(0, 4))
        ttk.Button(deck_actions, text="None", width=5, bootstyle="secondary-outline",
                   command=lambda: self._set_all_decks(False)).pack(side=LEFT)
        self.deck_selected_label = ttk.Label(deck_actions, text="All decks", font=("Segoe UI", 9))
        self.deck_selected_label.pack(side=LEFT, padx=(10, 0))

        # Shown only when the bridge cannot be reached, so the fallback deck
        # is explained where the user is looking.
        self.deck_warning = ttk.Label(
            deck_frame, text="Anki offline — using local 'Default' deck.",
            font=("Segoe UI", 9),
            foreground=(self.style.colors or {}).get("warning"),
        )

        self.deck_list_frame = ScrolledFrame(deck_frame, autohide=False)
        self.deck_list_frame.pack(fill=BOTH, expand=True)

        # 3. Bottom Bar: Logs & Sync
        bottom_frame = ttk.Frame(self.main_tab)
        bottom_frame.grid(row=2, column=0, sticky=EW, padx=20, pady=20)
        
        log_panel = ttk.Frame(bottom_frame)
        log_panel.pack(side=LEFT, padx=10, fill=BOTH, expand=True)

        log_header = ttk.Frame(log_panel)
        log_header.pack(fill=X, pady=(0, 4))
        ttk.Label(log_header, text="Activity Log", font=("Segoe UI", 9, "bold")).pack(side=LEFT)
        self.clear_on_run_var = ttk.BooleanVar(value=False)
        ttk.Checkbutton(log_header, text="Clear on run", variable=self.clear_on_run_var,
                        bootstyle="round-toggle").pack(side=LEFT, padx=(10, 0))
        self.log_search_var = ttk.StringVar()
        self.log_search = ttk.Entry(log_header, textvariable=self.log_search_var,
                                    placeholder="Find in log…", width=14)
        self.log_search.pack(side=LEFT, padx=(10, 0))
        self.log_search.bind("<KeyRelease>", self._search_log)
        self.log_search.bind("<Return>", self._jump_to_first_match)
        self.log_match_label = ttk.Label(log_header, text="", font=("Segoe UI", 8))
        self.log_match_label.pack(side=LEFT, padx=(5, 0))
        ttk.Button(log_header, text="×", width=2, bootstyle="secondary-outline",
                   command=self._clear_log_search).pack(side=LEFT, padx=(4, 0))
        log_actions = ttk.Frame(log_header)
        log_actions.pack(side=RIGHT)
        self.log_toggle_btn = ttk.Button(log_actions, text="Hide", width=5,
                                         command=self.toggle_log_panel,
                                         bootstyle="secondary-outline")
        self.log_toggle_btn.pack(side=LEFT, padx=(0, 4))
        self.errors_btn = ttk.Button(log_actions, text="Errors: Off",
                                     command=self.toggle_errors_only,
                                     bootstyle="secondary-outline", width=9)
        self.errors_btn.pack(side=LEFT, padx=(0, 4))
        self.autoscroll_btn = ttk.Button(log_actions, text="Follow: On",
                                         command=self.toggle_log_autoscroll,
                                         bootstyle="info-outline", width=9)
        self.autoscroll_btn.pack(side=LEFT, padx=(0, 4))
        self.wrap_btn = ttk.Button(log_actions, text="Wrap: On",
                                   command=self.toggle_log_wrap,
                                   bootstyle="info-outline", width=8)
        self.wrap_btn.pack(side=LEFT, padx=(0, 4))
        self.timestamp_btn = ttk.Button(log_actions, text="Time: Off",
                                        command=self.toggle_log_timestamps,
                                        bootstyle="secondary-outline", width=8)
        self.timestamp_btn.pack(side=LEFT, padx=(0, 4))
        self.copy_log_btn = ttk.Button(log_actions, text="Copy", command=self.copy_log,
                                       bootstyle="info-outline", width=6)
        self.copy_log_btn.pack(side=LEFT, padx=(0, 4))
        self.clear_log_btn = ttk.Button(log_actions, text="Clear", command=self.clear_log,
                                        bootstyle="info-outline", width=6)
        self.clear_log_btn.pack(side=LEFT)

        self.log_area = ScrolledText(log_panel, height=5, state='disabled', font=LOG_FONT, wrap="word")
        self.log_area.configure(**themed_text_options(self.style))
        self.log_area.pack(fill=BOTH, expand=True)
        
        # Right side buttons container
        btns_frame = ttk.Frame(bottom_frame)
        btns_frame.pack(side=RIGHT, padx=10, pady=10)

        self.stop_btn = ttk.Button(btns_frame, text="Stop Processing", command=self.stop_processing, bootstyle="danger", state="disabled")
        self.stop_btn.pack(side=TOP, fill=X, pady=(0, 5))

        self.sync_btn = ttk.Button(btns_frame, text="Sync Approved to Anki", command=self.sync_to_anki, state="disabled")
        self.sync_btn.pack(side=TOP, fill=X)

        # 4. Status bar: live process, card and Anki feedback at a glance.
        status_bar = ttk.Frame(self.main_tab)
        status_bar.grid(row=3, column=0, sticky=EW, padx=20, pady=(0, 12))

        self.status_state = ttk.Label(status_bar, text="● Ready", font=("Segoe UI", 9, "bold"))
        self.status_state.pack(side=LEFT)
        ttk.Label(status_bar, text="  │  ").pack(side=LEFT)
        self.status_cards = ttk.Label(status_bar, text="0 cards · 0 approved", font=("Segoe UI", 9))
        self.status_cards.pack(side=LEFT)
        self.status_progress = ttk.Progressbar(status_bar, mode="indeterminate", length=110)
        self.status_progress.pack(side=LEFT, padx=(14, 0))
        self.status_source = ttk.Label(status_bar, text="Source: none", font=("Segoe UI", 9))
        self.status_source.pack(side=LEFT, padx=(14, 0))
        self.status_model = ttk.Label(status_bar, text="Model: —", font=("Segoe UI", 9))
        self.status_model.pack(side=LEFT, padx=(14, 0))
        self.status_llm = ttk.Label(status_bar, text="LLM: —", font=("Segoe UI", 9))
        self.status_llm.pack(side=LEFT, padx=(14, 0))
        conn_frame = ttk.Frame(status_bar)
        conn_frame.pack(side=RIGHT)
        self.status_anki = ttk.Label(conn_frame, text="Anki: checking…", font=("Segoe UI", 9))
        self.status_anki.pack(side=LEFT)
        self.retry_anki_btn = ttk.Button(conn_frame, text="Retry", command=self.retry_anki_connection,
                                         bootstyle="info-outline", width=6)
        self.retry_anki_btn.pack(side=LEFT, padx=(8, 0))
        ttk.Button(conn_frame, text="?", width=2, bootstyle="info-outline",
                   command=self.show_shortcuts).pack(side=LEFT, padx=(8, 0))
        self._refresh_status()

    def setup_settings_tab(self):
        self._settings_ready = False
        self.settings_dirty = False

        # Fixed footer: the save action stays visible no matter how far the
        # settings have been scrolled (and cannot be clipped off-screen).
        footer = ttk.Frame(self.settings_tab, padding=(20, 10))
        footer.pack(fill=X, side=BOTTOM)
        self.settings_status = ttk.Label(footer, text="● Saved to config.json", font=("Segoe UI", 9))
        self.settings_status.pack(side=LEFT)
        footer_actions = ttk.Frame(footer)
        footer_actions.pack(side=RIGHT)
        ttk.Button(footer_actions, text="Reset", command=self.reset_settings_defaults,
                   bootstyle="info-outline", width=7).pack(side=LEFT, padx=(0, 6))
        self.save_settings_btn = ttk.Button(footer_actions, text="Save Settings",
                                            command=self.save_settings_ui, bootstyle="primary")
        self.save_settings_btn.pack(side=LEFT)
        ttk.Separator(footer, orient=HORIZONTAL).pack(fill=X, side=TOP, pady=(0, 8))

        # Use ScrolledFrame to ensure settings are accessible on smaller screens
        scroll_wrapper = ScrolledFrame(self.settings_tab, autohide=True)
        scroll_wrapper.pack(fill=BOTH, expand=True)
        
        container = ttk.Frame(scroll_wrapper, padding=20)
        container.pack(fill=BOTH, expand=True)
        
        # Theme Settings
        theme_frame = ttk.Labelframe(container, text="Appearance", padding=15)
        theme_frame.pack(fill=X, pady=10)
        
        ttk.Label(theme_frame, text="Theme:").pack(side=LEFT, padx=5)
        current_theme = self.config.get("theme", "darkly")
        self.theme_var = ttk.StringVar(value=current_theme)
        themes = list(THEMES)
        theme_combo = ttk.Combobox(theme_frame, textvariable=self.theme_var, values=themes, state="readonly")
        theme_combo.pack(side=LEFT, padx=5)
        theme_combo.bind("<<ComboboxSelected>>", self.apply_theme)
        
        # AI Settings
        ai_frame = ttk.Labelframe(container, text="AI Server Configuration (OpenAI Compatible / Local LLM)", padding=15)
        ai_frame.pack(fill=X, pady=10)
        
        ai_grid = ttk.Frame(ai_frame)
        ai_grid.pack(fill=X)
        
        # URL
        ttk.Label(ai_grid, text="API URL:").grid(row=0, column=0, sticky=W, pady=5)
        self.api_url_var = ttk.StringVar(value=self.config.get("api_url", "http://localhost:1234/v1/chat/completions"))
        ttk.Entry(ai_grid, textvariable=self.api_url_var, width=50).grid(row=0, column=1, sticky=EW, padx=10, pady=5)
        ttk.Label(ai_grid, text="(e.g. http://localhost:1234/v1/chat/completions)").grid(row=0, column=2, sticky=W, padx=5)
        
        # Key — masked by default; the local LLM key is still a credential and
        # should not be readable over the user's shoulder.
        ttk.Label(ai_grid, text="API Key:").grid(row=1, column=0, sticky=W, pady=5)
        self.api_key_var = ttk.StringVar(value=self.config.get("api_key", "lm-studio"))
        key_row = ttk.Frame(ai_grid)
        key_row.grid(row=1, column=1, sticky=EW, padx=10, pady=5)
        self.api_key_entry = ttk.Entry(key_row, textvariable=self.api_key_var, width=50, show="•")
        self.api_key_entry.pack(side=LEFT, fill=X, expand=True)
        self.show_key_btn = ttk.Button(key_row, text="Show", width=6,
                                       command=self.toggle_api_key_visibility,
                                       bootstyle="secondary-outline")
        self.show_key_btn.pack(side=LEFT, padx=(5, 0))

        self.test_llm_btn = ttk.Button(ai_grid, text="Test Connection",
                                       command=self.test_llm_connection,
                                       bootstyle="info-outline", width=14)
        self.test_llm_btn.grid(row=2, column=1, sticky=W, padx=10, pady=(4, 0))
        self.ai_test_result = ttk.Label(ai_grid, text="", font=("Segoe UI", 9))
        self.ai_test_result.grid(row=2, column=2, sticky=W, padx=8, pady=(4, 0))

        # Model Parameters
        param_frame = ttk.Labelframe(container, text="Model Parameters", padding=15)
        param_frame.pack(fill=X, pady=10)
        
        # Model Name
        ttk.Label(param_frame, text="Model Name:").grid(row=0, column=0, sticky=W, padx=5, pady=5)
        self.model_var = ttk.StringVar(value=self.config.get("model", "local-model"))
        ttk.Entry(param_frame, textvariable=self.model_var, width=30).grid(row=0, column=1, sticky=W, padx=5)
        
        # Temperature
        ttk.Label(param_frame, text="Temperature (0.0 - 1.0):").grid(row=0, column=2, sticky=W, padx=15, pady=5)
        self.temp_var = ttk.DoubleVar(value=self.config.get("temperature", 0.7))
        ttk.Spinbox(param_frame, textvariable=self.temp_var, from_=0.0, to=1.0, increment=0.1, width=10).grid(row=0, column=3, sticky=W, padx=5)
        
        # Max Tokens
        ttk.Label(param_frame, text="Max Tokens (-1 for auto):").grid(row=0, column=4, sticky=W, padx=15, pady=5)
        self.tokens_var = ttk.IntVar(value=self.config.get("max_tokens", -1))
        ttk.Entry(param_frame, textvariable=self.tokens_var, width=10).grid(row=0, column=5, sticky=W, padx=5)
        
        # Context Window
        ttk.Label(param_frame, text="Context Window:").grid(row=1, column=0, sticky=W, padx=5, pady=5)
        self.ctx_var = ttk.IntVar(value=self.config.get("context_window", 4096))
        ttk.Entry(param_frame, textvariable=self.ctx_var, width=30).grid(row=1, column=1, sticky=W, padx=5)

        # Concurrency
        ttk.Label(param_frame, text="Concurrency:").grid(row=2, column=0, sticky=W, padx=5, pady=5)
        self.concurrency_var = ttk.IntVar(value=self.config.get("concurrency", 1))
        ttk.Spinbox(param_frame, textvariable=self.concurrency_var, from_=1, to=10, width=5).grid(row=2, column=1, sticky=W, padx=5)

        # Card Density (variable is shared with the Generator quick control)
        ttk.Label(param_frame, text="Card Density:").grid(row=1, column=2, sticky=W, padx=15, pady=5)
        density_combo = ttk.Combobox(param_frame, textvariable=self.density_var, values=["Low", "Medium", "High"], state="readonly", width=10)
        density_combo.grid(row=1, column=3, sticky=W, padx=5)

        # Quality Control
        qc_frame = ttk.Labelframe(container, text="Quality Control & Filters", padding=15)
        qc_frame.pack(fill=X, pady=10)
        
        self.filter_yes_no_var = ttk.BooleanVar(value=self.config.get("filter_yes_no", True))
        ttk.Checkbutton(qc_frame, text="Auto-remove 'Yes/No' questions", variable=self.filter_yes_no_var, bootstyle="round-toggle").pack(anchor=W, pady=2)
        
        self.exclude_trivia_var = ttk.BooleanVar(value=self.config.get("exclude_trivia", True))
        ttk.Checkbutton(qc_frame, text="Exclude biographical trivia (dates, names)", variable=self.exclude_trivia_var, bootstyle="round-toggle").pack(anchor=W, pady=2)
        
        self.smart_deck_match_var = ttk.BooleanVar(value=self.config.get("smart_deck_match", True))
        ttk.Checkbutton(qc_frame, text="Smart Deck Matching (Content analysis + Shuffle)", variable=self.smart_deck_match_var, bootstyle="round-toggle").pack(anchor=W, pady=2)
        
        self.ai_refinement_var = ttk.BooleanVar(value=self.config.get("ai_refinement", False))
        ttk.Checkbutton(qc_frame, text="AI Refinement (Two-Pass: Generation -> AI Check -> Edit)", variable=self.ai_refinement_var, bootstyle="round-toggle").pack(anchor=W, pady=2)

        # Deterministic Mode
        self.deterministic_mode_var = ttk.BooleanVar(value=self.config.get("deterministic_mode", False))
        ttk.Checkbutton(qc_frame, text="Deterministic Mode (Reproducible Output, No Parallelism)", variable=self.deterministic_mode_var, bootstyle="round-toggle").pack(anchor=W, pady=2)

        # Debug Mode
        self.debug_mode_var = ttk.BooleanVar(value=self.config.get("debug_mode", False))
        ttk.Checkbutton(qc_frame, text="Debug Mode (Verbose Logging)", variable=self.debug_mode_var, bootstyle="round-toggle").pack(anchor=W, pady=2)

        # Prompt Settings
        prompt_frame = ttk.Labelframe(container, text="Custom Prompt / Style Instructions", padding=15)
        prompt_frame.pack(fill=BOTH, expand=True, pady=10)
        
        ttk.Label(prompt_frame, text="Add custom instructions (e.g., 'Make questions difficult', 'Focus on dates'):").pack(anchor=W, pady=(0, 5))
        
        self.prompt_text = ScrolledText(prompt_frame, height=4, font=("Segoe UI", 10))
        self.prompt_text.configure(**themed_text_options(self.style))
        self.prompt_text.pack(fill=BOTH, expand=True)
        self.prompt_text.insert("1.0", self.config.get("prompt_style", ""))
        self.prompt_count = ttk.Label(prompt_frame, text="0 characters", font=("Segoe UI", 8))
        self.prompt_count.pack(anchor=E, pady=(2, 0))
        self._refresh_prompt_count()

        # Mark the form dirty on any real edit (traces are installed after the
        # initial values are written so setup itself never looks like a change).
        for var in (
            self.theme_var, self.api_url_var, self.api_key_var, self.model_var,
            self.temp_var, self.tokens_var, self.ctx_var, self.concurrency_var,
            self.density_var, self.filter_yes_no_var, self.exclude_trivia_var,
            self.smart_deck_match_var, self.ai_refinement_var,
            self.deterministic_mode_var, self.debug_mode_var,
        ):
            var.trace_add("write", lambda *_: self._mark_settings_dirty())
        self.model_var.trace_add("write", lambda *_: self._refresh_status())
        for var in (self.api_url_var, self.api_key_var, self.model_var):
            var.trace_add("write", lambda *_: self._reset_llm_status())
        self.prompt_text.bind("<<Modified>>", self._on_prompt_modified)

        self._settings_ready = True
        self._refresh_settings_status()
        self._refresh_status()

    def load_config(self):
        errors = []
        raw_config = read_json_file(
            CONFIG_FILE,
            {},
            on_error=errors.append,
            quarantine_on_error=True,
        )
        self.config_write_blocked = bool(errors and CONFIG_FILE.exists())
        self.config = normalize_config(raw_config)
    
    def _read_int(self, var, default, minimum=None, maximum=None):
        """Read a numeric Tk variable without letting an empty field crash the UI."""
        try:
            raw_value = var.get()
        except TclError:  # hygiene: allow an empty numeric field is reported as its default
            raw_value = ""
        return parse_int_setting(raw_value, default, minimum, maximum)

    def _read_float(self, var, default, minimum=None, maximum=None):
        """Read a decimal Tk variable without letting an empty field crash the UI."""
        try:
            raw_value = var.get()
        except TclError:  # hygiene: allow an empty decimal field is reported as its default
            raw_value = ""
        return parse_float_setting(raw_value, default, minimum, maximum)

    def _mark_settings_dirty(self):
        """Flag the Settings form as having edits that are not saved yet."""
        if not getattr(self, "_settings_ready", False) or self.settings_dirty:
            return
        self.settings_dirty = True
        self._refresh_settings_status()

    def _refresh_prompt_count(self):
        count = len(self.prompt_text.get("1.0", "end-1c"))
        self.prompt_count.config(text=f"{count:,} character{'s' if count != 1 else ''}")

    def _on_prompt_modified(self, event=None):
        """Handle the Text widget's <<Modified>> event without re-triggering it."""
        if self.prompt_text.edit_modified():
            self._mark_settings_dirty()
            self._refresh_prompt_count()
            self.prompt_text.edit_modified(False)

    def _refresh_settings_status(self):
        """Show a coloured saved/unsaved state in the Settings footer."""
        if not hasattr(self, "settings_status"):
            return
        colors = self.style.colors or {}
        default_fg = colors.get("fg")
        self.notebook.tab(
            self.settings_tab,
            text="Settings •" if self.settings_dirty else "Settings",
        )
        if self.settings_dirty:
            self.settings_status.config(text="● Unsaved changes",
                                        foreground=colors.get("warning") or default_fg)
            self.save_settings_btn.config(text="Save Changes", bootstyle="warning")
        else:
            self.settings_status.config(text="● Saved to config.json",
                                        foreground=colors.get("success") or default_fg)
            self.save_settings_btn.config(text="Save Settings", bootstyle="primary")

    def reset_settings_defaults(self):
        """Restore the shipped defaults from config.example.json after confirming."""
        if not messagebox.askyesno(
            "Reset Settings",
            "Reset all settings to the shipped defaults? This overwrites config.json.",
        ):
            return
        defaults = read_json_file(CONFIG_FILE.parent / "config.example.json", {})
        if not defaults:
            messagebox.showerror("Reset Settings", "The shipped defaults file could not be read.")
            return

        self.config.update(defaults)
        self.theme_var.set(self.config.get("theme", "darkly"))
        self.lang_var.set(self.config.get("language", "English"))
        self.api_url_var.set(self.config.get("api_url", ""))
        self.api_key_var.set(self.config.get("api_key", ""))
        self.model_var.set(self.config.get("model", ""))
        self.temp_var.set(self.config.get("temperature", 0.7))
        self.tokens_var.set(self.config.get("max_tokens", -1))
        self.ctx_var.set(self.config.get("context_window", 4096))
        self.concurrency_var.set(self.config.get("concurrency", 1))
        self.density_var.set(self.config.get("card_density", "Medium"))
        self.filter_yes_no_var.set(self.config.get("filter_yes_no", True))
        self.exclude_trivia_var.set(self.config.get("exclude_trivia", True))
        self.smart_deck_match_var.set(self.config.get("smart_deck_match", True))
        self.ai_refinement_var.set(self.config.get("ai_refinement", False))
        self.deterministic_mode_var.set(self.config.get("deterministic_mode", False))
        self.debug_mode_var.set(self.config.get("debug_mode", False))
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("1.0", self.config.get("prompt_style", ""))
        self._refresh_prompt_count()
        self.apply_theme(None)

        if self.save_config():
            self.settings_dirty = False
            self._refresh_settings_status()
            messagebox.showinfo("Settings", "Settings reset to defaults.")

    def save_settings_ui(self):
        self.config["theme"] = self.theme_var.get()
        self.config["language"] = self.lang_var.get()
        self.config["api_url"] = self.api_url_var.get()
        self.config["api_key"] = self.api_key_var.get()
        self.config["model"] = self.model_var.get()
        self.config["temperature"] = self._read_float(self.temp_var, 0.7, 0.0, 1.0)
        self.config["max_tokens"] = self._read_int(self.tokens_var, -1)
        self.config["context_window"] = self._read_int(self.ctx_var, 4096, 1000, 131072)
        self.config["concurrency"] = self._read_int(self.concurrency_var, 1, 1, 10)
        self.temp_var.set(self.config["temperature"])
        self.tokens_var.set(self.config["max_tokens"])
        self.ctx_var.set(self.config["context_window"])
        self.concurrency_var.set(self.config["concurrency"])
        self.config["card_density"] = self.density_var.get()
        self.config["filter_yes_no"] = self.filter_yes_no_var.get()
        self.config["exclude_trivia"] = self.exclude_trivia_var.get()
        self.config["smart_deck_match"] = self.smart_deck_match_var.get()
        self.config["ai_refinement"] = self.ai_refinement_var.get()
        self.config["deterministic_mode"] = self.deterministic_mode_var.get()
        self.config["debug_mode"] = self.debug_mode_var.get()
        self.config["prompt_style"] = self.prompt_text.get("1.0", "end-1c")

        # Apply logging level immediately
        level = logging.DEBUG if self.config["debug_mode"] else logging.INFO
        self.logger.setLevel(level)

        if self.save_config():
            self.settings_dirty = False
            self._refresh_settings_status()
            messagebox.showinfo("Settings", "Settings saved successfully.")
        elif getattr(self, 'config_write_blocked', False) and CONFIG_FILE.exists():
            if messagebox.askyesno(
                "Settings",
                "The settings file is unreadable. Move it aside and save the current settings?",
            ):
                moved = quarantine_corrupt_file(CONFIG_FILE)
                if moved is not None:
                    self.config_write_blocked = False
                    self.logger.warning(f"Unreadable settings moved to {moved}.")
                    if self.save_config():
                        self.settings_dirty = False
                        self._refresh_settings_status()
                        messagebox.showinfo("Settings", "Settings saved successfully.")
                    else:
                        messagebox.showerror("Settings", "Settings could not be saved. See the log for details.")
                else:
                    messagebox.showerror("Settings", "The settings file could not be moved aside. See the log for details.")
            else:
                messagebox.showerror("Settings", "Settings were not saved. See the log for details.")
        else:
            messagebox.showerror("Settings", "Settings could not be saved. See the log for details.")

    def save_config(self):
        if getattr(self, 'config_write_blocked', False):
            if CONFIG_FILE.exists():
                if hasattr(self, 'logger'):
                    self.logger.error("Settings file is unreadable and was left untouched; refusing to overwrite it.")
                return False
            self.config_write_blocked = False

        # Update config object from vars if they exist (for auto-saves like language)
        if hasattr(self, 'lang_var'): self.config["language"] = self.lang_var.get()

        try:
            write_json_file(CONFIG_FILE, self.config, indent=4)
            return True
        except (OSError, TypeError, ValueError) as exc:
            if hasattr(self, 'logger'):
                self.logger.error(f"Failed to save settings: {exc}")
            return False

    def apply_theme(self, event):
        t = self.theme_var.get()
        self.style.theme_use(t)
        self.style.configure("TLabelframe.Label", font=("Segoe UI", 9, "bold"))
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(12, 6))
        # Tk Text widgets are not ttk themed; repaint them for the new palette.
        self.log_area.configure(**themed_text_options(self.style))
        self.prompt_text.configure(**themed_text_options(self.style))
        self._set_source_hint(
            bool(self.loaded_source_text or self.loaded_source_title
                 or self.selected_file_path)
        )
        self.deck_warning.config(
            foreground=(self.style.colors or {}).get("warning")
        )
        self._refresh_status()

    def toggle_api_key_visibility(self):
        """Reveal or re-mask the API key without changing the stored value."""
        was_masked = self.api_key_entry.cget("show") != ""
        self.api_key_entry.config(show="" if was_masked else "•")
        self.show_key_btn.config(text="Hide" if was_masked else "Show")

    def test_llm_connection(self):
        """Probe the configured LLM endpoint off the UI thread."""
        if str(self.test_llm_btn.cget("state")) != "normal":
            return
        url = self.api_url_var.get().strip()
        if not url:
            messagebox.showwarning("Connection", "Enter an API URL first.")
            return
        api_key = self.api_key_var.get().strip()
        self.test_llm_btn.config(state="disabled", text="Testing…")
        self.logger.info(f"Testing LLM connection at {url}...")

        def worker():
            try:
                check_llm_server(url, api_key)
                ok, message = True, f"Connected to LLM server at {url}."
            except Exception as exc:  # hygiene: show connection failure in the UI
                ok, message = False, f"Could not reach LLM server: {exc}"
            self.after(0, lambda: self._finish_llm_test(ok, message))

        threading.Thread(target=worker, daemon=True).start()

    def _reset_llm_status(self):
        """A changed endpoint/key invalidates the previous probe result."""
        if self.llm_status == "unknown":
            return
        self.llm_status = "unknown"
        self._refresh_status()

    def _finish_llm_test(self, ok, message):
        """Restore the test button, record the result and report it."""
        self.test_llm_btn.config(state="normal", text="Test Connection")
        self.llm_status = "online" if ok else "offline"
        self._refresh_status()
        if ok:
            self.logger.info(message)
        else:
            self.logger.error(message)
        messagebox.showinfo("Connection", message)

    def clear_log(self):
        """Clear only the on-screen console; session.log keeps the full history."""
        self.log_area.config(state='normal')
        self.log_area.delete('1.0', 'end')
        self.log_area.config(state='disabled')

    def show_shortcuts(self):
        """List the keyboard shortcuts in one place."""
        messagebox.showinfo(
            "Keyboard Shortcuts",
            "Ctrl+O   Select document / media\n"
            "Ctrl+Enter   Generate cards\n"
            "Ctrl+P   Preview transcript\n"
            "Ctrl+F   Find in the activity log\n"
            "Escape   Clear card and deck filters",
        )

    def _jump_to_first_match(self, event=None):
        """Enter scrolls the console to the first highlighted match."""
        ranges = self.log_area.tag_ranges("search")
        if ranges:
            self.log_area.see(ranges[0])
        return "break"

    def _clear_log_search(self):
        self.log_search_var.set("")
        self._search_log()

    def _search_log(self, event=None):
        """Highlight every match of the current search text in the console."""
        self.log_area.tag_remove("search", "1.0", "end")
        query = self.log_search_var.get().strip()
        if not query:
            self.log_match_label.config(text="")
            return
        colors = self.style.colors or {}
        self.log_area.tag_configure(
            "search",
            background=colors.get("warning"),
            foreground=colors.get("bg"),
        )
        index = "1.0"
        while True:
            index = self.log_area.search(query, index, stopindex="end", nocase=True)
            if not index:
                break
            end = f"{index}+{len(query)}c"
            self.log_area.tag_add("search", index, end)
            index = end
        count = len(self.log_area.tag_ranges("search")) // 2
        self.log_match_label.config(
            text=f"{count} match{'es' if count != 1 else ''}",
            foreground=colors.get("warning"),
        )

    def toggle_errors_only(self):
        """Hide info/warning lines so only errors remain visible."""
        self.errors_only = not self.errors_only
        for tag in ("info", "warning"):
            self.log_area.tag_configure(tag, elide=self.errors_only)
        self.errors_btn.config(
            text="Errors: On" if self.errors_only else "Errors: Off",
            bootstyle="danger-outline" if self.errors_only else "secondary-outline",
        )

    def toggle_log_autoscroll(self):
        """Stop new log lines from stealing the user's scroll position."""
        self.log_autoscroll = not self.log_autoscroll
        self.autoscroll_btn.config(
            text="Follow: On" if self.log_autoscroll else "Follow: Off",
            bootstyle="info-outline" if self.log_autoscroll else "secondary-outline",
        )

    def toggle_log_panel(self):
        """Collapse the console to give the review list more room."""
        if self.log_area.winfo_ismapped():
            self.log_area.pack_forget()
            self.log_toggle_btn.config(text="Show")
        else:
            self.log_area.pack(fill=BOTH, expand=True)
            self.log_toggle_btn.config(text="Hide")

    def toggle_log_wrap(self):
        """Switch long log lines between wrapping and horizontal scrolling."""
        wrapping = str(self.log_area.cget("wrap")) != "none"
        self.log_area.config(wrap="none" if wrapping else "word")
        self.wrap_btn.config(
            text="Wrap: Off" if wrapping else "Wrap: On",
            bootstyle="secondary-outline" if wrapping else "info-outline",
        )

    def toggle_log_timestamps(self):
        """Prefix on-screen log lines with the time for troubleshooting."""
        self._log_timestamps = not self._log_timestamps
        if self._log_timestamps:
            fmt, datefmt = "[%(asctime)s] %(message)s", "%H:%M:%S"
        else:
            fmt, datefmt = "%(message)s", None
        self.ui_log_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        self.timestamp_btn.config(
            text="Time: On" if self._log_timestamps else "Time: Off",
            bootstyle="info-outline" if self._log_timestamps else "secondary-outline",
        )
        self.logger.info("Timestamp display %s.", "enabled" if self._log_timestamps else "disabled")

    def copy_log(self):
        """Copy the log (or just the errors) for a bug report."""
        if self.errors_only:
            ranges = self.log_area.tag_ranges("error")
            text = "\n".join(
                self.log_area.get(ranges[i], ranges[i + 1])
                for i in range(0, len(ranges), 2)
            ).strip()
        else:
            text = self.log_area.get("1.0", "end-1c")
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.logger.info("Activity log copied to clipboard.")

    def _llm_startup_check(self):
        """Probe the configured LLM endpoint once at startup, off the UI thread."""
        url = self.api_url_var.get().strip()
        api_key = self.api_key_var.get().strip()

        def worker():
            try:
                check_llm_server(url, api_key)
                ok = True
            except Exception:  # hygiene: offline at startup is reported in the status bar
                ok = False
            self.after(0, lambda: self._set_llm_startup_result(ok))

        threading.Thread(target=worker, daemon=True).start()

    def _set_llm_startup_result(self, ok):
        self.llm_status = "online" if ok else "offline"
        self._refresh_status()

    def retry_anki_connection(self):
        """Re-run the deck fetch so starting Anki later needs no app restart."""
        if self.processing or self.preview_loading or str(self.retry_anki_btn.cget("state")) != "normal":
            return
        self.retry_anki_btn.config(state="disabled")
        self.anki_status = "checking"
        self._refresh_status()
        self.logger.info("Retrying the Anki bridge connection...")
        threading.Thread(target=self._fetch_decks_thread, daemon=True).start()

    def fetch_decks(self):
        # We need logger initialized before using it. setup_main_tab creates log_area, which is needed for setup_logging.
        # So setup_logging is called after setup_main_tab in __init__.
        # This function is called last in __init__, so self.logger should be ready.
        if hasattr(self, 'logger'):
            self.logger.info("Connecting to Anki...")
        threading.Thread(target=self._fetch_decks_thread).start()

    def _fetch_decks_thread(self):
        # Fallback if logger not ready (shouldn't happen)
        log_cb = self.logger.info if hasattr(self, 'logger') else print

        decks = get_deck_names(log_callback=log_cb)
        if decks:
            self.available_decks = decks
            self.anki_status = "connected"
            log_cb(f"Connected to Anki. Found {len(decks)} decks.")
        else:
            self.available_decks = ["Default"]
            self.anki_status = "disconnected"
            log_cb("Could not connect to Anki Add-on. Is Anki open?")
        
        self.after(0, self.update_deck_list_ui)

    def update_deck_list_ui(self):
        # Clear previous checkboxes
        for cb in self.deck_checkboxes:
            cb.destroy()
        self.deck_checkboxes = []
        self.deck_vars = {}
        self.deck_rows = {}

        saved_decks = self.config.get("selected_decks", [])
        is_first_run = "selected_decks" not in self.config

        if self.available_decks:
            for deck in sorted(self.available_decks):
                var = ttk.BooleanVar()
                # Default to selected if it's the first run, otherwise check config
                if is_first_run:
                    var.set(True)
                else:
                    var.set(deck in saved_decks)
                
                self.deck_vars[deck] = var
                cb = ttk.Checkbutton(self.deck_list_frame, text=deck, variable=var, command=self.save_deck_selection)
                cb.pack(anchor=W, padx=5, pady=2, fill=X)
                self.deck_checkboxes.append(cb)
                self.deck_rows[deck] = cb
        else:
            lbl = ttk.Label(self.deck_list_frame, text="(No decks found)")
            lbl.pack(anchor=W, padx=5)
            self.deck_checkboxes.append(lbl)
            
        count = len(self.available_decks)
        self.deck_frame.config(text=f"Available Decks ({count})")

        # Update bulk assignment dropdown
        if hasattr(self, 'bulk_deck_combo'):
            self.bulk_deck_combo['values'] = self.available_decks
            if self.available_decks and not self.bulk_deck_var.get():
                self.bulk_deck_var.set(self.available_decks[0])
            
        # Load session if not already loaded (runs once after initial deck fetch)
        if not self._session_loaded:
            self.load_session()
            self._session_loaded = True

        if getattr(self, "anki_status", "checking") == "disconnected":
            self.deck_warning.pack(anchor=W, padx=5, pady=(0, 6))
            # Re-pack the list so the notice sits above it in pack order.
            self.deck_list_frame.pack(fill=BOTH, expand=True)
        else:
            self.deck_warning.pack_forget()

        self.retry_anki_btn.config(state="normal")
        self._refresh_deck_selected_label()
        self._refresh_status()

    def _clear_deck_filter(self):
        self.deck_search_var.set("")
        self._filter_decks()

    def _filter_decks(self, event=None):
        """Show only decks whose name contains the current filter text."""
        query = self.deck_search_var.get().strip().casefold()
        visible = 0
        for name, checkbox in self.deck_rows.items():
            if query in name.casefold():
                checkbox.pack(anchor=W, padx=5, pady=2, fill=X)
                visible += 1
            else:
                checkbox.pack_forget()

        if query and not visible:
            color = (self.style.colors or {}).get("warning")
            self.deck_selected_label.config(text="No matching decks", foreground=color)
        else:
            self._refresh_deck_selected_label()

    def _refresh_deck_selected_label(self):
        count = sum(1 for var in self.deck_vars.values() if var.get())
        self.deck_selected_label.config(
            text="All decks" if count == 0 else f"{count} selected",
            foreground=(self.style.colors or {}).get("fg"),
        )

    def _set_all_decks(self, selected):
        """Select or clear every discovered deck in one action."""
        for var in self.deck_vars.values():
            var.set(selected)
        self.save_deck_selection()

    def save_deck_selection(self):
        selected = [d for d, v in self.deck_vars.items() if v.get()]
        self.config["selected_decks"] = selected
        self._refresh_deck_selected_label()
        self.save_config()

    def clear_source(self):
        """Forget the selected file/URL without discarding reviewed cards."""
        self.selected_file_path = None
        self.loaded_source_text = None
        self.loaded_source_title = None
        self.source_text = ""
        self.file_label.config(text="No file selected")
        self.emoji_label.config(text="📎")
        self.preview_btn.config(state="disabled",
                                text="Preview Transcript (select a source first)")
        self._set_source_hint(False)
        self._refresh_status()
        self.logger.info("Source selection cleared.")

    def _set_source_hint(self, ready):
        """Switch the source box's subtitle between format help and ready state."""
        if ready:
            self.source_hint.config(
                text="Source ready — preview it, then press Ctrl+Enter to generate.",
                foreground=(self.style.colors or {}).get("success"),
            )
        else:
            self.source_hint.config(
                text="PDF · Word · PowerPoint · text · VTT/SRT · audio/video — or paste a URL below",
                foreground=(self.style.colors or {}).get("fg"),
            )

    def select_file(self):
        filetypes = [
            ("All Supported Sources", "*.pdf *.docx *.pptx *.txt *.srt *.vtt *.json *.mp3 *.m4a *.wav *.ogg *.oga *.flac *.wma *.aac *.mp4 *.m4v *.mkv *.webm *.mov *.avi *.mpeg *.mpg"),
            ("Documents", "*.pdf *.docx *.pptx *.txt"),
            ("Transcripts", "*.srt *.vtt *.json *.txt"),
            ("Podcast Audio / Video", "*.mp3 *.m4a *.wav *.ogg *.oga *.flac *.wma *.aac *.mp4 *.m4v *.mkv *.webm *.mov *.avi *.mpeg *.mpg"),
            ("PDF Files", "*.pdf"),
            ("Word Documents", "*.docx"),
            ("PowerPoint Presentations", "*.pptx"),
            ("Text Files", "*.txt")
        ]
        file_path = filedialog.askopenfilename(filetypes=filetypes)
        if file_path:
            self.selected_file_path = file_path
            self.loaded_source_text = None
            self.loaded_source_title = None
            self.source_text = ""
            # preview_transcript() extracts local files on demand, so Preview
            # is available as soon as a source is chosen.
            self.preview_btn.config(state="normal")
            filename = os.path.basename(file_path)
            extension = os.path.splitext(filename)[1].lower()

            # Uzun dosya isimlerini kısalt (UI bozulmasını önlemek için)
            if len(filename) > 35:
                display_text = filename[:32] + "..."
            else:
                display_text = filename

            self.file_label.config(text=display_text)
            self.preview_btn.config(text="Preview Transcript (Ctrl+P)")
            self._set_source_hint(True)
            self._refresh_status()
            if extension in (".vtt", ".srt", ".json"):
                self.emoji_label.config(text="📝")
            elif is_video_file(filename):
                self.emoji_label.config(text="🎬")
            elif is_audio_file(filename):
                self.emoji_label.config(text="🎧")
            else:
                self.emoji_label.config(text="📄")
            ToolTip(self.file_label, text=filename)

    def import_media_url(self):
        """Fetch a transcript, article or PDF from a URL."""
        url = simpledialog.askstring(
            "Import URL / Media",
            "Paste a YouTube, Apple Podcasts or podcast RSS URL,\n"
            "a website article, PDF or direct video/audio URL, or a transcript URL:",
            parent=self,
        )
        if not url or not url.strip():
            return

        url = url.strip()
        self._set_import_busy(True)
        self.logger.info(f"Fetching transcript from {url}...")
        threading.Thread(
            target=self._import_media_url_worker,
            args=(url, self.lang_var.get()),
            daemon=True,
        ).start()

    def _import_media_url_worker(self, url, language):
        try:
            result = fetch_transcript_from_url(url, language=language, log_callback=self.logger.info)
        except Exception as exc:
            self.after(0, lambda error=exc: self._handle_import_error(error))
            return
        self.after(0, lambda value=result: self._apply_imported_transcript(value))
        self.after(0, self._reset_import_controls)

    def browse_podcast(self):
        """List a feed's transcribed episodes and fetch the chosen one."""
        url = simpledialog.askstring(
            "Browse Podcast Episodes",
            "Paste a podcast RSS feed or Apple Podcasts show URL:",
            parent=self,
        )
        if not url or not url.strip():
            return

        url = url.strip()
        self._set_import_busy(True)
        self.logger.info(f"Loading podcast feed {url}...")
        threading.Thread(
            target=self._browse_podcast_worker,
            args=(url, self.lang_var.get()),
            daemon=True,
        ).start()

    def _browse_podcast_worker(self, url, language):
        try:
            feed = fetch_podcast_feed(url, language=language, log_callback=self.logger.info)
        except Exception as exc:
            self.after(0, lambda error=exc: self._handle_import_error(error))
            return
        self.after(0, lambda value=feed: self._choose_podcast_episode(value))

    def _choose_podcast_episode(self, feed):
        try:
            selected = choose_podcast_episode(self, feed)
        except Exception as exc:
            self._handle_import_error(exc)
            return
        if selected is None:
            self.logger.info("Podcast episode selection cancelled.")
            self._reset_import_controls()
            return

        self.logger.info(f"Selected podcast episode: {selected.episode_title}")
        threading.Thread(
            target=self._fetch_podcast_episode_worker,
            args=(selected,),
            daemon=True,
        ).start()

    def _fetch_podcast_episode_worker(self, selected):
        try:
            result = fetch_podcast_transcript_for_ref(selected, log_callback=self.logger.info)
        except Exception as exc:
            self.after(0, lambda error=exc: self._handle_import_error(error))
            return
        self.after(0, lambda value=result: self._apply_imported_transcript(value))
        self.after(0, self._reset_import_controls)

    def _handle_import_error(self, exc):
        self.logger.error(f"Transcript import failed: {exc}")
        messagebox.showerror("Transcript Import Failed", str(exc))
        self._reset_import_controls()

    def _set_import_busy(self, busy):
        state = "disabled" if busy else "normal"
        self.import_btn.config(state=state)
        self.browse_btn.config(state=state)
        if busy:
            self.generate_btn.config(state="disabled")
        elif not self.processing:
            self.generate_btn.config(state="normal")

    def _apply_imported_transcript(self, result):
        self.loaded_source_text = result.text
        self.loaded_source_title = result.title
        self.selected_file_path = None
        self.source_text = result.text

        display_text = result.title or result.source_url
        if len(display_text) > 35:
            display_text = display_text[:32] + "..."
        self.file_label.config(text=display_text)
        self._set_source_hint(True)
        self._refresh_status()
        self.emoji_label.config(text={"youtube": "▶", "podcast": "🎧"}.get(result.kind, "📝"))
        ToolTip(self.file_label, text=f"{result.title}\n{result.source_url}")
        self.preview_btn.config(state="normal", text="Preview Transcript (Ctrl+P)")
        self.logger.info(f"Imported {len(result.text)} characters from {result.kind} source: {result.title}.")

    def _reset_import_controls(self):
        self._set_import_busy(False)

    def preview_transcript(self):
        """Show the text that will be sent to the LLM, extracting it if needed."""
        text = self.loaded_source_text or self.source_text
        if text:
            title = self.loaded_source_title
            if not title and self.selected_file_path:
                title = os.path.basename(self.selected_file_path)
            show_text_preview(self, title or "Source Text", text)
            return

        if not self.selected_file_path:
            messagebox.showinfo("Preview Transcript", "No source is loaded yet.")
            return
        if self.preview_loading:
            return

        self._set_preview_busy(True)
        self.logger.info("Extracting source text for preview...")
        threading.Thread(
            target=self._preview_file_worker,
            args=(self.selected_file_path,),
            daemon=True,
        ).start()

    def _check_local_source_size(self, file_path):
        """Enforce the 50 MB document guard and the 300 MB local media cap."""
        if is_audio_file(file_path):
            size = os.path.getsize(file_path)
            if size > MAX_MEDIA_BYTES:
                raise Exception(
                    f"Media file too large ({size / (1024 * 1024):.1f}MB). "
                    f"Max allowed is {MAX_MEDIA_BYTES // (1024 * 1024)}MB."
                )
            return
        ResourceGuard.check_file_size(file_path)

    def _preview_file_worker(self, file_path):
        try:
            self._check_local_source_size(file_path)
            text = extract_text_from_document(file_path, log_callback=self.logger.info)
        except Exception as exc:
            self.after(0, lambda error=exc: self._preview_failed(error))
            return
        self.after(0, lambda value=text: self._preview_ready(file_path, value))

    def _preview_ready(self, file_path, text):
        self.loaded_source_text = text
        self.loaded_source_title = os.path.basename(file_path)
        self.source_text = text
        self._set_preview_busy(False)
        show_text_preview(self, self.loaded_source_title, text)

    def _preview_failed(self, exc):
        self.logger.error(f"Preview extraction failed: {exc}")
        messagebox.showerror("Preview Failed", str(exc))
        self._set_preview_busy(False)
        # Keep preview available when a file is still selected so the user
        # can retry after fixing the cause (missing dependency, bad file).
        if self.selected_file_path:
            self.preview_btn.config(state="normal")

    def _set_preview_busy(self, busy):
        self.preview_loading = busy
        state = "disabled" if busy else "normal"
        self.select_btn.config(state=state)
        self.import_btn.config(state=state)
        self.browse_btn.config(state=state)
        if busy:
            self.generate_btn.config(state="disabled")
            self.preview_btn.config(state="disabled")
            return
        if not self.processing:
            self.generate_btn.config(state="normal")
        # A chosen local file is previewable too — text is extracted on demand.
        has_text = bool(self.loaded_source_text or self.source_text
                        or self.selected_file_path)
        self.preview_btn.config(state="normal" if has_text else "disabled")

    def _on_generator_density_changed(self, event=None):
        """Persist a density change made from the Generator quick control."""
        self.config["card_density"] = self.density_var.get()
        self.save_config()

    def _shortcut_select(self, event=None):
        """Ctrl+O opens the source chooser when that action is available."""
        if self.processing or self.preview_loading or str(self.select_btn.cget("state")) != "normal":
            return "break"
        self.select_file()
        return "break"

    def _shortcut_find(self, event=None):
        """Ctrl+F focuses and selects the log search field."""
        self.log_search.focus_set()
        self.log_search.select_range(0, "end")
        return "break"

    def _shortcut_preview(self, event=None):
        """Ctrl+P opens the transcript preview when a source is available."""
        if (self.processing or self.preview_loading
                or str(self.preview_btn.cget("state")) != "normal"):
            return "break"
        self.preview_transcript()
        return "break"

    def _shortcut_generate(self, event=None):
        """Ctrl+Enter starts generation when the button is enabled."""
        if self.processing or self.preview_loading or str(self.generate_btn.cget("state")) != "normal":
            return "break"
        self.start_processing()
        return "break"

    def start_processing(self):
        if self.preview_loading:
            messagebox.showwarning("Warning", "Please wait for the preview extraction to finish.")
            return
        if not self.selected_file_path and not self.loaded_source_text:
            messagebox.showwarning("Warning", "Please select a document, audio file, or import a transcript first.")
            return
        
        # Ensure we capture the latest prompt from the UI even if "Save Settings" wasn't clicked
        if hasattr(self, 'prompt_text'):
            self.config["prompt_style"] = self.prompt_text.get("1.0", "end-1c")

        target_lang = self.lang_var.get()
        api_url = self.api_url_var.get()
        api_key = self.api_key_var.get()
        model = self.model_var.get()
        temperature = self._read_float(self.temp_var, 0.7, 0.0, 1.0)
        max_tokens = self._read_int(self.tokens_var, -1)  # aikit:allow-secret default token limit, not a credential
        context_window = self._read_int(self.ctx_var, 4096, 1000, 131072)
        concurrency = self._read_int(self.concurrency_var, 1, 1, 10)
        card_density = self.density_var.get()
        prompt_style = self.config.get("prompt_style", "")
        filter_yes_no = self.filter_yes_no_var.get()
        exclude_trivia = self.exclude_trivia_var.get()
        smart_deck_match = self.smart_deck_match_var.get()
        ai_refinement = self.ai_refinement_var.get()
        deterministic_mode = self.deterministic_mode_var.get()
        
        # Get selected decks
        selected_decks = [d for d, v in self.deck_vars.items() if v.get()]
        
        # If no specific decks are selected, let AI choose from ALL available decks
        if not selected_decks:
            self.logger.info("No specific decks selected. AI will choose from all available decks.")
            selected_decks = self.available_decks
        
        # A new run should show all of its cards, not inherit a stale filter
        # from the previous review session.
        if (self.card_filter_var.get() or self.approved_only_var.get()
                or self.pending_only_var.get()):
            self.card_filter_var.set("")
            self.approved_only_var.set(False)
            self.pending_only_var.set(False)
            self._filter_cards()

        self.generate_btn.config(state="disabled", text="Working…")
        self.stop_btn.config(state="normal")
        self.select_btn.config(state="disabled")
        self.import_btn.config(state="disabled")
        self.browse_btn.config(state="disabled")
        self.preview_btn.config(state="disabled")
        self.processing = True
        self.stop_requested = False
        self.set_generation_phase("Starting…")
        if self.clear_on_run_var.get():
            self.after(0, self.clear_log)
        self.logger.info("Starting processing...")

        preloaded_text = self.loaded_source_text
        threading.Thread(target=self.run_process, args=(self.selected_file_path, target_lang, api_url, api_key, model, temperature, max_tokens, prompt_style, selected_decks, context_window, concurrency, card_density, filter_yes_no, exclude_trivia, smart_deck_match, ai_refinement, deterministic_mode, preloaded_text), daemon=True).start()

    def run_process(self, file_path, target_lang, api_url, api_key, model, temperature, max_tokens, prompt_style, deck_names, context_window, concurrency, card_density, filter_yes_no, exclude_trivia, smart_deck_match, ai_refinement, deterministic_mode, preloaded_text=None):
        pipeline_stats = PipelineStats()
        try:
            t_start = time.time()
            self.after(0, lambda: self.set_generation_phase("Extracting text…"))
            if preloaded_text:
                self.logger.info("Using the imported transcript...")
                text = preloaded_text
                pipeline_stats.record_extraction_time(0.0)
            else:
                self._check_local_source_size(file_path)
                self.logger.info(f"Extracting text from {os.path.basename(file_path)}...")
                text = extract_text_from_document(file_path, log_callback=self.logger.info)
                pipeline_stats.record_extraction_time(time.time() - t_start)

            self.logger.info(f"Extracted {len(text)} characters.")
            
            self.source_text = text
            
            self.logger.info("Generating Q&A with LLM...")
            self.after(0, lambda: self.set_generation_phase("Generating cards…"))

            # Clear existing cards before starting
            self.after(0, self.clear_review_area)
            
            # Define callback to add cards as they arrive
            def on_chunk_generated(new_cards):
                # Capture list by value (copy) to ensure thread safety
                cards_copy = list(new_cards)
                self.after(0, lambda: self.append_cards_to_review(cards_copy))

            # Pass available decks so LLM can categorize
            qa_data = generate_qa_pairs(text, deck_names=deck_names, target_language=target_lang, log_callback=self.logger.info, api_url=api_url, api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens, prompt_style=prompt_style, context_window=context_window, concurrency=concurrency, card_density=card_density, partial_result_callback=on_chunk_generated, stop_callback=lambda: self.stop_requested, filter_yes_no=filter_yes_no, exclude_trivia=exclude_trivia, smart_deck_match=smart_deck_match, ai_refinement=ai_refinement, deterministic_mode=deterministic_mode, pipeline_stats=pipeline_stats)
            
            self.after(0, lambda: self.set_generation_phase("Finalizing…"))
            pipeline_stats.finish()
            summary = pipeline_stats.get_summary()
            self.after(0, lambda: self.logger.info(summary))
            self.after(0, lambda: self.show_generation_summary(summary))

            # Final log
            self.after(0, lambda: self.logger.info(f"Generation complete. Total {len(qa_data)} cards. Please review and approve."))

        except FileNotFoundError as fnf:
             self.logger.error(f"Error: File not found. {fnf}")
             self.after(0, lambda: messagebox.showerror("Error", f"File not found:\n{fnf}"))
        except Exception as e:
            self.logger.error(f"Critical Error: {str(e)}")
            # Show popup for errors to ensure user sees it
            self.after(0, lambda: messagebox.showerror("Error", f"Processing Failed:\n{str(e)}"))
        finally:
            self.after(0, self._finish_processing)

    def _finish_processing(self):
        self.processing = False
        self.generation_phase = ""
        self.title("NeuralDeck")
        self.generate_btn.config(text="Generate Cards  (Ctrl+Enter)")
        self._refresh_status()
        self.generate_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.select_btn.config(state="normal")
        self.import_btn.config(state="normal")
        self.browse_btn.config(state="normal")
        self.preview_btn.config(state="normal" if self.source_text else "disabled")

    def set_generation_phase(self, phase):
        """Update the busy-state label and title without changing the flag."""
        self.generation_phase = phase
        self.title(f"NeuralDeck — {phase}")
        self._refresh_status()

    def _refresh_status(self):
        """Keep the status bar in sync with cards, approvals and Anki state."""
        if not hasattr(self, "status_cards"):
            return
        total = len(self.card_rows)
        approved = sum(1 for row in self.card_rows if row.approved_var.get())
        noun = "card" if total == 1 else "cards"
        self.status_cards.config(text=f"{total} {noun} · {approved} approved")
        source = self.loaded_source_title or os.path.basename(self.selected_file_path or "")
        if len(source) > 30:
            source = source[:27] + "..."
        self.status_source.config(text=f"Source: {source}" if source else "Source: none")
        if hasattr(self, "clear_source_btn"):
            self.clear_source_btn.config(state=NORMAL if source else DISABLED)
        self.sync_btn.config(text=(
            f"Sync Approved to Anki ({approved})" if approved else "Sync Approved to Anki"
        ))
        model_var = getattr(self, "model_var", None)
        if model_var is not None:
            self.status_model.config(text=f"Model: {model_var.get() or '—'}")

        colors = self.style.colors or {}
        default_fg = colors.get("fg")
        if self.processing:
            phase = getattr(self, "generation_phase", "") or "Generating…"
            self.status_state.config(text=f"● {phase}",
                                     foreground=colors.get("warning") or default_fg)
            if not getattr(self, "_progress_running", False):
                self.status_progress.start(12)
                self._progress_running = True
        else:
            self.status_state.config(text="● Ready",
                                     foreground=colors.get("success") or default_fg)
            if getattr(self, "_progress_running", False):
                self.status_progress.stop()
                self._progress_running = False

        anki = getattr(self, "anki_status", "checking")
        labels = {
            "connected": "Anki: connected",
            "disconnected": "Anki: not connected",
            "checking": "Anki: checking…",
        }
        tone = {"connected": "success", "disconnected": "danger", "checking": "info"}.get(anki, "info")
        self.status_anki.config(text=labels.get(anki, "Anki: unknown"),
                                foreground=colors.get(tone) or default_fg)

        llm = getattr(self, "llm_status", "unknown")
        llm_labels = {
            "online": "LLM: online", "offline": "LLM: offline",
            "checking": "LLM: checking…", "unknown": "LLM: —",
        }
        llm_tone = {
            "online": "success", "offline": "danger",
            "checking": "info", "unknown": "info",
        }.get(llm, "info")
        self.status_llm.config(text=llm_labels.get(llm, "LLM: —"),
                               foreground=colors.get(llm_tone) or default_fg)
        if hasattr(self, "ai_test_result"):
            ai_labels = {
                "online": "Connected", "offline": "Not connected",
                "checking": "Checking…", "unknown": "",
            }
            self.ai_test_result.config(
                text=ai_labels.get(llm, ""),
                foreground=colors.get(llm_tone) or default_fg,
            )

    def show_generation_summary(self, text):
        """Display the completed run's stats above the review list."""
        if not text:
            return
        self.summary_label.config(text=text)
        self.summary_label.pack(fill=X, padx=8, pady=(2, 4))

    def copy_cards(self):
        """Copy the currently visible cards as Q/A text for sharing."""
        rows = [row for row in self.card_rows if row.winfo_ismapped()]
        if not rows:
            return
        blocks = []
        for row in rows:
            blocks.append(
                f"Q: {row.q_entry.get().strip()}\nA: {row.a_entry.get().strip()}"
            )
        self.clipboard_clear()
        self.clipboard_append("\n\n".join(blocks))
        self.logger.info("Copied %d card(s) to the clipboard.", len(rows))

    def _on_approved_filter(self):
        if self.approved_only_var.get():
            self.pending_only_var.set(False)
        self._filter_cards()

    def _on_pending_filter(self):
        if self.pending_only_var.get():
            self.approved_only_var.set(False)
        self._filter_cards()

    def _clear_filters(self, event=None):
        """Escape clears both active filters in one action."""
        if (self.card_filter_var.get() or self.deck_search_var.get()
                or self.approved_only_var.get() or self.pending_only_var.get()):
            self._clear_card_filter()
            self._clear_deck_filter()
            self.approved_only_var.set(False)
            self.pending_only_var.set(False)
            self._filter_cards()
            return "break"

    def _clear_card_filter(self):
        self.card_filter_var.set("")
        self._filter_cards()

    def _filter_cards(self, event=None):
        """Show only cards whose question or answer contains the filter text."""
        query = self.card_filter_var.get().strip().casefold()
        shown = 0
        approved_only = self.approved_only_var.get()
        pending_only = self.pending_only_var.get()
        for row in self.card_rows:
            haystack = f"{row.q_entry.get()} {row.a_entry.get()}".casefold()
            approved = row.approved_var.get()
            matches = (not query or query in haystack) and (
                (not approved_only or approved) and (not pending_only or not approved)
            )
            if matches:
                row.pack(fill=X, pady=5, padx=5)
                shown += 1
            else:
                row.pack_forget()
        active_filter = bool(query) or approved_only or pending_only
        if active_filter and not shown:
            color = (self.style.colors or {}).get("warning")
            self.card_filter_count.config(text="No matches", foreground=color)
        else:
            self.card_filter_count.config(
                text=f"{shown}/{len(self.card_rows)}" if active_filter else "",
                foreground=(self.style.colors or {}).get("fg"),
            )

    def _refresh_card_indices(self):
        for position, row in enumerate(self.card_rows, 1):
            row.index_label.config(text=f"#{position}")

    def _sync_review_placeholder(self):
        """Keep the review pane, bulk actions and status bar in step with the cards."""
        self._refresh_status()
        self._refresh_card_indices()
        self._filter_cards()
        has_cards = bool(self.card_rows)
        noun = "card" if len(self.card_rows) == 1 else "cards"
        approved = sum(1 for row in self.card_rows if row.approved_var.get())
        self.review_container.config(
            text="Review & Source Comparison" if not has_cards
            else f"Review & Source Comparison — {len(self.card_rows)} {noun} · {approved} approved"
        )
        self.notebook.tab(
            self.main_tab,
            text=f"Generator ({len(self.card_rows)})" if has_cards else "Generator",
        )
        state = NORMAL if has_cards else DISABLED
        for button in (self.check_all_btn, self.uncheck_all_btn, self.move_selected_btn,
                       self.copy_cards_btn):
            button.config(state=state)
        self.bulk_deck_combo.config(state="readonly" if has_cards else "disabled")
        # A blocked session needs Clear All even with zero restored cards.
        self.clear_all_btn.config(state=NORMAL if has_cards or getattr(self, "session_write_blocked", False) else DISABLED)

        if getattr(self, "review_placeholder", None) is None:
            return
        if has_cards:
            self.review_placeholder.pack_forget()
        else:
            self.review_placeholder.pack(fill=BOTH, expand=True, pady=8)

    def clear_review_area(self):
        for row in self.card_rows:
            row.destroy()
        self.card_rows = []
        self.summary_label.pack_forget()
        self._sync_review_placeholder()

    def add_manual_card(self):
        """Adds a blank card row for manual authoring."""
        default_deck = "Default"
        if self.available_decks:
            # Try to get a sensible default from selected decks
            selected_decks = [d for d, v in self.deck_vars.items() if v.get()]
            if selected_decks:
                default_deck = selected_decks[0]
            elif self.available_decks:
                default_deck = self.available_decks[0]

        row = CardReviewRow(self.review_frame, "", "", default_deck, self.available_decks, quote="", on_remove=self.remove_card_row, on_approve=self._sync_review_placeholder)
        # Pre-approve manual cards since the user is adding it intentionally
        row.approved_var.set(True)
        self.card_rows.insert(0, row) # Add to top
        self._sync_review_placeholder()
        # Start typing immediately — the user clicked Add Manual Card to write.
        row.q_entry.focus_set()

        # Force layout update
        self.review_frame.update_idletasks()
        
        # Enable sync button
        if self.card_rows:
            self.sync_btn.config(state="normal")

    def append_cards_to_review(self, new_cards):
        self.logger.info(f"UI: Appending {len(new_cards)} new cards...")
        for item in new_cards:
            row = CardReviewRow(
                self.review_frame, 
                item['question'], 
                item['answer'], 
                item['deck'], 
                self.available_decks,
                quote=item.get('quote', ''),
                on_remove=self.remove_card_row,
                on_approve=self._sync_review_placeholder
            )
            self.card_rows.append(row)

        self._sync_review_placeholder()

        # Force layout update to ensure new cards are visible
        self.review_frame.update_idletasks()
        
        # Enable sync button immediately if we have cards
        if self.card_rows:
            self.sync_btn.config(state="normal")

    def remove_card_row(self, row):
        if row in self.card_rows:
            self.card_rows.remove(row)
            row.destroy()
            self._sync_review_placeholder()
            
    def save_session(self):
        """Saves the current state of generated cards to a JSON file."""
        if getattr(self, 'session_write_blocked', False):
            if SESSION_FILE.exists():
                self.logger.warning("Session cache is unreadable and was left untouched; use Clear All to discard it.")
                return
            self.session_write_blocked = False

        data = []
        for row in self.card_rows:
            row_data = row.get_data()
            # get_data doesn't include the quote, so we grab it from the object
            row_data['quote'] = row.quote
            data.append(row_data)
        
        try:
            write_json_file(SESSION_FILE, data)
            self.logger.info(f"Session saved. {len(data)} cards cached.")
        except Exception as e:
            self.logger.error(f"Failed to save session: {e}")

    def load_session(self):
        """Restores cards from the session cache file."""
        if not SESSION_FILE.exists():
            return

        try:
            read_failed = False

            def note_read_error(exc):
                nonlocal read_failed
                read_failed = True
                self.logger.warning(f"Could not read session cache: {exc}")

            raw_data = read_json_file(
                SESSION_FILE,
                [],
                on_error=note_read_error,
                quarantine_on_error=True,
            )
            if read_failed and SESSION_FILE.exists():
                self.session_write_blocked = True
                return
            self.session_write_blocked = False

            data = normalize_session_data(raw_data)
            if data is None:
                quarantine_corrupt_file(SESSION_FILE)
                self.session_write_blocked = SESSION_FILE.exists()
                self.logger.warning("Session cache had an unusable shape and was not loaded.")
                return
            if not data:
                return

            self.logger.info(f"Restoring previous session ({len(data)} cards)...")

            for item in data:
                # Create row with restored data
                row = CardReviewRow(self.review_frame, item.get('question', ''), item.get('answer', ''), item.get('deck', 'Default'), self.available_decks, quote=item.get('quote', ''), on_remove=self.remove_card_row, on_approve=self._sync_review_placeholder)
                if item.get('approved', False):
                    row.approved_var.set(True)
                self.card_rows.append(row)

            self._sync_review_placeholder()
            self.show_generation_summary(
                f"Restored {len(self.card_rows)} card{'s' if len(self.card_rows) != 1 else ''} "
                "from the previous session."
            )
            self.review_frame.update_idletasks()
            if self.card_rows:
                self.sync_btn.config(state="normal")
        except Exception as e:
            self.session_write_blocked = SESSION_FILE.exists()
            self.logger.error(f"Failed to load session: {e}")

    def stop_processing(self):
        if messagebox.askyesno("Stop", "Are you sure you want to stop processing?"):
            self.stop_requested = True
            self.logger.info("Stopping processing...")
            self.stop_btn.config(state="disabled")

    def on_close(self):
        """Handle window closing event to ensure all threads are killed."""
        if getattr(self, "settings_dirty", False):
            if not messagebox.askyesno(
                "Unsaved Settings",
                "You have unsaved settings changes. Quit without saving them?",
            ):
                return
        self.save_session()
        self.stop_requested = True
        self.destroy()
        os._exit(0)

    def clear_all_cards(self):
        blocked = getattr(self, 'session_write_blocked', False)
        if not self.card_rows and not blocked:
            return
        noun = "card" if len(self.card_rows) == 1 else "cards"
        prompt = (
            "Clear all generated cards and cached session data?" if blocked
            else f"Clear all {len(self.card_rows)} generated {noun}?"
        )
        if not messagebox.askyesno("Confirm", prompt):
            return

        for row in self.card_rows:
            row.destroy()
        self.card_rows = []
        self._sync_review_placeholder()

        if blocked:
            try:
                SESSION_FILE.unlink(missing_ok=True)
            except OSError as exc:
                self.logger.error(f"Could not discard the blocked session cache: {exc}")
            else:
                self.session_write_blocked = False
                self.logger.info("Discarded the blocked session cache.")
            
    def toggle_all_approvals(self, state):
        # Only change what the user can see: hidden (filtered-out) cards must
        # not be silently approved or rejected.
        for row in self.card_rows:
            if row.winfo_ismapped():
                row.approved_var.set(state)
        self._sync_review_placeholder()

    def bulk_assign_deck(self):
        """Assigns the selected deck to all checked cards."""
        target_deck = self.bulk_deck_var.get()
        if not target_deck:
            messagebox.showwarning("Warning", "Please select a deck to assign.")
            return

        # Match the review view: only approved cards the user can currently see.
        selected_rows = [
            row for row in self.card_rows
            if row.approved_var.get() and row.winfo_ismapped()
        ]
        
        if not selected_rows:
            messagebox.showinfo("Info", "No cards are checked. Please check the cards you want to move.")
            return
            
        if messagebox.askyesno("Confirm", f"Move {len(selected_rows)} checked cards to deck '{target_deck}'?"):
            for row in selected_rows:
                row.deck_var.set(target_deck)
            self.logger.info(f"Moved {len(selected_rows)} cards to deck '{target_deck}'.")

    def sync_to_anki(self):
        # check connection first
        if not check_anki_connection():
            messagebox.showerror("Error", "Could not connect to Anki.\nPlease ensure Anki is open and the 'NeuralDeck Bridge' add-on is installed and running on port 5005.")
            return

        approved_cards = []
        for row in self.card_rows:
            data = row.get_data()
            if data['approved']:
                approved_cards.append(data)
        
        if not approved_cards:
            messagebox.showinfo("Info", "No cards approved.")
            return

        # Group by deck to send efficiently (or just send one by one, but grouping is cleaner)
        # Our current anki_integration takes (deck_name, list_of_pairs)
        # So we group them.
        deck_groups = {}
        for card in approved_cards:
            d_name = card['deck']
            if d_name not in deck_groups:
                deck_groups[d_name] = []
            deck_groups[d_name].append((card['question'], card['answer']))
        
        total_added = 0
        try:
            for deck_name, pairs in deck_groups.items():
                count = create_anki_deck(deck_name, pairs, log_callback=self.logger.info)
                total_added += count
            
            messagebox.showinfo("Success", f"Successfully added {total_added} cards to Anki!")
            self.logger.info(f"Synced {total_added} cards.")
            
            # Optional: Clear session after successful sync? 
            # For now, we keep them until user manually clears or closes app (which saves them).
        except Exception as e:
            messagebox.showerror("Error", str(e))
