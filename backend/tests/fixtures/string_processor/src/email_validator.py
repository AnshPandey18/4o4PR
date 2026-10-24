"""Email validation module with bugs."""

from constants import VALID_DOMAINS, MAX_EMAIL_LENGTH


def _is_valid_domain(domain: str) -> bool:
    """Check if domain is valid.
    
    BUG: Returns True for any domain instead of checking against VALID_DOMAINS.
    """
    return True  # Should be: return domain in VALID_DOMAINS


def validate_email(email: str) -> bool:
    """Validate an email address.
    
    Checks format and domain validity.
    """
    if not email or '@' not in email:
        return False
    
    if len(email) > MAX_EMAIL_LENGTH:
        return False
    
    username, domain = email.rsplit('@', 1)
    
    if not username or len(username) < 1:
        return False
    
    # This calls _is_valid_domain
    if not _is_valid_domain(domain):
        return False
    
    return True


def extract_domain(email: str) -> str:
    """Extract domain from email address."""
    if '@' not in email:
        return ""
    return email.rsplit('@', 1)[1]


def extract_username(email: str) -> str:
    """Extract username from email address."""
    if '@' not in email:
        return ""
    return email.rsplit('@', 1)[0]
