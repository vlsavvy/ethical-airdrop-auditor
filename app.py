"""
Ethical Airdrop Auditor - Streamlit demo app
Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
import io
import requests

st.set_page_config(page_title="Ethical Airdrop Auditor", layout="wide")

# -----------------------------
# Helpers: Data generation + detection
# -----------------------------
@st.cache_data
def generate_demo_events(n=300, start_time=None, base_amount=10.0):
    """Generate a simulated list of token events (transfers/airdrops/mints)."""
    if start_time is None:
        end = datetime.now()
        start_time = end - timedelta(minutes=n)
    times = [start_time + timedelta(minutes=i) for i in range(n)]
    types = np.random.choice(["transfer", "airdrop", "mint"], size=n, p=[0.7, 0.25, 0.05])
    # Simulated amount series with occasional spikes
    amounts = np.abs(np.random.randn(n).cumsum()) * base_amount
    df = pd.DataFrame({"ts": times, "type": types, "amount": amounts})
    # Add some metadata columns to emulate wallets
    df["from_wallet"] = np.random.choice([f"0x{np.random.randint(10**8):08x}" for _ in range(50)], size=n)
    df["to_wallet"] = np.random.choice([f"0x{np.random.randint(10**8):08x}" for _ in range(50)], size=n)
    df["event_json"] = df.apply(lambda r: json.dumps({
        "ts": r.ts.isoformat(), "type": r.type, "amount": float(r.amount),
        "from": r.from_wallet, "to": r.to_wallet
    }), axis=1)
    return df

def compute_rolling_z(series: pd.Series, window: int):
    """Return rolling z-score and rolling mean/std for debugging/insights."""
    rolling_mean = series.rolling(window, min_periods=1).mean()
    rolling_std = series.rolling(window, min_periods=1).std().replace(0, 1e-9)
    z = (series - rolling_mean) / rolling_std
    return z, rolling_mean, rolling_std

def detect_anomalies(df: pd.DataFrame, window:int, z_threshold:float, airdrop_sensitivity:float):
    df = df.copy()
    z, _, _ = compute_rolling_z(df["amount"], window)
    df["z"] = z
    # basic anomaly by z-score
    df["anomaly_z"] = df["z"].abs() > z_threshold
    # additional heuristics: big airdrops relative to median of transfers
    median_transfer = df[df["type"]=="transfer"]["amount"].median() if not df[df["type"]=="transfer"].empty else df["amount"].median()
    df["anomaly_airdrop"] = False
    # mark an airdrop anomalous if it's many times larger than median_transfer
    df.loc[(df["type"]=="airdrop") & (df["amount"] > median_transfer * airdrop_sensitivity), "anomaly_airdrop"] = True
    # aggregated anomaly flag
    df["anomaly"] = df["anomaly_z"] | df["anomaly_airdrop"]
    return df

def generate_explanation(row):
    """Generate a human-readable explanation string for an anomaly row.
    This is templated; if you have an LLM API key you can replace this with a call to generate richer text."""
    reasons = []
    if row["anomaly_z"]:
        reasons.append(f"Amount deviates strongly from recent history (z={row['z']:.2f}).")
    if row["anomaly_airdrop"]:
        reasons.append("Airdrop amount is unusually large relative to typical transfers.")
    # heuristic wallet checks
    if row.get("from_wallet_clustered", False):
        reasons.append("Sender is part of a clustered wallet set (possible farming).")
    explanation = " ".join(reasons) if reasons else "Anomaly detected; investigate sender & recipients."
    # Suggested actions
    actions = ("Suggested actions: investigate sender/recipient addresses, check tokenomics & team "
               "transparency, pause listings if suspicious, and check contract audit status.")
    return explanation + " " + actions

# -----------------------------
# App UI: Controls
# -----------------------------
st.title("🔍 Ethical Airdrop Auditor")
st.markdown("Real-time anomaly detection + AI-style explanations for token activity (demo).")

col_left, col_right = st.columns([1,2])

with col_left:
    st.header("Settings")
    window = st.slider("Rolling window (events)", min_value=5, max_value=120, value=40)
    z_threshold = st.slider("Z-score anomaly threshold", min_value=1.5, max_value=6.0, value=3.0)
    airdrop_sensitivity = st.slider("Airdrop sensitivity (x median transfer)", min_value=1.0, max_value=50.0, value=8.0)
    base_amount = st.slider("Base amount volatility", 1.0, 100.0, 10.0)
    n_events = st.slider("Number of simulated events", 50, 1000, 300)
    use_llm = st.checkbox("Enable LLM-based richer explanations (requires API key)", value=False)
    if use_llm:
        st.info("LLM option included as a hook. Add your OpenAI-compatible API key in the text box below if you want richer explanations.")
        api_key = st.text_input("LLM API key (optional)", type="password")
    else:
        api_key = None

with col_right:
    st.header("Data source & demo control")
    st.write("You can either: (A) use simulated events (default) or (B) paste JSON webhook payloads into the textbox below.")
    if st.button("Generate simulated events"):
        # force regeneration by clearing cache manually (workaround)
        df = generate_demo_events(n_events, base_amount=base_amount)
        st.session_state["events_df"] = df
        st.success(f"Generated {len(df)} events.")
    # show webhook input
    webhook_text = st.text_area("Paste webhook payload(s) here (one JSON per line) — optional", height=120)
    if webhook_text and st.button("Ingest webhook text"):
        lines = [l.strip() for l in webhook_text.splitlines() if l.strip()]
        parsed = []
        for ln in lines:
            try:
                j = json.loads(ln)
                # normalize keys
                if "ts" not in j:
                    j["ts"] = datetime.now().isoformat()
                parsed.append({
                    "ts": pd.to_datetime(j.get("ts")),
                    "type": j.get("type", "transfer"),
                    "amount": float(j.get("amount", 0)),
                    "from_wallet": j.get("from","unknown"),
                    "to_wallet": j.get("to","unknown"),
                    "event_json": json.dumps(j)
                })
            except Exception as e:
                st.warning(f"Failed to parse line: {ln[:80]}... -> {e}")
        if parsed:
            df_web = pd.DataFrame(parsed)
            st.session_state["events_df"] = df_web
            st.success(f"Ingested {len(df_web)} webhook events.")

# restore or generate if not present
if "events_df" not in st.session_state:
    st.session_state["events_df"] = generate_demo_events(n_events, base_amount=base_amount)

df_events = st.session_state["events_df"]

# If user changed base_amount or n_events but didn't click generate, provide option
st.caption("Tip: click 'Generate simulated events' after changing settings to refresh the dataset.")

# -----------------------------
# Detection & scoring
# -----------------------------
df_scored = detect_anomalies(df_events, window=window, z_threshold=z_threshold, airdrop_sensitivity=airdrop_sensitivity)

# Optional: simple wallet clustering heuristic - mark many outgoing to same to_wallet as suspicious
to_counts = df_scored.groupby("to_wallet").size()
suspicious_targets = set(to_counts[to_counts > max(3, int(0.02*len(df_scored)))].index)
df_scored["to_wallet_clustered"] = df_scored["to_wallet"].isin(suspicious_targets)
# annotate explanations with cluster info
df_scored["from_wallet_clustered"] = df_scored.duplicated(subset=["from_wallet"], keep=False)

# Generate explanations
df_scored["explanation"] = df_scored.apply(generate_explanation, axis=1)

# -----------------------------
# UI: show feed + alerts
# -----------------------------
st.markdown("---")
st.subheader("📡 Live Event Feed (latest first)")
st.dataframe(df_scored.sort_values("ts", ascending=False).head(100), use_container_width=True)

st.subheader("🚨 Alerts")
alerts = df_scored[df_scored["anomaly"]].sort_values("ts", ascending=False)
if alerts.empty:
    st.success("No suspicious events detected with current settings.")
else:
    for _, row in alerts.head(25).iterrows():
        with st.container():
            st.markdown(f"**{row.ts}** — `{row.type}` — amount: **{row.amount:.2f}** — z={row.z:.2f}")
            st.markdown(f"> {row.explanation}")
            # buttons: copy JSON, mark false positive, push to Telegram (stub)
            cols = st.columns([1,1,1])
            if cols[0].button("Copy JSON", key=f"copy_{_}"):
                st.clipboard_set(row["event_json"])
                st.toast("Copied JSON to clipboard")
            if cols[1].button("Mark FP", key=f"fp_{_}"):
                st.info("Marked as false positive (local demo).")
            if cols[2].button("Send Alert (Telegram stub)", key=f"tg_{_}"):
                st.toast("Alert would be sent to Telegram (integration stub).")

# -----------------------------
# Exports & subscription stubs
# -----------------------------
st.markdown("---")
col1, col2 = st.columns([1,1])
with col1:
    if st.button("Export alerts to CSV"):
        buf = io.StringIO()
        alerts.to_csv(buf, index=False)
        b = buf.getvalue().encode()
        st.download_button("Download alerts.csv", data=b, file_name="alerts.csv", mime="text/csv")
with col2:
    st.markdown("Subscribe for premium alerts (demo)")
    email = st.text_input("Email for alerts (demo)")
    if st.button("Subscribe (demo)"):
        if email and "@" in email:
            st.success(f"Subscribed {email} to demo alerts. (No real emails will be sent in demo.)")
        else:
            st.error("Enter a valid email for demo subscription.")

# -----------------------------
# Optional LLM hook (demonstration only)
# -----------------------------
if use_llm and api_key:
    st.markdown("---")
    st.subheader("LLM-powered explanation preview (optional)")
    sample_row = df_scored.sort_values("ts", ascending=False).iloc[0]
    prompt = f"""
You are an explainability assistant for token airdrop/transfer anomalies.
Event: {sample_row.to_json()}
Return a short (1-2 sentence) human-friendly explanation of why this event is suspicious and 2 suggested mitigation steps.
"""
    st.code(prompt, language="text")
    st.info("LLM call is optional. If you have an OpenAI-compatible endpoint, replace this block to call it securely.")
    # Example placeholder code (commented out for safety)
    st.caption("To integrate: call your LLM provider with the prompt, and display results here.")

# -----------------------------
# Footer / notes
# -----------------------------
st.markdown("---")
st.caption("Demo prototype for Qubic Hack-the-Future (EasyConnect track). No real wallet keys stored. Replace simulated feed with real webhook ingestion for production.")
