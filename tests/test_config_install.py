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

    def test_logged_provider_detects_normalized_deepagents_config(self):
        tmp_path = Path(self.id().replace(".", "_"))
        tmp_path.mkdir(exist_ok=True)
        config = tmp_path / "config.toml"
        config.write_text(
            '[models.providers.gigachat_logged]\n'
            'class_path = "deepagents_logs.providers.gigachat:LoggedGigaChat"\n'
            'enabled = true\n'
        )
        self.assertTrue(logged_provider_installed(config))
        config.unlink()
        tmp_path.rmdir()


class CliStatusTests(unittest.TestCase):
    def test_gigachat_env_status_redacts_secrets_but_shows_safe_values(self):
        from deepagents_logs.cli import GIGACHAT_STATUS_ENV_KEYS, GIGACHAT_SECRET_ENV_KEYS

        env = {
            "GIGACHAT_CREDENTIALS": "secret",
            "GIGACHAT_SCOPE": "GIGACHAT_API_CORP",
            "GIGACHAT_VERIFY_SSL_CERTS": "false",
        }
        status = {
            key: (
                "present"
                if key in GIGACHAT_SECRET_ENV_KEYS and bool(env.get(key))
                else "missing"
                if key in GIGACHAT_SECRET_ENV_KEYS
                else env.get(key, "")
            )
            for key in GIGACHAT_STATUS_ENV_KEYS
        }

        self.assertEqual(status["GIGACHAT_CREDENTIALS"], "present")
        self.assertEqual(status["GIGACHAT_PASSWORD"], "missing")
        self.assertEqual(status["GIGACHAT_SCOPE"], "GIGACHAT_API_CORP")
        self.assertEqual(status["GIGACHAT_VERIFY_SSL_CERTS"], "false")


if __name__ == "__main__":
    unittest.main()
