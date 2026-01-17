#!/usr/bin/env python3
# ruff: noqa: S101
"""設定パースのユニットテスト"""

import pathlib

import pytest
import yaml


class TestConfigLoad:
    """設定ファイル読み込みのテスト"""

    def test_load_example_config(self):
        """example設定ファイルの読み込み"""
        import rasp_shutter.config

        config = rasp_shutter.config.load("config.example.yaml", pathlib.Path("config.schema"))

        assert config is not None
        assert hasattr(config, "shutter")
        assert hasattr(config, "liveness")
        assert hasattr(config, "slack")

    def test_config_shutter_list(self):
        """シャッターリストの確認"""
        import rasp_shutter.config

        config = rasp_shutter.config.load("config.example.yaml", pathlib.Path("config.schema"))

        assert len(config.shutter) > 0
        for shutter in config.shutter:
            assert hasattr(shutter, "name")
            assert hasattr(shutter, "endpoint")
            assert hasattr(shutter.endpoint, "open")
            assert hasattr(shutter.endpoint, "close")

    def test_config_liveness(self):
        """Liveness設定の確認"""
        import rasp_shutter.config

        config = rasp_shutter.config.load("config.example.yaml", pathlib.Path("config.schema"))

        assert hasattr(config.liveness, "file")
        assert hasattr(config.liveness.file, "scheduler")

    def test_config_slack(self):
        """Slack設定の確認"""
        import rasp_shutter.config

        config = rasp_shutter.config.load("config.example.yaml", pathlib.Path("config.schema"))

        assert hasattr(config.slack, "bot_token")
        # SlackErrorOnlyConfigの場合はerror属性を持つ
        if hasattr(config.slack, "error"):
            assert hasattr(config.slack.error, "channel")  # type: ignore[union-attr]


class TestToMyLibWebappConfig:
    """my_lib.webapp設定への変換テスト"""

    def test_convert_to_webapp_config(self):
        """webapp設定への変換"""
        import rasp_shutter.config

        config = rasp_shutter.config.load("config.example.yaml", pathlib.Path("config.schema"))
        webapp_config = rasp_shutter.config.to_my_lib_webapp_config(config)

        assert webapp_config is not None
        assert hasattr(webapp_config, "static_dir_path")
        assert hasattr(webapp_config, "data")
        assert hasattr(webapp_config.data, "schedule_file_path")


class TestConfigValidation:
    """設定バリデーションのテスト"""

    def test_missing_config_file(self):
        """存在しない設定ファイル"""
        import my_lib.config

        with pytest.raises(my_lib.config.ConfigFileNotFoundError):
            my_lib.config.load("nonexistent.yaml", pathlib.Path("config.schema"))

    def test_invalid_yaml_syntax(self, tmp_path):
        """不正なYAML構文"""
        import my_lib.config

        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("invalid: yaml: syntax:")

        with pytest.raises(yaml.YAMLError):
            my_lib.config.load(str(invalid_yaml), pathlib.Path("config.schema"))
