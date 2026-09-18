from agentic_ai.guardrails import mask_pii


def test_masks_common_sensitive_values() -> None:
    result = mask_pii("Contact sara@example.com or call +971 50 123 4567. Key: sk_test_1234567890123456")

    assert "sara@example.com" not in result.text
    assert "[MASKED_EMAIL]" in result.text
    assert "[MASKED_PHONE]" in result.text
    assert "[MASKED_API_KEY]" in result.text
    assert result.counts == {"email": 1, "phone": 1, "api_key": 1}
