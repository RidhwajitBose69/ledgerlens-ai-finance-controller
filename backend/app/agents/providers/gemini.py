import os
import json
import httpx
from typing import Dict, Any
from backend.app.agents.providers.base import BaseLLMProvider

class GeminiProvider(BaseLLMProvider):
    def name(self) -> str:
        return "GEMINI"

    async def investigate_exception(
        self,
        exception: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            from backend.app.agents.providers.mock import MockAIProvider
            return await MockAIProvider().investigate_exception(exception, context_data)

        prompt = f"""
        You are the LedgerLens AI Finance Controller. Investigate this discrepancy and respond in JSON:
        Exception: {json.dumps(exception, default=str)}
        Context Data: {json.dumps(context_data, default=str)}
        """

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                raise Exception(f"Gemini API error ({res.status_code}): {res.text}")

            data = res.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(text)
            result["tool_calls"] = [{"tool": "gemini_completion", "status": "success"}]
            return result
