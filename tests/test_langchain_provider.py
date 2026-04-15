import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from pydantic import Field

    from deepagents_logs.providers.langchain import LoggedLangChainModel

    HAS_LANGCHAIN = True
except Exception:
    HAS_LANGCHAIN = False

try:
    import langchain_gigachat.chat_models  # noqa: F401
    HAS_LANGCHAIN_GIGACHAT = True
except Exception:
    HAS_LANGCHAIN_GIGACHAT = False


if HAS_LANGCHAIN:
    class FakeInnerModel(BaseChatModel):
        model: str = "fake"
        callbacks: list = Field(default_factory=list)
        profile: dict | None = Field(
            default_factory=lambda: {"tool_calling": True, "max_input_tokens": 4096}
        )

        @property
        def _llm_type(self) -> str:
            return "fake-inner"

        @property
        def _identifying_params(self) -> dict:
            return {"model": self.model}

        def bind_tools(self, tools, *, tool_choice=None, **kwargs):  # noqa: ANN001, ARG002
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001, ARG002
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content="logged reply"))]
            )


@unittest.skipUnless(HAS_LANGCHAIN, "langchain runtime not available in this Python env")
class LoggedLangChainModelTests(unittest.TestCase):
    def _configure_local_logging(self, tmp_path: Path) -> None:
        os.environ["DEEPAGENTS_LOGS_ENABLED"] = "1"
        os.environ["DEEPAGENTS_LOGS_LOCAL_ENABLED"] = "1"
        os.environ["DEEPAGENTS_LOGS_S3_ENABLED"] = "0"
        os.environ["DEEPAGENTS_LOGS_LOCAL_ROOT"] = str(tmp_path / "log-export")
        os.environ["DEEPAGENTS_LOGS_INCLUDE_README"] = "1"

    def _clear_logging_env(self) -> None:
        for key in [
            "DEEPAGENTS_LOGS_ENABLED",
            "DEEPAGENTS_LOGS_LOCAL_ENABLED",
            "DEEPAGENTS_LOGS_S3_ENABLED",
            "DEEPAGENTS_LOGS_LOCAL_ROOT",
            "DEEPAGENTS_LOGS_INCLUDE_README",
        ]:
            os.environ.pop(key, None)

    def _remove_tree(self, path: Path) -> None:
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        path.rmdir()

    def test_logged_langchain_model_writes_request_response_pair(self):
        tmp_path = Path(self.id().replace(".", "_"))
        tmp_path.mkdir(exist_ok=True)
        self._configure_local_logging(tmp_path)
        with patch(
            "deepagents_cli.config.create_model",
            return_value=SimpleNamespace(model=FakeInnerModel(model="fake-model")),
        ):
            wrapper = LoggedLangChainModel(model="openai:gpt-5.4")
        wrapper._current_session_id = lambda: "session-1"
        wrapper._current_call_cwd = lambda: "/tmp/project"

        message = wrapper.invoke("hello from langchain wrapper")
        self.assertEqual(message.content, "logged reply")

        request_files = list((tmp_path / "log-export").rglob("*_request.json"))
        response_files = list((tmp_path / "log-export").rglob("*_response.json"))
        self.assertEqual(len(request_files), 1)
        self.assertEqual(len(response_files), 1)

        request_payload = json.loads(request_files[0].read_text())
        response_payload = json.loads(response_files[0].read_text())
        self.assertEqual(request_payload["source"], "langchain:openai")
        self.assertEqual(request_payload["body"]["model"], "openai:gpt-5.4")
        self.assertEqual(response_payload["status"], 200)

        self._clear_logging_env()
        self._remove_tree(tmp_path)

    @unittest.skipUnless(HAS_LANGCHAIN_GIGACHAT, "langchain_gigachat not available")
    def test_logged_langchain_model_supports_gigachat_inner_model(self):
        tmp_path = Path(self.id().replace(".", "_"))
        tmp_path.mkdir(exist_ok=True)
        self._configure_local_logging(tmp_path)
        with patch("langchain_gigachat.chat_models.GigaChat", FakeInnerModel):
            wrapper = LoggedLangChainModel(model="gigachat:GigaChat-2-Max")
        wrapper._current_session_id = lambda: "session-giga"
        wrapper._current_call_cwd = lambda: "/tmp/project"

        message = wrapper.invoke("hello giga")
        self.assertEqual(message.content, "logged reply")

        request_files = list((tmp_path / "log-export").rglob("*_request.json"))
        self.assertEqual(len(request_files), 1)
        request_payload = json.loads(request_files[0].read_text())
        self.assertEqual(request_payload["source"], "langchain:gigachat")
        self.assertEqual(request_payload["body"]["model"], "gigachat:GigaChat-2-Max")

        self._clear_logging_env()
        self._remove_tree(tmp_path)


if __name__ == "__main__":
    unittest.main()
