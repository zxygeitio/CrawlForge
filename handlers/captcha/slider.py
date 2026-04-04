"""
滑块验证码处理模块
提供滑块验证码的轨迹生成和缺口识别功能
"""

import math
import random
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from utils.logger import Logger, get_logger
from .base import BaseCaptchaHandler, CaptchaResult, CaptchaType


class SliderCaptchaHandler(BaseCaptchaHandler):
    """
    滑块验证码处理器

    支持滑块缺口识别和轨迹生成
    """

    def __init__(self, logger: Logger = None):
        """
        初始化滑块验证码处理器

        Args:
            logger: 日志记录器
        """
        super().__init__(logger)
        self._edge_threshold = 50
        self._min_gap = 10

    def get_captcha_type(self) -> CaptchaType:
        """获取验证码类型"""
        return CaptchaType.SLIDER

    async def recognize(self, image_data: bytes) -> CaptchaResult:
        """
        识别滑块缺口位置

        Args:
            image_data: 验证码图片数据

        Returns:
            识别结果
        """
        try:
            gap_position = self.find_gap_position(image_data)

            if gap_position is None:
                return CaptchaResult(
                    success=False,
                    message="未找到滑块缺口"
                )

            trajectory = self.generate_trajectory(gap_position)

            return CaptchaResult(
                success=True,
                solution={
                    "gap_x": gap_position,
                    "trajectory": trajectory
                },
                confidence=0.85,
                message="识别成功"
            )

        except Exception as e:
            self._logger.error(f"滑块识别失败: {e}")
            return CaptchaResult(
                success=False,
                message=f"识别异常: {e}"
            )

    def find_gap_position(self, image_data: bytes) -> Optional[int]:
        """
        查找滑块缺口位置

        使用边缘检测算法识别拼图缺口

        Args:
            image_data: 图片数据

        Returns:
            缺口位置x坐标，未找到返回None
        """
        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(image_data))

            if img.mode != "RGB":
                img = img.convert("RGB")

            img_array = np.array(img)
            gray = self._rgb_to_gray(img_array)

            edges = self._detect_edges(gray)

            gap_x = self._find_gap_in_edges(edges)

            return gap_x

        except ImportError:
            self._logger.warning("PIL或numpy未安装，使用随机位置")
            return random.randint(50, 150)

    def _rgb_to_gray(self, rgb_array: np.ndarray) -> np.ndarray:
        """RGB转灰度"""
        return np.dot(rgb_array[..., :3], [0.299, 0.587, 0.114])

    def _detect_edges(self, gray: np.ndarray) -> np.ndarray:
        """边缘检测（Sobel算子）"""
        rows, cols = gray.shape

        sobel_x = np.array([
            [-1, 0, 1],
            [-2, 0, 2],
            [-1, 0, 1]
        ])

        sobel_y = np.array([
            [-1, -2, -1],
            [0, 0, 0],
            [1, 2, 1]
        ])

        grad_x = np.zeros_like(gray, dtype=np.float32)
        grad_y = np.zeros_like(gray, dtype=np.float32)

        for i in range(1, rows - 1):
            for j in range(1, cols - 1):
                gx = np.sum(sobel_x * gray[i-1:i+2, j-1:j+2])
                gy = np.sum(sobel_y * gray[i-1:i+2, j-1:j+2])
                grad_x[i, j] = gx
                grad_y[i, j] = gy

        gradient = np.sqrt(grad_x**2 + grad_y**2)
        gradient = np.clip(gradient, 0, 255).astype(np.uint8)

        return gradient

    def _find_gap_in_edges(self, edges: np.ndarray) -> Optional[int]:
        """在边缘图中寻找缺口"""
        rows, cols = edges.shape

        col_sums = np.sum(edges, axis=0)

        threshold = np.max(col_sums) * 0.3

        gap_candidates = []
        in_gap = False
        gap_start = 0

        for j in range(cols):
            if col_sums[j] < threshold:
                if not in_gap:
                    in_gap = True
                    gap_start = j
            else:
                if in_gap:
                    in_gap = False
                    gap_width = j - gap_start
                    if gap_width >= self._min_gap:
                        gap_candidates.append((gap_start, j))

        if not gap_candidates:
            mean_val = np.mean(col_sums)
            for j in range(cols - 1):
                if col_sums[j] > mean_val and col_sums[j + 1] < mean_val * 0.5:
                    return j

            return cols // 2

        best_gap = max(gap_candidates, key=lambda x: x[1] - x[0])
        return (best_gap[0] + best_gap[1]) // 2

    def generate_trajectory(
        self,
        target_x: int,
        target_y: int = 0,
        duration: float = None,
        steps: int = None
    ) -> list[dict]:
        """
        生成滑块移动轨迹

        使用缓动函数生成更真实的轨迹

        Args:
            target_x: 目标x坐标
            target_y: 目标y坐标
            duration: 移动总时长（秒）
            steps: 轨迹点数量

        Returns:
            轨迹点列表，每个点包含 x, y, t（时间戳）
        """
        if duration is None:
            duration = random.uniform(1.5, 3.0)

        if steps is None:
            steps = int(duration * 60)

        trajectory = []
        start_time = time.time()

        for i in range(steps + 1):
            progress = i / steps

            eased_progress = self._ease_out_back(progress)

            x = int(target_x * eased_progress)
            y = int(target_y * eased_progress)

            y += self._add_human_variation(progress)

            timestamp = start_time + (i / steps) * duration

            trajectory.append({
                "x": x,
                "y": y,
                "t": timestamp
            })

        trajectory = self._add_micro_movements(trajectory, target_x)

        return trajectory

    def _ease_out_back(self, t: float) -> float:
        """
        缓动函数：先快后慢

        Args:
            t: 进度 (0-1)

        Returns:
            缓动后的进度
        """
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)

    def _ease_out_quad(self, t: float) -> float:
        """缓动函数：二次方缓出"""
        return 1 - (1 - t) * (1 - t)

    def _ease_in_out_cubic(self, t: float) -> float:
        """缓动函数：三次方缓入缓出"""
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2

    def _add_human_variation(self, progress: float) -> int:
        """
        添加人类手臂移动的随机抖动

        Args:
            progress: 当前进度

        Returns:
            y轴偏移量
        """
        if progress < 0.1:
            base = random.uniform(-3, 3)
        elif progress > 0.9:
            base = random.uniform(-1, 1)
        else:
            base = random.uniform(-0.5, 0.5) + math.sin(progress * 20) * 0.5

        return int(base)

    def _add_micro_movements(
        self,
        trajectory: list[dict],
        target_x: int
    ) -> list[dict]:
        """
        添加微小的移动（模拟人类手部不稳定）

        Args:
            trajectory: 原始轨迹
            target_x: 目标x坐标

        Returns:
            处理后的轨迹
        """
        processed = []
        last_x = 0

        for i, point in enumerate(trajectory):
            if i == 0:
                processed.append(point)
                last_x = point["x"]
                continue

            current_x = point["x"]
            diff = current_x - last_x

            if abs(diff) > 5:
                jitter = random.randint(-1, 1)
                new_x = last_x + diff + jitter
            else:
                new_x = current_x

            overshoot = 0
            if new_x > target_x:
                overshoot = random.randint(1, 3)
                new_x = target_x - overshoot

            new_y = point["y"] + random.randint(-1, 1)

            processed.append({
                "x": min(new_x, target_x + 2),
                "y": new_y,
                "t": point["t"]
            })

            last_x = min(new_x, target_x)

        return processed

    def calculate_trajectory_distance(self, trajectory: list[dict]) -> float:
        """
        计算轨迹总长度

        Args:
            trajectory: 轨迹点列表

        Returns:
            总长度
        """
        total_distance = 0.0

        for i in range(1, len(trajectory)):
            dx = trajectory[i]["x"] - trajectory[i-1]["x"]
            dy = trajectory[i]["y"] - trajectory[i-1]["y"]
            total_distance += math.sqrt(dx**2 + dy**2)

        return total_distance


