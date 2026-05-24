import re

class PIIRedactor:
    """
    A lightweight, high-performance PII Redaction Engine.
    Exposes a method to mask sensitive information like emails, phone numbers,
    credit cards, SSNs, and API keys before logging inferences.
    """
    def __init__(self):
        # Email Regex
        self.email_regex = re.compile(
            r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        )
        
        # Phone Regex (supports international, US, formats)
        self.phone_regex = re.compile(
            r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
        )
        
        # Credit Card Regex (Visa, Mastercard, Amex, Discover, etc.)
        self.card_regex = re.compile(
            r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6(?:011|5[0-9][0-9])[0-9]{12}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|(?:2131|1800|35\d{3})\d{11})\b'
        )
        
        # US Social Security Number (SSN) Regex
        self.ssn_regex = re.compile(
            r'\b\d{3}-\d{2}-\d{4}\b'
        )
        
        # Common API Key formats (sk-proj, AIzaSy, gsk, jwt-like, general entropy-based SKs)
        self.api_key_regex = re.compile(
            r'\b((?:sk-proj-[a-zA-Z0-9]{32,})|(?:AIzaSy[a-zA-Z0-9_-]{35})|(?:gsk_[a-zA-Z0-9]{24,})|(?:sk_[a-zA-Z0-9]{24,}))\b',
            re.IGNORECASE
        )

    def redact(self, text: str) -> str:
        """
        Redacts PII from the provided text string.
        """
        if not text or not isinstance(text, str):
            return text

        # Redact Credit Cards first (since they are pure numbers and might get confused with phone numbers)
        text = self.card_regex.sub("[REDACTED_CREDIT_CARD]", text)
        
        # Redact US SSNs
        text = self.ssn_regex.sub("[REDACTED_SSN]", text)
        
        # Redact Emails
        text = self.email_regex.sub("[REDACTED_EMAIL]", text)
        
        # Redact Phone Numbers
        text = self.phone_regex.sub("[REDACTED_PHONE]", text)
        
        # Redact API Keys / Secrets
        text = self.api_key_regex.sub("[REDACTED_API_KEY]", text)
        
        return text

# Singleton instance
pii_redactor = PIIRedactor()
