from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from functools import cached_property
from typing import Any

import gigachat
from gigachat.api import auth as auth_api
from gigachat.api import chat as chat_api
from gigachat.api import models as models_api
from gigachat.api import tools as tools_api
from gigachat.client import _parse_chat
from langchain_gigachat.chat_models import GigaChat as LangChainGigaChat

from deepagents_logs.core.session_logger import SessionArtifactLogger, absolute_url, build_request_body
from deepagents_logs.core.serialize import to_serializable
from deepagents_logs.providers.base import ProviderLoggingMixin


class LoggedGigaChatSDK(ProviderLoggingMixin, gigachat.GigaChat):
    source_name = "gigachat"

    def _log_pair(self, req_kwargs: dict[str, Any], response_body: Any, *, status: int | str | None = 200) -> None:
        session_id = self._ensure_session_id()
        if not session_id:
            return
        self._session_logger.log_api_pair(
            session_id=session_id,
            source=self.source_name,
            method=str(req_kwargs.get("method", "POST")),
            url=absolute_url(self._settings.base_url, str(req_kwargs.get("url", ""))),
            request_headers=to_serializable(req_kwargs.get("headers", {})),
            request_body=build_request_body(req_kwargs),
            response_status=status,
            response_headers=None,
            response_body=response_body,
            cwd=self._current_cwd(),
            model_name=self._settings.model,
        )

    def _extract_prompts(self, chat_data: Any) -> None:
        session_id = self._ensure_session_id()
        if not session_id:
            return
        payload = to_serializable(chat_data)
        prompts: list[str] = []
        for message in payload.get("messages", []):
            if message.get("role") != "user":
                continue
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                prompts.append(content.strip())
        if prompts:
            self._session_logger.append_prompt(session_id, prompts, timestamp=self._session_logger.ensure_state(session_id, self._current_cwd()).started_at, cwd=self._current_cwd())

    def _update_token(self) -> None:
        needs_refresh = not self._is_token_usable() and (
            bool(self._settings.credentials) or bool(self._settings.user and self._settings.password)
        )
        if not needs_refresh:
            return super()._update_token()
        if self._settings.credentials:
            req_kwargs = auth_api._get_auth_kwargs(
                url=self._settings.auth_url,
                credentials=self._settings.credentials,
                scope=self._settings.scope,
            )
        else:
            req_kwargs = auth_api._get_token_kwargs(
                user=self._settings.user,
                password=self._settings.password,
            )
        try:
            super()._update_token()
            self._log_pair(req_kwargs, self._access_token, status=200)
        except Exception as exc:
            self._log_pair(req_kwargs, {"error": str(exc), "type": type(exc).__name__}, status="error")
            raise

    async def _aupdate_token(self) -> None:
        needs_refresh = not self._is_token_usable() and (
            bool(self._settings.credentials) or bool(self._settings.user and self._settings.password)
        )
        if not needs_refresh:
            return await super()._aupdate_token()
        if self._settings.credentials:
            req_kwargs = auth_api._get_auth_kwargs(
                url=self._settings.auth_url,
                credentials=self._settings.credentials,
                scope=self._settings.scope,
            )
        else:
            req_kwargs = auth_api._get_token_kwargs(
                user=self._settings.user,
                password=self._settings.password,
            )
        try:
            await super()._aupdate_token()
            self._log_pair(req_kwargs, self._access_token, status=200)
        except Exception as exc:
            self._log_pair(req_kwargs, {"error": str(exc), "type": type(exc).__name__}, status="error")
            raise

    def get_models(self):
        req_kwargs = models_api._get_models_kwargs(access_token=self.token)
        try:
            response = super().get_models()
            self._log_pair(req_kwargs, response)
            return response
        except Exception as exc:
            self._log_pair(req_kwargs, {"error": str(exc), "type": type(exc).__name__}, status="error")
            raise

    async def aget_models(self):
        req_kwargs = models_api._get_models_kwargs(access_token=self.token)
        try:
            response = await super().aget_models()
            self._log_pair(req_kwargs, response)
            return response
        except Exception as exc:
            self._log_pair(req_kwargs, {"error": str(exc), "type": type(exc).__name__}, status="error")
            raise

    def tokens_count(self, input_: list[str], model: str | None = None):
        effective_model = model or self._settings.model or gigachat.client.GIGACHAT_MODEL
        req_kwargs = tools_api._get_tokens_count_kwargs(input_=input_, model=effective_model, access_token=self.token)
        try:
            response = super().tokens_count(input_, model=model)
            self._log_pair(req_kwargs, response)
            return response
        except Exception as exc:
            self._log_pair(req_kwargs, {"error": str(exc), "type": type(exc).__name__}, status="error")
            raise

    async def atokens_count(self, input_: list[str], model: str | None = None):
        effective_model = model or self._settings.model or gigachat.client.GIGACHAT_MODEL
        req_kwargs = tools_api._get_tokens_count_kwargs(input_=input_, model=effective_model, access_token=self.token)
        try:
            response = await super().atokens_count(input_, model=model)
            self._log_pair(req_kwargs, response)
            return response
        except Exception as exc:
            self._log_pair(req_kwargs, {"error": str(exc), "type": type(exc).__name__}, status="error")
            raise

    def chat(self, payload):
        chat_data = _parse_chat(payload, self._settings)
        self._extract_prompts(chat_data)
        req_kwargs = chat_api._get_chat_kwargs(chat=chat_data, access_token=self.token)
        try:
            response = super().chat(payload)
            self._log_pair(req_kwargs, response)
            return response
        except Exception as exc:
            self._log_pair(req_kwargs, {"error": str(exc), "type": type(exc).__name__}, status="error")
            raise

    async def achat(self, payload):
        chat_data = _parse_chat(payload, self._settings)
        self._extract_prompts(chat_data)
        req_kwargs = chat_api._get_chat_kwargs(chat=chat_data, access_token=self.token)
        try:
            response = await super().achat(payload)
            self._log_pair(req_kwargs, response)
            return response
        except Exception as exc:
            self._log_pair(req_kwargs, {"error": str(exc), "type": type(exc).__name__}, status="error")
            raise

    def stream(self, payload) -> Iterator[Any]:
        chat_data = _parse_chat(payload, self._settings)
        self._extract_prompts(chat_data)
        req_kwargs = chat_api._get_stream_kwargs(chat=chat_data, access_token=self.token)
        chunks: list[Any] = []
        try:
            for chunk in super().stream(payload):
                chunks.append(chunk)
                yield chunk
            self._log_pair(req_kwargs, {"chunks": chunks})
        except Exception as exc:
            self._log_pair(req_kwargs, {"error": str(exc), "type": type(exc).__name__}, status="error")
            raise

    async def astream(self, payload) -> AsyncIterator[Any]:
        chat_data = _parse_chat(payload, self._settings)
        self._extract_prompts(chat_data)
        req_kwargs = chat_api._get_stream_kwargs(chat=chat_data, access_token=self.token)
        chunks: list[Any] = []
        try:
            async for chunk in super().astream(payload):
                chunks.append(chunk)
                yield chunk
            self._log_pair(req_kwargs, {"chunks": chunks})
        except Exception as exc:
            self._log_pair(req_kwargs, {"error": str(exc), "type": type(exc).__name__}, status="error")
            raise


class LoggedGigaChat(LangChainGigaChat):
    allow_any_tool_choice_fallback: bool = True

    @cached_property
    def _client(self) -> LoggedGigaChatSDK:
        return LoggedGigaChatSDK(**self._get_client_init_kwargs())
