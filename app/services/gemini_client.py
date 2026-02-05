"""
Gemini API client wrapper for generating agent responses.
Uses gemini-1.5-flash model for low-latency responses.
"""

import json
import re
from typing import Dict, List, Optional

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError, ResourceExhausted, ServiceUnavailable

from app.core.config import AGENT_NOTES_PROMPT, AGENT_SYSTEM_PROMPT, get_settings
from app.models.schemas import AgentNotes


class GeminiClient:
    """
    Client for Google Gemini API.
    Handles agent response generation and notes extraction.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._configure_client()
        self.model = None
        self._initialize_model()
    
    def _configure_client(self):
        """Configure the Gemini client with API key."""
        api_key = self.settings.GEMINI_API_KEY
        if not api_key or api_key == "your-gemini-api-key-here":
            raise ValueError(
                "GEMINI_API_KEY not configured. "
                "Please set a valid Gemini API key in environment variables."
            )
        genai.configure(api_key=api_key)
    
    def _initialize_model(self):
        """Initialize the Gemini model with configuration."""
        generation_config = {
            "temperature": self.settings.GEMINI_TEMPERATURE,
            "max_output_tokens": self.settings.GEMINI_MAX_TOKENS,
            "top_p": 0.95,
            "top_k": 40,
        }
        
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
        ]
        
        self.model = genai.GenerativeModel(
            model_name=self.settings.GEMINI_MODEL,
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
    
    async def generate_agent_reply(
        self,
        conversation_history: List[str],
        latest_message: str,
        persona_name: str = None,
        persona_age: int = None
    ) -> str:
        """
        Generate an agent reply using Gemini.
        
        Args:
            conversation_history: Previous messages in the conversation
            latest_message: The most recent message from scammer
            persona_name: Agent persona name (default from config)
            persona_age: Agent persona age (default from config)
            
        Returns:
            Generated reply text
        """
        settings = get_settings()
        name = persona_name or settings.AGENT_PERSONA_NAME
        age = persona_age or settings.AGENT_PERSONA_AGE
        
        # Build system prompt
        system_prompt = AGENT_SYSTEM_PROMPT.format(name=name, age=age)
        
        # Build conversation context
        conversation_text = self._format_conversation(conversation_history, latest_message)
        
        # Build full prompt
        full_prompt = f"""{system_prompt}

CONVERSATION HISTORY:
{conversation_text}

Generate your next response as {name}. Remember:
- Stay in character as a confused but cooperative elderly person
- Keep response short (1-3 sentences)
- Ask probing questions to extract scammer information
- Never reveal you know this is a scam
- Output ONLY your response, nothing else

Your response:"""
        
        try:
            response = await self.model.generate_content_async(
                full_prompt,
                request_options={"timeout": self.settings.GEMINI_TIMEOUT}
            )
            
            # Extract and clean response
            reply = self._extract_text(response)
            return self._clean_response(reply)
            
        except ResourceExhausted:
            # Rate limit - return fallback
            return self._fallback_response(name)
        except ServiceUnavailable:
            # Service down - return fallback
            return self._fallback_response(name)
        except GoogleAPIError as e:
            # Other Gemini errors
            return self._fallback_response(name)
        except Exception as e:
            # Unexpected errors
            return self._fallback_response(name)
    
    async def generate_agent_notes(
        self,
        conversation_history: List[str]
    ) -> AgentNotes:
        """
        Generate analytical notes about the scam attempt.
        
        Args:
            conversation_history: Full conversation history
            
        Returns:
            AgentNotes with analysis
        """
        if not conversation_history:
            return AgentNotes()
        
        # Format conversation for analysis
        conversation_text = "\n".join([
            f"{'Scammer' if i % 2 == 0 else 'Agent'}: {msg}"
            for i, msg in enumerate(conversation_history)
        ])
        
        prompt = AGENT_NOTES_PROMPT.format(conversation=conversation_text)
        
        try:
            response = await self.model.generate_content_async(
                prompt,
                request_options={"timeout": self.settings.GEMINI_TIMEOUT}
            )
            
            text = self._extract_text(response)
            return self._parse_notes_response(text)
            
        except Exception as e:
            # Return default notes on error
            return AgentNotes(
                scam_type="unknown",
                tactics_used=[],
                extracted_entities=[],
                risk_assessment="medium",
                summary="Failed to generate notes due to API error"
            )
    
    def _format_conversation(
        self,
        conversation_history: List[str],
        latest_message: str
    ) -> str:
        """Format conversation history for prompt."""
        lines = []
        
        # Add history (last 10 messages for context)
        for i, msg in enumerate(conversation_history[-10:]):
            speaker = "Scammer" if i % 2 == 0 else "You"
            lines.append(f"{speaker}: {msg}")
        
        # Add latest message
        lines.append(f"Scammer: {latest_message}")
        
        return "\n".join(lines)
    
    def _extract_text(self, response) -> str:
        """Safely extract text from Gemini response."""
        try:
            if hasattr(response, 'text'):
                return response.text
            elif hasattr(response, 'parts') and response.parts:
                return "".join(part.text for part in response.parts if hasattr(part, 'text'))
            else:
                return str(response)
        except Exception:
            return ""
    
    def _clean_response(self, text: str) -> str:
        """Clean and sanitize agent response."""
        if not text:
            return "Sorry beta, I didn't understand. Can you repeat?"
        
        # Remove any markdown formatting
        text = re.sub(r'\*\*|__|\*|_|`', '', text)
        
        # Remove any JSON-like structures
        text = re.sub(r'\{[^}]*\}', '', text)
        
        # Remove quotes if the whole response is quoted
        text = text.strip('"\'')
        
        # Remove "Agent:" or "You:" prefixes if present
        text = re.sub(r'^(Agent|You):\s*', '', text, flags=re.IGNORECASE)
        
        # Limit length
        if len(text) > 500:
            text = text[:497] + "..."
        
        # Ensure response is not empty
        if not text.strip():
            return "Sorry, my phone is acting up. Can you say that again?"
        
        return text.strip()
    
    def _parse_notes_response(self, text: str) -> AgentNotes:
        """Parse JSON response for agent notes."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^}]*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group()
            
            data = json.loads(text)
            
            return AgentNotes(
                scam_type=data.get("scam_type", "unknown"),
                tactics_used=data.get("tactics_used", []),
                extracted_entities=data.get("extracted_entities", []),
                risk_assessment=data.get("risk_assessment", "medium"),
                summary=data.get("summary", "")
            )
        except json.JSONDecodeError:
            # Return default if parsing fails
            return AgentNotes(
                scam_type="unknown",
                tactics_used=[],
                extracted_entities=[],
                risk_assessment="medium",
                summary=text[:200] if text else "Analysis failed"
            )
        except Exception:
            return AgentNotes()
    
    def _fallback_response(self, name: str) -> str:
        """Generate fallback response when Gemini fails."""
        import random
        fallbacks = [
            f"Sorry beta, my phone is slow. Can you repeat what you said?",
            f"Arre, the network is bad here. What did you say about the payment?",
            f"One minute beta, I am looking for my glasses. Can you explain again?",
            f"Sorry, I didn't understand. Which company did you say you are from?",
            f"Theek hai, but can you tell me your name first? I want to write it down.",
            f"My grandson is coming to help me soon. Can you wait a few minutes?",
            f"I am a bit confused. Can you explain slowly what I need to do?",
        ]
        return random.choice(fallbacks)


# Singleton instance
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get singleton Gemini client instance."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
