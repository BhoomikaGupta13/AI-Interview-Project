"""
Shared UI theming module for the AI Interview System.

Provides:
    - apply_theme(app_kind)          -> injects the base CSS (light or dark)
    - render_theme_toggle()          -> in-page light/dark switch (main area, not sidebar)
    - render_sidebar_switcher()      -> "Candidate / Admin" login selector in the sidebar
    - render_hero(title, subtitle)   -> polished page hero header
    - stat_card / section_title      -> small reusable primitives

Palette   :  Deep navy + teal accents on light cream (or deep navy background in dark mode)
Fonts     :  Fraunces (display serif)  +  Manrope (UI sans)     [Google Fonts CDN]
"""

from __future__ import annotations
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Palette
# ─────────────────────────────────────────────────────────────────────────────
LIGHT = {
    "bg":          "#F5F1EA",   # warm cream page background
    "bg_soft":     "#EFE9DE",   # sidebar / secondary panels
    "surface":     "#FBF8F2",   # cards
    "surface_2":   "#FFFFFF",   # elevated / inputs
    "ink":         "#0B2545",   # primary text (deep navy)
    "ink_soft":    "#3D5875",   # secondary text
    "muted":       "#7A8AA0",
    "border":      "#E5DFD1",
    "accent":      "#0F766E",   # teal 700
    "accent_2":    "#14B8A6",   # teal 500  (hover / gradient)
    "accent_ink":  "#FFFFFF",
    "success":     "#0F766E",
    "warning":     "#B45309",
    "danger":      "#B91C1C",
    "info":        "#1E3A5F",
    "chip_bg":     "#E8F0EE",
    "chip_ink":    "#0F766E",
    "shadow":      "0 4px 24px rgba(11, 37, 69, 0.06), 0 1px 2px rgba(11,37,69,0.04)",
}

DARK = {
    "bg":          "#0A1626",
    "bg_soft":     "#0F2036",
    "surface":     "#132A44",
    "surface_2":   "#17324F",
    "ink":         "#EAE2CE",
    "ink_soft":    "#B8C4D6",
    "muted":       "#7C8CA6",
    "border":      "#1E3A5C",
    "accent":      "#2DD4BF",
    "accent_2":    "#14B8A6",
    "accent_ink":  "#031514",
    "success":     "#2DD4BF",
    "warning":     "#F59E0B",
    "danger":      "#F87171",
    "info":        "#93C5FD",
    "chip_bg":     "#0E3A38",
    "chip_ink":    "#5EEAD4",
    "shadow":      "0 6px 30px rgba(0,0,0,0.35), 0 1px 2px rgba(0,0,0,0.25)",
}


# ─────────────────────────────────────────────────────────────────────────────
# Theme resolver
# ─────────────────────────────────────────────────────────────────────────────
def _current_theme() -> str:
    if "ui_theme" not in st.session_state:
        st.session_state["ui_theme"] = "light"
    return st.session_state["ui_theme"]


def _palette() -> dict:
    return LIGHT if _current_theme() == "light" else DARK


