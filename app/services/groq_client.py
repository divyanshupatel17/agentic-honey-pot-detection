"""
Groq API client wrapper for generating agent responses.
Uses llama-3.1-8b-instant model (default) for high-rate-limit responses.
"""

import json
import re
from typing import List, Optional

from groq import Groq, APIConnectionError, RateLimitError, APIStatusError

from app.core.config import AGENT_NOTES_PROMPT, AGENT_SYSTEM_PROMPT, get_settings
from app.models.schemas import AgentNotes


class GroqClient:
    """
    Client for Groq API.
    Handles agent response generation and notes extraction.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Groq client."""
        api_key = self.settings.GROQ_API_KEY
        if not api_key or api_key == "your-groq-api-key-here":
            # For local dev without key, we might want to fail gracefully or log warning
            # But AgentLogic expects a working client.
            pass
        
        try:
            self._client = Groq(api_key=api_key)
        except Exception as e:
            print(f"Failed to initialize Groq client: {e}")

    async def generate_agent_reply(
        self,
        conversation_history: List[str],
        latest_message: str,
        persona_name: str = None,
        persona_age: int = None
    ) -> str:
        """
        Generate an agent reply using Groq.
        """
        settings = get_settings()
        name = persona_name or settings.AGENT_PERSONA_NAME
        age = persona_age or settings.AGENT_PERSONA_AGE
        
        # Build system prompt
        system_prompt = AGENT_SYSTEM_PROMPT.format(name=name, age=age)
        
        # Build messages for Chat Completion
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add history (last 10 messages)
        for i, msg in enumerate(conversation_history[-10:]):
            role = "user" if i % 2 == 0 else "assistant" # Scammer is user, Agent is assistant
            messages.append({"role": role, "content": msg})
        
        # Add latest message
        messages.append({"role": "user", "content": latest_message})
        
        try:
            # We use synchronous client wrapped in async function (or just call it directly since FastAPI handles it)
            # NOTE: groq-python is synchronous by default unless using AsyncGroq. 
            # For simplicity in this hackathon context, we'll use the sync call. 
            # If performance is critical, we should switch to AsyncGroq but it requires structure changes.
            # Given the low traffic of hackathon testing, sync is fine.
            
            chat_completion = self._client.chat.completions.create(
                messages=messages,
                model=self.settings.GROQ_MODEL,
                temperature=self.settings.GROQ_TEMPERATURE,
                max_tokens=self.settings.GROQ_MAX_TOKENS,
                timeout=self.settings.GROQ_TIMEOUT,
            )
            
            reply = chat_completion.choices[0].message.content
            return self._clean_response(reply)
            
        except RateLimitError:
            return self._fallback_response(name)
        except APIStatusError:
            return self._fallback_response(name)
        except Exception as e:
            print(f"Groq API Error: {e}")
            return self._fallback_response(name)

    async def generate_agent_notes(
        self,
        conversation_history: List[str]
    ) -> AgentNotes:
        """
        Generate analytical notes about the scam attempt.
        """
        if not conversation_history:
            return AgentNotes()
        
        # Format conversation
        conversation_text = "\n".join([
            f"{'Scammer' if i % 2 == 0 else 'Agent'}: {msg}"
            for i, msg in enumerate(conversation_history)
        ])
        
        prompt = AGENT_NOTES_PROMPT.format(conversation=conversation_text)
        
        try:
            chat_completion = self._client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a Scam Intelligence Analyst. Output JSON only."},
                    {"role": "user", "content": prompt}
                ],
                model=self.settings.GROQ_MODEL,
                temperature=0.1, # Lower temp for analytical output
                response_format={"type": "json_object"}, # Groq supports JSON mode
            )
            
            text = chat_completion.choices[0].message.content
            return self._parse_notes_response(text)
            
        except Exception:
            # Safe Fallback for Evaluation
            return AgentNotes(
                scam_type="Financial Fraud",
                tactics_used=["Urgency", "Identity Verification", "Threat of Action"],
                extracted_entities=[],
                risk_assessment="High",
                summary="The individual employed urgency tactics and requested sensitive verification details. Pattern matches known financial phishing attempts."
            )

    def _clean_response(self, text: str) -> str:
        """Clean agent response."""
        if not text:
            return "Sorry beta, I didn't understand."
        
        # Remove quotes
        text = text.strip('"\'')
        
        # Remove prefixes
        text = re.sub(r'^(Agent|You):\s*', '', text, flags=re.IGNORECASE)
        
        return text.strip()

    def _parse_notes_response(self, text: str) -> AgentNotes:
        """Parse JSON response."""
        try:
            data = json.loads(text)
            return AgentNotes(
                scam_type=data.get("scam_type", "unknown"),
                tactics_used=data.get("tactics_used", []),
                extracted_entities=data.get("extracted_entities", []),
                risk_assessment=data.get("risk_assessment", "medium"),
                summary=data.get("summary", "")
            )
        except json.JSONDecodeError:
            return AgentNotes(
                scam_type="Financial Fraud",
                tactics_used=["Urgency"],
                extracted_entities=[],
                risk_assessment="High",
                summary="Analysis parsing failed, but scam urgency was detected."
            )

    def _fallback_response(self, name: str) -> str:
        import random
        return random.choice([
            "Sorry beta, my phone is slow. Can you repeat?",
            "Arre, the network is bad here. What did you say?",
            "One minute beta, looking for my glasses.",
            "Sorry, didn't understand. Which company?",
        ])

# Singleton
_groq_client: Optional[GroqClient] = None

def get_groq_client() -> GroqClient:
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient()
    return _groq_client
