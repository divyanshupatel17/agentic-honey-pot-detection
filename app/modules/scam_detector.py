"""
Rule-based scam detection module.
Uses heuristics, keyword matching, and pattern analysis - NO LLM.
"""

import re
from typing import List, Set

from app.core.config import (
    PAYMENT_REDIRECTION_PATTERNS,
    SCAM_KEYWORDS,
    URGENCY_PATTERNS,
    get_settings,
)
from app.models.schemas import ScamDetectionResult


class ScamDetector:
    """
    Detects scam attempts using rule-based heuristics.
    No LLM is used - purely deterministic analysis.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.scam_keywords = [kw.lower() for kw in SCAM_KEYWORDS]
        self.urgency_patterns = [p.lower() for p in URGENCY_PATTERNS]
        self.payment_patterns = [p.lower() for p in PAYMENT_REDIRECTION_PATTERNS]
    
    def detect(self, message: str, conversation_history: List[str] = None) -> ScamDetectionResult:
        """
        Analyze message for scam indicators.
        
        Args:
            message: The incoming message to analyze
            conversation_history: Previous messages for context
            
        Returns:
            ScamDetectionResult with detection details
        """
        message_lower = message.lower()
        conversation_history = conversation_history or []
        
        # Collect all indicators
        matched_keywords = self._extract_keywords(message_lower)
        urgency_score = self._calculate_urgency(message_lower)
        payment_redirection = self._detect_payment_redirection(message_lower)
        
        # Context analysis from conversation history
        context_score = self._analyze_context(conversation_history)
        
        # Calculate confidence score (0.0 to 1.0)
        confidence_score = self._calculate_confidence(
            len(matched_keywords),
            urgency_score,
            payment_redirection,
            context_score
        )
        
        # Determine if scam based on thresholds
        is_scam = self._is_scam_threshold(
            len(matched_keywords),
            urgency_score,
            payment_redirection
        )
        
        # Build reasons list
        reasons = self._build_reasons(
            matched_keywords,
            urgency_score,
            payment_redirection
        )
        
        return ScamDetectionResult(
            is_scam=is_scam,
            confidence_score=confidence_score,
            matched_keywords=list(matched_keywords),
            urgency_score=urgency_score,
            payment_redirection_detected=payment_redirection,
            reasons=reasons
        )
    
    def _extract_keywords(self, message: str) -> Set[str]:
        """Extract matched scam keywords from message."""
        matched = set()
        for keyword in self.scam_keywords:
            if keyword in message:
                matched.add(keyword)
        return matched
    
    def _calculate_urgency(self, message: str) -> int:
        """
        Calculate urgency score based on urgency indicators.
        Returns score from 0 to 10.
        """
        score = 0
        for pattern in self.urgency_patterns:
            if pattern in message:
                score += 1
        
        # Check for time pressure indicators
        time_pressure_patterns = [
            r'\d+\s*(minute|min|hour|hr|second|sec)',
            r'within\s+\d+',
            r'in\s+\d+\s*(minute|min|hour|hr)',
        ]
        for pattern in time_pressure_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                score += 2
        
        # Cap at 10
        return min(score, 10)
    
    def _detect_payment_redirection(self, message: str) -> bool:
        """Detect if message tries to redirect to payment."""
        for pattern in self.payment_patterns:
            if pattern in message:
                return True
        
        # Check for URL patterns
        url_patterns = [
            r'https?://\S+',
            r'www\.\S+',
            r'\S+\.com\S*',
            r'\S+\.in\S*',
            r'\S+\.co\.\S*',
        ]
        for pattern in url_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                # If URL found with payment context
                if any(p in message for p in ["pay", "click", "link", "open", "download"]):
                    return True
        
        return False
    
    def _analyze_context(self, conversation_history: List[str]) -> float:
        """
        Analyze conversation history for cumulative scam indicators.
        Returns context score from 0.0 to 1.0.
        """
        if not conversation_history:
            return 0.0
        
        total_keywords = 0
        for msg in conversation_history[-5:]:  # Look at last 5 messages
            msg_lower = msg.lower()
            for keyword in self.scam_keywords:
                if keyword in msg_lower:
                    total_keywords += 1
        
        # Normalize to 0-1 range
        return min(total_keywords / 10, 1.0)
    
    def _calculate_confidence(
        self,
        keyword_count: int,
        urgency_score: int,
        payment_redirection: bool,
        context_score: float
    ) -> float:
        """
        Calculate overall confidence score for scam detection.
        Returns value between 0.0 and 1.0.
        """
        # Keyword contribution (max 0.4)
        keyword_contribution = min(keyword_count * 0.1, 0.4)
        
        # Urgency contribution (max 0.3)
        urgency_contribution = (urgency_score / 10) * 0.3
        
        # Payment redirection contribution (0 or 0.2)
        payment_contribution = 0.2 if payment_redirection else 0.0
        
        # Context contribution (max 0.1)
        context_contribution = context_score * 0.1
        
        total = keyword_contribution + urgency_contribution + payment_contribution + context_contribution
        return round(min(total, 1.0), 2)
    
    def _is_scam_threshold(
        self,
        keyword_count: int,
        urgency_score: int,
        payment_redirection: bool
    ) -> bool:
        """
        Determine if message meets scam threshold based on configured thresholds.
        """
        settings = get_settings()
        
        # Must have minimum keywords
        if keyword_count >= settings.SCAM_KEYWORD_THRESHOLD:
            return True
        
        # High urgency alone can trigger
        if urgency_score >= settings.URGENCY_SCORE_THRESHOLD:
            return True
        
        # Payment redirection with some keywords
        if payment_redirection and keyword_count >= 1:
            return True
        
        # Multiple moderate indicators
        indicators = sum([
            keyword_count >= 1,
            urgency_score >= 2,
            payment_redirection
        ])
        if indicators >= 2:
            return True
        
        return False
    
    def _build_reasons(
        self,
        matched_keywords: Set[str],
        urgency_score: int,
        payment_redirection: bool
    ) -> List[str]:
        """Build human-readable reasons for detection."""
        reasons = []
        
        if matched_keywords:
            keywords_list = list(matched_keywords)[:5]  # Top 5
            reasons.append(f"Matched scam keywords: {', '.join(keywords_list)}")
        
        if urgency_score >= 3:
            reasons.append(f"High urgency indicators detected (score: {urgency_score})")
        
        if payment_redirection:
            reasons.append("Payment redirection attempt detected")
        
        return reasons


# Singleton instance
_scam_detector: ScamDetector = None


def get_scam_detector() -> ScamDetector:
    """Get singleton scam detector instance."""
    global _scam_detector
    if _scam_detector is None:
        _scam_detector = ScamDetector()
    return _scam_detector