# ─────────────────────────────────────────────────────────────────────────────
# CSS injection
# ─────────────────────────────────────────────────────────────────────────────
def apply_theme(app_kind: str = "candidate") -> None:
    """
    Inject the global stylesheet. `app_kind` only affects the sidebar accent chip.
    """
    p = _palette()
    accent_grad = f"linear-gradient(135deg, {p['accent']} 0%, {p['accent_2']} 100%)"

    st.markdown(
        f"""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">

        <style>
        :root {{
            --bg: {p['bg']};
            --bg-soft: {p['bg_soft']};
            --surface: {p['surface']};
            --surface-2: {p['surface_2']};
            --ink: {p['ink']};
            --ink-soft: {p['ink_soft']};
            --muted: {p['muted']};
            --border: {p['border']};
            --accent: {p['accent']};
            --accent-2: {p['accent_2']};
            --accent-ink: {p['accent_ink']};
            --success: {p['success']};
            --warning: {p['warning']};
            --danger:  {p['danger']};
            --chip-bg: {p['chip_bg']};
            --chip-ink: {p['chip_ink']};
            --shadow: {p['shadow']};
        }}

        /* App background ------------------------------------------------- */
        .stApp {{
            background:
                radial-gradient(1200px 600px at -10% -10%, rgba(15,118,110,0.06), transparent 60%),
                radial-gradient(900px 500px at 110% 0%, rgba(11,37,69,0.05), transparent 55%),
                var(--bg) !important;
            color: var(--ink);
            font-family: 'Manrope', ui-sans-serif, system-ui, sans-serif;
        }}

        /* Kill default Streamlit chrome noise */
        header[data-testid="stHeader"] {{ background: transparent; }}
        #MainMenu, footer {{ visibility: hidden; }}

        /* Headings ------------------------------------------------------- */
        h1, h2, h3 {{
            font-family: 'Fraunces', 'Georgia', serif !important;
            color: var(--ink) !important;
            letter-spacing: -0.01em;
            font-weight: 600 !important;
        }}
        h1 {{ font-size: 2.1rem !important; }}
        h2 {{ font-size: 1.5rem !important; }}
        h3 {{ font-size: 1.15rem !important; }}
        h4, h5, h6, p, label, .stMarkdown {{
            font-family: 'Manrope', sans-serif !important;
            color: var(--ink);
        }}
        /* Spans/divs inherit Manrope by default, but we must NOT clobber
           icon fonts (Material Symbols / Material Icons / Font Awesome).
           Using :not() prevents ligature-based icons rendering as literal text
           (e.g. the expander arrow showing "arrow_right"). */
        p span, .stMarkdown span, label span,
        div:not([class*="material-symbols"]):not([class*="material-icons"]):not(.fa):not([class^="fa-"]) {{
            font-family: 'Manrope', sans-serif;
            color: var(--ink);
        }}
        span.material-symbols-outlined,
        span.material-symbols-rounded,
        span.material-symbols-sharp,
        span.material-icons,
        span.material-icons-outlined,
        span.material-icons-round,
        [class*="material-symbols"],
        [class*="material-icons"] {{
            font-family: 'Material Symbols Outlined', 'Material Symbols Rounded',
                         'Material Icons' !important;
            font-feature-settings: 'liga' !important;
            font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24 !important;
        }}
        .fa, .fas, .far, .fal, .fab, [class^="fa-"], [class*=" fa-"] {{
            font-family: 'Font Awesome 6 Free', 'Font Awesome 6 Brands' !important;
        }}
        code, pre, .stCode {{ font-family: 'JetBrains Mono', monospace !important; }}

        /* Main content padding ------------------------------------------ */
        .block-container {{
            padding-top: 1.6rem !important;
            padding-bottom: 4rem !important;
            max-width: 1240px;
        }}

        /* Sidebar -------------------------------------------------------- */
        section[data-testid="stSidebar"] {{
            background: var(--bg-soft) !important;
            border-right: 1px solid var(--border);
        }}
        section[data-testid="stSidebar"] * {{ color: var(--ink) !important; }}
        section[data-testid="stSidebar"] .stMarkdown h3 {{
            font-size: 0.78rem !important;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: var(--muted) !important;
            font-family: 'Manrope', sans-serif !important;
            font-weight: 700 !important;
        }}

        /* Buttons -------------------------------------------------------- */
        .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
            border-radius: 12px !important;
            border: 1px solid var(--border) !important;
            background: var(--surface-2) !important;
            color: var(--ink) !important;
            font-weight: 600 !important;
            padding: 0.55rem 1.15rem !important;
            transition: transform .12s ease, box-shadow .18s ease, background .18s ease;
            box-shadow: 0 1px 2px rgba(11,37,69,0.04);
        }}
        .stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 6px 18px rgba(15,118,110,0.15);
            border-color: var(--accent) !important;
            color: var(--accent) !important;
        }}
        /* Primary buttons */
        .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
            background: {accent_grad} !important;
            border: none !important;
            color: var(--accent-ink) !important;
        }}
        .stButton > button[kind="primary"]:hover {{
            color: var(--accent-ink) !important;
            box-shadow: 0 10px 24px rgba(15,118,110,0.30);
        }}

        /* Inputs --------------------------------------------------------- */
        .stTextInput input, .stPasswordInput input, .stTextArea textarea,
        .stSelectbox div[data-baseweb="select"] > div, .stNumberInput input {{
            background: var(--surface-2) !important;
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
            color: var(--ink) !important;
        }}
        .stTextInput input:focus, .stPasswordInput input:focus, .stTextArea textarea:focus {{
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 3px rgba(15,118,110,0.15) !important;
        }}
        label, .stTextInput label, .stSelectbox label {{
            color: var(--ink-soft) !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
        }}

        /* File uploader -------------------------------------------------- */
        [data-testid="stFileUploaderDropzone"] {{
            background: var(--surface) !important;
            border: 1.5px dashed var(--border) !important;
            border-radius: 16px !important;
            padding: 1.4rem !important;
            transition: border-color .2s ease, background .2s ease;
        }}
        [data-testid="stFileUploaderDropzone"]:hover {{
            border-color: var(--accent) !important;
            background: color-mix(in oklab, var(--accent) 6%, var(--surface)) !important;
        }}

        /* Metrics -------------------------------------------------------- */
        [data-testid="stMetric"] {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1rem 1.15rem;
            box-shadow: var(--shadow);
            transition: transform .15s ease, box-shadow .2s ease;
        }}
        [data-testid="stMetric"]:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(11,37,69,0.10);
        }}
        [data-testid="stMetricLabel"] {{
            color: var(--muted) !important;
            font-size: 0.78rem !important;
            text-transform: uppercase;
            letter-spacing: 0.10em;
            font-weight: 700 !important;
        }}
        [data-testid="stMetricValue"] {{
            font-family: 'Fraunces', serif !important;
            color: var(--ink) !important;
            font-weight: 600 !important;
        }}

        /* Alerts / info / warning / success ----------------------------- */
        div[data-testid="stAlert"] {{
            border-radius: 14px !important;
            border: 1px solid var(--border) !important;
            background: var(--surface) !important;
            box-shadow: var(--shadow);
        }}
        div[data-testid="stAlert"] p {{ color: var(--ink) !important; }}
        /* success */
        div[data-testid="stAlert"][data-baseweb="notification"] {{ }}
        .stAlert[data-baseweb="notification"] {{ }}

        /* Progress bar --------------------------------------------------- */
        [data-testid="stProgressBar"] > div > div {{
            background: {accent_grad} !important;
            border-radius: 10px !important;
        }}
        [data-testid="stProgressBar"] > div {{
            background: var(--bg-soft) !important;
            border-radius: 10px !important;
            height: 8px !important;
        }}

        /* Tabs ----------------------------------------------------------- */
        .stTabs [data-baseweb="tab-list"] {{
            gap: .4rem;
            border-bottom: 1px solid var(--border);
        }}
        .stTabs [data-baseweb="tab"] {{
            background: transparent !important;
            color: var(--ink-soft) !important;
            border-radius: 10px 10px 0 0 !important;
            font-weight: 600 !important;
            padding: 0.55rem 1rem !important;
        }}
        .stTabs [aria-selected="true"] {{
            color: var(--accent) !important;
            background: var(--surface) !important;
            border-bottom: 2px solid var(--accent) !important;
        }}

        /* Expander ------------------------------------------------------- */
        details[data-testid="stExpander"], .streamlit-expanderHeader, div[data-testid="stExpander"] {{
            background: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 14px !important;
            box-shadow: var(--shadow);
        }}

        /* DataFrame ------------------------------------------------------ */
        [data-testid="stDataFrame"] {{
            background: var(--surface);
            border-radius: 14px;
            border: 1px solid var(--border);
            overflow: hidden;
            box-shadow: var(--shadow);
        }}

        /* Divider -------------------------------------------------------- */
        hr {{ border-color: var(--border) !important; opacity: .8; }}

        /* Custom hero + card primitives --------------------------------- */
        .ai-hero {{
            display:flex; align-items:center; justify-content:space-between;
            gap:1rem;
            padding: 1.6rem 1.8rem;
            border-radius: 20px;
            background:
                radial-gradient(600px 200px at 100% 0%, rgba(20,184,166,0.12), transparent 60%),
                linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%);
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
            margin-bottom: 1.4rem;
        }}
        .ai-hero .eyebrow {{
            display:inline-flex; align-items:center; gap:.5rem;
            font-size:.72rem; letter-spacing:.16em; text-transform:uppercase;
            color: var(--accent); font-weight: 800;
            padding: .3rem .65rem; border-radius: 999px;
            background: var(--chip-bg); border: 1px solid var(--border);
            width: fit-content;
        }}
        .ai-hero h1 {{
            margin: .55rem 0 .25rem 0 !important;
            font-size: 2.05rem !important;
        }}
        .ai-hero p.sub {{
            color: var(--ink-soft) !important;
            margin: 0; font-size: 0.98rem;
            max-width: 680px;
        }}
        .ai-hero .badge {{
            display:inline-flex; align-items:center; gap:.5rem;
            padding:.5rem .85rem; border-radius: 12px;
            background: var(--surface-2); border:1px solid var(--border);
            color: var(--ink-soft); font-weight:600; font-size:.85rem;
        }}
        .ai-hero .badge i {{ color: var(--accent); }}

        .ai-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.15rem 1.3rem;
            box-shadow: var(--shadow);
            margin-bottom: 1rem;
        }}
        .ai-card h4 {{
            margin: 0 0 .35rem 0 !important;
            font-family:'Fraunces',serif !important;
            font-size: 1.05rem !important;
        }}
        .ai-chip {{
            display:inline-flex; align-items:center; gap:.4rem;
            padding:.28rem .7rem; border-radius:999px;
            background: var(--chip-bg); color: var(--chip-ink);
            font-size:.78rem; font-weight:700; letter-spacing:.02em;
            border:1px solid color-mix(in oklab, var(--accent) 20%, transparent);
        }}
        .ai-chip.warn {{ background: rgba(180,83,9,.10); color: var(--warning); border-color: color-mix(in oklab, var(--warning) 30%, transparent); }}
        .ai-chip.danger {{ background: rgba(185,28,28,.10); color: var(--danger); border-color: color-mix(in oklab, var(--danger) 30%, transparent); }}
        .ai-chip.muted {{ background: var(--bg-soft); color: var(--ink-soft); border-color: var(--border); }}

        .section-title {{
            display:flex; align-items:center; gap:.6rem;
            font-family:'Fraunces', serif; font-size:1.15rem; font-weight:600;
            color: var(--ink);
            margin: 1.2rem 0 .7rem 0;
        }}
        .section-title .dot {{
            width:8px; height:8px; border-radius:50%;
            background: {accent_grad};
            box-shadow: 0 0 0 4px color-mix(in oklab, var(--accent) 15%, transparent);
        }}

        /* Sidebar brand -------------------------------------------------- */
        .ai-brand {{
            display:flex; align-items:center; gap:.7rem;
            padding: .6rem .2rem 1.2rem .2rem;
            border-bottom: 1px solid var(--border);
            margin-bottom: 1rem;
        }}
        .ai-brand .logo {{
            width:38px; height:38px; border-radius: 11px;
            display:grid; place-items:center;
            background: {accent_grad}; color: var(--accent-ink);
            box-shadow: 0 6px 16px rgba(15,118,110,0.3);
        }}
        .ai-brand .name {{
            font-family:'Fraunces',serif; font-weight:600; font-size:1.1rem;
            color: var(--ink);
        }}
        .ai-brand .name span {{ color: var(--accent); }}
        .ai-brand .tag {{
            font-size:.72rem; color: var(--muted); letter-spacing:.08em;
            text-transform: uppercase;
        }}

        /* Nav-style radio (sidebar) ------------------------------------- */
        section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 12px;
            padding: .55rem .7rem !important;
            margin-bottom: .3rem !important;
            transition: all .15s ease;
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
            background: var(--surface);
            border-color: var(--border);
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"],
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
            background: {accent_grad} !important;
            border-color: transparent !important;
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) * {{
            color: var(--accent-ink) !important;
            font-weight: 700 !important;
        }}

        /* Top-right theme toggle row ------------------------------------ */
        .theme-row {{
            display:flex; justify-content:flex-end; align-items:center;
            gap:.6rem; margin: 0 0 .4rem 0;
        }}

        /* Smooth entrance ------------------------------------------------ */
        .block-container > div {{ animation: fadeUp .35s ease both; }}
        @keyframes fadeUp {{
            from {{ opacity:0; transform: translateY(6px); }}
            to   {{ opacity:1; transform: translateY(0); }}
        }}

        /* ============================================================== */
        /* READABILITY FIXES — dark-bg elements + chip layout             */
        /* ============================================================== */

        /* Chips: force clean single-line rendering and correct font/size.
           Prevents the "doubled letters" artifact from font inheritance. */
        .ai-chip {{
            font-family: 'Manrope', sans-serif !important;
            font-variation-settings: normal !important;
            line-height: 1.25 !important;
            white-space: nowrap;
            vertical-align: middle;
            margin: 0 .25rem .25rem 0;
            text-shadow: none !important;
        }}
        .ai-chip * {{ font-family: 'Manrope', sans-serif !important; }}

        /* File uploader "Browse files" button — was dark bg + dark text.
           Force it to match our light button style so the label is legible. */
        [data-testid="stFileUploaderDropzone"] button,
        [data-testid="stFileUploader"] button,
        [data-testid="stBaseButton-secondary"] {{
            background: var(--surface-2) !important;
            color: var(--ink) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
        }}
        [data-testid="stFileUploaderDropzone"] button:hover,
        [data-testid="stFileUploader"] button:hover {{
            border-color: var(--accent) !important;
            color: var(--accent) !important;
            background: var(--surface) !important;
        }}
        [data-testid="stFileUploaderDropzone"] button *,
        [data-testid="stFileUploader"] button * {{ color: inherit !important; }}
        /* "Drag and drop" / "200MB per file • PDF" helper text */
        [data-testid="stFileUploaderDropzone"] small,
        [data-testid="stFileUploaderDropzone"] span,
        [data-testid="stFileUploaderDropzone"] div,
        [data-testid="stFileUploaderDropzoneInstructions"],
        [data-testid="stFileUploaderDropzoneInstructions"] * {{
            color: var(--ink-soft) !important;
        }}

        /* Code blocks (st.code): guarantee dark bg + light text pairing. */
        [data-testid="stCode"], .stCode, pre, code {{
            background: #0F172A !important;
            color: #E5E7EB !important;
            border-radius: 10px !important;
            border: 1px solid rgba(255,255,255,0.06) !important;
        }}
        [data-testid="stCode"] *, .stCode *, pre *, pre code, pre span, code span {{
            color: #E5E7EB !important;
            background: transparent !important;
            font-family: 'JetBrains Mono', monospace !important;
        }}
        /* Inline code inside markdown should stay dark on subtle chip bg */
        .stMarkdown p code, .stMarkdown li code {{
            background: var(--chip-bg) !important;
            color: var(--chip-ink) !important;
            padding: .1rem .4rem !important;
            border-radius: 6px !important;
            border: 1px solid var(--border) !important;
            font-size: 0.88em !important;
        }}

        /* Tooltips (help="…", button tooltips) — dark bubble, white text. */
        [data-baseweb="tooltip"],
        [data-baseweb="tooltip"] *,
        [role="tooltip"], [role="tooltip"] * {{
            background: #0F172A !important;
            color: #F8FAFC !important;
            font-family: 'Manrope', sans-serif !important;
        }}

        /* Selectbox / multiselect / dropdown popover options
           — dark popover was showing dark navy text -> illegible. */
        [data-baseweb="popover"],
        [data-baseweb="popover"] [role="listbox"],
        [data-baseweb="menu"] {{
            background: var(--surface-2) !important;
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
            box-shadow: var(--shadow) !important;
        }}
        [data-baseweb="popover"] li,
        [data-baseweb="popover"] [role="option"],
        [data-baseweb="menu"] li,
        [data-baseweb="menu"] [role="option"] {{
            background: var(--surface-2) !important;
            color: var(--ink) !important;
        }}
        [data-baseweb="popover"] [role="option"] *,
        [data-baseweb="menu"] [role="option"] * {{ color: var(--ink) !important; }}
        [data-baseweb="popover"] [role="option"]:hover,
        [data-baseweb="popover"] [role="option"][aria-selected="true"],
        [data-baseweb="menu"] li:hover,
        [data-baseweb="menu"] [aria-selected="true"] {{
            background: var(--chip-bg) !important;
            color: var(--ink) !important;
        }}
        [data-baseweb="popover"] [role="option"]:hover *,
        [data-baseweb="popover"] [role="option"][aria-selected="true"] * {{
            color: var(--ink) !important;
        }}

        /* Dark-tooltip variant used by Streamlit's icon buttons (delete) */
        div[data-baseweb="popover"] div[role="tooltip"] {{
            background: #0F172A !important;
            color: #F8FAFC !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reusable pieces
# ─────────────────────────────────────────────────────────────────────────────
def render_theme_toggle(key: str = "theme_toggle_main") -> None:
    """A compact light/dark switch shown in the MAIN area (not sidebar)."""
    current = _current_theme()
    cols = st.columns([6, 1.6])
    with cols[1]:
        icon = "sun" if current == "dark" else "moon"
        label = "Light mode" if current == "dark" else "Dark mode"
        if st.button(
            f":material/{icon}: {label}" if False else f"{'☀️' if current=='dark' else '🌙'}  {label}",
            key=key,
            use_container_width=True,
        ):
            st.session_state["ui_theme"] = "dark" if current == "light" else "light"
            st.rerun()


def render_sidebar_brand(app_kind: str) -> None:
    role = "Candidate Portal" if app_kind == "candidate" else "Admin Console"
    st.sidebar.markdown(
        f"""
        <div class="ai-brand">
            <div class="logo"><i class="fa-solid fa-microphone-lines"></i></div>
            <div>
                <div class="name">Interview<span>AI</span></div>
                <div class="tag">{role}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_switcher(current: str) -> str:
    """
    Sidebar radio that switches between 'Candidate' and 'Admin' login views.
    Returns the newly selected value ('candidate' or 'admin').
    """
    st.sidebar.markdown("### Login as")
    options = ["Candidate", "Admin"]
    idx = 0 if current == "candidate" else 1
    choice = st.sidebar.radio(
        label="Login as",
        options=options,
        index=idx,
        label_visibility="collapsed",
        key="portal_login_role",
    )
    return "candidate" if choice == "Candidate" else "admin"


def render_hero(
    eyebrow: str,
    title: str,
    subtitle: str,
    right_badge: str | None = None,
    right_icon: str = "fa-shield-halved",
) -> None:
    right_html = ""
    if right_badge:
        right_html = f"""
        <div class="badge">
            <i class="fa-solid {right_icon}"></i> {right_badge}
        </div>
        """
    st.markdown(
        f"""
        <div class="ai-hero">
            <div>
                <div class="eyebrow"><i class="fa-solid fa-sparkles"></i> {eyebrow}</div>
                <h1>{title}</h1>
                <p class="sub">{subtitle}</p>
            </div>
            {right_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(text: str, icon: str = "fa-circle-nodes") -> None:
    st.markdown(
        f"""<div class="section-title"><span class="dot"></span>
            <i class="fa-solid {icon}" style="color:var(--accent);"></i> {text}</div>""",
        unsafe_allow_html=True,
    )


def chip(text: str, kind: str = "") -> str:
    """Return an HTML chip string (kind: '', 'warn', 'danger', 'muted')."""
    cls = f"ai-chip {kind}".strip()
    return f'<span class="{cls}">{text}</span>'


def card_open(title: str | None = None, icon: str = "fa-layer-group") -> None:
    st.markdown('<div class="ai-card">', unsafe_allow_html=True)
    if title:
        st.markdown(
            f'<h4><i class="fa-solid {icon}" style="color:var(--accent);margin-right:.4rem;"></i>{title}</h4>',
            unsafe_allow_html=True,
        )


def card_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)
