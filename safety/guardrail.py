"""Input and output checks for the career and research assistant."""

import re
from dataclasses import dataclass

MAX_CHAT_CHARS = 4000
MAX_FIELD_CHARS = 200
MAX_URL_CHARS = 500

USER_BLOCK_MESSAGE = (
    "**Request blocked**\n\n"
    "This message was stopped by the platform safety guardrail. "
    "Ask about the uploaded research paper, a public repository, or your career materials. "
    "An administrator has been notified."
)

SELF_HARM_MESSAGE = (
    "**Request blocked**\n\n"
    "I can't help with that. If you are in immediate danger, contact local emergency services. "
    "In the United States you can call or text 988 for the Suicide and Crisis Lifeline. "
    "An administrator has been notified."
)

_RULES = [
    (
        "prompt_injection",
        re.compile(
            r"("
            r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions"
            r"|disregard\s+(your|the|all)\s+(system|previous|prior|safety|rules)"
            r"|reveal\s+(your|the)\s+(system|hidden|developer)\s+prompt"
            r"|print\s+(your|the)\s+(system|hidden)\s+(prompt|instructions)"
            r"|\bjailbreak\b"
            r"|do\s+anything\s+now"
            r"|developer\s+mode"
            r"|you\s+are\s+now\s+(a|an|unrestricted|dan)\b"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "credential_theft",
        re.compile(
            r"("
            r"phish(ing)?\s+(email|page|kit|site)"
            r"|steal\s+(passwords|credentials|cookies|accounts)"
            r"|credential\s+dump"
            r"|keylogger"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "malware",
        re.compile(
            r"("
            r"\b(write|build|create|code)\b.{0,40}\b(malware|ransomware|virus|trojan|exploit)\b"
            r"|\bransomware\b"
            r"|\bremote\s+access\s+trojan\b"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "weapons",
        re.compile(
            r"("
            r"how\s+to\s+(make|build|assemble)\s+(a\s+)?(bomb|explosive|weapon)"
            r"|\bpipe\s+bomb\b"
            r"|\bbioweapon\b"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "child_exploitation",
        re.compile(
            r"("
            r"child\s+(sexual|porn|pornography)"
            r"|sexual\s+content\s+.*(minor|child|underage)"
            r"|\bcsam\b"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "self_harm",
        re.compile(
            r"("
            r"how\s+(can|do)\s+i\s+(kill|hurt)\s+myself"
            r"|suicide\s+method"
            r"|ways\s+to\s+end\s+my\s+life"
            r")",
            re.IGNORECASE,
        ),
    ),
]

_OUTPUT_LEAK = re.compile(
    r"("
    r"GEMINI_API_KEY\s*="
    r"|SMTP_PASSWORD\s*="
    r"|BEGIN\s+(RSA\s+|OPENSSH\s+)?PRIVATE\s+KEY"
    r"|You are a PhD-level Research Assistant\. You are grounded"
    r")",
    re.IGNORECASE,
)

_URL = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    category: str = ""
    reason: str = ""

    @property
    def user_message(self):
        if self.allowed:
            return ""
        if self.category == "invalid_input":
            return f"**Request blocked**\n\n{self.reason}"
        if self.category == "self_harm":
            return SELF_HARM_MESSAGE
        return USER_BLOCK_MESSAGE

    @property
    def plain_message(self):
        return " ".join(self.user_message.replace("**", "").split())


def check_text(text, field_name="message"):
    """Return a block result when text violates platform safety rules."""
    value = (text or "").strip()
    limit = MAX_URL_CHARS if field_name == "repo_url" else (
        MAX_CHAT_CHARS if field_name == "message" else MAX_FIELD_CHARS
    )
    if field_name in {"message", "repo_url", "author", "institution"} and not value:
        return GuardrailResult(False, "invalid_input", f"{field_name} is required.")
    if len(value) > limit:
        return GuardrailResult(
            False, "invalid_input", f"{field_name} exceeds {limit} characters."
        )
    if field_name == "repo_url" and not _URL.match(value):
        return GuardrailResult(
            False, "invalid_input", "Repository URL must start with http:// or https://."
        )

    for category, pattern in _RULES:
        if pattern.search(value):
            return GuardrailResult(
                False, category, f"{field_name} matched the {category} guardrail."
            )
    return GuardrailResult(True)


def check_output(text):
    """Block model output that leaks secrets or hidden instructions."""
    if text and _OUTPUT_LEAK.search(text):
        return GuardrailResult(
            False, "output_leak", "Model output contained restricted platform text."
        )
    return GuardrailResult(True)
