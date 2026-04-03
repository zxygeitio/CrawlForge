"""
Monitor 核心模块测试
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.monitor import (
    Monitor,
    AlertLevel,
    AlertRule,
    Alert,
    FileChannel,
    HealthCheckResult,
    HealthStatus,
    HealthChecker,
    MetricsCollector,
    ThresholdAlertRule,
    TrendAlertRule,
    AnomalyAlertRule,
)


# ============== HealthStatus & HealthCheckResult ==============

class TestHealthStatus:
    """HealthStatus 枚举测试"""

    def test_health_status_enum_exists(self):
        """测试 HealthStatus 枚举存在"""
        assert hasattr(HealthStatus, "HEALTHY")
        assert hasattr(HealthStatus, "DEGRADED")
        assert hasattr(HealthStatus, "UNHEALTHY")

    def test_health_status_values(self):
        """测试 HealthStatus 枚举值"""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestHealthCheckResult:
    """HealthCheckResult 数据类测试"""

    def test_health_check_result_creation(self):
        """测试 HealthCheckResult 创建"""
        result = HealthCheckResult(
            component="test_component",
            status=HealthStatus.HEALTHY,
            message="OK",
        )

        assert result.component == "test_component"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "OK"
        assert result.timestamp > 0
        assert result.details == {}

    def test_health_check_result_with_details(self):
        """测试带 details 的 HealthCheckResult"""
        result = HealthCheckResult(
            component="test_component",
            status=HealthStatus.DEGRADED,
            message="Degraded",
            details={"latency": 500, "error_rate": 0.1},
        )

        assert result.details["latency"] == 500
        assert result.details["error_rate"] == 0.1


class TestHealthChecker:
    """HealthChecker 测试"""

    @pytest.fixture
    def checker(self):
        """创建 HealthChecker 实例"""
        return HealthChecker()

    @pytest.mark.asyncio
    async def test_register_and_check(self, checker):
        """测试注册和检查组件"""
        async def mock_check():
            return HealthCheckResult(
                component="mock",
                status=HealthStatus.HEALTHY,
                message="OK",
            )

        checker.register("test_component", mock_check)
        result = await checker.check("test_component")

        assert result.component == "mock"
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_unregistered_component(self, checker):
        """测试检查未注册组件返回 UNHEALTHY"""
        result = await checker.check("nonexistent")

        assert result.status == HealthStatus.UNHEALTHY
        assert "未注册" in result.message

    @pytest.mark.asyncio
    async def test_check_all(self, checker):
        """测试检查所有组件"""
        async def mock_check():
            return HealthCheckResult(
                component="test",
                status=HealthStatus.HEALTHY,
                message="OK",
            )

        checker.register("component1", mock_check)
        checker.register("component2", mock_check)

        results = await checker.check_all()
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_summary_all_healthy(self, checker):
        """测试全部健康时返回 HEALTHY"""
        results = [
            HealthCheckResult(component="c1", status=HealthStatus.HEALTHY),
            HealthCheckResult(component="c2", status=HealthStatus.HEALTHY),
        ]

        summary = checker.get_summary(results)
        assert summary == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_get_summary_with_degraded(self, checker):
        """测试有 DEGRADED 时返回 DEGRADED"""
        results = [
            HealthCheckResult(component="c1", status=HealthStatus.HEALTHY),
            HealthCheckResult(component="c2", status=HealthStatus.DEGRADED),
        ]

        summary = checker.get_summary(results)
        assert summary == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_get_summary_with_unhealthy(self, checker):
        """测试有 UNHEALTHY 时返回 UNHEALTHY"""
        results = [
            HealthCheckResult(component="c1", status=HealthStatus.HEALTHY),
            HealthCheckResult(component="c2", status=HealthStatus.UNHEALTHY),
        ]

        summary = checker.get_summary(results)
        assert summary == HealthStatus.UNHEALTHY


# ============== AlertRule cooldown 逻辑 ==============

class TestAlertRuleCooldown:
    """AlertRule cooldown 逻辑测试 - 验证 cooldown <= 0 防护"""

    @pytest.mark.asyncio
    async def test_cooldown_zero_allows_immediate_trigger(self):
        """测试 cooldown=0 允许立即触发 (无冷却期)"""
        rule = ThresholdAlertRule(
            name="test_rule",
            metric_name="test_metric",
            threshold=10,
            operator="gt",
            cooldown=0,  # 零冷却
        )
        collector = MetricsCollector()

        # 连续触发应该都成功 (因为 cooldown=0)
        alert1 = await rule.check(20, collector)
        assert alert1 is not None

        # 立即再次触发应该也成功 (cooldown <= 0)
        alert2 = await rule.check(25, collector)
        assert alert2 is not None

    @pytest.mark.asyncio
    async def test_cooldown_negative_allows_immediate_trigger(self):
        """测试 cooldown<0 允许立即触发 (负冷却相当于无冷却)"""
        rule = ThresholdAlertRule(
            name="test_rule",
            metric_name="test_metric",
            threshold=10,
            operator="gt",
            cooldown=-1,  # 负冷却
        )
        collector = MetricsCollector()

        alert1 = await rule.check(20, collector)
        assert alert1 is not None

        # 负冷却也应该允许立即再次触发
        alert2 = await rule.check(25, collector)
        assert alert2 is not None

    @pytest.mark.asyncio
    async def test_positive_cooldown_blocks_immediate_trigger(self):
        """测试正 cooldown 阻止立即再次触发"""
        rule = ThresholdAlertRule(
            name="test_rule",
            metric_name="test_metric",
            threshold=10,
            operator="gt",
            cooldown=60,  # 60秒冷却
        )
        collector = MetricsCollector()

        alert1 = await rule.check(20, collector)
        assert alert1 is not None

        # 冷却期内不应再次触发
        alert2 = await rule.check(25, collector)
        assert alert2 is None

    @pytest.mark.asyncio
    async def test_cooldown_expires_after_time_passes(self):
        """测试冷却期过后可再次触发"""
        rule = ThresholdAlertRule(
            name="test_rule",
            metric_name="test_metric",
            threshold=10,
            operator="gt",
            cooldown=0,  # 零冷却
        )
        collector = MetricsCollector()

        # 触发
        alert1 = await rule.check(20, collector)
        assert alert1 is not None

        # 模拟时间流逝 (直接修改 _last_triggered)
        rule._last_triggered = time.time() - 100  # 100秒前

        # 冷却期过后可以再次触发
        alert2 = await rule.check(25, collector)
        assert alert2 is not None


# ============== FileChannel ==============

class TestFileChannel:
    """FileChannel 测试"""

    @pytest.fixture
    def temp_alert_file(self, tmp_path):
        """提供临时告警文件路径"""
        return str(tmp_path / "alerts.jsonl")

    @pytest.fixture
    def file_channel(self, temp_alert_file):
        """创建 FileChannel 实例"""
        return FileChannel(temp_alert_file)

    @pytest.fixture
    def sample_alert(self):
        """创建示例 Alert"""
        return Alert(
            level=AlertLevel.WARNING,
            title="Test Alert",
            message="This is a test alert",
            metric_name="test_metric",
            metric_value=50.0,
            threshold=10.0,
        )

    @pytest.mark.asyncio
    async def test_file_channel_writes_alert(self, file_channel, temp_alert_file, sample_alert):
        """测试 FileChannel 正确写入告警"""
        result = await file_channel.send(sample_alert)

        assert result is True

        # 验证文件内容
        with open(temp_alert_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["title"] == "Test Alert"
        assert data["level"] == "warning"
        assert data["metric_value"] == 50.0

    @pytest.mark.asyncio
    async def test_file_channel_writes_multiple_alerts(self, file_channel, temp_alert_file):
        """测试 FileChannel 写入多条告警"""
        alert1 = Alert(
            level=AlertLevel.INFO,
            title="Alert 1",
            message="First alert",
            metric_name="metric1",
            metric_value=10.0,
        )
        alert2 = Alert(
            level=AlertLevel.ERROR,
            title="Alert 2",
            message="Second alert",
            metric_name="metric2",
            metric_value=20.0,
        )

        await file_channel.send(alert1)
        await file_channel.send(alert2)

        with open(temp_alert_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 2
        assert json.loads(lines[0])["title"] == "Alert 1"
        assert json.loads(lines[1])["title"] == "Alert 2"

    @pytest.mark.asyncio
    async def test_file_channel_returns_false_on_error(self, tmp_path):
        """测试 FileChannel 写入失败时返回 False"""
        # 使用无效路径创建 FileChannel
        invalid_path = "/invalid/path/that/cannot/be/written/alerts.jsonl"
        channel = FileChannel(invalid_path)

        alert = Alert(
            level=AlertLevel.INFO,
            title="Test",
            message="Test",
            metric_name="test",
            metric_value=0.0,
        )

        result = await channel.send(alert)
        assert result is False

    @pytest.mark.asyncio
    async def test_file_channel_alert_to_dict(self, sample_alert):
        """测试 Alert to_dict 方法"""
        data = sample_alert.to_dict()

        assert data["level"] == "warning"
        assert data["title"] == "Test Alert"
        assert data["message"] == "This is a test alert"
        assert data["metric_name"] == "test_metric"
        assert data["metric_value"] == 50.0
        assert data["threshold"] == 10.0
        assert "timestamp" in data
        assert "datetime" in data


# ============== MetricsCollector ==============

class TestMetricsCollector:
    """MetricsCollector 测试"""

    @pytest.fixture
    def collector(self):
        """创建 MetricsCollector 实例"""
        return MetricsCollector(window_seconds=60.0)

    @pytest.mark.asyncio
    async def test_add_and_count(self, collector):
        """测试添加和计数"""
        await collector.add(1.0)
        await collector.add(2.0)
        await collector.add(3.0)

        count = await collector.count()
        assert count == 3

    @pytest.mark.asyncio
    async def test_avg(self, collector):
        """测试平均值计算"""
        await collector.add(10.0)
        await collector.add(20.0)
        await collector.add(30.0)

        avg = await collector.avg()
        assert avg == 20.0

    @pytest.mark.asyncio
    async def test_avg_empty_returns_zero(self, collector):
        """测试空收集器返回零"""
        avg = await collector.avg()
        assert avg == 0.0

    @pytest.mark.asyncio
    async def test_sum(self, collector):
        """测试求和"""
        await collector.add(10.0)
        await collector.add(20.0)
        await collector.add(30.0)

        total = await collector.sum()
        assert total == 60.0

    @pytest.mark.asyncio
    async def test_max_min(self, collector):
        """测试最大值和最小值"""
        await collector.add(10.0)
        await collector.add(30.0)
        await collector.add(20.0)

        max_val = await collector.max()
        min_val = await collector.min()
        assert max_val == 30.0
        assert min_val == 10.0

    @pytest.mark.asyncio
    async def test_last_n_values(self, collector):
        """测试获取最近 N 个值"""
        for i in range(10):
            await collector.add(float(i))

        last_3 = await collector.last(3)
        assert len(last_3) == 3
        assert last_3 == [7.0, 8.0, 9.0]

    @pytest.mark.asyncio
    async def test_cleanup_expired_values(self):
        """测试过期数据清理"""
        # 创建短窗口收集器
        collector = MetricsCollector(window_seconds=0.1)

        await collector.add(1.0)
        await asyncio.sleep(0.15)  # 等待数据过期

        # 过期数据应该被清理
        count = await collector.count()
        assert count == 0

        # 添加新数据
        await collector.add(2.0)
        count = await collector.count()
        assert count == 1


# ============== AlertLevel ==============

class TestAlertLevel:
    """AlertLevel 枚举测试"""

    def test_alert_level_enum_exists(self):
        """测试 AlertLevel 枚举存在"""
        assert hasattr(AlertLevel, "INFO")
        assert hasattr(AlertLevel, "WARNING")
        assert hasattr(AlertLevel, "ERROR")
        assert hasattr(AlertLevel, "CRITICAL")

    def test_alert_level_values(self):
        """测试 AlertLevel 枚举值"""
        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.ERROR.value == "error"
        assert AlertLevel.CRITICAL.value == "critical"


# ============== Monitor ==============

class TestMonitor:
    """Monitor 测试"""

    @pytest.fixture
    def monitor(self):
        """创建 Monitor 实例"""
        return Monitor(check_interval=10.0)

    @pytest.mark.asyncio
    async def test_monitor_initializes(self, monitor):
        """测试 Monitor 初始化"""
        assert monitor.check_interval == 10.0
        assert monitor.alert_manager is not None
        assert monitor.health_checker is not None
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_record_request_metric(self, monitor):
        """测试记录请求指标"""
        from src.monitor import RequestMetric

        metric = RequestMetric(
            url="https://example.com",
            success=True,
            latency=1.5,
            status_code=200,
        )

        await monitor.record_request(metric)

        # 验证指标已记录
        avg = await monitor._request_success.avg()
        assert avg == 1.0  # 100% 成功率

    @pytest.mark.asyncio
    async def test_record_request_failure_metric(self, monitor):
        """测试记录失败请求指标"""
        from src.monitor import RequestMetric

        metric = RequestMetric(
            url="https://example.com",
            success=False,
            latency=0.0,
            error="Connection timeout",
        )

        await monitor.record_request(metric)

        avg = await monitor._request_success.avg()
        assert avg == 0.0  # 0% 成功率

    @pytest.mark.asyncio
    async def test_setup_default_rules(self, monitor):
        """测试设置默认告警规则"""
        monitor.setup_default_rules()

        stats = monitor.alert_manager.get_stats()
        assert stats["rules_count"] > 0

    @pytest.mark.asyncio
    async def test_add_file_channel(self, monitor, tmp_path):
        """测试添加文件渠道"""
        alert_file = str(tmp_path / "alerts.jsonl")
        monitor.add_file_channel(alert_file)

        stats = monitor.alert_manager.get_stats()
        assert stats["channels_count"] > 0

    @pytest.mark.asyncio
    async def test_register_health_check(self, monitor):
        """测试注册健康检查"""
        async def mock_check():
            return HealthCheckResult(
                component="test",
                status=HealthStatus.HEALTHY,
            )

        monitor.register_health_check("test_component", mock_check)

        result = await monitor.health_checker.check("test_component")
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_and_alert(self, monitor):
        """测试检查和告警"""
        monitor.setup_default_rules()
        monitor.add_console_channel()

        # 记录一些指标
        from src.monitor import RequestMetric
        metric = RequestMetric(
            url="https://example.com",
            success=True,
            latency=1.0,
        )
        await monitor.record_request(metric)

        # 执行检查 (不应该抛出异常)
        await monitor.check_and_alert()

    @pytest.mark.asyncio
    async def test_start_and_stop(self, monitor):
        """测试 Monitor 启动和停止"""
        await monitor.start()
        assert monitor._running is True
        assert monitor._task is not None

        await monitor.stop()
        assert monitor._running is False
