import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from finance_data import ConfigurationError, DataAccess, DatabentoConfig, Settings, WRDSConfig


class ConfigurationTests(unittest.TestCase):
    def test_explicit_file_process_precedence_and_no_environment_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("WRDS_USERNAME=local-user\nWRDS_PASSWORD='literal-${OTHER}'\n"
                            "DATABENTO_API_KEY=file-key\nLSEG_APP_KEY=local-app-key\n")
            before = dict(os.environ)
            settings = Settings.from_env(path, environ={"DATABENTO_API_KEY": "process-key"})
            self.assertEqual(dict(os.environ), before)
            self.assertEqual(settings.wrds.username, "local-user")
            self.assertEqual(settings.wrds.password, "literal-${OTHER}")
            self.assertEqual(settings.databento.api_key, "process-key")
            for secret in ("local-user", "literal-${OTHER}", "process-key", "local-app-key"):
                self.assertNotIn(secret, repr(settings))

    def test_providers_read_only_their_own_settings(self):
        config = DatabentoConfig.from_env(environ={"WRDS_PORT": "invalid", "DATABENTO_API_KEY": "key"})
        self.assertEqual(config.api_key, "key")
        self.assertIsNone(Settings.from_env(environ={}).wrds.username)
        with self.assertRaises(ConfigurationError):
            WRDSConfig.from_env(environ={"WRDS_PORT": "invalid"})

    def test_missing_explicit_file_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ConfigurationError):
                Settings.from_env(Path(directory) / "missing.env", environ={})

    def test_direct_wrds_configuration_rejects_invalid_connection_numbers(self):
        for kwargs in ({"port": 0}, {"port": 65536}, {"port": True},
                       {"connect_timeout": 0}, {"connect_timeout": 1.5},
                       {"statement_timeout_ms": -1}, {"statement_timeout_ms": False},
                       {"statement_timeout_ms": "0 -c default_transaction_read_only=off"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ConfigurationError):
                WRDSConfig(**kwargs)
        self.assertEqual(WRDSConfig(statement_timeout_ms=0).statement_timeout_ms, 0)

    def test_data_access_does_not_open_providers(self):
        providers = [Mock(), Mock(), Mock()]
        with DataAccess(Settings(), wrds=providers[0], lseg=providers[1], databento=providers[2]):
            for provider in providers:
                provider.open.assert_not_called()
        for provider in providers:
            provider.close.assert_called_once_with()

    def test_all_providers_cleaned_even_if_one_close_fails(self):
        providers = [Mock(), Mock(), Mock()]
        providers[0].close.side_effect = RuntimeError("cleanup failed")
        access = DataAccess(Settings(), wrds=providers[0], lseg=providers[1], databento=providers[2])
        with self.assertRaises(ExceptionGroup):
            access.close()
        for provider in providers:
            provider.close.assert_called_once_with()

    def test_import_and_assembly_do_not_connect_or_prompt(self):
        program = '''
from unittest.mock import patch
with patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')) as connect, \\
     patch('builtins.input', side_effect=AssertionError('Prompt forbidden')) as prompt:
    from finance_data import DataAccess, Settings
    access = DataAccess(Settings.from_env(environ={}))
    access.close()
    assert not connect.called and not prompt.called
'''
        result = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
