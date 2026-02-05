"""
Callback sender module for sending final results to the platform.
Implements retry logic with exponential backoff and timeout protection.
"""

import asyncio
import json
import logging
from typing import Dict, Optional, Tuple

import httpx

from app.core.config import get_settings
from app.models.schemas import AgentNotes, CallbackPayload, ExtractedIntelligence

logger = logging.getLogger(__name__)


class CallbackSender:
    """
    Sends callback requests to the platform with retry logic.
    Implements timeout protection and exponential backoff.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.callback_url = self.settings.CALLBACK_URL
        self.timeout = self.settings.CALLBACK_TIMEOUT
        self.max_retries = self.settings.CALLBACK_MAX_RETRIES
        self.retry_delay = self.settings.CALLBACK_RETRY_DELAY
    
    async def send_callback(
        self,
        session_id: str,
        scam_detected: bool,
        total_messages_exchanged: int,
        extracted_intelligence: ExtractedIntelligence,
        agent_notes: AgentNotes
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Send final result callback to platform with retries.
        
        Args:
            session_id: Session identifier
            scam_detected: Whether scam was detected
            total_messages_exchanged: Total message count
            extracted_intelligence: Extracted intelligence data
            agent_notes: Agent-generated notes
            
        Returns:
            Tuple of (success, response_data)
        """
        # Build payload
        # Note: DETAILS.txt requires agentNotes to be a string
        # We use the summary from our structured notes
        notes_str = agent_notes.summary if agent_notes else ""
        
        payload = CallbackPayload(
            sessionId=session_id,
            scamDetected=scam_detected,
            totalMessagesExchanged=total_messages_exchanged,
            extractedIntelligence=extracted_intelligence,
            agentNotes=notes_str
        )
        
        # Convert to dict for JSON serialization
        payload_dict = self._payload_to_dict(payload)
        
        logger.info(f"Session {session_id}: Sending callback to {self.callback_url}")
        logger.debug(f"Callback payload: {json.dumps(payload_dict, indent=2)}")
        
        # Attempt with retries
        for attempt in range(1, self.max_retries + 1):
            try:
                success, response_data = await self._send_single_request(
                    payload_dict
                )
                
                if success:
                    logger.info(
                        f"Session {session_id}: Callback successful on attempt {attempt}"
                    )
                    return True, response_data
                
                # If not successful and not last attempt, retry
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(
                        f"Session {session_id}: Callback attempt {attempt} failed, "
                        f"retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                
            except Exception as e:
                logger.error(
                    f"Session {session_id}: Callback attempt {attempt} error: {e}"
                )
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
        
        logger.error(
            f"Session {session_id}: All {self.max_retries} callback attempts failed"
        )
        return False, None
    
    async def _send_single_request(
        self,
        payload: Dict
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Send a single callback request.
        
        Args:
            payload: Callback payload as dictionary
            
        Returns:
            Tuple of (success, response_data)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.callback_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "HoneyPot-Agent/1.0"
                    }
                )
                
                # Check response status
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        return True, response_data
                    except json.JSONDecodeError:
                        # Non-JSON 200 response is still success
                        return True, {"status": "success", "raw": response.text}
                
                elif response.status_code in [201, 202]:
                    # Accepted/Created
                    return True, {"status": "accepted", "code": response.status_code}
                
                else:
                    # Error response
                    logger.warning(
                        f"Callback returned status {response.status_code}: {response.text}"
                    )
                    return False, {
                        "error": f"HTTP {response.status_code}",
                        "body": response.text
                    }
                    
        except httpx.TimeoutException:
            logger.error(f"Callback request timed out after {self.timeout}s")
            return False, {"error": "timeout"}
        
        except httpx.ConnectError as e:
            logger.error(f"Callback connection error: {e}")
            return False, {"error": "connection_failed"}
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Callback HTTP error: {e}")
            return False, {"error": f"http_error", "details": str(e)}
        
        except Exception as e:
            logger.error(f"Callback unexpected error: {e}")
            return False, {"error": "unexpected", "details": str(e)}
    
    def _payload_to_dict(self, payload: CallbackPayload) -> Dict:
        """
        Convert CallbackPayload to dictionary for JSON serialization.
        
        Args:
            payload: CallbackPayload instance
            
        Returns:
            Dictionary representation
        """
        return {
            "sessionId": payload.sessionId,
            "scamDetected": payload.scamDetected,
            "totalMessagesExchanged": payload.totalMessagesExchanged,
            "extractedIntelligence": {
                "bankAccounts": payload.extractedIntelligence.bankAccounts,
                "upiIds": payload.extractedIntelligence.upiIds,
                "phishingLinks": payload.extractedIntelligence.phishingLinks,
                "phoneNumbers": payload.extractedIntelligence.phoneNumbers,
                "suspiciousKeywords": payload.extractedIntelligence.suspiciousKeywords,
            },
            "agentNotes": payload.agentNotes # Now a string
        }
    
    async def send_callback_with_fallback(
        self,
        session_id: str,
        scam_detected: bool,
        total_messages_exchanged: int,
        extracted_intelligence: ExtractedIntelligence,
        agent_notes: AgentNotes
    ) -> bool:
        """
        Send callback with fallback to local logging if all retries fail.
        
        Args:
            session_id: Session identifier
            scam_detected: Whether scam was detected
            total_messages_exchanged: Total message count
            extracted_intelligence: Extracted intelligence data
            agent_notes: Agent-generated notes
            
        Returns:
            True if callback was sent or logged locally
        """
        success, _ = await self.send_callback(
            session_id=session_id,
            scam_detected=scam_detected,
            total_messages_exchanged=total_messages_exchanged,
            extracted_intelligence=extracted_intelligence,
            agent_notes=agent_notes
        )
        
        if success:
            return True
        
        # Fallback: Log to local file for manual recovery
        await self._log_fallback(
            session_id,
            scam_detected,
            total_messages_exchanged,
            extracted_intelligence,
            agent_notes
        )
        
        return False
    
    async def _log_fallback(
        self,
        session_id: str,
        scam_detected: bool,
        total_messages_exchanged: int,
        extracted_intelligence: ExtractedIntelligence,
        agent_notes: AgentNotes
    ):
        """Log callback data locally for recovery."""
        import os
        from datetime import datetime
        
        fallback_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "callback_url": self.callback_url,
            "sessionId": session_id,
            "scamDetected": scam_detected,
            "totalMessagesExchanged": total_messages_exchanged,
            "extractedIntelligence": {
                "bankAccounts": extracted_intelligence.bankAccounts,
                "upiIds": extracted_intelligence.upiIds,
                "phishingLinks": extracted_intelligence.phishingLinks,
                "phoneNumbers": extracted_intelligence.phoneNumbers,
                "suspiciousKeywords": extracted_intelligence.suspiciousKeywords,
            },
            "agentNotes": {
                "scam_type": agent_notes.scam_type,
                "tactics_used": agent_notes.tactics_used,
                "extracted_entities": agent_notes.extracted_entities,
                "risk_assessment": agent_notes.risk_assessment,
                "summary": agent_notes.summary,
            },
            "status": "FAILED_CALLBACK_LOGGED_LOCALLY"
        }
        
        # Ensure logs directory exists
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        # Write to fallback log file
        log_file = os.path.join(log_dir, "failed_callbacks.jsonl")
        
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(fallback_data) + "\n")
            logger.warning(
                f"Session {session_id}: Callback logged to {log_file} for recovery"
            )
        except Exception as e:
            logger.error(
                f"Session {session_id}: Failed to log fallback: {e}"
            )


# Singleton instance
_sender: Optional[CallbackSender] = None


def get_callback_sender() -> CallbackSender:
    """Get singleton callback sender instance."""
    global _sender
    if _sender is None:
        _sender = CallbackSender()
    return _sender
