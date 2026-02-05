"""
Intelligence extraction module using regex patterns.
Extracts financial and contact information deterministically - NO LLM.
"""

import re
from typing import Dict, List, Set
from urllib.parse import urlparse

from app.core.config import EXTRACTION_PATTERNS, SUSPICIOUS_KEYWORDS
from app.models.schemas import ExtractedIntelligence


class IntelligenceExtractor:
    """
    Extracts intelligence from scam messages using regex patterns.
    Purely deterministic - no AI/LLM involved.
    """
    
    def __init__(self):
        self.patterns = EXTRACTION_PATTERNS
        self.suspicious_keywords = [kw.lower() for kw in SUSPICIOUS_KEYWORDS]
        self._compiled_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Pre-compile regex patterns for performance."""
        compiled = {}
        for category, patterns in self.patterns.items():
            compiled[category] = [re.compile(p, re.IGNORECASE) for p in patterns]
        return compiled
    
    def extract(self, message: str, existing_intelligence: ExtractedIntelligence = None) -> ExtractedIntelligence:
        """
        Extract all intelligence from a message.
        
        Args:
            message: The message to analyze
            existing_intelligence: Previously extracted intelligence to merge with
            
        Returns:
            ExtractedIntelligence with all findings
        """
        if existing_intelligence is None:
            existing_intelligence = ExtractedIntelligence()
        
        # Extract each category
        bank_accounts = self._extract_bank_accounts(message)
        upi_ids = self._extract_upi_ids(message)
        phishing_links = self._extract_phishing_links(message)
        phone_numbers = self._extract_phone_numbers(message)
        suspicious_keywords = self._extract_suspicious_keywords(message)
        
        # Merge with existing (deduplicate)
        return ExtractedIntelligence(
            bankAccounts=list(set(existing_intelligence.bankAccounts + bank_accounts)),
            upiIds=list(set(existing_intelligence.upiIds + upi_ids)),
            phishingLinks=list(set(existing_intelligence.phishingLinks + phishing_links)),
            phoneNumbers=list(set(existing_intelligence.phoneNumbers + phone_numbers)),
            suspiciousKeywords=list(set(existing_intelligence.suspiciousKeywords + suspicious_keywords)),
        )
    
    def _extract_bank_accounts(self, message: str) -> List[str]:
        """Extract bank account numbers and IFSC codes."""
        found = set()
        
        # Account numbers (9-18 digits, not part of phone number)
        account_pattern = re.compile(r'\b\d{9,18}\b')
        for match in account_pattern.findall(message):
            # Filter out likely phone numbers (10 digits starting with 6-9)
            if len(match) == 10 and match[0] in '6789':
                continue
            # Filter out UPI IDs
            if '@' in message[message.find(match):message.find(match)+len(match)+10]:
                continue
            found.add(match)
        
        # IFSC codes
        ifsc_pattern = re.compile(r'\b[A-Z]{4}0[A-Z0-9]{6}\b', re.IGNORECASE)
        for match in ifsc_pattern.findall(message):
            found.add(match.upper())
        
        return list(found)
    
    def _extract_upi_ids(self, message: str) -> List[str]:
        """Extract UPI IDs from message."""
        found = set()
        
        # Common UPI patterns
        upi_patterns = [
            r'\b[a-zA-Z0-9._-]+@[a-zA-Z]+\b',  # Generic UPI
            r'\b[a-zA-Z0-9._-]+@upi\b',
            r'\b[a-zA-Z0-9._-]+@paytm\b',
            r'\b[a-zA-Z0-9._-]+@ybl\b',  # Yes Bank
            r'\b[a-zA-Z0-9._-]+@ibl\b',  # ICICI Bank
            r'\b[a-zA-Z0-9._-]+@axl\b',  # Axis Bank
            r'\b[a-zA-Z0-9._-]+@okaxis\b',
            r'\b[a-zA-Z0-9._-]+@oksbi\b',
            r'\b[a-zA-Z0-9._-]+@okhdfcbank\b',
            r'\b[a-zA-Z0-9._-]+@okicici\b',
        ]
        
        for pattern in upi_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            for match in matches:
                # Validate it looks like a UPI ID
                if '@' in match and len(match) >= 5:
                    found.add(match.lower())
        
        return list(found)
    
    def _extract_phishing_links(self, message: str) -> List[str]:
        """Extract suspicious/phishing URLs from message."""
        found = set()
        
        # URL patterns
        url_patterns = [
            r'https?://[^\s<>"{}|\\^`\[\]]+',
            r'www\.[^\s<>"{}|\\^`\[\]]+',
        ]
        
        for pattern in url_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            for url in matches:
                url = url.strip('.,;:!?')
                if self._is_suspicious_url(url):
                    found.add(url)
        
        # Shortened URLs (always suspicious)
        short_url_pattern = re.compile(
            r'https?://(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|short\.link|rb\.gy|'
            r'cutt\.ly|shorturl\.at|is\.gd|ow\.ly|buff\.ly)/[a-zA-Z0-9]+',
            re.IGNORECASE
        )
        for match in short_url_pattern.findall(message):
            found.add(match)
        
        return list(found)
    
    def _is_suspicious_url(self, url: str) -> bool:
        """Check if a URL is suspicious."""
        url_lower = url.lower()
        
        # Suspicious keywords in URL
        suspicious_terms = [
            'secure', 'bank', 'login', 'verify', 'update', 'confirm', 'account',
            'password', 'credential', 'signin', 'authenticate', 'validation',
            'kyc', 'otp', 'payment', 'refund', 'prize', 'winner', 'lottery',
            'urgent', 'immediate', 'suspend', 'block', 'limited',
        ]
        
        for term in suspicious_terms:
            if term in url_lower:
                return True
        
        # IP-based URLs
        ip_pattern = re.compile(r'https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
        if ip_pattern.match(url):
            return True
        
        # Check for typosquatting (common brand misspellings)
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            brand_protections = [
                ('paypal', ['paypa1', 'paypall', 'paypaI']),
                ('amazon', ['amaz0n', 'amazn', 'amazzon']),
                ('google', ['g00gle', 'googIe', 'gooogle']),
                ('facebook', ['faceb00k', 'facebok', 'faceboook']),
                ('bank', ['b4nk', 'banq', 'bonk']),
                ('sbi', ['s8i', 'sbi-s', 'sbii']),
                ('hdfc', ['hdfcc', 'hdfv', 'hdffc']),
                ('icici', ['icic1', 'icicc', 'icicci']),
            ]
            
            for brand, typos in brand_protections:
                if brand in domain:
                    # Check for suspicious variations
                    for typo in typos:
                        if typo in domain:
                            return True
        except Exception:
            pass
        
        return False
    
    def _extract_phone_numbers(self, message: str) -> List[str]:
        """Extract phone numbers from message."""
        found = set()
        
        # Indian mobile numbers
        indian_patterns = [
            r'(?:\+91|91)?[ -]?[6-9]\d{9}',
            r'(?:\+91|91)?[ -]?[6-9]\d{4}[ -]?\d{5}',
        ]
        
        for pattern in indian_patterns:
            matches = re.findall(pattern, message)
            for match in matches:
                # Clean and normalize
                cleaned = re.sub(r'[^\d]', '', match)
                if len(cleaned) == 10:
                    found.add('+91' + cleaned)
                elif len(cleaned) == 12 and cleaned.startswith('91'):
                    found.add('+' + cleaned)
        
        # Generic phone format (international)
        generic_pattern = re.compile(r'\+\d{1,3}[ -]?\d{3,}[ -]?\d{3,}[ -]?\d{0,}')
        for match in generic_pattern.findall(message):
            cleaned = re.sub(r'[^\d+]', '', match)
            if len(cleaned) >= 10:
                found.add(cleaned)
        
        return list(found)
    
    def _extract_suspicious_keywords(self, message: str) -> List[str]:
        """Extract suspicious keywords from message."""
        found = set()
        message_lower = message.lower()
        
        for keyword in self.suspicious_keywords:
            if keyword in message_lower:
                found.add(keyword)
        
        return list(found)
    
    def count_intelligence(self, intelligence: ExtractedIntelligence) -> int:
        """
        Count total pieces of intelligence extracted.
        
        Returns:
            Total count of all intelligence items
        """
        return (
            len(intelligence.bankAccounts) +
            len(intelligence.upiIds) +
            len(intelligence.phishingLinks) +
            len(intelligence.phoneNumbers) +
            len(intelligence.suspiciousKeywords)
        )
    
    def has_critical_intelligence(self, intelligence: ExtractedIntelligence) -> bool:
        """
        Check if critical intelligence (financial/contact) has been extracted.
        
        Returns:
            True if bank accounts, UPI IDs, or phone numbers found
        """
        return (
            len(intelligence.bankAccounts) > 0 or
            len(intelligence.upiIds) > 0 or
            len(intelligence.phoneNumbers) > 0 or
            len(intelligence.phishingLinks) > 0
        )


# Singleton instance
_extractor: IntelligenceExtractor = None


def get_intelligence_extractor() -> IntelligenceExtractor:
    """Get singleton intelligence extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = IntelligenceExtractor()
    return _extractor
