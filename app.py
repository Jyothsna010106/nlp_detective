import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
import spacy
from pypdf import PdfReader
import io

from storage import (
    load_users, register_user, authenticate_user,
    load_org_cases, save_case, delete_case_from_disk, hash_val
)
from nlp_engine import (
    parse_document, post_process_entities, extract_triplets,
    extract_timeline_events
)
from visualizer import analyze_network_centrality
from pdf_generator import generate_pdf_report

# --- APP CONFIG & CSS ---
st.set_page_config(
    page_title="NLP Detective | Intelligence Suite",
    page_icon="🕵️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Libre+Baskerville:wght@400;700&display=swap');

    :root {
        --ink: #101315;
        --paper: #181c1d;
        --paper-light: #202526;
        --line: rgba(214, 183, 119, 0.22);
        --muted: #9a9b91;
        --bone: #e8e0cf;
        --amber: #d6b777;
        --signal: #c86b4b;
        --green: #8eae86;
    }
    html, body, [class*="css"] {
        font-family: 'Libre Baskerville', Georgia, serif;
    }
    .stApp {
        background-color: var(--ink);
        background-image: radial-gradient(circle at 20% 0%, rgba(214, 183, 119, 0.12), transparent 28%), linear-gradient(120deg, rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(30deg, rgba(255,255,255,0.018) 1px, transparent 1px);
        background-size: auto, 26px 26px, 26px 26px;
        color: var(--bone);
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] {
        background: #121617;
        border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] > div:first-child { padding-top: 2rem; }
    [data-testid="stSidebar"] hr { border-color: var(--line); }
    [data-testid="stSidebar"] .stCaption { color: var(--muted); }
    .hud-header {
        background: linear-gradient(135deg, rgba(32, 37, 38, 0.95), rgba(16, 19, 21, 0.9));
        border: 1px solid var(--line);
        border-top: 3px solid var(--amber);
        border-radius: 2px;
        padding: 24px 28px;
        margin-bottom: 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 18px 45px rgba(0, 0, 0, 0.28);
    }
    .hud-title {
        font-family: 'DM Mono', monospace;
        font-size: 1.55rem;
        letter-spacing: 0.08em;
        font-weight: 500;
        color: var(--bone);
        margin: 0;
    }
    .hud-badge {
        font-family: 'DM Mono', monospace;
        font-size: 0.68rem;
        letter-spacing: 0.1em;
        color: var(--amber);
        border: 1px solid rgba(214, 183, 119, 0.45);
        padding: 6px 11px;
        border-radius: 2px;
        background: rgba(214, 183, 119, 0.08);
    }
    h1, h2, h3, h4, h5, h6 { color: var(--bone) !important; letter-spacing: 0.015em; }
    [data-testid="stMarkdownContainer"] p, [data-testid="stCaptionContainer"] { color: #c7c1b4; }
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        margin: 8px 0 24px;
    }
    .metric-card {
        background: rgba(32, 37, 38, 0.8);
        border: 1px solid rgba(214, 183, 119, 0.16);
        border-radius: 2px;
        padding: 16px 12px;
        text-align: center;
        box-shadow: inset 0 1px rgba(255,255,255,0.03);
        transition: border-color 0.2s ease, transform 0.2s ease;
    }
    .metric-card:hover { transform: translateY(-2px); border-color: var(--amber); }
    .metric-val { font-family: 'DM Mono', monospace; font-size: 1.55rem; color: var(--amber); }
    .metric-lbl { font-family: 'DM Mono', monospace; font-size: 0.62rem; color: var(--muted); letter-spacing: 0.08em; text-transform: uppercase; margin-top: 5px; }
    .log-entry {
        background: rgba(24, 28, 29, 0.92);
        border: 1px solid rgba(232, 224, 207, 0.1);
        border-left: 3px solid var(--signal);
        border-radius: 2px;
        padding: 15px 18px;
        margin-bottom: 11px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.14);
    }
    .log-meta { font-family: 'DM Mono', monospace; font-size: 0.68rem; color: var(--amber); letter-spacing: 0.03em; margin-bottom: 8px; display: flex; justify-content: space-between; }
    .token-chip { display: inline-flex; background: rgba(214, 183, 119, 0.07); border: 1px solid rgba(214, 183, 119, 0.18); color: #d6cfbf; padding: 5px 9px; margin: 3px; border-radius: 2px; font-family: 'DM Mono', monospace; font-size: 11px; }
    .entity-block { background: rgba(24, 28, 29, 0.82); border: 1px solid rgba(214, 183, 119, 0.16); border-radius: 2px; padding: 15px; min-height: 220px; }
    .entity-header { font-family: 'DM Mono', monospace; font-size: 0.72rem; font-weight: 500; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 12px; }
    .tag-item { background: rgba(255, 255, 255, 0.035); border: 1px solid rgba(255, 255, 255, 0.08); padding: 6px 8px; border-radius: 2px; margin-bottom: 5px; font-size: 0.78rem; display: flex; justify-content: space-between; align-items: center; }
    .timeline-node { padding: 15px 18px; background: rgba(24, 28, 29, 0.92); border: 1px solid rgba(214, 183, 119, 0.16); border-left: 3px solid var(--amber); border-radius: 2px; margin-bottom: 12px; transition: transform 0.2s ease, border-color 0.2s ease; }
    .timeline-node:hover { transform: translateX(4px); border-left-color: var(--signal); }
    .timeline-date { font-family: 'DM Mono', monospace; font-size: 0.75rem; font-weight: 500; color: var(--amber); display: flex; align-items: center; gap: 8px; margin-bottom: 7px; }
    .timeline-desc { color: #d8d1c2; font-size: 0.88rem; line-height: 1.6; }
    .upload-card { background: rgba(24, 28, 29, 0.7); border: 1px dashed rgba(214, 183, 119, 0.35); border-radius: 2px; padding: 14px 18px; margin-bottom: 15px; }
    div[data-testid="stButton"] > button, div[data-testid="stDownloadButton"] > button { border-radius: 2px; border: 1px solid rgba(214, 183, 119, 0.35); font-family: 'DM Mono', monospace; letter-spacing: 0.02em; transition: all 0.2s ease; }
    div[data-testid="stButton"] > button:hover, div[data-testid="stDownloadButton"] > button:hover { border-color: var(--amber); color: var(--amber); }
    div[data-testid="stButton"] > button[kind="primary"], div[data-testid="stDownloadButton"] > button[kind="primary"] { background: var(--signal); border-color: var(--signal); color: #fff7e8; }
    div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea { background: #15191a; color: var(--bone); border: 1px solid rgba(214, 183, 119, 0.2); border-radius: 2px; }
    div[data-testid="stTextInput"] input:focus, div[data-testid="stTextArea"] textarea:focus { border-color: var(--amber); box-shadow: 0 0 0 1px var(--amber); }
    [data-baseweb="tab-list"] { gap: 0.25rem; border-bottom: 1px solid var(--line); }
    [data-baseweb="tab"] { font-family: 'DM Mono', monospace; color: var(--muted); font-size: 0.72rem; }
    [aria-selected="true"] { color: var(--amber) !important; }
    [data-testid="stDataFrame"] { border: 1px solid rgba(214, 183, 119, 0.16); }
    [data-testid="stExpander"] { border: 1px solid rgba(214, 183, 119, 0.18); border-radius: 2px; background: rgba(24, 28, 29, 0.58); }
    @media (max-width: 800px) { .metric-grid { grid-template-columns: repeat(2, 1fr); } .hud-header { padding: 18px; } .hud-title { font-size: 1.1rem; } .hud-badge { font-size: 0.58rem; } }
</style>
""", unsafe_allow_html=True)

# Session State Initialization
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

if "unlocked_cases" not in st.session_state:
    st.session_state.unlocked_cases = set()

# --- AUTHENTICATION GATEWAY ---
def auth_ui():
    st.markdown("""
        <div class="hud-header" style="justify-content: center; text-align: center; flex-direction: column; gap: 8px;">
            <h1 class="hud-title">🕵️ NLP DETECTIVE PORTAL</h1>
            <span class="hud-badge">SECURE MULTI-TENANT LOCAL VAULT</span>
        </div>
    """, unsafe_allow_html=True)
    
    _, col_auth, _ = st.columns([1, 1.4, 1])
    with col_auth:
        t_login, t_reg = st.tabs(["🔒 Secure Login", "📝 Agency Enlistment"])
        with t_login:
            u_id = st.text_input("Operative Handle", key="login_handle_input")
            u_pwd = st.text_input("Security Clearance Key", type="password", key="login_pass_input")
            
            if st.button("Access Organization Vault", type="primary", use_container_width=True):
                is_valid, response_msg = authenticate_user(u_id, u_pwd)
                if is_valid:
                    st.session_state.logged_in_user = u_id.strip().lower()
                    st.session_state.display_name = response_msg
                    st.session_state.current_case_id = None
                    st.rerun()
                else:
                    st.error(f"⚠ {response_msg}")
        
        with t_reg:
            r_org = st.text_input("Agency / Organization Name", placeholder="e.g. Cyber Crime Investigation Bureau", key="reg_org_input")
            r_id = st.text_input("Requested Operative Handle", key="reg_handle_input")
            r_pwd = st.text_input("Set Clearance Key", type="password", key="reg_pass_input")
            
            if st.button("Register & Create Local Vault", use_container_width=True):
                success, msg = register_user(r_id, r_pwd, r_org)
                if success:
                    st.success(msg)
                    st.session_state.logged_in_user = r_id.strip().lower()
                    st.session_state.display_name = r_id.strip()
                    st.session_state.current_case_id = None
                    st.rerun()
                else:
                    st.error(f"⚠️ {msg}")

if not st.session_state.get("logged_in_user"):
    auth_ui()
    st.stop()

# Load User and Org Specific Cases safely
cur_agent_key = st.session_state.logged_in_user
users_db = load_users()
user_info = users_db.get(cur_agent_key, {})
cur_agent = user_info.get("display_name", cur_agent_key)
cur_org = user_info.get("org", "Unknown Agency")
org_cases = load_org_cases(cur_org)

def create_new_case():
    new_id = f"CASE-{datetime.now().strftime('%y%m%d%H%M%S')}"
    new_case_obj = {
        "id": new_id,
        "title": "New Incident File",
        "entries": [],
        "creator": cur_agent,
        "is_locked": False,
        "pin_hash": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_case(cur_org, new_id, new_case_obj)
    st.session_state.current_case_id = new_id
    st.rerun()

if st.session_state.get("current_case_id") not in org_cases:
    if org_cases:
        st.session_state.current_case_id = list(org_cases.keys())[0]
    else:
        st.session_state.current_case_id = None

# --- SIDEBAR: CASE ARCHIVE ---
with st.sidebar:
    st.markdown(f"**Operative:** `{cur_agent}`")
    st.caption(f"🏛 **Vault:** {cur_org}")
    
    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in_user = None
        st.session_state.current_case_id = None
        st.session_state.unlocked_cases = set()
        st.rerun()

    st.markdown("---")
    
    if st.button("➕ Open New Case", type="primary", use_container_width=True):
        create_new_case()

    st.markdown(f"##### 🗄️ {cur_org[:18]} Archives")
    if org_cases:
        for cid, cdata in list(org_cases.items()):
            is_active = cid == st.session_state.current_case_id
            icon = "🔒" if cdata.get("is_locked") else "📁"
            prefix = "▸ " if is_active else ""
            num_logs = len(cdata.get("entries", []))
            
            c_col1, c_col2 = st.columns([5, 1])
            with c_col1:
                if st.button(f"{prefix}{icon} {cdata.get('title', 'Case')[:14]} ({num_logs})", key=f"btn_{cid}", use_container_width=True):
                    st.session_state.current_case_id = cid
                    st.rerun()
            with c_col2:
                if st.button("✕", key=f"del_case_{cid}", help="Delete entire case file"):
                    delete_case_from_disk(cur_org, cid)
                    if st.session_state.current_case_id == cid:
                        st.session_state.current_case_id = None
                    st.rerun()
    else:
        st.caption("No cases registered in this vault yet.")

# --- MAIN WORKSPACE ---
active_id = st.session_state.current_case_id

if not active_id or active_id not in org_cases:
    st.markdown(f"""
    <div class="hud-header">
        <div>
            <h1 class="hud-title">NLP DETECTIVE SUITE</h1>
            <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 4px;">AGENCY VAULT: {cur_org}</div>
        </div>
        <span class="hud-badge">CLEARED</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.info(f"📂 Organization vault for **{cur_org}** is currently empty. No default case is loaded.")
    if st.button("➕ Initialize First Case File", type="primary"):
        create_new_case()
    st.stop()

active_case = org_cases[active_id]

st.markdown(f"""
<div class="hud-header">
    <div>
        <h1 class="hud-title">NLP DETECTIVE SUITE</h1>
        <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 4px;">CASE: {active_id} // AGENCY VAULT: {cur_org}</div>
    </div>
    <span class="hud-badge">{'RESTRICTED' if active_case.get('is_locked') else 'OPEN CASE'}</span>
</div>
""", unsafe_allow_html=True)

# Lock Screen Verification
if active_case.get("is_locked") and (active_id not in st.session_state.unlocked_cases):
    st.warning(f"🔒 {active_id} is encrypted by agency protocol. Confidential PIN required.")
    pin_guess = st.text_input("Security PIN", type="password", key=f"pin_in_{active_id}")
    if st.button("Decrypt Dossier", type="primary"):
        if hash_val(pin_guess) == active_case.get("pin_hash"):
            st.session_state.unlocked_cases.add(active_id)
            st.rerun()
        else:
            st.error("PIN verification failed.")
    st.stop()

# Title and File Security Popover
col_t1, col_t2 = st.columns([4, 1])
with col_t1:
    new_title = st.text_input("Case Designation:", value=active_case.get("title", ""), label_visibility="collapsed")
    if new_title != active_case.get("title"):
        active_case["title"] = new_title
        save_case(cur_org, active_id, active_case)

with col_t2:
    with st.popover("🛡️ File Security"):
        lock_toggle = st.checkbox("Lock with Password PIN", value=active_case.get("is_locked", False))
        if lock_toggle:
            pin_input = st.text_input("Enter Passcode PIN:", type="password")
            if st.button("Save Encryption"):
                if pin_input:
                    active_case["is_locked"] = True
                    active_case["pin_hash"] = hash_val(pin_input)
                    save_case(cur_org, active_id, active_case)
                    st.success("Case PIN locked to disk.")
                    st.rerun()
        else:
            if active_case.get("is_locked"):
                active_case["is_locked"] = False
                active_case["pin_hash"] = None
                save_case(cur_org, active_id, active_case)
                st.info("Lock removed.")
                st.rerun()

# --- CHRONOLOGICAL INVESTIGATION FEED ---
st.markdown("#### 📜 Chronological Investigation Feed")
entries = active_case.get("entries", [])

if entries:
    for idx, entry in enumerate(entries):
        col_log, col_del = st.columns([11, 1])
        with col_log:
            st.markdown(f"""
            <div class="log-entry">
                <div class="log-meta">
                    <span>LOG #{idx + 1} // AGENT: {entry['author']}</span>
                    <span>{entry['timestamp']}</span>
                </div>
                <div style="color: #E2E8F0; font-size: 0.95rem; line-height: 1.5;">{entry['text']}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_del:
            st.write("")
            if st.button("🗑️", key=f"del_entry_{active_id}_{idx}", help=f"Delete Log #{idx + 1}"):
                entries.pop(idx)
                active_case["entries"] = entries
                save_case(cur_org, active_id, active_case)
                st.rerun()
else:
    st.caption("No evidence logged yet in this case. Append your first report below.")

# --- EVIDENCE INGESTION: DRAG & DROP + TEXT ENTRY ---
st.markdown("##### 📥 Append Evidence / Ingestion Hub")

with st.expander("📂 Upload External Evidence File (.TXT or .PDF)", expanded=False):
    uploaded_file = st.file_uploader(
        "Upload FIR, Interrogation Transcript, or Forensic Report:",
        type=["txt", "pdf"],
        help="Upload a raw text file or scanned PDF report to extract text automatically into the active case."
    )
    if uploaded_file is not None:
        extracted_file_text = ""
        try:
            if uploaded_file.name.endswith(".txt"):
                extracted_file_text = uploaded_file.read().decode("utf-8", errors="ignore")
            elif uploaded_file.name.endswith(".pdf"):
                pdf_reader = PdfReader(io.BytesIO(uploaded_file.read()))
                for page in pdf_reader.pages:
                    text_content = page.extract_text()
                    if text_content:
                        extracted_file_text += text_content + "\n"

            extracted_file_text = extracted_file_text.strip()

            if extracted_file_text:
                st.success(f"Extracted {len(extracted_file_text)} characters from `{uploaded_file.name}`.")
                st.text_area("Preview Extracted Document Content:", value=extracted_file_text[:600] + ("..." if len(extracted_file_text) > 600 else ""), height=100, disabled=True)
                
                if st.button("➕ Ingest Document into Case File", type="primary"):
                    entries.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "text": extracted_file_text,
                        "author": f"{cur_agent} (via {uploaded_file.name})"
                    })
                    active_case["entries"] = entries
                    save_case(cur_org, active_id, active_case)
                    st.rerun()
            else:
                st.warning("No readable text could be parsed from this file.")
        except Exception as e:
            st.error(f"Error parsing file: {e}")

# Manual Text Entry
with st.container():
    col_in, col_btn = st.columns([5, 1])
    with col_in:
        new_evidence = st.text_area(
            "Log Manual Evidence Update:",
            placeholder="Type or paste incoming witness statements, forensic updates, or intercepted communications...",
            height=85,
            label_visibility="collapsed",
            key="new_evidence_input"
        )
    with col_btn:
        st.write("")
        if st.button("➕ Log Update", type="primary", use_container_width=True):
            clean_text = new_evidence.strip()
            if clean_text:
                if entries and entries[-1]["text"].strip() == clean_text:
                    st.warning("⚠️ This evidence statement was already logged as the latest entry.")
                else:
                    entries.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "text": clean_text,
                        "author": cur_agent
                    })
                    active_case["entries"] = entries
                    save_case(cur_org, active_id, active_case)
                    st.rerun()

# Cumulative Analysis
cumulative_text = " ".join([e["text"] for e in entries if e["text"].strip()])

if cumulative_text:
    doc = parse_document(cumulative_text)
    processed_entities = post_process_entities(doc)
    triplets = extract_triplets(doc)
    timeline_events = extract_timeline_events(doc)

    st.markdown(f"""
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-val">{len(cumulative_text)}</div>
            <div class="metric-lbl">Cumulative Characters</div>
        </div>
        <div class="metric-card">
            <div class="metric-val">{len(list(doc.sents))}</div>
            <div class="metric-lbl">Total Sentences</div>
        </div>
        <div class="metric-card">
            <div class="metric-val">{len(processed_entities)}</div>
            <div class="metric-lbl">Entities Detected</div>
        </div>
        <div class="metric-card">
            <div class="metric-val">{len(timeline_events)}</div>
            <div class="metric-lbl">Timeline Milestones</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    pdf_bytes = generate_pdf_report(
        case_id=active_id,
        title=active_case.get("title", "Case"),
        entries=entries,
        processed_entities=processed_entities,
        triplets=triplets,
        operative=cur_agent,
        agency=cur_org
    )

    st.download_button(
        label="📑 Export Full Case PDF Dossier",
        data=pdf_bytes,
        file_name=f"{active_id}_Dossier.pdf",
        mime="application/pdf",
        type="primary"
    )

    t_intel, t_timeline, t_entities, t_tokens, t_graph = st.tabs([
        "🔍 Consolidated Dossier",
        "⏱️ Incident Timeline",
        "🏷️ Cumulative Entities",
        "🧩 Token Segmentation",
        "🌐 Relational Knowledge Graph"
    ])

    # 1. Consolidated Dossier
    with t_intel:
        c_p, c_o, c_l, c_v = st.columns(4)
        people = list(set([e["text"] for e in processed_entities if e["label"] == "PERSON"]))
        orgs = list(set([e["text"] for e in processed_entities if e["label"] == "ORG"]))
        locs = list(set([e["text"] for e in processed_entities if e["label"] in ("GPE", "FAC")]))
        vals = list(set([e["text"] for e in processed_entities if e["label"] in ("DATE", "TIME", "MONEY")]))

        with c_p:
            items = "".join([f"<div class='tag-item'><span>{p}</span><span style='color:#38BDF8;'>PERSON</span></div>" for p in people]) or "<div style='color:#64748B;'>No individuals detected</div>"
            st.markdown(f"<div class='entity-block'><div class='entity-header' style='color:#38BDF8;'>👤 Persons</div>{items}</div>", unsafe_allow_html=True)
        with c_o:
            items = "".join([f"<div class='tag-item'><span>{o}</span><span style='color:#F472B6;'>ORG</span></div>" for o in orgs]) or "<div style='color:#64748B;'>No organizations detected</div>"
            st.markdown(f"<div class='entity-block'><div class='entity-header' style='color:#F472B6;'>🏢 Organizations</div>{items}</div>", unsafe_allow_html=True)
        with c_l:
            items = "".join([f"<div class='tag-item'><span>{l}</span><span style='color:#4ADE80;'>LOC</span></div>" for l in locs]) or "<div style='color:#64748B;'>No locations detected</div>"
            st.markdown(f"<div class='entity-block'><div class='entity-header' style='color:#4ADE80;'>📍 Locations</div>{items}</div>", unsafe_allow_html=True)
        with c_v:
            items = "".join([f"<div class='tag-item'><span>{v}</span><span style='color:#FBBF24;'>VALUE</span></div>" for v in vals]) or "<div style='color:#64748B;'>No temporal/currency tags</div>"
            st.markdown(f"<div class='entity-block'><div class='entity-header' style='color:#FBBF24;'>⏱️ Times & Values</div>{items}</div>", unsafe_allow_html=True)

        st.markdown("#### Cumulative Grammatical S-V-O Triplet Extractions")
        if triplets:
            st.dataframe(pd.DataFrame(triplets), use_container_width=True)
        else:
            st.info("No explicit Subject-Verb-Object triplets parsed.")

    # 2. Automated Incident Timeline Tab
    with t_timeline:
        st.markdown("#### ⏱️ Chronological Incident Reconstruction")
        st.caption("Temporal expressions parsed, normalized, and ordered from earliest to latest:")

        if timeline_events:
            for idx, event in enumerate(timeline_events, 1):
                clean_date_display = event["parsed_dt"].strftime("%d %B %Y (%A)") if event["parsed_dt"] else event["raw_date"]
                st.markdown(f"""
                <div class="timeline-node">
                    <div class="timeline-date">
                        <span>🚩 MILESTONE #{idx}</span> • <span>{clean_date_display}</span>
                    </div>
                    <div class="timeline-desc">{event['event']}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No date or temporal indicators detected in the current evidence text to construct a timeline.")

    # 3. Cumulative Entities
    with t_entities:
        if processed_entities:
            records = [{"Mention": e["text"], "Type": e["label"], "Meaning": spacy.explain(e["label"])} for e in processed_entities]
            st.dataframe(pd.DataFrame(records), use_container_width=True)
        else:
            st.info("No entities identified.")

    # 4. Token Segmentation
    with t_tokens:
        st.markdown("#### Cumulative Discrete Tokens")
        token_pills = "".join([f"<span class='token-chip'>{t.text}</span>" for t in doc])
        st.markdown(token_pills, unsafe_allow_html=True)

    # 5. Relational Knowledge Graph
    with t_graph:
        if triplets:
            g_html, ranked_suspects, top_poi = analyze_network_centrality(triplets, processed_entities)
            
            if top_poi and ranked_suspects:
                if isinstance(top_poi, dict):
                    poi_data = top_poi
                else:
                    poi_data = next((item for item in ranked_suspects if item.get("Entity") == top_poi), ranked_suspects[0])

                poi_name = poi_data.get("Entity", "Unknown")
                poi_type = poi_data.get("Type", "ENTITY")
                poi_score = poi_data.get("Involvement Score", 0.0)
                poi_role = poi_data.get("Network Role", "Central Figure")
                poi_links = poi_data.get("Direct Connections", f"{poi_data.get('Degree Centrality', 'N/A')} connectivity")

                st.markdown(f"""
                <div class="poi-card" style="border-left: 5px solid #38BDF8; background: rgba(15, 23, 42, 0.75); padding: 14px 18px; border-radius: 8px; margin-bottom: 15px;">
                    <div style="font-family:'JetBrains Mono', monospace; font-size:0.75rem; color:#38BDF8; font-weight:700; letter-spacing:1px;">
                        🎯 PRIMARY PERSON / ENTITY OF INTEREST (KEY SUSPECT)
                    </div>
                    <div style="font-size:1.5rem; font-weight:700; color:#F8FAFC; margin:4px 0;">
                        {poi_name} <span style="font-size:0.85rem; color:#94A3B8;">[{poi_type}]</span>
                    </div>
                    <div style="font-size:0.9rem; color:#CBD5E1; line-height:1.6;">
                        Investigation Significance: <b>{poi_score}%</b> • 
                        Role: <span style="color:#4ADE80; font-weight:600;">{poi_role}</span> • 
                        Connections: <b>{poi_links}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            components.html(g_html, height=520)

            st.markdown("#### 📊 Suspect Centrality & Influence Ranking")
            st.caption("How actors connect across evidence logs (ranked by relational importance):")
            if ranked_suspects:
                cols_to_show = [c for c in ["Entity", "Type", "Direct Connections", "Network Role", "Involvement Score"] if c in ranked_suspects[0]]
                st.dataframe(pd.DataFrame(ranked_suspects)[cols_to_show], use_container_width=True)
        else:
            st.info("The knowledge graph requires at least one extracted S-V-O relationship triplet.")