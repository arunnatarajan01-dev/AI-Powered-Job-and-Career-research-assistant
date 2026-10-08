"""
Text Cleaning Module - Normalizes and cleans resume text for processing.
"""
import re
import unicodedata


def clean_text(text):
    """
    Clean and normalize resume text.
    
    Args:
        text: Raw text extracted from resume
    
    Returns:
        str: Cleaned text
    """
    if not text:
        return ""

    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)

    # Normalize newlines and whitespace
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\r', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)  # Collapse horizontal whitespace
    text = re.sub(r'\n{3,}', '\n\n', text) # Limit excessive newlines

    # Remove special characters but keep useful punctuation
    text = re.sub(r'[^\w\s@.,:;/\-+#()&|]', '', text)

    # Fix common encoding issues
    text = text.replace('â€™', "'")
    text = text.replace('â€"', "-")
    text = text.replace('â€œ', '"')
    text = text.replace('â€', '"')

    # Remove extra spaces around punctuation
    text = re.sub(r'\s*([,:;])\s*', r'\1 ', text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def normalize_text(text):
    """
    Normalize text for comparison (lowercase, remove extra spaces).
    
    Args:
        text: Text to normalize
    
    Returns:
        str: Normalized text
    """
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def extract_email(text):
    """Extract email addresses from text."""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(pattern, text)
    return emails[0] if emails else None


def extract_phone(text):
    """Extract phone numbers from text."""
    pattern = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    phones = re.findall(pattern, text)
    return phones[0] if phones else None


def extract_links(text):
    """Extract URLs and links from text."""
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    links = re.findall(pattern, text)
    return links


_HEADER_SKIP = re.compile(r"^(resume|curriculum vitae|cv)$", re.IGNORECASE)
_ROLE_LINE = re.compile(
    r"\b(engineer|developer|manager|analyst|designer|consultant|intern|summary|objective|profile|skills|experience|education)\b",
    re.IGNORECASE,
)


def extract_candidate_name(text):
    """Read the candidate name from the top of a resume.

    The name is usually the first line of a resume PDF. Lines that are only
    a document title or a job title are skipped.
    """
    checked = 0
    for raw in (text or "").splitlines():
        line = " ".join(raw.split()).strip()
        if not line or _HEADER_SKIP.match(line.strip(":- ")):
            continue
        checked += 1
        name = _name_on_line(line)
        if name and not _ROLE_LINE.search(name):
            return name
        if checked >= 4:
            break
    return ""


def _name_on_line(line):
    """Keep the name when contact details share the first resume line."""
    head = re.split(r"\s+[|•]\s+|\s{2,}", line, maxsplit=1)[0]
    head = re.split(
        r"\s+(?=https?://|www\.|[A-Za-z0-9._%+-]+@)",
        head,
        maxsplit=1,
    )[0].strip(" |,-")
    if not head or "@" in head or "http" in head.lower() or re.search(r"\d{5,}", head):
        return ""
    if len(head) > 80:
        return ""
    words = head.split()
    if not words or len(words) > 5:
        return ""
    if sum(ch.isalpha() for ch in head) < 2:
        return ""
    return head
