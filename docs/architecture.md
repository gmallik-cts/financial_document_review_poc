# Architecture

## Local POC
FastAPI accepts synthetic extracted text, stores cases in SQLite, schedules an in-process background task, masks common PII patterns, runs deterministic rules, invokes a no-op AI adapter, and exposes results for polling.

## Production-shaped target
Client application -> API Gateway/WAF -> Python API on ECS Fargate -> S3 quarantine -> file validation/malware scan -> Step Functions + SQS/DLQ -> OCR adapter (Textract/native PDF) -> PII detection and masking -> deterministic rules + internal verification adapters -> approved LLM adapter -> decision policy -> Aurora/PostgreSQL -> result polling and signed event/webhook.

## Critical boundaries
- Queues carry identifiers, not raw documents.
- AI adapter accepts only masked/minimized content.
- Token maps, if needed, are isolated from AI and ordinary logs.
- Model output cannot generate arbitrary SQL or tool destinations.
- Recommendation and final decision are separate.
- Existing application remains the reviewer UI and final-decision authority.
- Record schema, rules, prompt and model profile versions for every result.

## Replace before deployment
SQLite -> managed PostgreSQL; in-process task -> durable queue/orchestration; demo headers -> verified identity; text input -> private S3 upload flow; stub AI -> approved provider; regex masking -> tested layered PII detection and image redaction where applicable.
