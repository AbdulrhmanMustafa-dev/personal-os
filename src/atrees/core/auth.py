"""Small constant-time authentication helpers."""

import hmac


def secret_matches(candidate: str | None, expected: str | None) -> bool:
    """Return true only when both secrets exist and match in constant time."""
    if not candidate or not expected:
        return False
    return hmac.compare_digest(candidate, expected)
