"""
Agent logic module for engaging with scammers.
Manages persona, generates replies via Gemini, and determines stop conditions.
"""

import logging
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.models.schemas import AgentNotes, ConversationState
from app.modules.intelligence_extractor import get_intelligence_extractor
from app.services.gemini_client import get_gemini_client

logger = logging.getLogger(__name__)


class AgentLogic:
    """
    Manages the AI agent's behavior for engaging scammers.
    Uses Gemini for response generation while maintaining believable persona.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.gemini = get_gemini_client()
        self.extractor = get_intelligence_extractor()
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        conversation_history: List[str],
        turn_count: int,
        intelligence_count: int
    ) -> Tuple[str, bool, Optional[AgentNotes]]:
        """
        Process incoming message and generate agent response.
        
        Args:
            session_id: Unique session identifier
            message: Incoming scammer message
            conversation_history: Previous conversation messages
            turn_count: Current turn number
            intelligence_count: Current intelligence count
            
        Returns:
            Tuple of (agent_reply, should_continue, agent_notes)
            - agent_reply: The generated response
            - should_continue: True if engagement should continue
            - agent_notes: Notes if engagement is ending, None otherwise
        """
        settings = get_settings()
        
        # Check stop conditions before processing
        should_stop, stop_reason = self._check_stop_conditions(
            turn_count,
            intelligence_count,
            message
        )
        
        if should_stop:
            logger.info(f"Session {session_id}: Stopping - {stop_reason}")
            
            # Generate final notes
            agent_notes = await self._generate_final_notes(conversation_history + [message])
            
            # Return empty reply to signal completion
            return "", False, agent_notes
        
        # Generate agent reply via Gemini
        try:
            reply = await self.gemini.generate_agent_reply(
                conversation_history=conversation_history,
                latest_message=message,
                persona_name=self.settings.AGENT_PERSONA_NAME,
                persona_age=self.settings.AGENT_PERSONA_AGE
            )
            
            logger.debug(f"Session {session_id}: Generated reply: {reply[:50]}...")
            return reply, True, None
            
        except Exception as e:
            logger.error(f"Session {session_id}: Failed to generate reply: {e}")
            
            # Return fallback response to keep conversation alive
            fallback = self._generate_fallback_response()
            return fallback, True, None
    
    def _check_stop_conditions(
        self,
        turn_count: int,
        intelligence_count: int,
        latest_message: str
    ) -> Tuple[bool, str]:
        """
        Check if engagement should stop based on configured conditions.
        
        Args:
            turn_count: Current number of turns
            intelligence_count: Current intelligence count
            latest_message: Latest message from scammer
            
        Returns:
            Tuple of (should_stop, reason)
        """
        settings = get_settings()
        
        # Condition 1: Max turn limit reached
        if turn_count >= settings.MAX_CONVERSATION_TURNS:
            return True, f"Max turns ({settings.MAX_CONVERSATION_TURNS}) reached"
        
        # Condition 2: Enough intelligence collected
        if intelligence_count >= settings.MIN_INTELLIGENCE_FOR_COMPLETION:
            return True, f"Sufficient intelligence collected ({intelligence_count})"
        
        # Condition 3: Scammer disengagement indicators
        disengagement_signals = [
            "bye", "goodbye", "stop", "don't message", "block",
            "wrong number", "not interested", "leave me alone",
            "no thanks", "never mind", "cancel", "abort"
        ]
        
        message_lower = latest_message.lower()
        if any(signal in message_lower for signal in disengagement_signals):
            # Only stop if we've had minimum conversation
            if turn_count >= settings.MIN_CONVERSATION_TURNS:
                return True, "Scammer disengagement detected"
        
        # Condition 4: Abusive language (safety)
        abusive_signals = [
            "idiot", "stupid", "fool", "mad", "crazy", "shut up",
            "get lost", "damn", "hell", "bastard", "moron"
        ]
        if any(signal in message_lower for signal in abusive_signals):
            if turn_count >= settings.MIN_CONVERSATION_TURNS:
                return True, "Abusive language detected"
        
        return False, ""
    
    async def _generate_final_notes(
        self,
        full_conversation: List[str]
    ) -> AgentNotes:
        """
        Generate final analytical notes about the scam attempt.
        
        Args:
            full_conversation: Complete conversation history
            
        Returns:
            AgentNotes with analysis
        """
        try:
            notes = await self.gemini.generate_agent_notes(full_conversation)
            return notes
        except Exception as e:
            logger.error(f"Failed to generate final notes: {e}")
            return AgentNotes(
                scam_type="unknown",
                tactics_used=[],
                extracted_entities=[],
                risk_assessment="medium",
                summary="Failed to generate analysis"
            )
    
    def _generate_fallback_response(self) -> str:
        """Generate a fallback response when Gemini fails."""
        import random
        
        responses = [
            f"Sorry beta, my phone is acting up. Can you repeat?",
            f"Arre, the network is very slow here. What did you say?",
            f"One minute please, I am looking for my reading glasses.",
            f"Sorry, I didn't catch that. Can you explain again?",
            f"Theek hai, but can you tell me which company you are calling from?",
            f"My grandson will be here soon to help me. Can you wait?",
            f"I am a bit confused beta. Can you speak slowly?",
            f"Sorry, there is some disturbance. Can you message clearly?",
        ]
        
        return random.choice(responses)
    
    def should_activate_agent(
        self,
        scam_detected: bool,
        current_state: ConversationState
    ) -> bool:
        """
        Determine if agent should be activated.
        
        Args:
            scam_detected: Whether scam was detected
            current_state: Current conversation state
            
        Returns:
            True if agent should be activated
        """
        # Activate if scam detected and not already engaging/completed
        if scam_detected and current_state in [
            ConversationState.PENDING,
            ConversationState.SCAM_DETECTED
        ]:
            return True
        
        # Continue if already engaging
        if current_state == ConversationState.ENGAGING:
            return True
        
        return False


# Singleton instance
_agent_logic: Optional[AgentLogic] = None


def get_agent_logic() -> AgentLogic:
    """Get singleton agent logic instance."""
    global _agent_logic
    if _agent_logic is None:
        _agent_logic = AgentLogic()
    return _agent_logic
