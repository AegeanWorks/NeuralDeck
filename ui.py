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
from audio_transcription import is_audio_file
from document_processor import extract_text_from_document, generate_qa_pairs
from transcript_sources import (
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

class TextWidgetHandler(logging.Handler):
    """Custom logging handler that writes to a Tkinter ScrolledText widget thread-safely."""
    def __init__(self, text_widget, root):
        super().__init__()
        self.text_widget = text_widget
        self.root = root

    def emit(self, record):
        msg = self.format(record)
        self.root.after(0, self.append_log, msg)

    def append_log(self, msg):
        try:
            self.text_widget.config(state='normal')
            self.text_widget.insert("end", msg + "\n")
            # Limit to approx 50000 characters
            text = self.text_widget.get("1.0", "end")
            if len(text) > 50000:
                excess = len(text) - 50000
                self.text_widget.delete("1.0", f"1.0+{excess}c")
            self.text_widget.see("end")
            self.text_widget.config(state='disabled')
        except Exception:  # hygiene: allow widget teardown must not break logging
            pass

class CardReviewRow(ttk.Frame):
    """A row representing a single generated card for review."""
    def __init__(self, parent, question, answer, assigned_deck, available_decks, quote="", on_remove=None):
        super().__init__(parent)
        self.quote = quote
        self.on_remove = on_remove
        self.pack(fill=X, pady=5, padx=5)
        
        # Layout columns
        self.columnconfigure(1, weight=1) # Question/Answer area stretches
        
        # Checkbox for approval
        self.approved_var = ttk.BooleanVar(value=False)
        self.checkbox = ttk.Checkbutton(self, text="Approve", variable=self.approved_var, bootstyle="round-toggle")
        self.checkbox.grid(row=0, column=0, rowspan=2, padx=10, sticky="ns")
        
        # Inputs
        self.q_entry = ttk.Entry(self)
        self.q_entry.insert(0, question)
        self.q_entry.grid(row=0, column=1, sticky=EW, padx=5, pady=2)
        
        self.a_entry = ttk.Entry(self)
        self.a_entry.insert(0, answer)
        self.a_entry.grid(row=1, column=1, sticky=EW, padx=5, pady=2)
        
        # Deck Selection
        self.deck_var = ttk.StringVar(value=assigned_deck)
        # Use a local copy to avoid polluting the global available_decks list with generated names
        deck_options = list(available_decks)
        if assigned_deck and assigned_deck not in deck_options:
            deck_options.append(assigned_deck)
            
        self.deck_dropdown = ttk.Combobox(self, textvariable=self.deck_var, values=deck_options, width=20, state="readonly")
        self.deck_dropdown.grid(row=0, column=2, rowspan=2, padx=10)
        self.deck_dropdown.bind('<Button-1>', lambda e: self.deck_dropdown.event_generate('<Down>'))

        # Source Quote Button - Always visible to keep layout consistent
        btn_state = "normal" if self.quote else "disabled"
        btn_style = "info-outline" if self.quote else "secondary-outline"
        
        self.quote_btn = ttk.Button(self, text="❝", command=self.show_source, bootstyle=btn_style, width=3, state=btn_state)
        self.quote_btn.grid(row=0, column=3, rowspan=2, padx=2)
        
        if self.quote:
            ToolTip(self.quote_btn, text=f"Source: {self.quote[:100]}...")

        # Remove Button
        self.remove_btn = ttk.Button(self, text="🗑", command=self.remove_row, bootstyle="danger-outline", width=3)
        self.remove_btn.grid(row=0, column=4, rowspan=2, padx=5)

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
    preview = text if len(text) <= 50000 else text[:50000] + "\n\n[... preview truncated to 50,000 characters ...]"
    viewer.insert("1.0", preview)
    viewer.config(state="disabled")
    viewer.pack(fill=BOTH, expand=True)

    ttk.Button(frame, text="Close", command=dialog.destroy, bootstyle="secondary").pack(anchor=E, pady=(8, 0))
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
        
        self.title("NeuralDeck")
        self.geometry("1200x800")
        
        # Data
        self.selected_file_path = None
        self.loaded_source_text = None
        self.loaded_source_title = None
        self.processing = False
        self.preview_loading = False
        self.available_decks = []
        self.deck_vars = {}
        self.deck_checkboxes = []
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

        # Initial Fetch
        self.fetch_decks()

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

    def setup_main_tab(self):
        self.main_tab.columnconfigure(0, weight=1)
        self.main_tab.rowconfigure(0, weight=1) # Review area expands (now at top)
        
        # 1. Review Area (Scrollable) - Moved to Top
        self.review_container = ttk.Labelframe(self.main_tab, text="Review & Source Comparison")
        self.review_container.grid(row=0, column=0, sticky=NSEW, padx=20, pady=(20, 10))
        
        # Review Toolbar (Select All / None)
        toolbar = ttk.Frame(self.review_container)
        toolbar.pack(fill=X, padx=5, pady=2)
        
        ttk.Button(toolbar, text="Check All", command=lambda: self.toggle_all_approvals(True), 
                   bootstyle="secondary-outline", width=10).pack(side=LEFT, padx=2)
        ttk.Button(toolbar, text="Uncheck All", command=lambda: self.toggle_all_approvals(False), 
                   bootstyle="secondary-outline", width=12).pack(side=LEFT, padx=2)

        ttk.Button(toolbar, text="Add Manual Card", command=self.add_manual_card, 
                   bootstyle="info-outline").pack(side=LEFT, padx=(10, 0))

        # Proposal: Clear All Button
        ttk.Button(toolbar, text="Clear All", command=self.clear_all_cards, bootstyle="danger-link").pack(side=RIGHT, padx=5)

        # Bulk move
        bulk_deck_frame = ttk.Frame(toolbar)
        bulk_deck_frame.pack(side=RIGHT, padx=10)
        self.bulk_deck_var = ttk.StringVar()
        self.bulk_deck_combo = ttk.Combobox(bulk_deck_frame, textvariable=self.bulk_deck_var, values=self.available_decks, state="readonly", width=20)
        self.bulk_deck_combo.pack(side=LEFT, padx=(10, 5))
        ttk.Button(bulk_deck_frame, text="Move Selected", command=self.bulk_assign_deck, bootstyle="primary-outline").pack(side=LEFT)

        # Review Area (Single Pane)
        self.review_frame = ScrolledFrame(self.review_container, autohide=True)
        self.review_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)

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

        self.file_label = ttk.Label(self.file_box, text="No file selected", font=("Helvetica", 10), anchor="w")
        self.file_label.pack(side=LEFT, fill=X, expand=True)
        
        # Select Document Button
        self.select_btn = ttk.Button(left_panel, text="Select Document / Media", command=self.select_file, bootstyle="primary-outline")
        self.select_btn.pack(fill=X, pady=(0, 5))

        # Import a YouTube or podcast transcript URL
        import_row = ttk.Frame(left_panel)
        import_row.pack(fill=X, pady=(0, 5))
        self.import_btn = ttk.Button(import_row, text="Import URL / Media", command=self.import_media_url, bootstyle="info-outline")
        self.import_btn.pack(side=LEFT, fill=X, expand=True, padx=(0, 3))
        self.browse_btn = ttk.Button(import_row, text="Browse Podcast", command=self.browse_podcast, bootstyle="info-outline")
        self.browse_btn.pack(side=LEFT, fill=X, expand=True, padx=(3, 0))

        # Preview the text that will be sent to the LLM
        self.preview_btn = ttk.Button(left_panel, text="Preview Transcript", command=self.preview_transcript, bootstyle="secondary-outline", state="disabled")
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

        # Generate Button
        self.generate_btn = ttk.Button(left_panel, text="Generate Cards", command=self.start_processing, bootstyle="success")
        self.generate_btn.pack(fill=X)

        # Right Panel (Deck List)
        deck_frame = ttk.Labelframe(top_frame, text="Available Decks", padding=5)
        deck_frame.grid(row=0, column=1, sticky=NSEW)
        
        self.deck_list_frame = ScrolledFrame(deck_frame, autohide=True)
        self.deck_list_frame.pack(fill=BOTH, expand=True)

        # 3. Bottom Bar: Logs & Sync
        bottom_frame = ttk.Frame(self.main_tab)
        bottom_frame.grid(row=2, column=0, sticky=EW, padx=20, pady=20)
        
        self.log_area = ScrolledText(bottom_frame, height=6, state='disabled', font=("Segoe UI", 9))
        self.log_area.pack(side=LEFT, padx=10, fill=X, expand=True)
        
        # Right side buttons container
        btns_frame = ttk.Frame(bottom_frame)
        btns_frame.pack(side=RIGHT, padx=10, pady=10)

        self.stop_btn = ttk.Button(btns_frame, text="Stop Processing", command=self.stop_processing, bootstyle="danger", state="disabled")
        self.stop_btn.pack(side=TOP, fill=X, pady=(0, 5))

        self.sync_btn = ttk.Button(btns_frame, text="Sync Approved to Anki", command=self.sync_to_anki, state="disabled")
        self.sync_btn.pack(side=TOP, fill=X)

    def setup_settings_tab(self):
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
        
        # Key
        ttk.Label(ai_grid, text="API Key:").grid(row=1, column=0, sticky=W, pady=5)
        self.api_key_var = ttk.StringVar(value=self.config.get("api_key", "lm-studio"))
        ttk.Entry(ai_grid, textvariable=self.api_key_var, width=50).grid(row=1, column=1, sticky=EW, padx=10, pady=5)
        
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

        # Card Density
        ttk.Label(param_frame, text="Card Density:").grid(row=1, column=2, sticky=W, padx=15, pady=5)
        self.density_var = ttk.StringVar(value=self.config.get("card_density", "Medium"))
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
        self.prompt_text.pack(fill=BOTH, expand=True)
        self.prompt_text.insert("1.0", self.config.get("prompt_style", ""))

        # Save Button
        ttk.Button(container, text="Save Settings", command=self.save_settings_ui, bootstyle="primary").pack(pady=20, anchor=E)

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
            log_cb(f"Connected to Anki. Found {len(decks)} decks.")
        else:
            self.available_decks = ["Default"]
            log_cb("Could not connect to Anki Add-on. Is Anki open?")
        
        self.after(0, self.update_deck_list_ui)

    def update_deck_list_ui(self):
        # Clear previous checkboxes
        for cb in self.deck_checkboxes:
            cb.destroy()
        self.deck_checkboxes = []
        self.deck_vars = {}
        
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
        else:
            lbl = ttk.Label(self.deck_list_frame, text="(No decks found)")
            lbl.pack(anchor=W, padx=5)
            self.deck_checkboxes.append(lbl)
            
        # Update bulk assignment dropdown
        if hasattr(self, 'bulk_deck_combo'):
            self.bulk_deck_combo['values'] = self.available_decks
            if self.available_decks and not self.bulk_deck_var.get():
                self.bulk_deck_var.set(self.available_decks[0])
            
        # Load session if not already loaded (runs once after initial deck fetch)
        if not self._session_loaded:
            self.load_session()
            self._session_loaded = True

    def save_deck_selection(self):
        selected = [d for d, v in self.deck_vars.items() if v.get()]
        self.config["selected_decks"] = selected
        self.save_config()

    def select_file(self):
        filetypes = [
            ("All Supported Sources", "*.pdf *.docx *.pptx *.txt *.srt *.vtt *.json *.mp3 *.m4a *.wav *.ogg *.flac *.mp4 *.mkv *.webm"),
            ("Documents", "*.pdf *.docx *.pptx *.txt"),
            ("Transcripts", "*.srt *.vtt *.json *.txt"),
            ("Podcast Audio / Video", "*.mp3 *.m4a *.wav *.ogg *.flac *.mp4 *.mkv *.webm"),
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
            self.preview_btn.config(state="disabled")
            filename = os.path.basename(file_path)
            extension = os.path.splitext(filename)[1].lower()

            # Uzun dosya isimlerini kısalt (UI bozulmasını önlemek için)
            if len(filename) > 35:
                display_text = filename[:32] + "..."
            else:
                display_text = filename

            self.file_label.config(text=display_text)
            if extension in (".vtt", ".srt", ".json"):
                self.emoji_label.config(text="📝")
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
            "a website article or PDF URL, or a .vtt/.srt/.txt/.json transcript URL:",
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
        self.emoji_label.config(text={"youtube": "▶", "podcast": "🎧"}.get(result.kind, "📝"))
        ToolTip(self.file_label, text=f"{result.title}\n{result.source_url}")
        self.preview_btn.config(state="normal")
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

    def _preview_file_worker(self, file_path):
        try:
            if not is_audio_file(file_path):
                ResourceGuard.check_file_size(file_path)
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
        has_text = bool(self.loaded_source_text or self.source_text)
        self.preview_btn.config(state="normal" if has_text else "disabled")

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
        
        self.generate_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.import_btn.config(state="disabled")
        self.browse_btn.config(state="disabled")
        self.preview_btn.config(state="disabled")
        self.processing = True
        self.stop_requested = False
        self.logger.info("Starting processing...")

        preloaded_text = self.loaded_source_text
        threading.Thread(target=self.run_process, args=(self.selected_file_path, target_lang, api_url, api_key, model, temperature, max_tokens, prompt_style, selected_decks, context_window, concurrency, card_density, filter_yes_no, exclude_trivia, smart_deck_match, ai_refinement, deterministic_mode, preloaded_text), daemon=True).start()

    def run_process(self, file_path, target_lang, api_url, api_key, model, temperature, max_tokens, prompt_style, deck_names, context_window, concurrency, card_density, filter_yes_no, exclude_trivia, smart_deck_match, ai_refinement, deterministic_mode, preloaded_text=None):
        pipeline_stats = PipelineStats()
        try:
            t_start = time.time()
            if preloaded_text:
                self.logger.info("Using the imported transcript...")
                text = preloaded_text
                pipeline_stats.record_extraction_time(0.0)
            else:
                if not is_audio_file(file_path):
                    ResourceGuard.check_file_size(file_path)
                self.logger.info(f"Extracting text from {os.path.basename(file_path)}...")
                text = extract_text_from_document(file_path, log_callback=self.logger.info)
                pipeline_stats.record_extraction_time(time.time() - t_start)

            self.logger.info(f"Extracted {len(text)} characters.")
            
            self.source_text = text
            
            self.logger.info("Generating Q&A with LLM...")
            
            # Clear existing cards before starting
            self.after(0, self.clear_review_area)
            
            # Define callback to add cards as they arrive
            def on_chunk_generated(new_cards):
                # Capture list by value (copy) to ensure thread safety
                cards_copy = list(new_cards)
                self.after(0, lambda: self.append_cards_to_review(cards_copy))

            # Pass available decks so LLM can categorize
            qa_data = generate_qa_pairs(text, deck_names=deck_names, target_language=target_lang, log_callback=self.logger.info, api_url=api_url, api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens, prompt_style=prompt_style, context_window=context_window, concurrency=concurrency, card_density=card_density, partial_result_callback=on_chunk_generated, stop_callback=lambda: self.stop_requested, filter_yes_no=filter_yes_no, exclude_trivia=exclude_trivia, smart_deck_match=smart_deck_match, ai_refinement=ai_refinement, deterministic_mode=deterministic_mode, pipeline_stats=pipeline_stats)
            
            pipeline_stats.finish()
            summary = pipeline_stats.get_summary()
            self.after(0, lambda: self.logger.info(summary))

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
        self.generate_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.select_btn.config(state="normal")
        self.import_btn.config(state="normal")
        self.browse_btn.config(state="normal")
        self.preview_btn.config(state="normal" if self.source_text else "disabled")

    def clear_review_area(self):
        for row in self.card_rows:
            row.destroy()
        self.card_rows = []

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

        row = CardReviewRow(self.review_frame, "", "", default_deck, self.available_decks, quote="", on_remove=self.remove_card_row)
        # Pre-approve manual cards since the user is adding it intentionally
        row.approved_var.set(True)
        self.card_rows.insert(0, row) # Add to top
        
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
                on_remove=self.remove_card_row
            )
            self.card_rows.append(row)
        
        # Force layout update to ensure new cards are visible
        self.review_frame.update_idletasks()
        
        # Enable sync button immediately if we have cards
        if self.card_rows:
            self.sync_btn.config(state="normal")

    def remove_card_row(self, row):
        if row in self.card_rows:
            self.card_rows.remove(row)
            row.destroy()
            
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
                row = CardReviewRow(self.review_frame, item.get('question', ''), item.get('answer', ''), item.get('deck', 'Default'), self.available_decks, quote=item.get('quote', ''), on_remove=self.remove_card_row)
                if item.get('approved', False):
                    row.approved_var.set(True)
                self.card_rows.append(row)
            
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
        self.save_session()
        self.stop_requested = True
        self.destroy()
        os._exit(0)

    def clear_all_cards(self):
        blocked = getattr(self, 'session_write_blocked', False)
        if not self.card_rows and not blocked:
            return
        prompt = "Clear all generated cards and cached session data?" if blocked else "Clear all generated cards?"
        if not messagebox.askyesno("Confirm", prompt):
            return

        for row in self.card_rows:
            row.destroy()
        self.card_rows = []

        if blocked:
            try:
                SESSION_FILE.unlink(missing_ok=True)
            except OSError as exc:
                self.logger.error(f"Could not discard the blocked session cache: {exc}")
            else:
                self.session_write_blocked = False
                self.logger.info("Discarded the blocked session cache.")
            
    def toggle_all_approvals(self, state):
        for row in self.card_rows:
            row.approved_var.set(state)

    def bulk_assign_deck(self):
        """Assigns the selected deck to all checked cards."""
        target_deck = self.bulk_deck_var.get()
        if not target_deck:
            messagebox.showwarning("Warning", "Please select a deck to assign.")
            return

        selected_rows = [row for row in self.card_rows if row.approved_var.get()]
        
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
