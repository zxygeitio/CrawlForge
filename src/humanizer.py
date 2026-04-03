"""
爬虫拟人化模块
模拟人类行为特征，绕过反爬检测

核心维度:
1. User-Agent 池
2. 请求间隔 (正态/泊松/均匀分布)
3. 鼠标/滑动轨迹
4. 浏览器指纹池
5. HTTP头顺序
6. TLS/SSL指纹
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Callable
from functools import wraps


# ============== User-Agent 池 ==============

class UserAgentPool:
    """
    User-Agent 池

    按浏览器和版本分类，支持随机选择
    """

    # Chrome UA (按版本分层)
    CHROME_UA = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    # Firefox UA
    FIREFOX_UA = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
    ]

    # Edge UA (Chromium内核)
    EDGE_UA = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]

    # Safari UA (Mac)
    SAFARI_UA = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    ]

    # Mobile UA
    MOBILE_UA = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
    ]

    _instance: Optional["UserAgentPool"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pool = {
                "chrome": cls.CHROME_UA,
                "firefox": cls.FIREFOX_UA,
                "edge": cls.EDGE_UA,
                "safari": cls.SAFARI_UA,
                "mobile": cls.MOBILE_UA,
            }
        return cls._instance

    def get(self, browser: str = None) -> str:
        """获取随机 UA"""
        if browser is None:
            browser = random.choice(list(self._pool.keys()))
        uas = self._pool.get(browser, self.CHROME_UA)
        return random.choice(uas)

    def get_all_browsers(self) -> List[str]:
        """获取所有浏览器类型"""
        return list(self._pool.keys())


# ============== 请求间隔模拟 ==============

class HumanDelay:
    """
    人类延迟模拟

    人类操作不是固定间隔，而是符合某种概率分布
    """

    @staticmethod
    def normal(mean: float = 1.0, std: float = 0.3, min_delay: float = 0.5) -> float:
        """
        正态分布延迟

        模拟人类操作: 大部分操作在1秒左右，有些快有些慢
        """
        delay = random.gauss(mean, std)
        return max(min_delay, delay)

    @staticmethod
    def poisson(lambda_: float = 1.0, min_delay: float = 0.3) -> float:
        """
        泊松分布延迟

        模拟随机事件发生的时间间隔
        """
        delay = random.expovariate(1.0 / lambda_)
        return max(min_delay, delay)

    @staticmethod
    def uniform(min_delay: float = 0.5, max_delay: float = 3.0) -> float:
        """
        均匀分布延迟

        最简单的随机延迟
        """
        return random.uniform(min_delay, max_delay)

    @staticmethod
    def adaptive(last_delay: float = None) -> float:
        """
        自适应延迟

        根据上次延迟动态调整，模拟"思考"行为
        - 如果上次很快，这次可能变慢
        - 如果上次很慢，可能恢复
        """
        if last_delay is None:
            return random.uniform(0.5, 2.0)

        # 随机加减延迟，但保持合理范围
        change = random.uniform(-0.5, 0.8)
        new_delay = last_delay + change
        return max(0.3, min(5.0, new_delay))

    @staticmethod
    def jitter(base_delay: float, jitter_range: float = 0.2) -> float:
        """
        添加抖动的延迟

        基础延迟 ± 抖动范围
        """
        jitter = base_delay * random.uniform(-jitter_range, jitter_range)
        return max(0.1, base_delay + jitter)


# ============== 鼠标轨迹生成 ==============

class MouseTrajectory:
    """
    人类鼠标轨迹生成

    人类移动鼠标不是直线，而是有加速、减速、抖动
    """

    @staticmethod
    def bezier_curve(points: List[Tuple[float, float]], num_points: int = 50) -> List[Tuple[float, float]]:
        """
        生成贝塞尔曲线路径

        Args:
            points: 控制点 [(x0,y0), (x1,y1), ..., (xn,yn)]
            num_points: 采样点数

        Returns:
            路径点列表
        """
        if len(points) < 2:
            return points

        result = []
        for t in range(num_points):
            t_norm = t / (num_points - 1)
            x, y = MouseTrajectory._de_casteljau(points, t_norm)
            result.append((x, y))

        return result

    @staticmethod
    def _de_casteljau(points: List[Tuple[float, float]], t: float) -> Tuple[float, float]:
        """De Casteljau 算法计算贝塞尔曲线点"""
        if len(points) == 1:
            return points[0]

        new_points = []
        for i in range(len(points) - 1):
            x = (1 - t) * points[i][0] + t * points[i + 1][0]
            y = (1 - t) * points[i][1] + t * points[i + 1][1]
            new_points.append((x, y))

        return MouseTrajectory._de_casteljau(new_points, t)

    @staticmethod
    def human_curve(
        start: Tuple[float, float],
        end: Tuple[float, float],
        curvature: float = 0.3,
        wobble: float = 10.0,
        num_points: int = 50,
    ) -> List[Tuple[float, float]]:
        """
        生成人类化曲线轨迹

        Args:
            start: 起始点 (x, y)
            end: 终点 (x, y)
            curvature: 曲率 (0-1, 越大越弯曲)
            wobble: 抖动幅度
            num_points: 采样点数

        Returns:
            轨迹点列表 [(x, y, time), ...]
        """
        # 添加控制点产生曲线
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2

        # 垂直偏移产生弧度
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dist = (dx ** 2 + dy ** 2) ** 0.5

        # 控制点偏移
        offset = dist * curvature * random.uniform(-1, 1)
        if abs(dx) > abs(dy):
            ctrl_x = mid_x + offset
            ctrl_y = mid_y
        else:
            ctrl_x = mid_x
            ctrl_y = mid_y + offset

        # 生成贝塞尔曲线
        control_points = [start, (ctrl_x, ctrl_y), end]
        path = MouseTrajectory.bezier_curve(control_points, num_points)

        # 添加抖动
        result = []
        for x, y in path:
            jitter_x = random.gauss(0, wobble)
            jitter_y = random.gauss(0, wobble)
            result.append((x + jitter_x, y + jitter_y))

        return result

    @staticmethod
    def generate_slider_trajectory(
        distance: int,
        duration: float = 1.5,
        steps: int = 60,
    ) -> List[Tuple[int, int, float]]:
        """
        生成滑块验证码的人类滑动轨迹

        特点:
        - 先快后慢 (缓动)
        - 中间有小抖动
        - 末端有时会"过冲"再回退
        - 人类不会完美线性

        Args:
            distance: 滑动距离
            duration: 总时长(秒)
            steps: 轨迹点数

        Returns:
            [(x, y, timestamp), ...]
        """
        trajectory = []
        start_time = time.time()

        # 人类滑动特点: 先快后慢，中间有随机抖动
        for step in range(steps):
            progress = step / steps

            # 缓动函数 (ease-out cubic)
            ease_out = 1 - (1 - progress) ** 3

            # 添加随机抖动
            if progress < 0.9:  # 90%之前都可能抖动
                jitter = random.gauss(0, 2) if random.random() > 0.7 else 0
            else:
                # 快到终点时可能有"过冲"
                jitter = random.uniform(-3, 3)

            # 计算位置
            x = int(distance * ease_out + jitter)

            # 确保不倒退
            if step > 0 and x < trajectory[-1][0]:
                x = trajectory[-1][0] + random.randint(0, 2)

            # 确保不超出终点
            x = min(x, distance + random.randint(0, 3))

            timestamp = start_time + (duration * step / steps)
            trajectory.append((x, 0, timestamp))

        # 确保到达终点
        if trajectory:
            trajectory[-1] = (distance, 0, start_time + duration)

        # 随机在某个位置停顿一下 (模拟犹豫)
        if random.random() > 0.7:
            pause_at = random.randint(int(steps * 0.3), int(steps * 0.7))
            pause_duration = random.uniform(0.1, 0.3)
            orig_time = trajectory[pause_at][2]
            for i in range(pause_at, min(pause_at + 3, steps)):
                if i < len(trajectory):
                    trajectory[i] = (trajectory[i][0], trajectory[i][1], orig_time + pause_duration)

        return trajectory


# ============== 浏览器指纹池 ==============

class FingerprintPool:
    """
    浏览器指纹池

    生成随机但合理的浏览器指纹
    """

    # 屏幕分辨率
    SCREEN_RESOLUTIONS = [
        (1920, 1080), (2560, 1440), (3840, 2160), (1366, 768),
        (1536, 864), (1440, 900), (1600, 900), (1280, 720),
    ]

    # 浏览器视口
    VIEWPORTS = [
        (1920, 955), (2560, 1359), (1366, 695), (1536, 802),
        (1440, 900), (1600, 900), (1280, 720), (1280, 800),
    ]

    # 时区
    TIMEZONES = [
        "Asia/Shanghai", "Asia/Tokyo", "Asia/Seoul", "Asia/Singapore",
        "America/New_York", "America/Los_Angeles", "America/Chicago",
        "Europe/London", "Europe/Paris", "Europe/Berlin",
    ]

    # 语言
    LANGUAGES = [
        "zh-CN,zh,en-US,en", "en-US,en", "zh-CN,zh",
        "ja-JP,ja,en-US,en", "ko-KR,ko,en-US,en",
    ]

    # 平台
    PLATFORMS = ["Win32", "MacIntel", "Linux x86_64"]

    @classmethod
    def generate_screen(cls) -> dict:
        """生成屏幕指纹"""
        width, height = random.choice(cls.SCREEN_RESOLUTIONS)
        return {
            "width": width,
            "height": height,
            "availWidth": width - random.randint(0, 100),
            "availHeight": height - random.randint(80, 150),
            " colorDepth": random.choice([24, 30, 32]),
            "pixelDepth": random.choice([24, 30, 32]),
        }

    @classmethod
    def generate_viewport(cls) -> dict:
        """生成视口指纹"""
        width, height = random.choice(cls.VIEWPORTS)
        return {
            "width": width,
            "height": height,
            "innerWidth": width - random.randint(0, 50),
            "innerHeight": height - random.randint(0, 150),
        }

    @classmethod
    def generate_timezone(cls) -> dict:
        """生成时区指纹"""
        tz = random.choice(cls.TIMEZONES)
        offset = cls._tz_to_offset(tz)
        return {
            "timezone": tz,
            "offset": offset,
        }

    @classmethod
    def _tz_to_offset(cls, tz: str) -> int:
        """时区转偏移量"""
        tz_offsets = {
            "Asia/Shanghai": 8, "Asia/Tokyo": 9, "Asia/Seoul": 9,
            "Asia/Singapore": 8, "America/New_York": -5,
            "America/Los_Angeles": -8, "America/Chicago": -6,
            "Europe/London": 0, "Europe/Paris": 1, "Europe/Berlin": 1,
        }
        return tz_offsets.get(tz, 0)

    @classmethod
    def generate_canvas(cls) -> dict:
        """生成Canvas指纹种子 (用于StealthBrowser的Canvas噪声)"""
        # 不同的噪声参数会产生不同的Canvas指纹
        return {
            "noise_scale": random.uniform(0.01, 0.05),
            "noise_offset": random.uniform(-0.5, 0.5),
        }

    @classmethod
    def generate_webgl(cls) -> dict:
        """生成WebGL指纹"""
        vendors = ["Intel Inc.", "NVIDIA Corporation", "AMD", "Apple Inc."]
        renderers = ["Intel Iris OpenGL Engine", "NVIDIA GeForce GTX 1080", "AMD Radeon Pro 5500M"]
        return {
            "vendor": random.choice(vendors),
            "renderer": random.choice(renderers),
        }

    @classmethod
    def generate_all(cls) -> dict:
        """生成完整指纹"""
        return {
            "screen": cls.generate_screen(),
            "viewport": cls.generate_viewport(),
            "timezone": cls.generate_timezone(),
            "language": random.choice(cls.LANGUAGES),
            "platform": random.choice(cls.PLATFORMS),
            "hardware_concurrency": random.choice([2, 4, 6, 8, 12, 16]),
            "device_memory": random.choice([2, 4, 8, 16, 32]),
            "max_touch_points": random.choice([0, 1, 2, 5, 10]),
            "canvas": cls.generate_canvas(),
            "webgl": cls.generate_webgl(),
        }


# ============== HTTP 头顺序 ==============

class HeaderOrder:
    """
    HTTP 头顺序模拟

    不同浏览器的 header 顺序不同，这也是指纹之一
    """

    # Chrome 常见的 header 顺序 (简化)
    CHROME_ORDER = [
        "host", "connection", "content-length", "cache-control",
        "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
        "upgrade-insecure-requests", "origin", "content-type",
        "user-agent", "accept", "sec-fetch-site", "sec-fetch-mode",
        "sec-fetch-dest", "sec-fetch-user", "accept-encoding",
        "accept-language", "cookie", "referer",
    ]

    # Firefox 常见的 header 顺序
    FIREFOX_ORDER = [
        "host", "user-agent", "accept", "accept-language",
        "accept-encoding", "connection", "content-type", "content-length",
        "origin", "cookie", "referer", "upgrade-insecure-requests",
    ]

    # Safari 常见的 header 顺序
    SAFARI_ORDER = [
        "host", "connection", "content-length", "cache-control",
        "accept", "user-agent", "accept-language", "accept-encoding",
        "content-type", "origin", "referer",
    ]

    @classmethod
    def reorder_headers(cls, headers: dict, browser: str = "chrome") -> list:
        """
        根据浏览器类型重排 header 顺序

        Args:
            headers: 原始 header dict
            browser: 浏览器类型 (chrome/firefox/safari)

        Returns:
            [(key, value), ...] 按浏览器顺序排列
        """
        order_map = {
            "chrome": cls.CHROME_ORDER,
            "firefox": cls.FIREFOX_ORDER,
            "safari": cls.SAFARI_ORDER,
        }

        order = order_map.get(browser.lower(), cls.CHROME_ORDER)

        # 按 order 排序，未知 header 放最后
        result = []
        remaining = []
        for key, value in headers.items():
            lower_key = key.lower()
            if lower_key in order:
                result.append((key, value, order.index(lower_key)))
            else:
                remaining.append((key, value))

        # 按 order 索引排序
        result.sort(key=lambda x: x[2])
        result = [(k, v) for k, v in result[:len(result) - len(remaining)]] + remaining

        return result


# ============== 行为模式模拟 ==============

class BehaviorSimulator:
    """
    行为模式模拟

    模拟人类浏览网页的行为模式
    """

    def __init__(self):
        self.last_action_time = time.time()
        self.page_stay_times: List[float] = []

    def get_read_time(self, content_length: int = 0) -> float:
        """
        计算阅读时间

        人类不会一口气读完，而是断断续续
        """
        # 基础阅读速度 (字符/秒)
        base_speed = random.uniform(20, 50)

        # 计算总阅读时间
        total_time = content_length / base_speed if content_length > 0 else random.uniform(5, 30)

        # 分成几段阅读
        segments = random.randint(1, 4)
        read_time = 0

        for _ in range(segments):
            # 每段阅读时间
            segment_time = total_time / segments * random.uniform(0.5, 1.5)
            read_time += segment_time

            # 段之间可能停顿
            if _ < segments - 1:
                read_time += random.uniform(1, 5)  # 刷手机/思考时间

        return max(3, min(read_time, 120))

    def get_scroll_pattern(self, page_height: int, viewport_height: int) -> List[dict]:
        """
        生成滚动模式

        人类滚动不是匀速，而是:
        - 快速扫过不感兴趣的内容
        - 在感兴趣的内容处停顿
        - 偶尔回滚查看
        """
        pattern = []
        current_pos = 0
        total_height = page_height

        while current_pos < total_height:
            # 滚动距离: 随机
            scroll_amount = random.randint(
                int(viewport_height * 0.3),
                int(viewport_height * 1.5)
            )

            # 可能回滚 (10%概率)
            if random.random() < 0.1 and current_pos > 0:
                scroll_amount = -random.randint(50, 200)
            else:
                scroll_amount = abs(scroll_amount)

            new_pos = max(0, min(current_pos + scroll_amount, total_height))

            # 滚动速度
            speed = abs(new_pos - current_pos)
            duration = random.uniform(0.2, 0.8) if speed < 500 else random.uniform(0.5, 1.5)

            pattern.append({
                "from": current_pos,
                "to": new_pos,
                "duration": duration,
                "timestamp": time.time(),
            })

            current_pos = new_pos

            # 滚动后可能停顿
            if random.random() > 0.5:
                pattern.append({
                    "action": "pause",
                    "duration": random.uniform(0.5, 3),
                    "timestamp": time.time(),
                })

        return pattern

    def should_click(self, element_type: str = "link") -> bool:
        """
        判断是否点击

        人类点击有随机性，不是100%点击所有链接
        """
        click_probability = {
            "link": 0.3,      # 链接30%概率点击
            "button": 0.5,    # 按钮50%概率点击
            "image": 0.1,    # 图片10%概率点击
            "text": 0.05,    # 文本5%概率点击
        }
        return random.random() < click_probability.get(element_type, 0.2)

    def get_click_position(self, element_bounds: dict) -> Tuple[int, int]:
        """
        计算点击位置

        人类不会精确点击中心，而是有偏移
        """
        x = element_bounds.get("x", 0) + element_bounds.get("width", 0) / 2
        y = element_bounds.get("y", 0) + element_bounds.get("height", 0) / 2

        # 添加高斯偏移 (中心偏移概率大)
        offset_x = random.gauss(0, element_bounds.get("width", 100) / 6)
        offset_y = random.gauss(0, element_bounds.get("height", 30) / 6)

        return (int(x + offset_x), int(y + offset_y))


# ============== 拟人化装饰器 ==============

def humanized_delay(
    mean: float = 1.0,
    std: float = 0.3,
    min_delay: float = 0.5,
):
    """
    拟人化延迟装饰器

    包装函数，自动添加人类延迟
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            await asyncio.sleep(HumanDelay.normal(mean, std, min_delay))
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            time.sleep(HumanDelay.normal(mean, std, min_delay))
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ============== 导出 ==============

__all__ = [
    "UserAgentPool",
    "HumanDelay",
    "MouseTrajectory",
    "FingerprintPool",
    "HeaderOrder",
    "BehaviorSimulator",
    "humanized_delay",
]
