import httpx

from agentic_ai.observability import LangfuseObservability


class OllamaChatModel:
    """Local Ollama chat adapter; no hosted model API is required."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 90.0,
        observability: LangfuseObservability | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.observability = observability

    async def answer(self, system_prompt: str, user_prompt: str) -> str:
        async def call_model() -> str:
            payload = {
                "model": self.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {"temperature": 0.1},
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
            message = response.json().get("message", {})
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Ollama returned an empty response")
            return content.strip()

        if not self.observability:
            return await call_model()
        return await self.observability.observe(
            name="llm.ollama_chat",
            as_type="generation",
            operation=call_model,
            input_data={"model": self.model, "system": system_prompt, "user": user_prompt},
            metadata={"model": self.model, "temperature": 0.1},
            output_builder=lambda result: {"chars": len(result)},
        )
