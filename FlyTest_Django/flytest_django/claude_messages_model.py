from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

import httpx
from pydantic import Field

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.tool import tool_call
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool


class ClaudeMessagesCompatibleChatModel(BaseChatModel):
    model: str
    api_key: str = Field(default="", repr=False)
    base_url: str
    temperature: float = 0.7
    timeout: float = 120
    max_retries: int = 3
    anthropic_version: str = "2023-06-01"
    max_output_tokens: int = 1024
    wire_api: str = "messages"
    bound_tools: list[dict[str, Any]] = Field(default_factory=list)
    bound_tool_choice: dict[str, Any] | None = None

    @property
    def _llm_type(self) -> str:
        return "claude_messages_compatible"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "base_url": self.base_url,
            "wire_api": self.wire_api,
        }

    def bind_tools(self, tools: Sequence[Any], *, tool_choice: str | None = None, **kwargs: Any):
        converted_tools = [self._convert_tool_schema(tool) for tool in tools]
        converted_choice = self._convert_tool_choice(tool_choice)
        return self.model_copy(
            update={
                "bound_tools": converted_tools,
                "bound_tool_choice": converted_choice,
            }
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = self._build_payload(messages, stop=stop, **kwargs)
        response = self._post_messages(payload)
        ai_message = self._response_to_message(response)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        payload = self._build_payload(messages, stop=stop, **kwargs)
        response = self._post_messages(payload)
        ai_message = self._response_to_message(response)
        chunk = AIMessageChunk(
            content=ai_message.content,
            tool_calls=ai_message.tool_calls,
            response_metadata=ai_message.response_metadata,
            usage_metadata=ai_message.usage_metadata,
        )
        yield ChatGenerationChunk(message=chunk)

    def _post_messages(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": self.anthropic_version,
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = httpx.post(
            f"{self.base_url.rstrip('/')}/messages",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def _build_payload(
        self,
        messages: list[BaseMessage],
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, Any]] = []

        def append_message(role: str, content: Any) -> None:
            if anthropic_messages and anthropic_messages[-1]["role"] == role:
                previous_content = anthropic_messages[-1]["content"]
                if isinstance(previous_content, list) and isinstance(content, list):
                    previous_content.extend(content)
                    return
                anthropic_messages[-1]["content"] = self._coerce_content_blocks(previous_content) + self._coerce_content_blocks(content)
                return
            anthropic_messages.append({"role": role, "content": content})

        for message in messages:
            if isinstance(message, SystemMessage):
                extracted = self._extract_text_from_content(message.content)
                if extracted:
                    system_parts.append(extracted)
                continue

            if isinstance(message, ToolMessage):
                append_message(
                    "user",
                    [
                        {
                            "type": "tool_result",
                            "tool_use_id": message.tool_call_id,
                            "content": self._extract_text_from_content(message.content) or "",
                        }
                    ],
                )
                continue

            if isinstance(message, HumanMessage):
                append_message("user", self._coerce_content_blocks(message.content))
                continue

            if isinstance(message, AIMessage):
                assistant_blocks = self._coerce_content_blocks(message.content)
                for call in message.tool_calls or []:
                    assistant_blocks.append(
                        {
                            "type": "tool_use",
                            "id": call.get("id") or f"tool_{call.get('name', 'call')}",
                            "name": call.get("name") or "tool",
                            "input": call.get("args") or {},
                        }
                    )
                append_message("assistant", assistant_blocks or "")
                continue

            append_message("user", self._coerce_content_blocks(message.content))

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens") or self.max_output_tokens,
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": False,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if stop:
            payload["stop_sequences"] = stop
        if self.bound_tools:
            payload["tools"] = self.bound_tools
        if self.bound_tool_choice:
            payload["tool_choice"] = self.bound_tool_choice
        return payload

    def _response_to_message(self, payload: dict[str, Any]) -> AIMessage:
        content_blocks = payload.get("content") or []
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = str(block.get("text") or "").strip()
                if text:
                    text_parts.append(text)
            elif block_type == "tool_use":
                tool_calls.append(
                    tool_call(
                        name=str(block.get("name") or "tool"),
                        args=block.get("input") or {},
                        id=str(block.get("id") or ""),
                    )
                )

        usage = payload.get("usage") or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        usage_metadata = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
        response_metadata = {
            "finish_reason": payload.get("stop_reason") or payload.get("status") or "",
            "token_usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

        content: str | list[dict[str, Any]]
        if text_parts:
            content = "\n".join(text_parts).strip()
        else:
            content = content_blocks

        return AIMessage(
            content=content,
            tool_calls=tool_calls,
            response_metadata=response_metadata,
            usage_metadata=usage_metadata,
        )

    def _coerce_content_blocks(self, content: Any) -> list[dict[str, Any]]:
        if isinstance(content, str):
            text = content.strip()
            return [{"type": "text", "text": text}] if text else []

        if isinstance(content, list):
            blocks: list[dict[str, Any]] = []
            for item in content:
                blocks.extend(self._coerce_content_blocks(item))
            return blocks

        if isinstance(content, dict):
            content_type = content.get("type")
            if content_type == "text":
                text = str(content.get("text") or "").strip()
                return [{"type": "text", "text": text}] if text else []
            text = self._extract_text_from_content(content)
            return [{"type": "text", "text": text}] if text else []

        text = self._extract_text_from_content(content)
        return [{"type": "text", "text": text}] if text else []

    @staticmethod
    def _extract_text_from_content(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [ClaudeMessagesCompatibleChatModel._extract_text_from_content(item) for item in content]
            return "\n".join(part for part in parts if part).strip()
        if isinstance(content, dict):
            direct_text = str(content.get("text") or content.get("content") or "").strip()
            if direct_text:
                return direct_text
        return str(getattr(content, "text", "") or getattr(content, "content", "") or "").strip()

    @staticmethod
    def _convert_tool_schema(tool_definition: Any) -> dict[str, Any]:
        openai_tool = convert_to_openai_tool(tool_definition)
        function = openai_tool.get("function", {})
        return {
            "name": function.get("name"),
            "description": function.get("description", ""),
            "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
        }

    @staticmethod
    def _convert_tool_choice(tool_choice: str | None) -> dict[str, Any] | None:
        if not tool_choice:
            return None
        lowered = str(tool_choice).strip().lower()
        if lowered in {"auto", "none"}:
            return {"type": "auto"}
        if lowered in {"any", "required"}:
            return {"type": "any"}
        return {"type": "tool", "name": str(tool_choice)}
