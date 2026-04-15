from pathlib import Path
import unittest

from deepagents_logs.core.env import parse_env_file
from deepagents_logs.installers.env_config import install_logging_env


class EnvInstallTests(unittest.TestCase):
    def test_install_logging_env_preserves_existing_s3_values(self):
        tmp_path = Path(self.id().replace(".", "_"))
        tmp_path.mkdir(exist_ok=True)
        path = tmp_path / "deepagents-logs.env"
        path.write_text(
            "DEEPAGENTS_LOGS_S3_ENABLED=1\n"
            "DEEPAGENTS_LOGS_S3_BUCKET=my-bucket\n"
            "AWS_ACCESS_KEY_ID=existing-key\n"
            "AWS_SECRET_ACCESS_KEY=existing-secret\n"
            "AWS_ENDPOINT_URL=https://s3.example.test\n"
        )
        install_logging_env(path)
        parsed = parse_env_file(path)
        self.assertEqual(parsed["DEEPAGENTS_LOGS_S3_ENABLED"], "1")
        self.assertEqual(parsed["DEEPAGENTS_LOGS_S3_BUCKET"], "my-bucket")
        self.assertEqual(parsed["AWS_ACCESS_KEY_ID"], "existing-key")
        self.assertEqual(parsed["AWS_SECRET_ACCESS_KEY"], "existing-secret")
        self.assertEqual(parsed["AWS_ENDPOINT_URL"], "https://s3.example.test")
        path.unlink()
        tmp_path.rmdir()


if __name__ == "__main__":
    unittest.main()
