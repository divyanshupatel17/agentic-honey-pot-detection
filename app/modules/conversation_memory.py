"""
Conversation memory and state management module.
Tracks sessions, states, and message history in memory.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.core.config import get_settings
from app.models.schemas import (
    AgentNotes,
    ConversationSession,
    ConversationState,
    ExtractedIntelligence,
)
from app.modules.intelligence_extractor import get_intelligence_extractor

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Manages conversation sessions and their states.
    In-memory storage with periodic cleanup.
    """
    
    def __init__(self):
        self.sessions: Dict[str, ConversationSession] = {}
        self.lock = asyncio.Lock()
        self.settings = get_settings()
        self.extractor = get_intelligence_extractor()
        
        # Start cleanup task
        self._cleanup_interval = 300  # 5 minutes
        self._max_session_age = 3600  # 1 hour
    
    async def get_or_create_session(
        self,
        session_id: str
    ) -> ConversationSession:
        """
        Get existing session or create new one.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            ConversationSession (existing or new)
        """
        async with self.lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.updated_at = datetime.utcnow()
                return session
            
            # Create new session
            new_session = ConversationSession(session_id=session_id)
            self.sessions[session_id] = new_session
            logger.info(f"Created new session: {session_id}")
            return new_session
    
    async def get_session(
        self,
        session_id: str
    ) -> Optional[ConversationSession]:
        """
        Get existing session if it exists.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ConversationSession or None
        """
        async with self.lock:
            return self.sessions.get(session_id)
    
    async def add_message(
        self,
        session_id: str,
        role: str,  # "scammer" or "agent"
        message: str,
        scam_detected: bool = False
    ) -> ConversationSession:
        """
        Add a message to the session and update state.
        
        Args:
            session_id: Session identifier
            role: Message sender role ("scammer" or "agent")
            message: Message content
            scam_detected: Whether scam was detected in this message
            
        Returns:
            Updated ConversationSession
        """
        async with self.lock:
            session = await self._get_or_create_locked(session_id)
            
            # Add message to history
            message_entry = {
                "role": role,
                "content": message,
                "timestamp": datetime.utcnow().isoformat(),
            }
            session.messages.append(message_entry)
            
            # Update counters
            session.total_messages_exchanged += 1
            session.turn_count = len(session.messages) // 2
            session.last_message_at = datetime.utcnow()
            
            # Update scam detection flag
            if scam_detected:
                session.scam_detected = True
                if session.state == ConversationState.PENDING:
                    session.state = ConversationState.SCAM_DETECTED
            
            # Update state based on current status
            await self._update_state_locked(session)
            
            # Extract intelligence from message
            await self._extract_intelligence_locked(session, message)
            
            session.updated_at = datetime.utcnow()
            return session
    
    async def update_state(
        self,
        session_id: str,
        new_state: ConversationState
    ) -> Optional[ConversationSession]:
        """
        Update session state.
        
        Args:
            session_id: Session identifier
            new_state: New state to set
            
        Returns:
            Updated session or None if not found
        """
        async with self.lock:
            if session_id not in self.sessions:
                return None
            
            session = self.sessions[session_id]
            old_state = session.state
            session.state = new_state
            session.updated_at = datetime.utcnow()
            
            logger.info(
                f"Session {session_id}: State changed {old_state} -> {new_state}"
            )
            return session
    
    async def complete_session(
        self,
        session_id: str,
        agent_notes: AgentNotes
    ) -> Optional[ConversationSession]:
        """
        Mark session as completed with agent notes.
        
        Args:
            session_id: Session identifier
            agent_notes: Final agent notes
            
        Returns:
            Completed session or None
        """
        async with self.lock:
            if session_id not in self.sessions:
                return None
            
            session = self.sessions[session_id]
            session.state = ConversationState.COMPLETED
            session.agent_notes = agent_notes
            session.updated_at = datetime.utcnow()
            
            logger.info(f"Session {session_id}: Marked as COMPLETED")
            return session
    
    async def mark_callback_sent(
        self,
        session_id: str
    ) -> Optional[ConversationSession]:
        """
        Mark session as callback sent.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Updated session or None
        """
        async with self.lock:
            if session_id not in self.sessions:
                return None
            
            session = self.sessions[session_id]
            session.state = ConversationState.CALLBACK_SENT
            session.updated_at = datetime.utcnow()
            
            logger.info(f"Session {session_id}: Callback marked as SENT")
            return session
    
    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = None
    ) -> List[str]:
        """
        Get conversation history as list of message strings.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return
            
        Returns:
            List of message strings
        """
        async with self.lock:
            if session_id not in self.sessions:
                return []
            
            session = self.sessions[session_id]
            messages = [m["content"] for m in session.messages]
            
            if limit:
                messages = messages[-limit:]
            
            return messages
    
    async def get_stats(self, session_id: str) -> Dict:
        """
        Get session statistics.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session stats
        """
        async with self.lock:
            if session_id not in self.sessions:
                return {}
            
            session = self.sessions[session_id]
            return {
                "session_id": session_id,
                "state": session.state.value,
                "total_messages": session.total_messages_exchanged,
                "turn_count": session.turn_count,
                "scam_detected": session.scam_detected,
                "intelligence_count": session.intelligence_count,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
            }
    
    async def _get_or_create_locked(
        self,
        session_id: str
    ) -> ConversationSession:
        """Get or create session (assumes lock is held)."""
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        new_session = ConversationSession(session_id=session_id)
        self.sessions[session_id] = new_session
        logger.info(f"Created new session: {session_id}")
        return new_session
    
    async def _update_state_locked(self, session: ConversationSession):
        """Update session state based on current status (assumes lock is held)."""
        # If scam detected and we're in SCAM_DETECTED, move to ENGAGING
        if session.state == ConversationState.SCAM_DETECTED:
            session.state = ConversationState.ENGAGING
            logger.info(f"Session {session.session_id}: State -> ENGAGING")
    
    async def _extract_intelligence_locked(
        self,
        session: ConversationSession,
        message: str
    ):
        """Extract intelligence from message (assumes lock is held)."""
        # Extract new intelligence
        new_intelligence = self.extractor.extract(
            message,
            session.extracted_intelligence
        )
        
        # Update session
        session.extracted_intelligence = new_intelligence
        session.intelligence_count = self.extractor.count_intelligence(
            new_intelligence
        )
    
    async def cleanup_old_sessions(self):
        """Remove old sessions to prevent memory leaks."""
        async with self.lock:
            now = datetime.utcnow()
            max_age = timedelta(seconds=self._max_session_age)
            
            to_remove = []
            for session_id, session in self.sessions.items():
                # Don't remove active engaging sessions
                if session.state == ConversationState.ENGAGING:
                    continue
                
                # Remove old completed/pending sessions
                if now - session.updated_at > max_age:
                    to_remove.append(session_id)
            
            for session_id in to_remove:
                del self.sessions[session_id]
                logger.info(f"Cleaned up old session: {session_id}")
    
    async def get_all_sessions(self) -> List[ConversationSession]:
        """Get all active sessions (for monitoring)."""
        async with self.lock:
            return list(self.sessions.values())


# Singleton instance
_memory: Optional[ConversationMemory] = None


def get_conversation_memory() -> ConversationMemory:
    """Get singleton conversation memory instance."""
    global _memory
    if _memory is None:
        _memory = ConversationMemory()
    return _memory
