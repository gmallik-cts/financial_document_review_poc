from app.privacy import mask_pii

def test_masks_common_sensitive_values():
    result = mask_pii("Email: jane@example.test\\nID: 123-45-6789\\nAccount Number: 123456789")
    assert "[EMAIL]" in result.masked_text
    assert "[US_SSN]" in result.masked_text
    assert "[ACCOUNT_NUMBER]" in result.masked_text

def test_plain_text_remains():
    assert mask_pii("Account Type: Brokerage").masked_text == "Account Type: Brokerage"
