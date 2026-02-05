# 🍯 Agentic Honey-Pot for Scam Detection & Intelligence Extraction

A production-ready FastAPI backend that acts as an intelligent honey-pot system to detect scam attempts, engage scammers with an AI-powered elderly persona, and extract actionable intelligence for law enforcement.

## 🏗️ Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Platform      │────▶│   FastAPI        │────▶│   Scam Detector │
│   (Webhook)     │     │   /webhook       │     │   (Rule-based)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │                           │
                               ▼                           ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │   Conversation   │     │   Intelligence  │
                        │   Memory         │     │   Extractor     │
                        └──────────────────┘     └─────────────────┘
                               │                           │
                               ▼                           ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │   AI Agent       │◄────│   Gemini API    │
                        │   (Gemini)       │     │   (gemini-1.5-  │
                        └──────────────────┘     │   flash)        │
                               │                 └─────────────────┘
                               ▼
                        ┌──────────────────┐
                        │   Callback       │────▶ Platform API
                        │   Sender         │     (Final Results)
                        └──────────────────┘
```

## 📁 Project Structure

```
guvi-honeypot/
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Configuration & constants
│   │   └── auth.py            # API key authentication
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py         # Pydantic models
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── scam_detector.py   # Rule-based scam detection
│   │   ├── agent.py           # Agent logic & stop conditions
│   │   ├── conversation_memory.py  # Session state management
│   │   └── intelligence_extractor.py  # Regex-based extraction
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gemini_client.py   # Gemini API wrapper
│   │   └── callback_sender.py # Callback with retry logic
│   ├── __init__.py
│   └── main.py                # FastAPI application
├── logs/                      # Failed callback logs
├── .env.example               # Environment template
├── requirements.txt           # Dependencies
└── README.md                  # This file
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone/navigate to project
cd guvi-honeypot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your keys
nano .env
```

Required environment variables:
- `API_KEY`: Your webhook authentication key
- `GEMINI_API_KEY`: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)

### 3. Run the Server

```bash
# Development mode
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 🔌 API Endpoints

### POST /webhook

Main endpoint for processing incoming messages.

**Headers:**
```
x-api-key: your-secure-api-key
Content-Type: application/json
```

**Request Body:**
```json
{
  "sessionId": "unique-session-id",
  "message": "Your account will be blocked. Click here immediately!",
  "conversationHistory": ["previous message 1", "previous message 2"],
  "metadata": {
    "source": "whatsapp",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "reply": "Sorry beta, my phone is slow. Can you tell me which bank you are from?"
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 🧠 System Flow

```
1. Platform sends message to POST /webhook
   │
   ▼
2. API Key Validation (x-api-key header)
   │
   ▼
3. Scam Detection (Rule-based, NO LLM)
   ├── Keyword matching (urgent, payment, OTP, etc.)
   ├── Urgency score calculation
   └── Payment redirection detection
   │
   ▼
4. If scam_detected == true:
   │
   ├── 4a. Activate AI Agent (Gemini)
   │   ├── Generate elderly persona reply
   │   ├── Ask probing questions
   │   └── Extract scammer information
   │
   ├── 4b. Intelligence Extraction (Regex)
   │   ├── Bank accounts / IFSC codes
   │   ├── UPI IDs
   │   ├── Phishing links
   │   └── Phone numbers
   │
   └── 4c. Check Stop Conditions
       ├── Enough intelligence collected?
       ├── Max turns reached (default: 15)?
       └── Scammer disengaged?
   │
   ▼
5. If engagement completed:
   │
   ├── Generate agent notes via Gemini
   │
   └── Send callback to platform
       POST https://hackathon.guvi.in/api/updateHoneyPotFinalResult
       {
         "sessionId": "...",
         "scamDetected": true,
         "totalMessagesExchanged": 8,
         "extractedIntelligence": {...},
         "agentNotes": {...}
       }
```

## 🔒 Scam Detection (Rule-Based)

The system uses deterministic detection **without LLM** for speed and reliability:

### Detection Signals

| Category | Examples | Weight |
|----------|----------|--------|
| Urgency | "urgent", "immediately", "now", "hurry" | High |
| Payment | "pay", "transfer", "UPI", "QR code" | High |
| Sensitive Info | "OTP", "password", "CVV", "PIN" | Critical |
| Threats | "block", "suspend", "legal action" | Medium |
| Impersonation | "bank", "RBI", "police", "income tax" | Medium |

### Scoring Logic

```python
# Confidence score (0.0 - 1.0)
score = (keywords * 0.1) + (urgency * 0.03) + (payment * 0.2) + context

