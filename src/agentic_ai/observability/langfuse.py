from collections.abc import Awaitable, Callable
from typing import Any

from agentic_ai.config import Settings


class LangfuseObservability:
    """Optional Langfuse tracing with content capture disabled by default."""

    def __init__(self, settings: Settings):
        self.enabled = bool(settings.langfuse_public_key and settings.langfuse_secret_key)
        self.capture_content = settings.langfuse_capture_content
        self._client = None
        if self.enabled:
            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_base_url,
                environment=settings.app_env,
                release=settings.langfuse_release,
            )

    async def observe(
        self,
        *,
        name: str,
        as_type: str,
        operation: Callable[[], Awaitable[Any]],
        input_data: Any | None = None,
        metadata: dict[str, Any] | None = None,
        output_builder: Callable[[Any], Any] | None = None,
    ) -> Any:
        if not self._client:
            return await operation()

        with self._client.start_as_current_observation(
            name=name,
            as_type=as_type,
            input=input_data if self.capture_content else None,
            metadata=metadata or {},
        ) as observation:
            try:
                result = await operation()
            except Exception as exc:
                observation.update(level="ERROR", status_message=type(exc).__name__)
                raise
            observation.update(output=output_builder(result) if output_builder else result)
            return result

    def shutdown(self) -> None:
        if self._client:
            self._client.shutdown()