@dataclass
class SliderTrajectoryConfig:
    """轨迹生成配置"""
    duration_min: float = 1.5
    duration_max: float = 3.0
    steps_per_second: int = 60
    overshoot_probability: float = 0.3
    overshoot_distance: int = 5
    return_speed_multiplier: float = 2.0


def generate_slider_trajectory(
    target_x: int,
    config: SliderTrajectoryConfig = None
) -> list[dict]:
    """
    生成滑块轨迹的便捷函数

    Args:
        target_x: 目标x坐标
        config: 轨迹配置

    Returns:
        轨迹点列表
    """
    if config is None:
        config = SliderTrajectoryConfig()

    duration = random.uniform(config.duration_min, config.duration_max)
    steps = int(duration * config.steps_per_second)

    handler = SliderCaptchaHandler()
    return handler.generate_trajectory(target_x, steps=steps)


if __name__ == "__main__":
    print("=== 滑块验证码处理测试 ===")

    handler = SliderCaptchaHandler()

    print(f"验证码类型: {handler.get_captcha_type().value}")

    trajectory = handler.generate_trajectory(200, duration=2.0)
    print(f"生成轨迹点数: {len(trajectory)}")
    print(f"轨迹起点: {trajectory[0]}")
    print(f"轨迹终点: {trajectory[-1]}")

    distance = handler.calculate_trajectory_distance(trajectory)
    print(f"轨迹总长度: {distance:.2f}")

    config = SliderTrajectoryConfig(
        duration_min=1.0,
        duration_max=2.0,
        overshoot_probability=0.5
    )
    trajectory2 = generate_slider_trajectory(150, config)
    print(f"\n使用自定义配置生成的轨迹点数: {len(trajectory2)}")
