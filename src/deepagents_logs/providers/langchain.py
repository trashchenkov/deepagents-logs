from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any
from uuid import UUID

from pydantic import Field, PrivateAttr

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult, LLMResult

from deepagents_logs.core.paths import LOGGED_GIGACHAT_PROVIDER, LOGGED_LANGCHAIN_PROVIDER
from deepagents_logs.core.serialize import to_serializable
from deepagents_logs.core.session_logger import SessionArtifactLogger
from deepagents_logs.providers.base import ProviderLoggingMixin


@dataclass(frozen=True)
class PendingChatRun:
    session_id: str
    cwd: str
    request_body: dict[str, Any]
    model_name: str


class LangChainLoggingCallback(BaseCallbackHandler):
    run_inline = True

    def __init__(
        self,
        *,
        session_logger: SessionArtifactLogger,
        session_id_getter: Any,
        cwd_getter: Any,
        model_name: str,
        inner_provider: str | None,
    ) -> None:
        self._session_logger = session_logger
        self._session_id_getter = session_id_getter
        self._cwd_getter = cwd_getter
        self._model_name = model_name
        self._inner_provider = inner_provider
        self._pending: dict[UUID, PendingChatRun] = {}
        self._lock = Lock()

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        session_id = self._session_id_getter()
        if not session_id:
            return
        cwd = self._cwd_getter()
        request_body = {
            "messages": to_serializable(messages),
            "metadata": metadata or {},
            "invocation_params": kwargs.get("invocation_params"),
            "options": kwargs.get("options"),
            "serialized": serialized,
            "model": self._model_name,
            "provider": self._inner_provider,
        }
        prompts = _extract_prompt_texts(messages)
        if prompts:
            started_at = self._session_logger.ensure_state(session_id, cwd).started_at
            self._session_logger.append_prompt(session_id, prompts, timestamp=started_at, cwd=cwd)
        with self._lock:
            self._pending[run_id] = PendingChatRun(
                session_id=session_id,
                cwd=cwd,
                request_body=request_body,
                model_name=self._model_name,
            )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> Any:
        pending = self._pop_pending(run_id)
        if pending is None:
            return
        self._session_logger.log_api_pair(
            session_id=pending.session_id,
            source=self._source_name,
            method="CHAT",
            url=self._pseudo_url,
            request_headers=None,
            request_body=pending.request_body,
            response_status=200,
            response_headers=None,
            response_body=to_serializable(response),
            cwd=pending.cwd,
            model_name=pending.model_name,
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> Any:
        pending = self._pop_pending(run_id)
        if pending is None:
            return
        self._session_logger.log_api_pair(
            session_id=pending.session_id,
            source=self._source_name,
            method="CHAT",
            url=self._pseudo_url,
            request_headers=None,
            request_body=pending.request_body,
            response_status="error",
            response_headers=None,
            response_body={"error": str(error), "type": type(error).__name__},
            cwd=pending.cwd,
            model_name=pending.model_name,
        )

    @property
    def _source_name(self) -> str:
        if self._inner_provider:
            return f"langchain:{self._inner_provider}"
        return "langchain"

    @property
    def _pseudo_url(self) -> str:
        if self._inner_provider:
            return f"langchain://{self._inner_provider}/chat_model"
        return "langchain://chat_model"

    def _pop_pending(self, run_id: UUID) -> PendingChatRun | None:
        with self._lock:
            return self._pending.pop(run_id, None)


class LoggedLangChainModel(ProviderLoggingMixin, BaseChatModel):
    model: str = Field(...)
    model_provider: str | None = Field(default=None)
    profile: dict[str, Any] | None = Field(default=None)

    _session_logger: SessionArtifactLogger = PrivateAttr(default_factory=SessionArtifactLogger)
    _inner_model: BaseChatModel = PrivateAttr()
    _logging_handler: LangChainLoggingCallback = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        inner_model = self._create_inner_model()
        self._logging_handler = LangChainLoggingCallback(
            session_logger=self._session_logger,
            session_id_getter=self._ensure_session_id,
            cwd_getter=self._current_cwd,
            model_name=self.inner_model_spec,
            inner_provider=self.inner_provider,
        )
        self._attach_logging_handler(inner_model)
        self._inner_model = inner_model
        if self.profile is None:
            resolved_profile = getattr(inner_model, "profile", None)
            if isinstance(resolved_profile, dict):
                self.profile = dict(resolved_profile)

    @property
    def inner_model_spec(self) -> str:
        model = str(self.model).strip()
        if self.model_provider and ":" not in model:
            return f"{self.model_provider}:{model}"
        return model

    @property
    def inner_provider(self) -> str | None:
        if self.model_provider:
            return self.model_provider
        provider, separator, _ = self.inner_model_spec.partition(":")
        return provider if separator else None

    @property
    def _llm_type(self) -> str:
        return "logged-langchain"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "model_provider": self.model_provider,
            "inner_model_spec": self.inner_model_spec,
        }

    def bind_tools(
        self,
        tools: Any,
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._inner_model.bind_tools(tools, tool_choice=tool_choice, **kwargs)

    def with_structured_output(
        self,
        schema: dict[str, Any] | type,
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> Any:
        return self._inner_model.with_structured_output(
            schema,
            include_raw=include_raw,
            **kwargs,
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        result = self._inner_model.generate([messages], stop=stop, **kwargs)
        return _llm_result_to_chat_result(result)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        result = await self._inner_model.agenerate([messages], stop=stop, **kwargs)
        return _llm_result_to_chat_result(result)

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ):
        for chunk in self._inner_model.stream(messages, stop=stop, **kwargs):
            yield ChatGenerationChunk(message=chunk)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ):
        async for chunk in self._inner_model.astream(messages, stop=stop, **kwargs):
            yield ChatGenerationChunk(message=chunk)

    def _create_inner_model(self) -> BaseChatModel:
        spec = self.inner_model_spec
        if spec.startswith(f"{LOGGED_LANGCHAIN_PROVIDER}:") or spec.startswith(f"{LOGGED_GIGACHAT_PROVIDER}:"):
            raise ValueError("Nested logged providers are not supported")
        from deepagents_cli.config import create_model

        result = create_model(spec)
        return result.model

    def _attach_logging_handler(self, inner_model: BaseChatModel) -> None:
        callbacks = list(getattr(inner_model, "callbacks", []) or [])
        if not any(callback is self._logging_handler for callback in callbacks):
            callbacks.append(self._logging_handler)
            inner_model.callbacks = callbacks


def _extract_prompt_texts(message_batches: list[list[BaseMessage]]) -> list[str]:
    prompts: list[str] = []
    for batch in message_batches:
        for message in batch:
            if getattr(message, "type", "") not in {"human", "user"}:
                continue
            text = _message_text(message)
            if text:
                prompts.append(text)
    return prompts


def _message_text(message: BaseMessage) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                if block.strip():
                    parts.append(block.strip())
            elif isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return str(content).strip()


def _llm_result_to_chat_result(result: LLMResult) -> ChatResult:
    generations = result.generations[0] if result.generations else []
    return ChatResult(generations=generations, llm_output=result.llm_output)
