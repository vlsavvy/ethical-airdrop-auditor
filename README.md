# Ethical Airdrop Auditor

A fast, lightweight prototype built for the **Qubic Hack-the-Future Hackathon (EasyConnect Track)**.  
This project detects suspicious token events (airdrops, transfers, mints) using rolling statistical analysis and heuristics, then generates human-friendly AI-style explanations.

This system works **with or without blockchain access**. For hackathon demo purposes, it includes:
- Simulated token activity stream
- Real-time anomaly detection
- Transparent explainability
- CSV export
- Optional webhook ingestion for EasyConnect
- Optional LLM hook for richer explanations

---

## 🚀 Features
- **Rolling Z-score anomaly detection** over recent event windows
- **Airdrop outlier identification** (large relative to median transfers)
- **Wallet clustering heuristic** to detect farming behavior
- **AI-style explanations** (template; can plug in an LLM)
- **Event feed UI** (Streamlit)
- **Alerts panel** with copyable JSON
- **CSV export** for suspicious events
- **Webhook ingestion** (paste JSON or connect EasyConnect)
- **Demo-friendly setup**—works instantly with simulated events

---

## 📁 Project Structure
```
.
├── app.py                # Main Streamlit application
├── requirements.txt      # Python dependencies
├── README.md             # (This file)
└── assets/               # (Optional) images for slides or cover
```

---

## 🧩 Installation
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## ▶️ Run the App
```bash
streamlit run app.py
```

A local browser window will open automatically.

---

## 🌐 Deploying the Demo
### **Option 1: Streamlit Cloud (recommended)**
1. Push this project to a public GitHub repo.
2. Go to https://share.streamlit.io
3. Select your repo → pick `app.py`
4. Deploy.

This generates the **Application URL** required for the submission.

---

## 🔌 Optional: Webhook Integration
### 1. Paste JSON directly in UI
You can paste webhook JSON (one per line) into the text box.

### 2. Or connect EasyConnect
Configure EasyConnect to POST events to a webhook endpoint you expose via:
- ngrok
- FastAPI/Flask on Cloud Run
- Railway

A basic webhook snippet can be added if needed.

---

## 🧠 Explanation Engine
Default explanations are rule
