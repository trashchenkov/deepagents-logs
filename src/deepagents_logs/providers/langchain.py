from __future__ import annotations

import asyncio
from contextvars import ContextVar
import importlib
import os
from typing import Any

from pydantic import Field, PrivateAttr

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, BaseMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult, LLMResult

from deepagents_logs.core.env import parse_env_file
from deepagents_logs.core.paths import DEEPAGENTS_ENV_PATH
from deepagents_logs.core.paths import LOGGED_GIGACHAT_PROVIDER, LOGGED_LANGCHAIN_PROVIDER
from deepagents_logs.core.serialize import to_serializable
from deepagents_logs.core.session_logger import SessionArtifactLogger
from deepagents_logs.providers.base import ProviderLoggingMixin


_CALL_CONTEXT: ContextVar[dict[str, str] | None] = ContextVar(
    "deepagents_logs_langchain_call_context",
    default=None,
)


class LoggedLangChainModel(ProviderLoggingMixin, BaseChatModel):
    model: str = Field(...)
    model_provider: str | None = Field(default=None)
    profile: dict[str, Any] | None = Field(default=None)
    disable_streaming: bool = Field(default=True)

    _session_logger: SessionArtifactLogger = PrivateAttr(default_factory=SessionArtifactLogger)
    _inner_model: BaseChatModel = PrivateAttr()
    _bound_tools: Any = PrivateAttr(default=None)
    _bound_tool_choice: str | None = PrivateAttr(default=None)
    _bound_kwargs: dict[str, Any] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        inner_model = self._create_inner_model()
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
        clone = self.model_copy(deep=False)
        clone._session_logger = self._session_logger
        clone._inner_model = self._inner_model
        clone._bound_tools = tools
        clone._bound_tool_choice = tool_choice
        clone._bound_kwargs = dict(kwargs)
        return clone

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
        with self._call_context():
            request = self._request_body(messages, stop=stop, extra_kwargs=kwargs)
            try:
                if self._bound_tools is None:
                    result = self._inner_model.generate([messages], stop=stop, **kwargs)
                    chat_result = _llm_result_to_chat_result(result)
                else:
                    runnable = self._inner_model.bind_tools(
                        self._bound_tools,
                        tool_choice=self._bound_tool_choice,
                        **self._bound_kwargs,
                    )
                    message = runnable.invoke(messages, stop=stop, **kwargs)
                    chat_result = ChatResult(generations=[ChatGeneration(message=_ensure_ai_message(message))])
                self._log_success(request, chat_result)
                return chat_result
            except Exception as exc:
                self._log_error(request, exc)
                raise

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return await asyncio.to_thread(
            self._generate,
            messages,
            stop,
            run_manager,
            **kwargs,
        )

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ):
        with self._call_context():
            request = self._request_body(messages, stop=stop, extra_kwargs=kwargs)
            chunks: list[ChatGenerationChunk] = []
            try:
                runnable = self._bound_runnable() if self._bound_tools is not None else self._inner_model
                for chunk in runnable.stream(messages, stop=stop, **kwargs):
                    generation_chunk = ChatGenerationChunk(message=_ensure_ai_message(chunk))
                    chunks.append(generation_chunk)
                    yield generation_chunk
                merged = _merge_chunks_to_result(chunks)
                self._log_success(request, merged)
            except Exception as exc:
                self._log_error(request, exc)
                raise

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ):
        result = await asyncio.to_thread(
            self._generate,
            messages,
            stop,
            run_manager,
            **kwargs,
        )
        generations = result.generations or []
        if not generations:
            yield ChatGenerationChunk(message=AIMessageChunk(content=""))
            return
        for generation in generations:
            yield ChatGenerationChunk(message=_ensure_ai_message_chunk(generation.message))

    def _create_inner_model(self) -> BaseChatModel:
        spec = self.inner_model_spec
        if spec.startswith(f"{LOGGED_LANGCHAIN_PROVIDER}:") or spec.startswith(f"{LOGGED_GIGACHAT_PROVIDER}:"):
            raise ValueError("Nested logged providers are not supported")
        provider, separator, model_name = spec.partition(":")
        if separator:
            configured = self._create_from_custom_provider(provider, model_name)
            if configured is not None:
                return configured
            if provider == "gigachat":
                return self._create_builtin_gigachat_model(model_name)
        from deepagents_cli.config import create_model

        result = create_model(spec)
        return result.model

    def _create_from_custom_provider(self, provider: str, model_name: str) -> BaseChatModel | None:
        from deepagents_cli.model_config import ModelConfig

        config = ModelConfig.load()
        class_path = config.get_class_path(provider)
        if not class_path:
            return None
        kwargs = config.get_kwargs(provider, model_name=model_name)
        model = _instantiate_class_path(class_path, model_name=model_name, kwargs=kwargs)
        profile = getattr(model, "profile", None)
        overrides = config.get_profile_overrides(provider, model_name=model_name)
        if overrides and isinstance(profile, dict):
            model.profile = {**profile, **overrides}
        elif overrides:
            model.profile = dict(overrides)
        return model

    def _create_builtin_gigachat_model(self, model_name: str) -> BaseChatModel:
        module = importlib.import_module("langchain_gigachat.chat_models")
        cls = getattr(module, "GigaChat")
        kwargs = _load_gigachat_kwargs()
        kwargs["model"] = model_name
        return cls(**kwargs)

    def _bound_runnable(self):
        return self._inner_model.bind_tools(
            self._bound_tools,
            tool_choice=self._bound_tool_choice,
            **self._bound_kwargs,
        )

    def _current_session_id(self) -> str | None:
        context = _CALL_CONTEXT.get()
        if context and context.get("session_id"):
            return context["session_id"]
        return self._ensure_session_id()

    def _current_call_cwd(self) -> str:
        context = _CALL_CONTEXT.get()
        if context and context.get("cwd"):
            return context["cwd"]
        return self._current_cwd()

    def _call_context(self):
        wrapper = self

        class _CallContext:
            def __enter__(self_inner):
                token = _CALL_CONTEXT.set(
                    {
                        "session_id": wrapper._ensure_session_id() or "",
                        "cwd": wrapper._current_cwd(),
                    }
                )
                self_inner._token = token
                return None

            def __exit__(self_inner, exc_type, exc, tb):
                _CALL_CONTEXT.reset(self_inner._token)
                return False

        return _CallContext()

    def _request_body(
        self,
        messages: list[BaseMessage],
        *,
        stop: list[str] | None,
        extra_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        prompts = _extract_prompt_texts([messages])
        if prompts:
            started_at = self._session_logger.ensure_state(
                self._current_session_id() or "unknown",
                self._current_call_cwd(),
            ).started_at
            session_id = self._current_session_id()
            if session_id:
                self._session_logger.append_prompt(
                    session_id,
                    prompts,
                    timestamp=started_at,
                    cwd=self._current_call_cwd(),
                )
        return {
            "messages": to_serializable([messages]),
            "stop": stop,
            "kwargs": to_serializable(extra_kwargs),
            "model": self.inner_model_spec,
            "provider": self.inner_provider,
            "bound_tools": self._bound_tool_descriptors(),
            "tool_choice": self._bound_tool_choice,
            "bound_kwargs": to_serializable(self._bound_kwargs),
        }

    def _log_success(self, request_body: dict[str, Any], result: ChatResult) -> None:
        session_id = self._current_session_id()
        if not session_id:
            return
        self._session_logger.log_api_pair(
            session_id=session_id,
            source=f"langchain:{self.inner_provider}" if self.inner_provider else "langchain",
            method="CHAT",
            url=f"langchain://{self.inner_provider}/chat_model" if self.inner_provider else "langchain://chat_model",
            request_headers=None,
            request_body=request_body,
            response_status=200,
            response_headers=None,
            response_body=result,
            cwd=self._current_call_cwd(),
            model_name=self.inner_model_spec,
        )

    def _log_error(self, request_body: dict[str, Any], error: BaseException) -> None:
        session_id = self._current_session_id()
        if not session_id:
            return
        self._session_logger.log_api_pair(
            session_id=session_id,
            source=f"langchain:{self.inner_provider}" if self.inner_provider else "langchain",
            method="CHAT",
            url=f"langchain://{self.inner_provider}/chat_model" if self.inner_provider else "langchain://chat_model",
            request_headers=None,
            request_body=request_body,
            response_status="error",
            response_headers=None,
            response_body={"error": str(error), "type": type(error).__name__},
            cwd=self._current_call_cwd(),
            model_name=self.inner_model_spec,
        )

    def _bound_tool_descriptors(self) -> list[dict[str, Any]] | None:
        if not self._bound_tools:
            return None
        tools = self._bound_tools
        if not isinstance(tools, (list, tuple)):
            tools = [tools]
        descriptors: list[dict[str, Any]] = []
        for tool in tools:
            name = getattr(tool, "name", None) or getattr(tool, "__name__", None) or type(tool).__name__
            descriptors.append({
                "name": str(name),
                "type": type(tool).__name__,
            })
        return descriptors


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


def _instantiate_class_path(class_path: str, *, model_name: str, kwargs: dict[str, Any]) -> BaseChatModel:
    if ":" not in class_path:
        raise ValueError(f"Invalid class_path: {class_path}")
    module_path, class_name = class_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    if not isinstance(cls, type) or not issubclass(cls, BaseChatModel):
        raise TypeError(f"{class_path} is not a BaseChatModel subclass")
    return cls(model=model_name, **kwargs)


def _ensure_ai_message(message: Any) -> AIMessage:
    if isinstance(message, AIMessage):
        return message
    content = getattr(message, "content", message)
    additional_kwargs = getattr(message, "additional_kwargs", {})
    response_metadata = getattr(message, "response_metadata", {})
    return AIMessage(
        content=content,
        additional_kwargs=additional_kwargs,
        response_metadata=response_metadata,
    )


def _ensure_ai_message_chunk(message: Any) -> AIMessageChunk:
    if isinstance(message, AIMessageChunk):
        return message
    if isinstance(message, BaseMessageChunk):
        return AIMessageChunk(
            content=getattr(message, "content", ""),
            additional_kwargs=getattr(message, "additional_kwargs", {}) or {},
            response_metadata=getattr(message, "response_metadata", {}) or {},
            id=getattr(message, "id", None),
        )
    ai_message = _ensure_ai_message(message)
    return AIMessageChunk(
        content=ai_message.content,
        additional_kwargs=ai_message.additional_kwargs,
        response_metadata=ai_message.response_metadata,
        id=ai_message.id,
    )


def _merge_chunks_to_result(chunks: list[ChatGenerationChunk]) -> ChatResult:
    if not chunks:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=""))])
    content_parts: list[str] = []
    additional_kwargs: dict[str, Any] = {}
    response_metadata: dict[str, Any] = {}
    for chunk in chunks:
        message = chunk.message
        content = getattr(message, "content", "")
        if isinstance(content, str):
            content_parts.append(content)
        additional_kwargs.update(getattr(message, "additional_kwargs", {}) or {})
        response_metadata.update(getattr(message, "response_metadata", {}) or {})
    return ChatResult(
        generations=[
            ChatGeneration(
                message=AIMessage(
                    content="".join(content_parts),
                    additional_kwargs=additional_kwargs,
                    response_metadata=response_metadata,
                )
            )
        ]
    )


