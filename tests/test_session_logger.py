import os
import json
import unittest
from pathlib import Path

from deepagents_logs.core.session_logger import SessionArtifactLogger


class SessionLoggerTests(unittest.TestCase):
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

    def test_log_api_pair_writes_local_files(self):
        tmp_path = Path(self.id().replace(".", "_"))
        tmp_path.mkdir(exist_ok=True)
        self._configure_local_logging(tmp_path)
        logger = SessionArtifactLogger()
        logger.log_api_pair(
            session_id="session-1",
            source="gigachat",
            method="POST",
            url="https://example.com/chat",
            request_headers={"authorization": "secret"},
            request_body={"messages": []},
            response_status=200,
            response_headers={"content-type": "application/json"},
            response_body={"ok": True},
            cwd="/tmp/project",
            model_name="GigaChat-2-Max",
        )
        files = list((tmp_path / "log-export").rglob("*_request.json"))
        self.assertEqual(len(files), 1)
        self._clear_logging_env()
        self._remove_tree(tmp_path)

    def test_append_hook_event_updates_meta_count(self):
        tmp_path = Path(self.id().replace(".", "_"))
        tmp_path.mkdir(exist_ok=True)
        self._configure_local_logging(tmp_path)
        logger = SessionArtifactLogger()
        logger.append_hook_event(
            "session-1",
            {"event": "session.start", "thread_id": "session-1"},
            cwd="/tmp/project",
        )
        meta_files = list((tmp_path / "log-export").rglob("session-meta.json"))
        self.assertEqual(len(meta_files), 1)
        meta = json.loads(meta_files[0].read_text())
        self.assertEqual(meta["hook_events"], 1)
        self._clear_logging_env()
        self._remove_tree(tmp_path)


if __name__ == "__main__":
    unittest.main()
