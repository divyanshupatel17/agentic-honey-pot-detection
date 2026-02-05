"""
Main FastAPI application for Honey-Pot Scam Detection API.
Provides webhook endpoint and health checks.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.auth import verify_api_key
from app.core.config import get_settings
from app.models.schemas import (
    ConversationState,
    HealthResponse,
    WebhookRequest,
    WebhookResponse,
)
from app.modules.agent import get_agent_logic
from app.modules.conversation_memory import get_conversation_memory
from app.modules.intelligence_extractor import get_intelligence_extractor
from app.modules.scam_detector import get_scam_detector
from app.services.callback_sender import get_callback_sender

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    logger.info("Starting Honey-Pot Scam Detection API...")
    settings = get_settings()
    
    # Validate configuration
    if settings.GROQ_API_KEY == "your-groq-api-key-here":
        logger.warning("GROQ_API_KEY not configured! Agent responses will fail.")
    
    if settings.API_KEY == "your-secure-api-key-here":
        logger.warning("API_KEY using default value! Please change for production.")
    
    logger.info(f"API Version: {settings.API_VERSION}")
    logger.info(f"Groq Model: {settings.GROQ_MODEL}")
    logger.info(f"Max Conversation Turns: {settings.MAX_CONVERSATION_TURNS}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Honey-Pot Scam Detection API...")


# Create FastAPI app
settings = get_settings()
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "Internal server error",
            "reply": ""
        }
    )


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with basic info."""
    return HealthResponse(
        status="ok",
        version=settings.API_VERSION,
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    return HealthResponse(
        status="healthy",
        version=settings.API_VERSION,
        timestamp=datetime.utcnow().isoformat()
    )


@app.post("/webhook", response_model=WebhookResponse)
async def webhook(
    request: WebhookRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Main webhook endpoint for processing incoming scam messages.
    
    This endpoint:
    1. Validates the API key
    2. Detects if message is a scam (rule-based)
    3. Activates AI agent if scam detected
    4. Extracts intelligence from messages
    5. Sends callback when engagement completes
    
    Args:
        request: WebhookRequest with sessionId, message, conversationHistory, metadata
        api_key: Validated API key from header
        
    Returns:
        WebhookResponse with status and agent reply (or empty if completed)
    """
    session_id = request.sessionId
    message_obj = request.message
    conversation_history = request.conversationHistory or []
    
    # Extract text content
    message_text = message_obj.text
    history_text = [m.text for m in conversation_history]
    
    logger.info(f"Session {session_id}: Received webhook request")
    logger.debug(f"Message: {message_text[:100]}...")
    
    try:
        # Get services
        scam_detector = get_scam_detector()
        memory = get_conversation_memory()
        agent = get_agent_logic()
        extractor = get_intelligence_extractor()
        callback_sender = get_callback_sender()
        
        # Get or create session
        session = await memory.get_or_create_session(session_id)
        
        # Step 1: Scam Detection (Rule-based, NO LLM)
        detection_result = scam_detector.detect(message_text, history_text)
        scam_detected = detection_result.is_scam
        
        logger.info(
            f"Session {session_id}: Scam detection result: "
            f"detected={scam_detected}, confidence={detection_result.confidence_score}"
        )
        
        # Step 2: Add message to conversation history
        session = await memory.add_message(
            session_id=session_id,
            role="scammer",
            message=message_text,
            scam_detected=scam_detected
        )
        
        # Step 3: Check if agent should be activated
        should_activate = agent.should_activate_agent(
            scam_detected=scam_detected,
            current_state=session.state
        )
        
        if not should_activate:
            # No scam detected or already completed - return empty reply
            logger.info(f"Session {session_id}: Agent not activated (state={session.state.value})")
            return WebhookResponse(
                status="success",
                reply=""
            )
        
        # Step 4: Get conversation history for agent
        full_history = await memory.get_conversation_history(session_id)
        
        # Step 5: Process with agent
        agent_reply, should_continue, agent_notes = await agent.process_message(
            session_id=session_id,
            message=message_text,
            conversation_history=full_history[:-1],  # Exclude latest (just added)
            turn_count=session.turn_count,
            intelligence_count=session.intelligence_count
        )
        
        # Step 6: Handle completion
        if not should_continue:
            # Engagement completed - send callback
            logger.info(f"Session {session_id}: Engagement completed")
            
            # Complete the session
            await memory.complete_session(session_id, agent_notes)
            
            # Send callback
            callback_success = await callback_sender.send_callback_with_fallback(
                session_id=session_id,
                scam_detected=session.scam_detected,
                total_messages_exchanged=session.total_messages_exchanged,
                extracted_intelligence=session.extracted_intelligence,
                agent_notes=agent_notes
            )
            
            if callback_success:
                await memory.mark_callback_sent(session_id)
                logger.info(f"Session {session_id}: Callback sent successfully")
            else:
                logger.error(f"Session {session_id}: Callback failed but logged locally")
            
            # Return empty reply to indicate completion
            return WebhookResponse(
                status="success",
                reply=""
            )
        
        # Step 7: Add agent reply to conversation
        if agent_reply:
            await memory.add_message(
                session_id=session_id,
                role="agent",
                message=agent_reply,
                scam_detected=False
            )
        
        logger.info(
            f"Session {session_id}: Returning agent reply "
            f"(turn={session.turn_count}, intel={session.intelligence_count})"
        )
        
        return WebhookResponse(
            status="success",
            reply=agent_reply
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session {session_id}: Error processing webhook: {e}", exc_info=True)
        
        # Return error response but don't expose internal details
        return WebhookResponse(
            status="error",
            reply="Sorry beta, there seems to be some network issue. Can you repeat?"
        )


@app.get("/sessions/{session_id}")
async def get_session_status(
    session_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get status of a conversation session (for debugging/monitoring).
    
    Args:
        session_id: Session identifier
        api_key: Validated API key
        
    Returns:
        Session statistics
    """
    memory = get_conversation_memory()
    stats = await memory.get_stats(session_id)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    return stats


@app.get("/sessions")
async def list_sessions(
    api_key: str = Depends(verify_api_key)
):
    """
    List all active sessions (for monitoring).
    
    Args:
        api_key: Validated API key
        
    Returns:
        List of active session stats
    """
    memory = get_conversation_memory()
    sessions = await memory.get_all_sessions()
    
    return [
        {
            "session_id": s.session_id,
            "state": s.state.value,
            "total_messages": s.total_messages_exchanged,
            "turn_count": s.turn_count,
            "scam_detected": s.scam_detected,
            "intelligence_count": s.intelligence_count,
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