def _load_gigachat_kwargs() -> dict[str, Any]:
    env = parse_env_file(DEEPAGENTS_ENV_PATH)
    merged = {**env, **{k: v for k, v in os.environ.items() if k.startswith("GIGACHAT_")}}
    kwargs: dict[str, Any] = {}
    string_keys = {
        "GIGACHAT_BASE_URL": "base_url",
        "GIGACHAT_AUTH_URL": "auth_url",
        "GIGACHAT_CREDENTIALS": "credentials",
        "GIGACHAT_SCOPE": "scope",
        "GIGACHAT_ACCESS_TOKEN": "access_token",
        "GIGACHAT_USER": "user",
        "GIGACHAT_PASSWORD": "password",
        "GIGACHAT_CA_BUNDLE_FILE": "ca_bundle_file",
        "GIGACHAT_CERT_FILE": "cert_file",
        "GIGACHAT_KEY_FILE": "key_file",
        "GIGACHAT_KEY_FILE_PASSWORD": "key_file_password",
    }
    for env_key, kwarg in string_keys.items():
        value = str(merged.get(env_key, "")).strip()
        if value:
            kwargs[kwarg] = value
    float_keys = {
        "GIGACHAT_TIMEOUT": "timeout",
        "GIGACHAT_RETRY_BACKOFF_FACTOR": "retry_backoff_factor",
    }
    for env_key, kwarg in float_keys.items():
        value = str(merged.get(env_key, "")).strip()
        if value:
            try:
                kwargs[kwarg] = float(value)
            except ValueError:
                pass
    int_keys = {
        "GIGACHAT_MAX_CONNECTIONS": "max_connections",
        "GIGACHAT_MAX_RETRIES": "max_retries",
    }
    for env_key, kwarg in int_keys.items():
        value = str(merged.get(env_key, "")).strip()
        if value:
            try:
                kwargs[kwarg] = int(value)
            except ValueError:
                pass
    bool_keys = {
        "GIGACHAT_VERIFY_SSL_CERTS": "verify_ssl_certs",
        "GIGACHAT_PROFANITY_CHECK": "profanity_check",
    }
    for env_key, kwarg in bool_keys.items():
        value = str(merged.get(env_key, "")).strip().lower()
        if value in {"1", "true", "yes", "on"}:
            kwargs[kwarg] = True
        elif value in {"0", "false", "no", "off"}:
            kwargs[kwarg] = False
    flags = str(merged.get("GIGACHAT_FLAGS", "")).strip()
    if flags:
        kwargs["flags"] = [flag.strip() for flag in flags.split(",") if flag.strip()]
    return kwargs
