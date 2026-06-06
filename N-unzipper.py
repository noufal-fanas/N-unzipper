import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import sys
import shutil
import gzip
import bz2
import lzma
import zipfile
import tarfile
import zlib
import struct
import os
import time
from pathlib import Path
from collections import defaultdict


# ══════════════════════════════════════════════════════
# 1. EXTRACTION STATS TRACKER
# ══════════════════════════════════════════════════════
class ExtractionStats:
    def __init__(self):
        self.files_extracted = 0
        self.files_failed    = 0
        self.files_skipped   = 0
        self.bytes_processed = 0
        self.start_time      = None

    def start(self):
        self.start_time = time.time()

    def elapsed(self):
        return (time.time() - self.start_time) if self.start_time else 0

    def summary(self):
        return (
            f"  Extracted : {self.files_extracted} file(s)\n"
            f"  Failed    : {self.files_failed} file(s)\n"
            f"  Skipped   : {self.files_skipped} file(s)\n"
            f"  Data      : {self._fmt(self.bytes_processed)}\n"
            f"  Duration  : {self.elapsed():.2f}s"
        )

    def _fmt(self, b):
        for u in ['B','KB','MB','GB']:
            if b < 1024: return f"{b:.1f} {u}"
            b /= 1024
        return f"{b:.1f} TB"


# ══════════════════════════════════════════════════════
# 2. IDENTIFICATION ENGINE
# ══════════════════════════════════════════════════════
MAGIC_SIGNATURES = [
    (b'PK\x03\x04',           'zip'),
    (b'PK\x05\x06',           'zip'),
    (b'\x1f\x8b',             'gz'),
    (b'BZh',                  'bz2'),
    (b'\xfd7zXZ\x00',         'xz'),
    (b'7z\xbc\xaf\x27\x1c',  '7z'),
    (b'Rar!\x1a\x07\x00',     'rar'),
    (b'Rar!\x1a\x07\x01\x00', 'rar'),
    (b'\x04\x22\x4d\x18',     'lz4'),
    (b'\x28\xb5\x2f\xfd',     'zst'),
    (b'LZIP',                  'lz'),
]
EXTENSION_FALLBACKS = {
    '.zip':'zip','.gz':'gz','.tgz':'gz','.bz2':'bz2','.tbz2':'bz2',
    '.tbz':'bz2','.xz':'xz','.txz':'xz','.tar':'tar',
    '.7z':'7z','.rar':'rar','.lz4':'lz4','.zst':'zst','.lz':'lz','.Z':'compress',
}
SUPPORTED_FORMATS   = {'zip','gz','bz2','xz','tar'}
UNSUPPORTED_FORMATS = {'7z','rar','lz4','zst','lz','compress'}


def identify_compression(fp: Path):
    if not fp.is_file(): return None
    try:
        with open(fp,'rb') as f: magic = f.read(8)
    except: return None
    for sig, fmt in MAGIC_SIGNATURES:
        if magic.startswith(sig):
            if fmt in ('gz','bz2','xz'):
                try:
                    if tarfile.is_tarfile(str(fp)): return 'tar'
                except: pass
            return fmt
    try:
        if tarfile.is_tarfile(str(fp)): return 'tar'
    except: pass
    return EXTENSION_FALLBACKS.get(fp.suffix.lower())


def safe_extract_path(archive: Path, out_dir: Path) -> Path:
    stem = archive.stem
    while Path(stem).suffix.lower() in EXTENSION_FALLBACKS:
        stem = Path(stem).stem
    candidate = out_dir / stem
    if candidate.exists() and candidate.is_file():
        candidate = out_dir / (stem + "_extracted")
    counter = 1
    base = candidate
    while (candidate.exists() and
           (candidate.is_file() or (candidate.is_dir() and any(candidate.iterdir())))):
        candidate = base.parent / f"{base.name}_{counter}"
        counter += 1
    return candidate


