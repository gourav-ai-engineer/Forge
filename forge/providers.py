from __future__ import annotations

import os
from dataclasses import dataclass

from .planner import JSONPlanner, SYSTEM_PROMPT
from .types import ForgeTask, ToolCall


@dataclass(frozen=True)
class OpenAIPlanner:
    """Optional model-backed planner using the OpenAI Responses API."""

    model: str = "gpt-5.6-luna"

    def plan(self, task: ForgeTask, context: str) -> tuple[ToolCall, ...]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Install the optional 'openai' dependency to use model planning"
            ) from exc

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for model planning")

        client = OpenAI(api_key=api_key)
        user = (
            f"Task: {task.request}\nWorkspace snapshot:\n{context[-30_000:]}\n"
            "Return only the required JSON object."
        )
        response = client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=user,
        )
        raw = response.output_text.strip()
        return JSONPlanner().parse(raw)


def provider_from_env() -> OpenAIPlanner | None:
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIPlanner(model=os.getenv("FORGE_MODEL", "gpt-5.6-luna"))
    return None
