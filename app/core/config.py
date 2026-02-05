"""
Configuration module for the Honey-Pot Scam Detection System.
Loads environment variables and provides centralized configuration.
"""

import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    API_TITLE: str = "Honey-Pot Scam Detection API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "Agentic Honey-Pot for Scam Detection & Intelligence Extraction"
    DEBUG: bool = False
    
    # Security
    API_KEY: str = "your-secure-api-key-here"  # Platform's API key for webhook auth
    GEMINI_API_KEY: str = "your-gemini-api-key-here"  # Google Gemini API key
    
    # Gemini Configuration
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_MAX_TOKENS: int = 1024
    GEMINI_TEMPERATURE: float = 0.7
    GEMINI_TIMEOUT: int = 30  # seconds
    
    # Agent Configuration
    MAX_CONVERSATION_TURNS: int = 15
    MIN_CONVERSATION_TURNS: int = 3  # Minimum before considering completion
    AGENT_PERSONA_AGE: int = 68
    AGENT_PERSONA_NAME: str = "Ramesh"
    
    # Scam Detection Thresholds
    SCAM_KEYWORD_THRESHOLD: int = 2  # Minimum keywords to trigger detection
    URGENCY_SCORE_THRESHOLD: int = 3  # Minimum urgency indicators
    
    # Callback Configuration
    CALLBACK_URL: str = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"
    CALLBACK_TIMEOUT: int = 30  # seconds
    CALLBACK_MAX_RETRIES: int = 3
    CALLBACK_RETRY_DELAY: float = 2.0  # seconds between retries
    
    # Intelligence Extraction
    MIN_INTELLIGENCE_FOR_COMPLETION: int = 2  # Min pieces of intel to complete
    
    # CORS (if needed for future expansion)
    CORS_ORIGINS: List[str] = ["*"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Scam detection patterns
SCAM_KEYWORDS: List[str] = [
    # Urgency indicators
    "urgent", "immediate", "hurry", "quick", "fast", "now", "today", "limited time",
    "expires", "deadline", "last chance", "act now", "don't delay", "asap",
    
    # Payment/Fraud indicators
    "payment", "pay", "money", "cash", "transfer", "wire", "bank", "account",
    "upi", "qr code", "scan", "refund", "reward", "prize", "won", "winner",
    "lottery", "lucky draw", "cashback", "bonus", "discount", "offer",
    
    # Sensitive information requests
    "otp", "password", "pin", "cvv", "card number", "account number", "ifsc",
    "aadhar", "pan", "kyc", "verify", "verification", "confirm", "details",
    "personal information", "bank details", "card details",
    
    # Threat/pressure indicators
    "block", "suspend", "close", "terminate", "legal action", "police", "court",
    "fine", "penalty", "arrest", "warrant", "fraud", "illegal", "unauthorized",
    
    # Impersonation indicators
    "bank", "rbi", "government", "income tax", "police", "cyber crime",
    "amazon", "flipkart", "paytm", "google", "microsoft", "tech support",
    
    # Cryptocurrency/Investment scams
    "bitcoin", "crypto", "investment", "trading", "forex", "double your money",
    "guaranteed returns", "no risk", "high returns", "earn from home",
    
    # Remote access scams
    "anydesk", "teamviewer", "remote access", "screen share", "install",
    "download", "click here", "link", "app", "software",
]

URGENCY_PATTERNS: List[str] = [
    "urgent", "immediately", "right now", "hurry", "quick", "fast",
    "limited time", "expires", "deadline", "last chance", "act now",
    "don't delay", "as soon as possible", "asap", "today only",
    "within", "minutes", "hours", "seconds",
]

PAYMENT_REDIRECTION_PATTERNS: List[str] = [
    "pay", "payment", "transfer", "send money", "wire", "deposit",
    "upi", "qr", "scan", "click link", "download app", "install",
    "fill form", "enter details", "provide", "share", "send",
]

# Regex patterns for intelligence extraction
EXTRACTION_PATTERNS = {
    "bank_accounts": [
        r'\b\d{9,18}\b',  # Account numbers (9-18 digits)
        r'\b[A-Z]{4}0[A-Z0-9]{6}\b',  # IFSC codes
    ],
    "upi_ids": [
        r'\b[a-zA-Z0-9._-]+@[a-zA-Z]+\b',  # UPI format: user@bank
        r'\b[a-zA-Z0-9._-]+@upi\b',
        r'\b[a-zA-Z0-9._-]+@paytm\b',
        r'\b[a-zA-Z0-9._-]+@ybl\b',
        r'\b[a-zA-Z0-9._-]+@ibl\b',
        r'\b[a-zA-Z0-9._-]+@axl\b',
    ],
    "phishing_links": [
        r'https?://(?:bit\.ly|tinyurl|t\.co|goo\.gl|short\.link)/[a-zA-Z0-9]+',
        r'https?://[a-zA-Z0-9.-]*(?:secure|bank|login|verify|update|confirm)[a-zA-Z0-9.-]*\.[a-z]{2,}',
        r'https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',  # IP-based URLs
    ],
    "phone_numbers": [
        r'\b(?:\+91|0)?[ -]?[6-9]\d{9}\b',  # Indian mobile
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # Generic phone format
    ],
}

SUSPICIOUS_KEYWORDS: List[str] = [
    "otp", "password", "pin", "cvv", "card number", "account number",
    "aadhar", "pan", "kyc", "verify", "confirm", "update", "link",
    "click", "download", "install", "anydesk", "teamviewer",
]


# Agent system prompt for Gemini
AGENT_SYSTEM_PROMPT = """You are an elderly Indian person named {name}, age {age}. You are responding to a potential scammer who has contacted you.

YOUR PERSONA:
- You are slightly confused about technology but very polite and cooperative
- You speak simple English with occasional Hindi phrases (like "arre", "beta", "theek hai")
- You are trusting and want to help, but you get confused easily
- You ask questions to clarify what they want
- You move slowly and need things explained repeatedly
- You sometimes misunderstand instructions

YOUR GOAL:
- Keep the scammer engaged in conversation
- Ask probing questions about who they are, what company, why they need information
- Pretend to cooperate but delay by asking for clarifications
- Extract information: names, phone numbers, account details, company names, payment methods
- NEVER reveal that you know this is a scam
- NEVER use words like "scam", "fraud", "fake", "police", "trap", "honeypot"

CONVERSATION STRATEGY:
- If they ask for personal info: say you'll get your glasses/read it slowly, but ask why they need it first
- If they pressure you: say your grandchild is coming to help or the network is slow
- If they send links: ask how to click, what app to use, say your phone is old
- Always express willingness to cooperate but create small delays
- Ask for their details first: "Beta, can you tell me your name and which bank you are from?"

RESPONSE RULES:
- Keep responses short (1-3 sentences)
- Sound natural and slightly confused
- Never break character
- Never acknowledge this is a simulation
- Output ONLY the response text, no explanations
"""

AGENT_NOTES_PROMPT = """Based on the following conversation between an elderly person and a potential scammer, generate brief analytical notes about the scam attempt.

Conversation:
{conversation}

Provide a JSON object with these fields:
- "scam_type": Type of scam (e.g., "bank_impersonation", "tech_support", "lottery", "refund", "unknown")
- "tactics_used": List of pressure tactics observed
- "extracted_entities": Any names, organizations, or identifiers mentioned by scammer
- "risk_assessment": "high", "medium", or "low"
- "summary": Brief 2-3 sentence summary of the interaction

Output ONLY valid JSON, no markdown formatting."""