# ══════════════════════════════════════════════════════
# 3. EXTRACTION ENGINE
# ══════════════════════════════════════════════════════
def extract_single(fp: Path, pwd_bytes, stats: ExtractionStats, log) -> bool:
    comp = identify_compression(fp)
    if not comp: return False
    if comp in UNSUPPORTED_FORMATS:
        log(f"  ⚠  UNSUPPORTED [{comp.upper()}] {fp.name} — needs 7-Zip/unrar")
        stats.files_skipped += 1
        return False

    log(f"  ⊛  [{comp.upper()}]  {fp.name}")
    out = safe_extract_path(fp, fp.parent)
    try:
        stats.bytes_processed += fp.stat().st_size
        if comp == 'zip':
            out.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(fp,'r') as zf:
                needs_pwd = any(i.flag_bits & 0x1 for i in zf.infolist())
                if needs_pwd and not pwd_bytes:
                    raise RuntimeError("encrypted — no password")
                bad = zf.testzip()
                if bad: raise zipfile.BadZipFile(f"CRC fail: {bad}")
                zf.extractall(path=out, pwd=pwd_bytes)
                log(f"    ↳ {len(zf.namelist())} item(s)")
        elif comp == 'tar':
            out.mkdir(parents=True, exist_ok=True)
            with tarfile.open(str(fp),'r:*') as tf:
                safe = [m for m in tf.getmembers()
                        if not m.name.startswith('/') and '..' not in m.name and not m.isdev()]
                tf.extractall(path=out, members=safe)
                log(f"    ↳ {len(safe)} item(s)")
        elif comp in ('gz','bz2','xz'):
            opener = {'gz':gzip.open,'bz2':bz2.open,'xz':lzma.open}[comp]
            sfx_map = {'.gz':'','.tgz':'.tar','.bz2':'','.tbz2':'.tar','.tbz':'.tar','.xz':'','.txz':'.tar'}
            sfx = fp.suffix.lower()
            out_p = fp.with_suffix(sfx_map.get(sfx,'')) if sfx in sfx_map else fp.with_name(fp.stem)
            if out_p.exists(): out_p = fp.with_name(fp.stem + "_decompressed")
            with opener(fp,'rb') as fi, open(out_p,'wb') as fo:
                shutil.copyfileobj(fi, fo, length=1<<20)
            fp.unlink()
            log(f"    ↳ ✓ Decompressed")
            stats.files_extracted += 1
            return True
        fp.unlink()
        log(f"    ↳ ✓  → {out.name}/")
        stats.files_extracted += 1
        return True
    except zipfile.BadZipFile as e:
        _broken(fp, log, f"Bad ZIP: {e}"); stats.files_failed += 1
    except RuntimeError as e:
        msg = "Wrong password" if pwd_bytes else "Encrypted — password required"
        _broken(fp, log, msg if 'password' in str(e).lower() or 'encrypt' in str(e).lower() else str(e))
        stats.files_failed += 1
    except tarfile.TarError as e:
        _broken(fp, log, f"TAR: {e}"); stats.files_failed += 1
    except (EOFError, zlib.error, struct.error) as e:
        _broken(fp, log, f"Corrupt: {e}"); stats.files_failed += 1
    except PermissionError as e:
        log(f"    ↳ ✗  Permission denied: {e}"); stats.files_failed += 1
    except Exception as e:
        _broken(fp, log, f"{type(e).__name__}: {e}"); stats.files_failed += 1
    return False


def _broken(fp: Path, log, reason):
    dst = fp.with_name(fp.name + ".broken")
    try: fp.rename(dst); log(f"    ↳ ✗  {reason}  →  .broken")
    except: log(f"    ↳ ✗  {reason}")


