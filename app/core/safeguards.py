import re

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|system)\s+instructions",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"show\s+(me\s+)?(the\s+)?database\s+password",
    r"bypass\s+(authentication|authorization|security)",
    r"you\s+are\s+now\s+(an?\s+)?administrator",
]


def detects_injection(text: str) -> bool:

    return any(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        for pattern in INJECTION_PATTERNS
    )


def redact_sensitive_text(text: str) -> str:

    # Email addresses
    text = re.sub(
        r"\b[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[EMAIL_REDACTED]",
        text,
    )

    # Contiguous international or local phone numbers
    text = re.sub(
        r"(?<!\d)\+?\d{10,15}(?!\d)",
        "[PHONE_REDACTED]",
        text,
    )

    # Demo customer account identifiers
    text = re.sub(
        r"\bCUST\d+\b",
        "[CUSTOMER_ID]",
        text,
        flags=re.IGNORECASE,
    )

    # Confirmation codes
    text = re.sub(
        r"\bCONFIRM\s+[A-F0-9]{8}\b",
        "[CONFIRMATION_REDACTED]",
        text,
        flags=re.IGNORECASE,
    )

    # Common JWT representation
    text = re.sub(
        r"\beyJ[A-Za-z0-9_-]+\."
        r"[A-Za-z0-9_-]+\."
        r"[A-Za-z0-9_-]+\b",
        "[TOKEN_REDACTED]",
        text,
    )

    # Common API key formats
    text = re.sub(
        r"\b(?:gsk_|sk-|AIza)[A-Za-z0-9_-]{16,}\b",
        "[API_KEY_REDACTED]",
        text,
    )

    return text


class ProtectedLLMMixin:

    async def structured(
        self,
        system_prompt,
        user_prompt,
        schema,
    ):

        return await super().structured(
            system_prompt,
            redact_sensitive_text(user_prompt),
            schema,
        )

    async def generate(
        self,
        system_prompt,
        user_prompt,
    ):

        return await super().generate(
            system_prompt,
            redact_sensitive_text(user_prompt),
        )

    async def choose_tool(
        self,
        system_prompt,
        user_prompt,
        tools,
    ):

        return await super().choose_tool(
            system_prompt,
            redact_sensitive_text(user_prompt),
            tools,
        )