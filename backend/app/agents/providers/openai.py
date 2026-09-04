import os
import json
import httpx
from typing import Dict, Any
from backend.app.agents.providers.base import BaseLLMProvider

class OpenAIProvider(BaseLLMProvider):
    def name(self) -> str:
        return "OPENAI"

    async def investigate_exception(
        self,
        exception: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Return graceful fallback mock if key not set
            from backend.app.agents.providers.mock import MockAIProvider
            return await MockAIProvider().investigate_exception(exception, context_data)

        prompt = f"""
        You are the LedgerLens AI Finance Controller investigating a settlement reconciliation discrepancy.
        Exception: {json.dumps(exception, default=str)}
        Context Data: {json.dumps(context_data, default=str)}

        Analyze the evidence and return a JSON object with:
        "decision": "AUTO_RESOLVE" or "HUMAN_REVIEW",
        "confidence": float (0.0 to 1.0),
        "reason_code": string,
        "summary": string,
        "evidence_items": list of strings,
        "recommended_action": string,
        "risk_level": "LOW", "MEDIUM", "HIGH", or "CRITICAL",
        "financial_impact_paise": integer
        """

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if res.status_code != 200:
                raise Exception(f"OpenAI API error ({res.status_code}): {res.text}")

            data = res.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            result["tool_calls"] = [{"tool": "openai_completion", "status": "success"}]
            return result
