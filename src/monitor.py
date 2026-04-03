"""
监控告警模块
- 指标采集 (请求成功率、延迟、代理可用率、验证码解决率)
- 告警规则 (阈值告警、趋势告警、异常检测)
- 通知渠道 (控制台、文件、Webhook 钉钉/企业微信)
- 健康检查 (自动巡检关键组件状态)
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import logging

from src.logger import get_logger


# ============== 指标数据结构 ==============

class MetricType(Enum):
    """指标类型"""
    REQUEST = "request"
    PROXY = "proxy"
    CAPTCHA = "captcha"
    CUSTOM = "custom"


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MetricValue:
    """指标值"""
    value: float
    timestamp: float = field(default_factory=time.time)
    tags: dict = field(default_factory=dict)


@dataclass
class RequestMetric:
    """请求指标"""
    url: str
    success: bool
    status_code: Optional[int] = None
    latency: float = 0.0
    error: Optional[str] = None
    proxy: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    @property
    def metric_type(self) -> MetricType:
        return MetricType.REQUEST


@dataclass
class ProxyMetric:
    """代理指标"""
    proxy_url: str
    alive: bool
    latency: float = 0.0
    score: float = 100.0
    timestamp: float = field(default_factory=time.time)

    @property
    def metric_type(self) -> MetricType:
        return MetricType.PROXY


@dataclass
class CaptchaMetric:
    """验证码指标"""
    captcha_type: str
    solved: bool
    duration: float = 0.0
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    @property
    def metric_type(self) -> MetricType:
        return MetricType.CAPTCHA


@dataclass
class Alert:
    """告警信息"""
    level: AlertLevel
    title: str
    message: str
    metric_name: str
    metric_value: float
    threshold: Optional[float] = None
    tags: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "tags": self.tags,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
        }


# ============== 统计计算器 ==============

class MetricsCollector:
    """
    指标采集器

    收集并计算滑动窗口统计
    """

    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        self._values: list[tuple[float, float]] = []  # (timestamp, value)
        self._lock = asyncio.Lock()

    async def add(self, value: float, timestamp: float = None):
        """添加指标值"""
        async with self._lock:
            ts = timestamp or time.time()
            self._values.append((ts, value))
            self._cleanup(ts)

    def _cleanup(self, current_time: float):
        """清理过期数据"""
        cutoff = current_time - self.window_seconds
        self._values = [(ts, v) for ts, v in self._values if ts > cutoff]

    async def count(self) -> int:
        """窗口内数据条数"""
        async with self._lock:
            return len(self._values)

    async def sum(self) -> float:
        """窗口内数据总和"""
        async with self._lock:
            self._cleanup(time.time())
            return sum(v for _, v in self._values)

    async def avg(self) -> float:
        """窗口内数据平均值"""
        async with self._lock:
            self._cleanup(time.time())
            if not self._values:
                return 0.0
            return sum(v for _, v in self._values) / len(self._values)

    async def max(self) -> float:
        """窗口内最大值"""
        async with self._lock:
            self._cleanup(time.time())
            if not self._values:
                return 0.0
            return max(v for _, v in self._values)

    async def min(self) -> float:
        """窗口内最小值"""
        async with self._lock:
            self._cleanup(time.time())
            if not self._values:
                return 0.0
            return min(v for _, v in self._values)

    async def last(self, n: int = 1) -> list[float]:
        """获取最近N个值"""
        async with self._lock:
            self._cleanup(time.time())
            return [v for _, v in self._values[-n:]]


# ============== 告警规则 ==============

class AlertRule:
    """告警规则基类"""

    def __init__(
        self,
        name: str,
        metric_name: str,
        level: AlertLevel = AlertLevel.WARNING,
        cooldown: float = 60.0,
    ):
        self.name = name
        self.metric_name = metric_name
        self.level = level
        self.cooldown = cooldown
        self._last_triggered: float = 0

    async def check(self, metric_value: float, collector: MetricsCollector) -> Optional[Alert]:
        """检查是否触发告警"""
        raise NotImplementedError

    def _can_trigger(self) -> bool:
        """检查是否在冷却期"""
        if self.cooldown <= 0:
            return True
        return time.time() - self._last_triggered >= self.cooldown

    def _triggered(self):
        """记录触发时间"""
        self._last_triggered = time.time()


class ThresholdAlertRule(AlertRule):
    """
    阈值告警规则

    当指标超过/低于阈值时触发
    """

    def __init__(
        self,
        name: str,
        metric_name: str,
        threshold: float,
        operator: str = "gt",  # gt, lt, gte, lte, eq
        level: AlertLevel = AlertLevel.WARNING,
        cooldown: float = 60.0,
    ):
        super().__init__(name, metric_name, level, cooldown)
        self.threshold = threshold
        self.operator = operator

    async def check(self, metric_value: float, collector: MetricsCollector) -> Optional[Alert]:
        if not self._can_trigger():
            return None

        triggered = False
        if self.operator == "gt":
            triggered = metric_value > self.threshold
        elif self.operator == "lt":
            triggered = metric_value < self.threshold
        elif self.operator == "gte":
            triggered = metric_value >= self.threshold
        elif self.operator == "lte":
            triggered = metric_value <= self.threshold
        elif self.operator == "eq":
            triggered = metric_value == self.threshold

        if triggered:
            self._triggered()
            return Alert(
                level=self.level,
                title=f"{self.name}",
                message=f"{self.metric_name} = {metric_value:.2f} (阈值: {self.threshold})",
                metric_name=self.metric_name,
                metric_value=metric_value,
                threshold=self.threshold,
            )
        return None


class TrendAlertRule(AlertRule):
    """
    趋势告警规则

    当指标趋势持续上升/下降时触发
    """

    def __init__(
        self,
        name: str,
        metric_name: str,
        window_size: int = 5,
        threshold: float = 0.5,
        direction: str = "up",  # up, down
        level: AlertLevel = AlertLevel.WARNING,
        cooldown: float = 60.0,
    ):
        super().__init__(name, metric_name, level, cooldown)
        self.window_size = window_size
        self.threshold = threshold
        self.direction = direction

    async def check(self, metric_value: float, collector: MetricsCollector) -> Optional[Alert]:
        if not self._can_trigger():
            return None

        await collector.add(metric_value)
        recent = await collector.last(self.window_size)

        if len(recent) < self.window_size:
            return None

        # 计算趋势 (简单线性回归斜率)
        n = len(recent)
        sum_x = sum(range(n))
        sum_y = sum(recent)
        sum_xy = sum(i * v for i, v in enumerate(recent))
        sum_x2 = sum(i * i for i in range(n))

        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return None

        slope = (n * sum_xy - sum_x * sum_y) / denominator

        triggered = False
        if self.direction == "up" and slope > self.threshold:
            triggered = True
        elif self.direction == "down" and slope < -self.threshold:
            triggered = True

        if triggered:
            self._triggered()
            return Alert(
                level=self.level,
                title=f"{self.name} (趋势:{self.direction})",
                message=f"{self.metric_name} 趋势斜率 = {slope:.4f} (阈值: {self.threshold})",
                metric_name=self.metric_name,
                metric_value=slope,
                threshold=self.threshold,
                tags={"direction": self.direction},
            )
        return None


class AnomalyAlertRule(AlertRule):
    """
    异常检测告警规则

    当指标偏离正常范围时触发 (基于标准差)
    """

    def __init__(
        self,
        name: str,
        metric_name: str,
        std_threshold: float = 2.0,
        min_samples: int = 10,
        level: AlertLevel = AlertLevel.WARNING,
        cooldown: float = 60.0,
    ):
        super().__init__(name, metric_name, level, cooldown)
        self.std_threshold = std_threshold
        self.min_samples = min_samples

    async def check(self, metric_value: float, collector: MetricsCollector) -> Optional[Alert]:
        if not self._can_trigger():
            return None

        await collector.add(metric_value)
        recent = await collector.last(self.min_samples)

        if len(recent) < self.min_samples:
            return None

        # 计算均值和标准差
        mean = sum(recent) / len(recent)
        variance = sum((v - mean) ** 2 for v in recent) / len(recent)
        std = variance ** 0.5

        if std == 0:
            return None

        # 计算偏离程度
        deviation = abs(metric_value - mean) / std

        if deviation > self.std_threshold:
            self._triggered()
            return Alert(
                level=self.level,
                title=f"{self.name} (异常)",
                message=f"{self.metric_name} = {metric_value:.2f}, 均值 = {mean:.2f}, 偏离 = {deviation:.2f}σ",
                metric_name=self.metric_name,
                metric_value=metric_value,
                threshold=self.std_threshold,
                tags={"mean": mean, "std": std, "deviation": deviation},
            )
        return None


# ============== 通知渠道 ==============

class NotificationChannel:
    """通知渠道基类"""

    def __init__(self, name: str):
        self.name = name

    async def send(self, alert: Alert) -> bool:
        """发送告警通知"""
        raise NotImplementedError

    async def close(self):
        """关闭渠道"""
        pass


class ConsoleChannel(NotificationChannel):
    """控制台通知渠道"""

    def __init__(self):
        super().__init__("console")
        self._logger = get_logger()

    async def send(self, alert: Alert) -> bool:
        """输出到控制台"""
        msg = f"[{alert.level.value.upper()}] {alert.title}: {alert.message}"
        if alert.level == AlertLevel.CRITICAL:
            self._logger.error(msg)
        elif alert.level == AlertLevel.ERROR:
            self._logger.error(msg)
        elif alert.level == AlertLevel.WARNING:
            self._logger.warning(msg)
        else:
            self._logger.info(msg)
        return True


class FileChannel(NotificationChannel):
    """文件通知渠道"""

    def __init__(self, file_path: str, rotation: str = "10 MB", retention: str = "7 days"):
        super().__init__("file")
        self.file_path = file_path
        self._lock = asyncio.Lock()
        self._logger = get_logger()

    async def send(self, alert: Alert) -> bool:
        """写入文件"""
        async with self._lock:
            try:
                with open(self.file_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(alert.to_dict(), ensure_ascii=False) + "\n")
                return True
            except Exception as e:
                self._logger.warning(f"Failed to write alert to file {self.file_path}: {e}")
                return False


class WebhookChannel(NotificationChannel):
    """
    Webhook通知渠道

    支持钉钉、企业微信等
    """

    def __init__(
        self,
        url: str,
        channel_type: str = "dingtalk",  # dingtalk, wecom, custom
        secret: Optional[str] = None,
        mention_list: list = None,
    ):
        super().__init__(f"webhook_{channel_type}")
        self.url = url
        self.channel_type = channel_type
        self.secret = secret
        self.mention_list = mention_list or []

    async def send(self, alert: Alert) -> bool:
        """发送Webhook通知"""
        try:
            payload = self._build_payload(alert)
            async with asyncio.timeout(10):
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    ) as resp:
                        return resp.status == 200
        except Exception:
            return False

    def _build_payload(self, alert: Alert) -> dict:
        """构建请求载荷"""
        if self.channel_type == "dingtalk":
            return self._build_dingtalk_payload(alert)
        elif self.channel_type == "wecom":
            return self._build_wecom_payload(alert)
        else:
            return self._build_custom_payload(alert)

    def _build_dingtalk_payload(self, alert: Alert) -> dict:
        """构建钉钉格式载荷"""
        level_text = {
            AlertLevel.INFO: "信息",
            AlertLevel.WARNING: "警告",
            AlertLevel.ERROR: "错误",
            AlertLevel.CRITICAL: "严重",
        }

        msg_type = "text"
        if self.mention_list:
            msg_type = "actionCard"

        content = f"**{level_text.get(alert.level, '信息')}告警**\n\n" \
                  f"**{alert.title}**\n\n" \
                  f"{alert.message}\n\n" \
                  f"时间: {datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')}"

        if self.mention_list:
            mention_text = " ".join(f"@{u}" for u in self.mention_list)
            content += f"\n\n{mention_text}"

        if msg_type == "actionCard":
            return {
                "msgtype": "actionCard",
                "actionCard": {
                    "title": f"{level_text.get(alert.level, '信息')} - {alert.title}",
                    "text": content,
                    "btnOrientation": "0",
                },
            }

        return {
            "msgtype": "text",
            "text": {"content": content},
        }

    def _build_wecom_payload(self, alert: Alert) -> dict:
        """构建企业微信格式载荷"""
        level_text = {
            AlertLevel.INFO: "INFO",
            AlertLevel.WARNING: "WARNING",
            AlertLevel.ERROR: "ERROR",
            AlertLevel.CRITICAL: "CRITICAL",
        }

        content = f"[{level_text.get(alert.level, 'INFO')}] {alert.title}\n{alert.message}\n" \
                  f"时间: {datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')}"

        return {
            "msgtype": "text",
            "text": {"content": content, "mentioned_list": self.mention_list},
        }

    def _build_custom_payload(self, alert: Alert) -> dict:
        """构建自定义格式载荷"""
        return alert.to_dict()


# ============== 健康检查 ==============

class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    component: str
    status: HealthStatus
    message: str = ""
    details: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class HealthChecker:
    """
    健康检查器

    自动巡检关键组件状态
    """

    def __init__(self):
        self._components: dict[str, callable] = {}

    def register(self, name: str, checker: callable):
        """
        注册健康检查函数

        Args:
            name: 组件名称
            checker: 异步检查函数, 返回 HealthCheckResult
        """
        self._components[name] = checker

    async def check(self, name: str) -> HealthCheckResult:
        """检查单个组件"""
        if name not in self._components:
            return HealthCheckResult(
                component=name,
                status=HealthStatus.UNHEALTHY,
                message=f"组件 {name} 未注册",
            )

        try:
            result = await self._components[name]()
            if isinstance(result, HealthCheckResult):
                return result
            return HealthCheckResult(
                component=name,
                status=HealthStatus.HEALTHY,
                message="OK",
            )
        except Exception as e:
            return HealthCheckResult(
                component=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )

    async def check_all(self) -> list[HealthCheckResult]:
        """检查所有组件"""
        tasks = [self.check(name) for name in self._components]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        # 将 Exception 对象转换为 UNHEALTHY 结果，避免调用方 AttributeError
        results = []
        for r in raw:
            if isinstance(r, Exception):
                results.append(HealthCheckResult(
                    component="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {r}",
                ))
            else:
                results.append(r)
        return results

    def get_summary(self, results: list[HealthCheckResult]) -> HealthStatus:
        """获取总体健康状态"""
        if not results:
            return HealthStatus.HEALTHY

        statuses = [r.status for r in results]

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY


# ============== 告警管理器 ==============

class AlertManager:
    """
    告警管理器

    管理告警规则和通知渠道
    """

    def __init__(self):
        self._rules: dict[str, AlertRule] = {}
        self._channels: dict[str, NotificationChannel] = {}
        self._collectors: dict[str, MetricsCollector] = {}
        self._logger = get_logger()

    def add_rule(self, rule: AlertRule, collector: MetricsCollector):
        """添加告警规则"""
        self._rules[rule.name] = rule
        self._collectors[rule.metric_name] = collector

    def remove_rule(self, name: str):
        """移除告警规则"""
        self._rules.pop(name, None)

    def add_channel(self, channel: NotificationChannel):
        """添加通知渠道"""
        self._channels[channel.name] = channel

    def remove_channel(self, name: str):
        """移除通知渠道"""
        channel = self._channels.pop(name, None)
        if channel:
            asyncio.create_task(channel.close())

    async def process_metric(self, metric_name: str, value: float) -> list[Alert]:
        """处理指标, 返回触发的告警列表"""
        alerts = []

        if metric_name not in self._collectors:
            self._collectors[metric_name] = MetricsCollector()

        collector = self._collectors[metric_name]
        await collector.add(value)

        for rule in self._rules.values():
            if rule.metric_name == metric_name:
                alert = await rule.check(value, collector)
                if alert:
                    alerts.append(alert)

        return alerts

    async def send_alerts(self, alerts: list[Alert]):
        """发送告警到所有渠道"""
        for alert in alerts:
            for channel in self._channels.values():
                try:
                    success = await channel.send(alert)
                    if success:
                        self._logger.info(f"Alert sent via {channel.name}: {alert.title}")
                    else:
                        self._logger.warning(f"Failed to send alert via {channel.name}")
                except Exception as e:
                    self._logger.error(f"Error sending alert via {channel.name}: {e}")

    def get_stats(self) -> dict:
        """获取告警统计"""
        return {
            "rules_count": len(self._rules),
            "channels_count": len(self._channels),
            "collectors_count": len(self._collectors),
        }


# ============== 监控器 ==============

class Monitor:
    """
    监控系统

    采集指标、处理告警、执行健康检查
    """

    def __init__(self, check_interval: float = 60.0):
        self.check_interval = check_interval
        self.alert_manager = AlertManager()
        self.health_checker = HealthChecker()
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._logger = get_logger()

        # 预置指标采集器
        self._request_success = MetricsCollector()
        self._request_latency = MetricsCollector()
        self._proxy_available = MetricsCollector()
        self._captcha_success = MetricsCollector()

    # ============== 指标采集 ==============

    async def record_request(self, metric: RequestMetric):
        """记录请求指标"""
        await self._request_success.add(1.0 if metric.success else 0.0)
        if metric.latency > 0:
            await self._request_latency.add(metric.latency)

    async def record_proxy(self, metric: ProxyMetric):
        """记录代理指标"""
        await self._proxy_available.add(1.0 if metric.alive else 0.0)

    async def record_captcha(self, metric: CaptchaMetric):
        """记录验证码指标"""
        await self._captcha_success.add(1.0 if metric.solved else 0.0)

    # ============== 快捷方法 ==============

    def setup_default_rules(self):
        """设置默认告警规则"""

        # 请求成功率 < 80% 告警
        self.alert_manager.add_rule(
            ThresholdAlertRule(
                name="low_success_rate",
                metric_name="request_success_rate",
                threshold=0.8,
                operator="lt",
                level=AlertLevel.ERROR,
                cooldown=120,
            ),
            self._request_success,
        )

        # 请求延迟 > 5s 告警
        self.alert_manager.add_rule(
            ThresholdAlertRule(
                name="high_latency",
                metric_name="request_latency",
                threshold=5.0,
                operator="gt",
                level=AlertLevel.WARNING,
                cooldown=60,
            ),
            self._request_latency,
        )

        # 代理可用率 < 60% 告警
        self.alert_manager.add_rule(
            ThresholdAlertRule(
                name="low_proxy_availability",
                metric_name="proxy_availability",
                threshold=0.6,
                operator="lt",
                level=AlertLevel.ERROR,
                cooldown=120,
            ),
            self._proxy_available,
        )

        # 验证码解决率 < 70% 告警
        self.alert_manager.add_rule(
            ThresholdAlertRule(
                name="low_captcha_success",
                metric_name="captcha_success_rate",
                threshold=0.7,
                operator="lt",
                level=AlertLevel.WARNING,
                cooldown=180,
            ),
            self._captcha_success,
        )

    def add_console_channel(self):
        """添加控制台通知渠道"""
        self.alert_manager.add_channel(ConsoleChannel())

    def add_file_channel(self, file_path: str):
        """添加文件通知渠道"""
        self.alert_manager.add_channel(FileChannel(file_path))

    def add_webhook_channel(
        self,
        url: str,
        channel_type: str = "dingtalk",
        secret: Optional[str] = None,
        mention_list: list = None,
    ):
        """添加Webhook通知渠道"""
        self.alert_manager.add_channel(
            WebhookChannel(url, channel_type, secret, mention_list)
        )

    def register_health_check(self, name: str, checker: callable):
        """注册健康检查"""
        self.health_checker.register(name, checker)

    # ============== 告警处理 ==============

    async def check_and_alert(self):
        """检查所有指标并发送告警"""
        # 采集当前指标值
        metrics_to_check = [
            ("request_success_rate", await self._request_success.avg()),
            ("request_latency", await self._request_latency.avg()),
            ("proxy_availability", await self._proxy_available.avg()),
            ("captcha_success_rate", await self._captcha_success.avg()),
        ]

        for metric_name, value in metrics_to_check:
            if value > 0:  # 只处理有效的指标
                alerts = await self.alert_manager.process_metric(metric_name, value)
                if alerts:
                    await self.alert_manager.send_alerts(alerts)

    # ============== 生命周期 ==============

    async def start(self):
        """启动监控"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        self._logger.info("Monitor started")

    async def stop(self):
        """停止监控"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._logger.info("Monitor stopped")

    async def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                await asyncio.wait_for(
                    self.check_and_alert(),
                    timeout=self.check_interval,
                )
            except asyncio.TimeoutError:
                self._logger.warning("Monitor check timed out")
            except Exception as e:
                self._logger.error(f"Monitor loop error: {e}")

            await asyncio.sleep(self.check_interval)

    # ============== 集成支持 ==============

    async def integrate_with_crawler(self, crawler):
        """
        集成到 AdvancedCrawler

        Args:
            crawler: AdvancedCrawler 实例
        """

        # 注册爬虫健康检查
        async def check_crawler() -> HealthCheckResult:
            try:
                # 检查存储
                if hasattr(crawler, "storage"):
                    storage_ok = True
                    # 可以添加更多检查
                    if not storage_ok:
                        return HealthCheckResult(
                            component="crawler_storage",
                            status=HealthStatus.UNHEALTHY,
                            message="存储不可用",
                        )

                # 检查代理池
                if hasattr(crawler, "proxy_pool"):
                    stats = crawler.proxy_pool.get_stats()
                    if stats["alive"] == 0:
                        return HealthCheckResult(
                            component="crawler_proxy",
                            status=HealthStatus.DEGRADED,
                            message=f"无可用代理 (总计: {stats['total']})",
                        )

                return HealthCheckResult(
                    component="crawler",
                    status=HealthStatus.HEALTHY,
                    message="爬虫运行正常",
                )
            except Exception as e:
                return HealthCheckResult(
                    component="crawler",
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                )

        self.register_health_check("crawler", check_crawler)

    # ============== 统计 ==============

    def get_stats(self) -> dict:
        """获取监控统计"""
        return {
            "alert_manager": self.alert_manager.get_stats(),
            "request_success_rate": self._request_success.avg() if hasattr(self._request_success, 'avg') else None,
            "request_latency": self._request_latency.avg() if hasattr(self._request_latency, 'avg') else None,
            "proxy_availability": self._proxy_available.avg() if hasattr(self._proxy_available, 'avg') else None,
            "captcha_success_rate": self._captcha_success.avg() if hasattr(self._captcha_success, 'avg') else None,
        }


# ============== 便捷函数 ==============

def create_monitor(
    check_interval: float = 60.0,
    enable_console: bool = True,
    alert_file: str = None,
    webhook_url: str = None,
    webhook_type: str = "dingtalk",
) -> Monitor:
    """
    创建监控器并配置

    Args:
        check_interval: 检查间隔(秒)
        enable_console: 启用控制台通知
        alert_file: 告警日志文件路径
        webhook_url: Webhook URL
        webhook_type: Webhook类型 (dingtalk/wecom/custom)

    Returns:
        配置好的 Monitor 实例
    """
    monitor = Monitor(check_interval=check_interval)
    monitor.setup_default_rules()

    if enable_console:
        monitor.add_console_channel()

    if alert_file:
        monitor.add_file_channel(alert_file)

    if webhook_url:
        monitor.add_webhook_channel(webhook_url, webhook_type)

    return monitor


# ============== 独立运行测试 ==============

if __name__ == "__main__":
    async def test_monitor():
        """测试监控模块"""
        print("Testing Monitor module...")

        # 创建监控器
        monitor = Monitor(check_interval=5)
        monitor.setup_default_rules()
        monitor.add_console_channel()

        # 添加测试规则
        from src.monitor import ThresholdAlertRule, MetricsCollector

        test_collector = MetricsCollector(window_seconds=30)
        monitor.alert_manager.add_rule(
            ThresholdAlertRule(
                name="test_rule",
                metric_name="test_metric",
                threshold=50,
                operator="gt",
                level=AlertLevel.INFO,
            ),
            test_collector,
        )

        # 模拟指标
        await monitor.record_request(RequestMetric(
            url="https://example.com",
            success=True,
            latency=1.5,
        ))

        await monitor.record_proxy(ProxyMetric(
            proxy_url="http://proxy.example.com:8080",
            alive=True,
            latency=0.5,
            score=95.0,
        ))

        await monitor.record_captcha(CaptchaMetric(
            captcha_type="image",
            solved=True,
            duration=2.0,
        ))

        # 处理告警
        await monitor.check_and_alert()

        # 发送测试告警
        test_alert = Alert(
            level=AlertLevel.INFO,
            title="测试告警",
            message="这是一条测试告警消息",
            metric_name="test",
            metric_value=100.0,
        )
        await monitor.alert_manager.send_alerts([test_alert])

        # 健康检查
        monitor.register_health_check("test_component", lambda: HealthCheckResult(
            component="test",
            status=HealthStatus.HEALTHY,
            message="测试组件正常",
        ))

        results = await monitor.health_checker.check_all()
        for r in results:
            print(f"Health check: {r.component} - {r.status.value}: {r.message}")

        print("Monitor test completed!")

    asyncio.run(test_monitor())