# Scam detected if:
- keywords >= 2, OR
- urgency >= 3, OR
- payment + keywords >= 1, OR
- multiple indicators present
```

## 🤖 AI Agent Persona

The agent uses **Gemini 1.5 Flash** to generate believable responses:

### Persona: "Ramesh" (Age 68)

**Characteristics:**
- Slightly confused about technology
- Very polite and cooperative
- Simple English with occasional Hindi phrases
- Trusting but asks many questions
- Moves slowly, needs repeated explanations

**Conversation Strategy:**
1. **Delay tactics**: "My phone is slow", "Getting my glasses"
2. **Probing questions**: "Which company?", "Your name?", "Why needed?"
3. **Fake cooperation**: Pretend to follow instructions
4. **Never reveal**: Never use "scam", "fraud", "police", "trap"

**Example Responses:**
- "Sorry beta, my phone is acting up. Can you repeat?"
- "Arre, which bank did you say you are from?"
- "Theek hai, but my grandson is coming to help soon."

## 📊 Intelligence Extraction

Extracted deterministically using regex patterns:

| Type | Pattern Example |
|------|-----------------|
| Bank Accounts | `\d{9,18}` (9-18 digits) |
| IFSC Codes | `[A-Z]{4}0[A-Z0-9]{6}` |
| UPI IDs | `user@bank`, `user@upi` |
| Phone Numbers | `+91XXXXXXXXXX`, `0XXXXXXXXXX` |
| Phishing Links | Shortened URLs, suspicious domains |

## 🔄 Conversation States

```
PENDING ──► SCAM_DETECTED ──► ENGAGING ──► COMPLETED ──► CALLBACK_SENT
                ▲                              │
                └──────────────────────────────┘
                    (if more messages arrive)
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | - | Webhook authentication key |
| `GEMINI_API_KEY` | - | Google Gemini API key |
| `GEMINI_MODEL` | gemini-1.5-flash | Gemini model name |
| `MAX_CONVERSATION_TURNS` | 15 | Max agent interactions |
| `MIN_CONVERSATION_TURNS` | 3 | Min before completion |
| `CALLBACK_URL` | - | Platform callback endpoint |
| `CALLBACK_MAX_RETRIES` | 3 | Retry attempts |

### Stop Conditions

Engagement ends when:
1. ✅ Enough intelligence collected (default: 2+ items)
2. ✅ Max turn limit reached (default: 15 turns)
3. ✅ Scammer disengages ("bye", "stop", etc.)
4. ✅ Abusive language detected

## 📞 Callback Payload

When engagement completes, the system sends:

```json
{
  "sessionId": "session-123",
  "scamDetected": true,
  "totalMessagesExchanged": 8,
  "extractedIntelligence": {
    "bankAccounts": ["1234567890"],
    "upiIds": ["scammer@upi"],
    "phishingLinks": ["https://bit.ly/fake"],
    "phoneNumbers": ["+919876543210"],
    "suspiciousKeywords": ["urgent", "otp", "payment"]
  },
  "agentNotes": {
    "scam_type": "bank_impersonation",
    "tactics_used": ["urgency", "threat"],
    "extracted_entities": ["RBI", "SBI"],
    "risk_assessment": "high",
    "summary": "Scammer impersonated RBI official..."
  }
}
```

## 🛡️ Security Features

1. **API Key Authentication**: Constant-time comparison to prevent timing attacks
2. **No LLM for Detection**: Rule-based detection prevents prompt injection
3. **Input Sanitization**: All responses cleaned before output
4. **Timeout Protection**: All external calls have timeouts
5. **Retry with Backoff**: Callback failures use exponential backoff
6. **Fallback Logging**: Failed callbacks logged locally for recovery

## 🧪 Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test webhook (scam message)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "sessionId": "test-123",
    "message": "URGENT: Your account will be blocked. Click link now!",
    "conversationHistory": [],
    "metadata": {"source": "test"}
  }'

# Test webhook (normal message)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "sessionId": "test-456",
    "message": "Hello, how are you today?",
    "conversationHistory": [],
    "metadata": {"source": "test"}
  }'
```

## 📈 Monitoring

```bash
# View active sessions
curl http://localhost:8000/sessions \
  -H "x-api-key: your-api-key"

# View specific session
curl http://localhost:8000/sessions/test-123 \
  -H "x-api-key: your-api-key"
```

## 🚀 Deployment

### Docker (Optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Checklist

- [ ] Change default `API_KEY`
- [ ] Set valid `GEMINI_API_KEY`
- [ ] Set `DEBUG=false`
- [ ] Configure proper logging
- [ ] Set up monitoring/alerting
- [ ] Enable HTTPS
- [ ] Configure firewall rules

## 📜 License

This project is built for the GUVI Hackathon.

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| Gemini API errors | Check `GEMINI_API_KEY` is valid |
| 403 Forbidden | Verify `x-api-key` header matches `API_KEY` |
| Callback failures | Check network connectivity to callback URL |
| High latency | Reduce `GEMINI_MAX_TOKENS` or use caching |

## 📧 Support

For issues or questions, please refer to the hackathon documentation or contact the organizers.
