"""Tests for logger.py"""

import sys
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestLogManagerSetup:
    """Test LogManager.setup() functionality"""

    def test_setup_default_initialization(self):
        """Test LogManager.setup() with default parameters"""
        from src.logger import LogManager

        # Reset singleton state for isolated test
        LogManager._instance = None
        LogManager._initialized = False

        manager = LogManager()
        result = manager.setup()

        assert result is manager
        assert manager._log_level == "INFO"
        assert manager._enable_console is True

        # Cleanup global state
        LogManager._instance = None
        LogManager._initialized = False

    def test_setup_with_custom_parameters(self):
        """Test LogManager.setup() with custom log level and file"""
        from src.logger import LogManager

        # Reset singleton state
        LogManager._instance = None
        LogManager._initialized = False

        manager = LogManager()
        result = manager.setup(
            log_level="DEBUG",
            log_file="test.log",
            log_dir="test_logs",
            enable_console=False
        )

        assert result is manager
        assert manager._log_level == "DEBUG"
        assert manager._enable_console is False

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False


class TestLoguruFallback:
    """Test fallback to StandardLogger when loguru is unavailable"""

    def test_fallback_to_standard_logger(self):
        """Test that LogManager falls back to StandardLogger when loguru not available"""
        from src.logger import LogManager, StandardLogger

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        # Mock loguru as unavailable
        with patch('src.logger.LOGURU_AVAILABLE', False):
            LogManager._instance = None
            LogManager._initialized = False
            manager = LogManager()

            assert isinstance(manager._logger, StandardLogger)

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False

    def test_standard_logger_instantiation(self):
        """Test that StandardLogger can be instantiated"""
        from src.logger import StandardLogger

        logger = StandardLogger()

        assert logger._logger is not None
        assert logger._logger.name == "crawler"
        assert logger._logger.level == logging.INFO


class TestStandardLogger:
    """Test StandardLogger methods"""

    def test_add_file(self, tmp_path):
        """Test StandardLogger.add_file() creates file handler"""
        from src.logger import StandardLogger

        logger = StandardLogger()
        log_file = tmp_path / "test.log"

        logger.add_file(str(log_file), "INFO")

        # Verify file handler was added
        handlers = [h for h in logger._logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(handlers) >= 1

    def test_add_console(self):
        """Test StandardLogger has console handler from init"""
        from src.logger import StandardLogger

        logger = StandardLogger()

        # Verify stream handler was added
        handlers = [h for h in logger._logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(handlers) >= 1

    def test_log_methods(self):
        """Test StandardLogger logging methods don't raise"""
        from src.logger import StandardLogger

        logger = StandardLogger()

        # Should not raise
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")
        logger.critical("critical message")
        logger.success("success message")

    def test_exception_method(self):
        """Test StandardLogger.exception() handles exc_info"""
        from src.logger import StandardLogger

        logger = StandardLogger()

        try:
            raise ValueError("test error")
        except ValueError:
            # Should not raise
            logger.exception("exception occurred")


class TestGetLogger:
    """Test get_logger() function"""

    def test_get_logger_returns_valid_instance(self):
        """Test get_logger() returns a valid LogManager instance"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        logger = get_logger()

        assert logger is not None
        assert isinstance(logger, LogManager)

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False

    def test_get_logger_singleton(self):
        """Test get_logger() returns same instance"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        logger1 = get_logger()
        logger2 = get_logger()

        assert logger1 is logger2

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False


class TestLogManagerMethods:
    """Test LogManager logging methods"""

    def test_debug_method(self):
        """Test LogManager.debug() doesn't raise"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.debug("debug message")

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False

    def test_info_method(self):
        """Test LogManager.info() doesn't raise"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.info("info message")

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False

    def test_warning_method(self):
        """Test LogManager.warning() doesn't raise"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.warning("warning message")

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False

    def test_error_method(self):
        """Test LogManager.error() doesn't raise"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.error("error message")

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False

    def test_critical_method(self):
        """Test LogManager.critical() doesn't raise"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.critical("critical message")

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False

    def test_success_method(self):
        """Test LogManager.success() doesn't raise"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.success("success message")

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False


class TestLogCrawlEvent:
    """Test log_crawl_event method"""

    def test_log_crawl_event_request(self):
        """Test log_crawl_event with request type"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.log_crawl_event("request", "https://example.com", "pending")

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False

    def test_log_crawl_event_success(self):
        """Test log_crawl_event with success type"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.log_crawl_event("success", "https://example.com", "200", duration=1.5)

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False

    def test_log_crawl_event_retry(self):
        """Test log_crawl_event with retry type"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.log_crawl_event("retry", "https://example.com", "retry", error="timeout")

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False

    def test_log_crawl_event_fail(self):
        """Test log_crawl_event with fail type"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.log_crawl_event("fail", "https://example.com", "500", error="server error")

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False


class TestLogProxyEvent:
    """Test log_proxy_event method"""

    def test_log_proxy_event_success(self):
        """Test log_proxy_event with success=True"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.log_proxy_event("http://proxy.example.com:8080", "connected", success=True)

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False

    def test_log_proxy_event_failure(self):
        """Test log_proxy_event with success=False"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.log_proxy_event("http://proxy.example.com:8080", "connection failed", success=False)

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False


class TestLogCaptchaEvent:
    """Test log_captcha_event method"""

    def test_log_captcha_event_solved(self):
        """Test log_captcha_event with solved=True"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.log_captcha_event("image_captcha", solved=True, duration=2.5)

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False

    def test_log_captcha_event_failed(self):
        """Test log_captcha_event with solved=False"""
        from src.logger import get_logger, LogManager

        # Reset singleton
        LogManager._instance = None
        LogManager._initialized = False

        manager = get_logger()
        manager.log_captcha_event("image_captcha", solved=False)

        # Cleanup
        LogManager._instance = None
        LogManager._initialized = False
