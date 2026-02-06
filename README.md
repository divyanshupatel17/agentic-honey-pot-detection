| | |
|---|---|
| **Project Name** | Agentic Honey-Pot for Scam Detection & Intelligence Extraction |
| **Hackathon** | India AI Impact Buildathon |
| **Organizer** | GUVI - HCL |
| **Hackathon URL** | [Event Page](https://hackathon.guvi.in/timeline?hackathon-id=a90c3b95-4406-46b9-870d-b52d0e430a6f) |
| **Team Lead** | Divyanshu Patel |

# 🍯 Agentic Honey-Pot for Scam Detection & Intelligence Extraction

A production-ready FastAPI backend that acts as an intelligent honey-pot system to detect scam attempts, engage scammers with an AI-powered elderly persona, and extract actionable intelligence for law enforcement.

**Author:** Divyanshu Patel  
**LinkedIn:** [https://www.linkedin.com/in/patel-divyanshu/](https://www.linkedin.com/in/patel-divyanshu/)

---

## 🚀 Key Features

*   **Rule-Based Scam Detection**: Deterministic detection ensuring 100% safety (No Prompt Injection).
*   **AI Agent (Groq)**: Uses `llama-3.1-8b-instant` for high-speed, 14k/day rate-limited responses.
*   **Persona "Ramesh"**: Believable 68-year-old persona that wastes scammer's time.
*   **Intelligence Extraction**: Auto-extracts Bank Accounts, UPI IDs, and Phishing Links using Regex.
*   **Secure**: API Key authentication and input sanitization.

## 🏗️ Architecture

1.  **Incoming Message** (/webhook) -> **Scam Detector**
2.  **If Scam Detected** -> Activate **AI Agent**
3.  **Agent Logic** -> Generate "confused elderly" reply
4.  **Extract Info** -> Bank/UPI details saved
5.  **Completion** -> Send Callback with full intelligence report

## � Project Structure

```bash
guvi-honeypot/
├── app/
│   ├── modules/
│   │   ├── scam_detector.py   # Rule-based logic
│   │   ├── agent.py           # Groq-powered Agent
│   │   └── intelligence_extractor.py # Regex extraction
│   ├── services/
│   │   ├── groq_client.py     # Groq API Wrapper
│   │   └── callback_sender.py # Webhook Notifier
│   └── main.py                # FastAPI App
└── requirements.txt
```

## �️ Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create `.env`:
```ini
API_KEY=your-secure-key
GROQ_API_KEY=your-groq-key
GROQ_MODEL=llama-3.1-8b-instant
```

### 3. Run Server
```bash
uvicorn app.main:app --reload
```

## � API Endpoints

### `POST /webhook`
Input:
```json
{
  "sessionId": "123",
  "message": "URGENT: Your account blocked. Share OTP."
}
```

Response:
```json
{
  "status": "success",
  "reply": "Arre beta, what is OTP? My eyes are not good."
}
```

### `GET /health`
Returns system status (200 OK).

## 🔒 Security
*   **Authentication**: `x-api-key` header required.
*   **Safe Mode**: Falls back to "Network Error" simulation if AI fails.
*   **Data Privacy**: No PII stored persistently.
