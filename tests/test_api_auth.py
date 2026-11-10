"""API key comparison tests; no external services or DB required."""

from atrees.core.auth import secret_matches


def test_api_key_comparison_accepts_only_exact_nonempty_key() -> None:
    assert secret_matches("test-secret", "test-secret")
    assert not secret_matches("", "test-secret")
    assert not secret_matches("wrong-secret", "test-secret")
    assert not secret_matches("test-secret", None)
