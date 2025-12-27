import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from ai_context_studio.config import ConfigManager

class TestConfigManager:
    @pytest.fixture
    def mock_paths(self):
        with patch('ai_context_studio.config.CONFIG_DIR', new_callable=MagicMock) as mock_dir, \
             patch('ai_context_studio.config.CONFIG_FILE', new_callable=MagicMock) as mock_file, \
             patch('ai_context_studio.config.KEY_FILE', new_callable=MagicMock) as mock_key:

            mock_dir.exists.return_value = True
            mock_file.exists.return_value = False
            mock_key.exists.return_value = False

            yield mock_dir, mock_file, mock_key

    def test_singleton(self, mock_paths):
        ConfigManager._instance = None
        c1 = ConfigManager()
        c2 = ConfigManager()
        assert c1 is c2

    def test_load_default_config(self, mock_paths):
        ConfigManager._instance = None
        manager = ConfigManager()
        assert manager._config == {}

    def test_set_and_get(self, mock_paths):
        ConfigManager._instance = None
        manager = ConfigManager()
        manager.set('test_key', 'test_value')
        assert manager.get('test_key') == 'test_value'
        assert manager.get('non_existent') is None

    @patch('ai_context_studio.config.CRYPTO_AVAILABLE', False)
    def test_api_key_no_crypto(self, mock_paths):
        ConfigManager._instance = None
        manager = ConfigManager()
        manager.set_api_key('secret_key')
        assert manager.get_api_key() == 'secret_key'
        assert manager.get('api_key') == 'secret_key'