# ══════════════════════════════════════════════════════
# 4. ORCHESTRATOR
# ══════════════════════════════════════════════════════
def run_n_unzipper(master_path, output_dir, password=None,
                   cancel_event=None, progress_cb=None):
    stats    = ExtractionStats(); stats.start()
    pwd      = password.encode('utf-8') if password else None
    target   = Path(output_dir)
    cancelled = lambda: cancel_event and cancel_event.is_set()

    if master_path:
        m = Path(master_path)
        if not m.exists():
            print(f"[ERROR] Not found: {m}"); return stats
        target.mkdir(parents=True, exist_ok=True)
        print(f"▶ MASTER: {m.name}  ({m.stat().st_size/1024:.1f} KB)")
        print(f"  DEST  : {target}\n")
        if not extract_single(m, pwd, stats, print):
            print("\n[HALTED] Master extraction failed."); return stats
    else:
        if not target.exists():
            print(f"[ERROR] Dir not found: {target}"); return stats
        print(f"▶ DIRECTORY SCAN: {target}\n")

    if cancelled(): print("\n[ABORTED]"); return stats

    print("▶ RECURSIVE SCAN...\n")
    pass_num, any_found = 1, True
    while any_found and not cancelled():
        any_found  = False
        candidates = [p for p in target.rglob("*")
                      if p.is_file() and not p.name.endswith('.broken')
                      and identify_compression(p)]
        if not candidates: break
        print(f"── Pass {pass_num}: {len(candidates)} archive(s) ──")
        for i, fp in enumerate(candidates):
            if cancelled(): print("\n[ABORTED]"); return stats
            if progress_cb: progress_cb(i, len(candidates))
            if extract_single(fp, pwd, stats, print):
                any_found = True
        pass_num += 1
        if pass_num > 20:
            print("\n[WARNING] Recursion cap (20 passes). Stopping."); break

    print("\n" + "═"*52)
    print("  EXTRACTION COMPLETE")
    print("═"*52)
    print(stats.summary())
    if stats.files_failed: print(f"\n  Tip: .broken files can be inspected manually.")
    print("═"*52 + "\n")
    return stats


# ══════════════════════════════════════════════════════
# 5. TEXT REDIRECTOR
# ══════════════════════════════════════════════════════
class TextRedirector:
    def __init__(self, w): self.w = w
    def write(self, t): self.w.after(0, self._write, t)
    def _write(self, t):
        self.w.configure(state="normal")
        self.w.insert("end", t)
        self.w.see("end")
        self.w.configure(state="disabled")
    def flush(self): pass


