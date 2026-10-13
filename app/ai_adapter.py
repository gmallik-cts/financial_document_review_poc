from .schemas import Finding, WorkflowType

class AIReviewAdapter:
    # Safe local stub: no LLM is called and no data leaves the process.
    async def analyze(self, workflow: WorkflowType, masked_texts: list[str]) -> list[Finding]:
        return [Finding(code="AI_ANALYSIS_STUB", severity="INFO",
            summary="POC AI adapter is a stub; no external model was called.",
            evidence=[{"type":"PIPELINE_STATUS","workflow":workflow.value}],
            requires_human_review=True)]
