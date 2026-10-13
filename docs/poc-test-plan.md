# POC test plan

Use synthetic data only.

## Functional cases
1. Onboarding with matching Name/DOB and required document types.
2. Missing identity document.
3. Mismatching names or DOB across documents.
4. Missing signature indicator.
5. Transfer missing authorization form.
6. Missing account-holder/delivering/receiving account fields.
7. Result requested before processing completes.
8. Authorized final decision capture.
9. Cross-tenant/client case access attempt is denied.
10. Missing idempotency header is rejected.

## Privacy checks
- Check masking for email, SSN-like values, phone, DOB and account-number patterns.
- Use canary values and inspect only masked content at the AI adapter boundary.
- Test unusual formatting, OCR errors, free text and false negatives before production.
- Ensure logs, errors and callback payloads do not include raw document text.

## Production blockers
Replace demo auth, implement real idempotency and durable orchestration, add secure upload/malware scan, improve PII detection and fail-closed masking, obtain model-provider approval, and complete security, quality, retention, load and recovery testing.
