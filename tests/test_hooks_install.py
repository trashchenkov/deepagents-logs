import json
from pathlib import Path
import unittest

from deepagents_logs.installers.hooks_config import install_hook, managed_hook_command, remove_hook


class HooksInstallTests(unittest.TestCase):
    def test_install_hook_adds_managed_hook(self):
        tmp_path = Path(self.id().replace(".", "_"))
        tmp_path.mkdir(exist_ok=True)
        path = tmp_path / "hooks.json"
        install_hook(path)
        payload = json.loads(path.read_text())
        self.assertTrue(
            any(hook["command"] == managed_hook_command() for hook in payload["hooks"])
        )
        path.unlink()
        tmp_path.rmdir()

    def test_remove_hook_deletes_managed_hook(self):
        tmp_path = Path(self.id().replace(".", "_"))
        tmp_path.mkdir(exist_ok=True)
        path = tmp_path / "hooks.json"
        install_hook(path)
        remove_hook(path)
        payload = json.loads(path.read_text())
        self.assertFalse(
            any(hook["command"] == managed_hook_command() for hook in payload["hooks"])
        )
        path.unlink()
        tmp_path.rmdir()


if __name__ == "__main__":
    unittest.main()
