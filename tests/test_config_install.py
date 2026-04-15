from pathlib import Path
import unittest

from deepagents_logs.installers.deepagents_config import (
    configured_default_model,
    install_logged_gigachat_provider,
    logged_provider_installed,
    remove_logged_provider,
)


class ConfigInstallTests(unittest.TestCase):
    def test_install_logged_provider_updates_models_default(self):
        tmp_path = Path(self.id().replace(".", "_"))
        tmp_path.mkdir(exist_ok=True)
        config = tmp_path / "config.toml"
        config.write_text('[models]\ndefault = "openai:gpt-4o"\n')
        install_logged_gigachat_provider(
            config, default_model="GigaChat-2-Max", set_default=True
        )
        text = config.read_text()
        self.assertIn('default = "gigachat_logged:GigaChat-2-Max"', text)
        self.assertEqual(configured_default_model(config), "gigachat_logged:GigaChat-2-Max")
        self.assertTrue(logged_provider_installed(config))
        self.assertIn(
            'class_path = "deepagents_logs.providers.gigachat:LoggedGigaChat"',
            text,
        )
        config.unlink()
        tmp_path.rmdir()

    def test_remove_logged_provider_removes_managed_block(self):
        tmp_path = Path(self.id().replace(".", "_"))
        tmp_path.mkdir(exist_ok=True)
        config = tmp_path / "config.toml"
        install_logged_gigachat_provider(config)
        remove_logged_provider(config)
        text = config.read_text()
        self.assertNotIn("deepagents_logs.providers.gigachat", text)
        self.assertFalse(logged_provider_installed(config))
        config.unlink()
        tmp_path.rmdir()


if __name__ == "__main__":
    unittest.main()
