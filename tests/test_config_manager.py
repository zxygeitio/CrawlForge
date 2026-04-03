"""
配置管理器测试
"""

import json
import os
import tempfile

import pytest
import yaml

from src.config_manager import (
    ConfigManager,
    CrawlerConfig,
    create_default_config,
)


class TestCrawlerConfig:
    """CrawlerConfig 数据类测试"""

    def test_default_values(self):
        """测试默认值"""
        config = CrawlerConfig()
        assert config.name == "crawler"
        assert config.timeout == 30
        assert config.retry_times == 3
        assert config.concurrent == 5
        assert config.headless is True

    def test_custom_values(self):
        """测试自定义值"""
        config = CrawlerConfig(
            name="test_crawler",
            timeout=60,
            proxy_enabled=True,
        )
        assert config.name == "test_crawler"
        assert config.timeout == 60
        assert config.proxy_enabled is True


class TestConfigManager:
    """ConfigManager 测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as td:
            yield td

    @pytest.fixture
    def manager(self, temp_dir):
        """创建配置管理器实例"""
        # 重置单例，设置 CRAWLER_CONFIG_ROOT 使保存测试能写到 temp_dir
        # （CRAWLER_CONFIG_ROOT 作为保存的目标根目录；加载时同样受其约束）
        ConfigManager._instance = None
        old_env = os.environ.get("CRAWLER_CONFIG_ROOT")
        os.environ["CRAWLER_CONFIG_ROOT"] = temp_dir
        mgr = ConfigManager()
        yield mgr
        if old_env is None:
            os.environ.pop("CRAWLER_CONFIG_ROOT", None)
        else:
            os.environ["CRAWLER_CONFIG_ROOT"] = old_env

    @pytest.fixture
    def sample_yaml_config(self, temp_dir):
        """创建示例 YAML 配置"""
        config_path = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "name": "test_crawler",
            "timeout": 60,
            "retry_times": 5,
            "headless": False,
            "proxy_enabled": True,
            "rate_limit": 20.0,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)
        return config_path

    @pytest.fixture
    def sample_json_config(self, temp_dir):
        """创建示例 JSON 配置"""
        config_path = os.path.join(temp_dir, "config.json")
        config_data = {
            "name": "json_crawler",
            "timeout": 45,
            "concurrent": 10,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)
        return config_path

    def test_singleton_pattern(self):
        """测试单例模式"""
        ConfigManager._instance = None
        m1 = ConfigManager()
        m2 = ConfigManager()
        assert m1 is m2

    def test_load_from_yaml(self, manager, sample_yaml_config):
        """测试从 YAML 加载配置"""
        config = manager.load_from_yaml(sample_yaml_config)

        assert config.name == "test_crawler"
        assert config.timeout == 60
        assert config.retry_times == 5
        assert config.headless is False
        assert config.proxy_enabled is True
        assert config.rate_limit == 20.0

    def test_load_from_json(self, manager, sample_json_config):
        """测试从 JSON 加载配置"""
        config = manager.load_from_json(sample_json_config)

        assert config.name == "json_crawler"
        assert config.timeout == 45
        assert config.concurrent == 10

    def test_load_from_dict(self, manager):
        """测试从字典加载配置"""
        config_dict = {
            "name": "dict_crawler",
            "timeout": 120,
        }
        config = manager.load_from_dict(config_dict)

        assert config.name == "dict_crawler"
        assert config.timeout == 120
        assert config.concurrent == 5  # 默认值

    def test_load_yaml_file_not_found(self, manager):
        """测试加载不存在的 YAML 文件（路径在 cwd 内）"""
        with pytest.raises(FileNotFoundError):
            manager.load_from_yaml("nonexistent_dir/config.yaml")

    def test_load_json_file_not_found(self, manager):
        """测试加载不存在的 JSON 文件（路径在 cwd 内）"""
        with pytest.raises(FileNotFoundError):
            manager.load_from_json("nonexistent_dir/config.json")

    def test_get_config(self, manager):
        """测试获取配置"""
        manager.load_from_dict({"name": "test"})
        config = manager.get_config()
        assert config.name == "test"

    def test_get_config_when_not_loaded(self, manager):
        """测试未加载时获取配置返回 None"""
        ConfigManager._instance = None
        m = ConfigManager()
        assert m.get_config() is None

    def test_update_config(self, manager):
        """测试更新配置"""
        manager.load_from_dict({"name": "original"})
        manager.update_config(name="updated", timeout=100)

        config = manager.get_config()
        assert config.name == "updated"
        assert config.timeout == 100

    def test_update_config_no_config_loaded(self, manager):
        """测试未加载时更新配置抛出异常"""
        with pytest.raises(RuntimeError, match="No config loaded"):
            manager.update_config(name="test")

    def test_save_to_yaml(self, manager, temp_dir):
        """测试保存为 YAML"""
        manager.load_from_dict({"name": "save_test", "timeout": 30})
        save_path = os.path.join(temp_dir, "saved.yaml")

        manager.save_to_yaml(save_path)

        with open(save_path, "r", encoding="utf-8") as f:
            saved = yaml.safe_load(f)
        assert saved["name"] == "save_test"

    def test_save_to_json(self, manager, temp_dir):
        """测试保存为 JSON"""
        manager.load_from_dict({"name": "save_test", "timeout": 30})
        save_path = os.path.join(temp_dir, "saved.json")

        manager.save_to_json(save_path)

        with open(save_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["name"] == "save_test"

    def test_save_without_config(self, manager):
        """测试未加载时保存抛出异常"""
        with pytest.raises(RuntimeError, match="No config to save"):
            manager.save_to_yaml("/path/to/save.yaml")

    def test_env_override_timeout(self, manager, temp_dir):
        """测试环境变量覆盖 timeout"""
        config_path = os.path.join(temp_dir, "env_test.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"timeout": 30}, f)

        os.environ["CRAWLER_TIMEOUT"] = "100"
        try:
            manager.load_from_yaml(config_path)
            assert manager.get_config().timeout == 100
        finally:
            os.environ.pop("CRAWLER_TIMEOUT", None)

    def test_env_override_proxy_enabled(self, manager, temp_dir):
        """测试环境变量覆盖 proxy_enabled"""
        config_path = os.path.join(temp_dir, "env_test2.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"proxy_enabled": False}, f)

        os.environ["CRAWLER_PROXY_ENABLED"] = "true"
        try:
            manager.load_from_yaml(config_path)
            assert manager.get_config().proxy_enabled is True
        finally:
            os.environ.pop("CRAWLER_PROXY_ENABLED", None)

    def test_env_override_headless(self, manager, temp_dir):
        """测试环境变量覆盖 headless"""
        config_path = os.path.join(temp_dir, "env_test3.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"headless": True}, f)

        os.environ["CRAWLER_HEADLESS"] = "false"
        try:
            manager.load_from_yaml(config_path)
            assert manager.get_config().headless is False
        finally:
            os.environ.pop("CRAWLER_HEADLESS", None)


    def test_path_traversal_yaml(self, manager, temp_dir):
        """测试 YAML 加载时防止 path traversal"""
        # 在 cwd（项目目录）内创建合法配置
        legitimate_path = os.path.join(os.getcwd(), "tests", "legitimate_test_cfg.yaml")
        os.makedirs(os.path.dirname(legitimate_path), exist_ok=True)
        with open(legitimate_path, "w", encoding="utf-8") as f:
            yaml.dump({"name": "legitimate"}, f)
        try:
            # 正常加载应该成功（路径在 cwd 内）
            config = manager.load_from_yaml(legitimate_path)
            assert config.name == "legitimate"

            # 尝试 path traversal 应该被拒绝（逃逸 cwd）
            bad_path = os.path.join(temp_dir, "..", "..", "etc", "passwd")
            with pytest.raises(ValueError, match="Path traversal attempt detected"):
                manager.load_from_yaml(bad_path)
        finally:
            os.unlink(legitimate_path)

    def test_path_traversal_json(self, manager, temp_dir):
        """测试 JSON 加载时防止 path traversal"""
        # 尝试 path traversal 应该被拒绝
        bad_path = os.path.join(temp_dir, "..", "..", "etc", "passwd")
        with pytest.raises(ValueError, match="Path traversal attempt detected"):
            manager.load_from_json(bad_path)

    def test_path_traversal_save(self, manager, temp_dir):
        """测试保存时防止 path traversal"""
        manager.load_from_dict({"name": "save_test", "timeout": 30})

        # 尝试保存到允许目录之外应该被拒绝
        bad_path = os.path.join(temp_dir, "..", "..", "tmp", "evil.yaml")
        with pytest.raises(ValueError, match="Path traversal attempt detected"):
            manager.save_to_yaml(bad_path)


class TestCreateDefaultConfig:
    """create_default_config 测试"""

    def test_create_default_config(self, temp_dir):
        """测试创建默认配置"""
        config_path = os.path.join(temp_dir, "default.yaml")
        result_path = create_default_config(config_path)

        assert result_path == config_path
        assert os.path.exists(config_path)

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["name"] == "crawler"
        assert config["timeout"] == 30