# ══════════════════════════════════════════════════════
# 6. APPLICATION GUI  —  Black × Purple × Green theme
# ══════════════════════════════════════════════════════
class NUnzipperApp(ctk.CTk):
    # ── Palette ───────────────────────────────────────
    BG          = "#060608"          # near-black base
    PANEL       = "#0d0d14"          # slightly lifted panel
    CARD        = "#11111c"          # card surface
    BORDER      = "#2a1f4a"          # purple-tinted border
    BORDER_LIT  = "#5b21b6"          # lit purple border
    PUR_DEEP    = "#1e0a3c"          # deep purple fill
    PUR_MID     = "#3b0f7a"          # mid purple
    PUR_BRIGHT  = "#7c3aed"          # bright violet
    PUR_HOT     = "#a855f7"          # hover violet
    GRN         = "#22c55e"          # primary green
    GRN_DIM     = "#16a34a"          # darker green
    GRN_GLOW    = "#4ade80"          # bright green text
    GRN_FAINT   = "#052e16"          # very dark green fill
    RED         = "#ef4444"
    RED_DIM     = "#7f1d1d"
    WARN        = "#f59e0b"
    TXT         = "#d4d4d8"
    TXT_DIM     = "#52525b"
    TXT_MID     = "#a1a1aa"
    TERM_BG     = "#020204"
    TERM_FG     = "#22c55e"          # green console text

    def __init__(self):
        super().__init__()
        self.title("N-UNZIPPER  ·  Recursive Extraction Engine  v2.0")
        self.geometry("1020x780")
        self.minsize(900, 700)
        self.resizable(True, True)
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=self.BG)
        self.cancel_event   = threading.Event()
        self._worker_thread = None

        # ── Fonts ─────────────────────────────────────
        self.F_LOGO   = ("Courier New", 30, "bold")
        self.F_TAG    = ("Courier New",  9)
        self.F_BADGE  = ("Courier New", 10, "bold")
        self.F_LABEL  = ("Courier New", 10, "bold")
        self.F_SMALL  = ("Courier New",  9)
        self.F_BTN    = ("Courier New", 12, "bold")
        self.F_TERM   = ("Courier New", 10)

        self._build()
        sys.stdout = TextRedirector(self.console)
        self._banner()

    # ─────────────────────────────────────────────────
    def _build(self):
        # Root: fixed 3-row grid — header | body | (none)
        self.rowconfigure(0, weight=0)   # header
        self.rowconfigure(1, weight=1)   # body expands
        self.columnconfigure(0, weight=1)

        self._header()
        self._body()

    # ── HEADER ────────────────────────────────────────
    def _header(self):
        hdr = ctk.CTkFrame(self, fg_color=self.PANEL,
                           border_width=1, border_color=self.BORDER,
                           corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(1, weight=1)

        # Logo block
        logo_blk = ctk.CTkFrame(hdr, fg_color=self.PUR_DEEP,
                                 border_width=1, border_color=self.BORDER_LIT,
                                 corner_radius=6)
        logo_blk.grid(row=0, column=0, padx=(18,14), pady=14, sticky="ns")

        ctk.CTkLabel(logo_blk, text="⬡", font=("Courier New",28,"bold"),
                     text_color=self.GRN).pack(padx=14, pady=(10,0))
        ctk.CTkLabel(logo_blk, text="NUZ", font=("Courier New",11,"bold"),
                     text_color=self.GRN_GLOW).pack(padx=14, pady=(0,10))

        # Title block
        title_blk = ctk.CTkFrame(hdr, fg_color="transparent")
        title_blk.grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(title_blk, text="N-UNZIPPER",
                     font=self.F_LOGO, text_color=self.GRN_GLOW).pack(anchor="w")
        ctk.CTkLabel(title_blk,
                     text="RECURSIVE EXTRACTION ENGINE  ·  ZIP  TAR  GZ  BZ2  XZ",
                     font=self.F_TAG, text_color=self.TXT_DIM).pack(anchor="w", pady=(2,0))

        # Format badges
        badge_row = ctk.CTkFrame(title_blk, fg_color="transparent")
        badge_row.pack(anchor="w", pady=(6,0))
        for lbl, col in [("ZIP",self.PUR_MID),("TAR",self.PUR_MID),
                          ("GZ",self.PUR_MID),("BZ2",self.PUR_MID),("XZ",self.PUR_MID)]:
            b = ctk.CTkFrame(badge_row, fg_color=col,
                              border_width=1, border_color=self.BORDER_LIT,
                              corner_radius=3)
            b.pack(side="left", padx=(0,5))
            ctk.CTkLabel(b, text=lbl, font=self.F_BADGE,
                         text_color=self.GRN_GLOW).pack(padx=7, pady=2)

        # Version / status pill (right side)
        pill = ctk.CTkFrame(hdr, fg_color=self.GRN_FAINT,
                             border_width=1, border_color=self.GRN_DIM,
                             corner_radius=20)
        pill.grid(row=0, column=2, padx=18, pady=14)
        ctk.CTkLabel(pill, text="● READY", font=self.F_BADGE,
                     text_color=self.GRN).pack(padx=14, pady=6)
        self.pill_label = pill.winfo_children()[-1]   # ref for status updates

    # ── BODY ──────────────────────────────────────────
    def _body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=18, pady=(12,14))
        body.rowconfigure(0, weight=0)   # config panel
        body.rowconfigure(1, weight=1)   # terminal expands
        body.columnconfigure(0, weight=1)

        self._config_panel(body)
        self._terminal_panel(body)

    # ── CONFIG PANEL (top half) ───────────────────────
    def _config_panel(self, parent):
        top = ctk.CTkFrame(parent, fg_color=self.CARD,
                            border_width=1, border_color=self.BORDER,
                            corner_radius=10)
        top.grid(row=0, column=0, sticky="ew", pady=(0,12))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)

        # ── LEFT COLUMN: inputs ────────────────────────
        left = ctk.CTkFrame(top, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(16,8), pady=16)

        self._section_label(left, "① INPUTS")

        self.entry_master = self._input_row(
            left, "MASTER ARCHIVE",
            "Primary archive file  (optional — leave blank to scan a folder)",
            browse_cmd=self._browse_file)

        self.entry_folder = self._input_row(
            left, "DESTINATION",
            "Output directory for all extracted files",
            browse_cmd=self._browse_folder)

        self.entry_pwd, self.btn_toggle_pwd = self._pwd_row(left)

        # ── RIGHT COLUMN: options + actions ───────────
        right = ctk.CTkFrame(top, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8,16), pady=16)

        self._section_label(right, "② OPTIONS")

        self.var_skip_hidden   = ctk.BooleanVar(value=True)
        self.var_delete_broken = ctk.BooleanVar(value=False)

        self._check(right, "Skip hidden files / dot-dirs",
                    "Ignore hidden items during recursive scan",
                    self.var_skip_hidden)
        self._check(right, "Auto-delete .broken files on finish",
                    "Remove unrecoverable archive stubs after run",
                    self.var_delete_broken)

        # ── Progress bar ──────────────────────────────
        self._section_label(right, "③ PROGRESS", pady_top=14)

        self.progress_bar = ctk.CTkProgressBar(
            right, height=6, corner_radius=3,
            fg_color=self.PUR_DEEP, progress_color=self.GRN)
        self.progress_bar.pack(fill="x", pady=(4,0))
        self.progress_bar.set(0)

        prog_info = ctk.CTkFrame(right, fg_color="transparent")
        prog_info.pack(fill="x", pady=(3,0))
        self.lbl_status = ctk.CTkLabel(prog_info, text="IDLE",
                                        font=self.F_SMALL, text_color=self.TXT_DIM)
        self.lbl_status.pack(side="left")
        self.lbl_count  = ctk.CTkLabel(prog_info, text="",
                                        font=self.F_SMALL, text_color=self.TXT_DIM)
        self.lbl_count.pack(side="right")

        # ── Action buttons ────────────────────────────
        self._section_label(right, "④ ACTIONS", pady_top=14)

        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.pack(fill="x", pady=(4,0))
        btn_row.columnconfigure(0, weight=3)
        btn_row.columnconfigure(1, weight=1)
        btn_row.columnconfigure(2, weight=0)

        self.btn_start = ctk.CTkButton(
            btn_row, text="▶  ENGAGE", height=40, corner_radius=6,
            font=self.F_BTN, fg_color=self.PUR_BRIGHT,
            hover_color=self.PUR_HOT, text_color=self.GRN_GLOW,
            border_width=1, border_color=self.PUR_HOT,
            command=self._start)
        self.btn_start.grid(row=0, column=0, padx=(0,6), sticky="ew")

        self.btn_cancel = ctk.CTkButton(
            btn_row, text="■  ABORT", height=40, corner_radius=6,
            font=self.F_BTN, fg_color="transparent",
            border_width=1, border_color=self.RED,
            hover_color=self.RED_DIM, text_color=self.RED,
            state="disabled", command=self._cancel)
        self.btn_cancel.grid(row=0, column=1, padx=(0,6), sticky="ew")

        self.btn_clear = ctk.CTkButton(
            btn_row, text="CLR", width=46, height=40, corner_radius=6,
            font=self.F_SMALL, fg_color="transparent",
            border_width=1, border_color=self.BORDER,
            hover_color=self.PUR_DEEP, text_color=self.TXT_DIM,
            command=self._clear)
        self.btn_clear.grid(row=0, column=2, sticky="ew")

    # ── TERMINAL PANEL (bottom half, expands) ─────────
    def _terminal_panel(self, parent):
        term_wrap = ctk.CTkFrame(parent, fg_color=self.CARD,
                                  border_width=1, border_color=self.BORDER,
                                  corner_radius=10)
        term_wrap.grid(row=1, column=0, sticky="nsew")
        term_wrap.rowconfigure(1, weight=1)
        term_wrap.columnconfigure(0, weight=1)

        # Title bar
        tbar = ctk.CTkFrame(term_wrap, fg_color=self.PUR_DEEP,
                             corner_radius=0, height=30)
        tbar.grid(row=0, column=0, sticky="ew")
        tbar.grid_propagate(False)

        # traffic-light dots
        dot_row = ctk.CTkFrame(tbar, fg_color="transparent")
        dot_row.pack(side="left", padx=12, pady=6)
        for col in [self.RED, self.WARN, self.GRN]:
            d = ctk.CTkFrame(dot_row, width=10, height=10, corner_radius=5,
                              fg_color=col)
            d.pack(side="left", padx=3)

        ctk.CTkLabel(tbar, text="SYSTEM TERMINAL  ·  stdout",
                     font=self.F_BADGE, text_color=self.GRN_DIM).pack(side="left", padx=6)

        # Console textbox
        self.console = ctk.CTkTextbox(
            term_wrap, font=self.F_TERM, state="disabled",
            fg_color=self.TERM_BG, text_color=self.TERM_FG,
            corner_radius=0, border_width=0,
            scrollbar_button_color=self.BORDER,
            scrollbar_button_hover_color=self.PUR_BRIGHT)
        self.console.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0,1))

    # ─────────────────────────────────────────────────
    # UI WIDGET HELPERS
    # ─────────────────────────────────────────────────
    def _section_label(self, parent, text, pady_top=0):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(pady_top, 4))
        ctk.CTkLabel(row, text=text, font=self.F_BADGE,
                     text_color=self.PUR_HOT).pack(side="left")
        # hairline
        line = ctk.CTkFrame(row, height=1, fg_color=self.BORDER)
        line.pack(side="left", fill="x", expand=True, padx=(8,0))

    def _input_row(self, parent, label, hint, browse_cmd):
        frame = ctk.CTkFrame(parent, fg_color=self.PUR_DEEP,
                              border_width=1, border_color=self.BORDER,
                              corner_radius=6)
        frame.pack(fill="x", pady=(0,8))

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8,2))
        ctk.CTkLabel(top, text=label, font=self.F_LABEL,
                     text_color=self.GRN).pack(side="left")
        ctk.CTkLabel(top, text=hint, font=self.F_SMALL,
                     text_color=self.TXT_DIM).pack(side="left", padx=(8,0))

        bot = ctk.CTkFrame(frame, fg_color="transparent")
        bot.pack(fill="x", padx=10, pady=(0,8))

        entry = ctk.CTkEntry(bot, height=32,
                              placeholder_text="Type path or click BROWSE…",
                              fg_color=self.BG, border_color=self.BORDER,
                              text_color=self.GRN_GLOW, corner_radius=4,
                              font=self.F_SMALL,
                              placeholder_text_color=self.TXT_DIM)
        entry.pack(side="left", fill="x", expand=True, padx=(0,6))

        ctk.CTkButton(bot, text="BROWSE", width=74, height=32, corner_radius=4,
                      font=self.F_SMALL, fg_color=self.PUR_MID,
                      hover_color=self.PUR_BRIGHT, text_color=self.GRN_GLOW,
                      border_width=1, border_color=self.BORDER_LIT,
                      command=browse_cmd).pack(side="left")
        return entry

    def _pwd_row(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=self.PUR_DEEP,
                              border_width=1, border_color=self.BORDER,
                              corner_radius=6)
        frame.pack(fill="x", pady=(0,8))

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8,2))
        ctk.CTkLabel(top, text="PASSWORD", font=self.F_LABEL,
                     text_color=self.GRN).pack(side="left")
        ctk.CTkLabel(top, text="ZIP decryption key (leave blank if not encrypted)",
                     font=self.F_SMALL, text_color=self.TXT_DIM).pack(side="left", padx=(8,0))

        bot = ctk.CTkFrame(frame, fg_color="transparent")
        bot.pack(fill="x", padx=10, pady=(0,8))

        entry = ctk.CTkEntry(bot, height=32, show="●",
                              placeholder_text="Leave blank if archive is not encrypted…",
                              fg_color=self.BG, border_color=self.BORDER,
                              text_color=self.GRN_GLOW, corner_radius=4,
                              font=self.F_SMALL,
                              placeholder_text_color=self.TXT_DIM)
        entry.pack(side="left", fill="x", expand=True, padx=(0,6))

        btn = ctk.CTkButton(bot, text="SHOW", width=58, height=32, corner_radius=4,
                            font=self.F_SMALL, fg_color=self.PUR_MID,
                            hover_color=self.PUR_BRIGHT, text_color=self.GRN_GLOW,
                            border_width=1, border_color=self.BORDER_LIT,
                            command=self._toggle_pwd)
        btn.pack(side="left")
        return entry, btn

    def _check(self, parent, label, hint, var):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0,6))
        ctk.CTkCheckBox(row, text=label, variable=var,
                        font=self.F_SMALL, text_color=self.TXT,
                        checkmark_color=self.BG,
                        fg_color=self.GRN, hover_color=self.GRN_DIM,
                        border_color=self.BORDER, corner_radius=3).pack(anchor="w")
        ctk.CTkLabel(row, text=hint, font=("Courier New",8),
                     text_color=self.TXT_DIM).pack(anchor="w", padx=(26,0))

    # ─────────────────────────────────────────────────
    # BANNER
    # ─────────────────────────────────────────────────
    def _banner(self):
        print("╔" + "═"*50 + "╗")
        print("║   N-UNZIPPER  ·  Recursive Extraction Engine  ║")
        print("║   v2.0  ·  ZIP · TAR · GZ · BZ2 · XZ         ║")
        print("║   Path-traversal guard  ·  CRC validation     ║")
        print("╚" + "═"*50 + "╝")
        print()

    # ─────────────────────────────────────────────────
    # LOGIC
    # ─────────────────────────────────────────────────
    def _toggle_pwd(self):
        if self.entry_pwd.cget("show") == "●":
            self.entry_pwd.configure(show="")
            self.btn_toggle_pwd.configure(text="HIDE")
        else:
            self.entry_pwd.configure(show="●")
            self.btn_toggle_pwd.configure(text="SHOW")

    def _browse_file(self):
        f = filedialog.askopenfilename(
            title="Select Master Archive",
            filetypes=[("Archives","*.zip *.tar *.gz *.tgz *.bz2 *.tbz2 *.xz *.txz"),
                       ("All Files","*.*")])
        if f: self.entry_master.delete(0,"end"); self.entry_master.insert(0, f)

    def _browse_folder(self):
        f = filedialog.askdirectory(title="Select Destination Folder")
        if f: self.entry_folder.delete(0,"end"); self.entry_folder.insert(0, f)

    def _clear(self):
        self.console.configure(state="normal")
        self.console.delete("1.0","end")
        self.console.configure(state="disabled")
        self._banner()

    def _cancel(self):
        print("\n[!] Abort requested — finishing current file…")
        self.cancel_event.set()
        self.btn_cancel.configure(state="disabled", text="ABORTING…")
        self._set_status("ABORTING", self.WARN)

    def _start(self):
        m = self.entry_master.get().strip()
        f = self.entry_folder.get().strip()
        p = self.entry_pwd.get().strip()
        if not f:
            messagebox.showerror("Missing Input", "Destination folder is required.")
            return
        if m and not Path(m).exists():
            messagebox.showerror("Not Found", f"Archive not found:\n{m}")
            return

        self.cancel_event.clear()
        self._clear()
        self.progress_bar.set(0)
        self.lbl_count.configure(text="")
        self._set_status("RUNNING", self.GRN)

        self.btn_start.configure(state="disabled", text="◈  RUNNING…",
                                 fg_color=self.PUR_DEEP, text_color=self.GRN)
        self.btn_cancel.configure(state="normal")

        def pcb(done, total):
            self.after(0, self._prog, done, total)

        self._worker_thread = threading.Thread(
            target=self._work, args=(m or None, f, p or None, pcb), daemon=True)
        self._worker_thread.start()

    def _prog(self, done, total):
        if total > 0:
            self.progress_bar.set(done / total)
            self.lbl_count.configure(text=f"{done} / {total}")

    def _work(self, m, f, p, pcb):
        try:
            run_n_unzipper(m, f, p, self.cancel_event, pcb)
        except Exception as e:
            print(f"\n[CRITICAL] {type(e).__name__}: {e}")
        finally:
            self.after(0, self._finish)

    def _finish(self):
        self.progress_bar.set(1)
        aborted = self.cancel_event.is_set()
        self._set_status("ABORTED" if aborted else "COMPLETE",
                         self.WARN if aborted else self.GRN)
        self.btn_start.configure(state="normal", text="▶  ENGAGE",
                                 fg_color=self.PUR_BRIGHT, text_color=self.GRN_GLOW)
        self.btn_cancel.configure(state="disabled", text="■  ABORT")

        if self.var_delete_broken.get():
            dest = self.entry_folder.get().strip()
            if dest:
                count = sum(1 for p in Path(dest).rglob("*.broken")
                            if not (lambda _: False)(p.unlink()))
                if count: print(f"[CLEANUP] Removed {count} .broken file(s).\n")

    def _set_status(self, text, color):
        self.lbl_status.configure(text=text, text_color=color)
        self.pill_label.configure(text=f"● {text}", text_color=color)


# ══════════════════════════════════════════════════════
if __name__ == "__main__":
    NUnzipperApp().mainloop()