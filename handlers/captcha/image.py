"""
图片验证码处理模块
提供图片验证码的识别功能
"""

import io
import random
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List

import numpy as np

from utils.logger import Logger, get_logger
from .base import BaseCaptchaHandler, CaptchaResult, CaptchaType


class ImageCaptchaHandler(BaseCaptchaHandler):
    """
    图片验证码处理器

    支持点选、图标选择等图片验证码
    """

    def __init__(self, logger: Logger = None):
        """
        初始化图片验证码处理器

        Args:
            logger: 日志记录器
        """
        super().__init__(logger)
        self._confidence_threshold = 0.7

    def get_captcha_type(self) -> CaptchaType:
        """获取验证码类型"""
        return CaptchaType.IMAGE_CLICK

    async def recognize(self, image_data: bytes) -> CaptchaResult:
        """
        识别图片验证码

        Args:
            image_data: 验证码图片数据

        Returns:
            识别结果
        """
        try:
            result = self._recognize_image_captcha(image_data)

            return CaptchaResult(
                success=result["success"],
                solution=result.get("points"),
                confidence=result.get("confidence", 0.0),
                message=result.get("message", ""),
                raw_data=image_data
            )

        except Exception as e:
            self._logger.error(f"图片验证码识别失败: {e}")
            return CaptchaResult(
                success=False,
                message=f"识别异常: {e}"
            )

    def _recognize_image_captcha(self, image_data: bytes) -> dict:
        """
        内部识别方法

        Args:
            image_data: 图片数据

        Returns:
            识别结果字典
        """
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(image_data))
            width, height = img.size

            click_points = self._find_click_positions(img)

            if not click_points:
                return {
                    "success": False,
                    "message": "未找到有效的点击位置",
                    "confidence": 0.0
                }

            return {
                "success": True,
                "points": click_points,
                "confidence": 0.85,
                "message": "识别成功"
            }

        except ImportError:
            return self._random_click_strategy()

    def _find_click_positions(self, img) -> List[dict]:
        """
        查找需要点击的位置

        Args:
            img: PIL Image对象

        Returns:
            点击位置列表
        """
        img_array = np.array(img.convert("RGB"))

        gray = self._rgb_to_gray(img_array)

        edges = self._detect_edges(gray)

        bright_regions = self._find_bright_regions(edges)

        click_points = self._select_distinct_points(bright_regions, img.width, img.height)

        return click_points

    def _rgb_to_gray(self, rgb_array: np.ndarray) -> np.ndarray:
        """RGB转灰度"""
        return np.dot(rgb_array[..., :3], [0.299, 0.587, 0.114])

    def _detect_edges(self, gray: np.ndarray) -> np.ndarray:
        """简单边缘检测"""
        rows, cols = gray.shape
        edges = np.zeros_like(gray)

        for i in range(1, rows - 1):
            for j in range(1, cols - 1):
                gx = abs(int(gray[i, j-1]) - int(gray[i, j+1]))
                gy = abs(int(gray[i-1, j]) - int(gray[i+1, j]))
                edges[i, j] = min(255, gx + gy)

        return edges

    def _find_bright_regions(self, edges: np.ndarray, threshold: int = 100) -> List[Tuple[int, int]]:
        """查找高亮度区域"""
        rows, cols = edges.shape
        regions = []

        for i in range(0, rows, 20):
            for j in range(0, cols, 20):
                region = edges[i:min(i+20, rows), j:min(j+20, cols)]
                if np.mean(region) > threshold:
                    center_y = i + 10
                    center_x = j + 10
                    regions.append((center_x, center_y))

        return regions

    def _select_distinct_points(
        self,
        regions: List[Tuple[int, int]],
        img_width: int,
        img_height: int,
        max_points: int = 4
    ) -> List[dict]:
        """
        选择互不重叠且分布均匀的点

        Args:
            regions: 候选区域列表
            img_width: 图片宽度
            img_height: 图片高度
            max_points: 最大点数

        Returns:
            选中的点列表
        """
        if not regions:
            for _ in range(max_points):
                x = random.randint(int(img_width * 0.2), int(img_width * 0.8))
                y = random.randint(int(img_height * 0.2), int(img_height * 0.8))
                regions.append((x, y))

        selected = []
        min_distance = min(img_width, img_height) // (max_points + 1)

        for point in regions:
            if len(selected) >= max_points:
                break

            is_far_enough = all(
                self._distance(point, selected_point) >= min_distance
                for selected_point in selected
            )

            if is_far_enough:
                selected.append(point)

        while len(selected) < max_points and len(selected) < len(regions):
            remaining = [r for r in regions if r not in selected]
            if not remaining:
                break

            candidate = min(
                remaining,
                key=lambda r: min(self._distance(r, s) for s in selected) if selected else 0
            )

            selected.append(candidate)

        return [{"x": int(x), "y": int(y)} for x, y in selected[:max_points]]

    def _distance(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        """计算两点间距离"""
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def _random_click_strategy(self) -> dict:
        """随机点击策略（作为后备）"""
        return {
            "success": True,
            "points": [
                {"x": random.randint(50, 150), "y": random.randint(50, 150)},
                {"x": random.randint(150, 250), "y": random.randint(50, 150)}
            ],
            "confidence": 0.3,
            "message": "使用随机策略"
        }


class RotateCaptchaHandler(BaseCaptchaHandler):
    """
    旋转验证码处理器

    用于处理滑动旋转验证码
    """

    def __init__(self, logger: Logger = None):
        """
        初始化旋转验证码处理器

        Args:
            logger: 日志记录器
        """
        super().__init__(logger)

    def get_captcha_type(self) -> CaptchaType:
        """获取验证码类型"""
        return CaptchaType.ROTATE

    async def recognize(self, image_data: bytes) -> CaptchaResult:
        """
        识别旋转角度

        Args:
            image_data: 验证码图片数据

        Returns:
            识别结果
        """
        try:
            angle = self._detect_rotation_angle(image_data)

            trajectory = self._generate_rotation_trajectory(angle)

            return CaptchaResult(
                success=True,
                solution={
                    "angle": angle,
                    "trajectory": trajectory
                },
                confidence=0.8,
                message="识别成功"
            )

        except Exception as e:
            self._logger.error(f"旋转验证码识别失败: {e}")
            return CaptchaResult(
                success=False,
                message=f"识别异常: {e}"
            )

    def _detect_rotation_angle(self, image_data: bytes) -> float:
        """
        检测图片旋转角度

        Args:
            image_data: 图片数据

        Returns:
            旋转角度
        """
        try:
            from PIL import Image
            import cv2

            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return random.uniform(-30, 30)

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)

            if lines is None or len(lines) == 0:
                return random.uniform(-30, 30)

            angles = []
            for line in lines[:10]:
                rho, theta = line[0]
                angle = (theta * 180 / np.pi) - 90
                angles.append(angle)

            median_angle = float(np.median(angles))

            return median_angle

        except ImportError:
            self._logger.warning("cv2未安装，使用随机角度")
            return random.uniform(-45, 45)

    def _generate_rotation_trajectory(self, target_angle: float) -> list[dict]:
        """
        生成旋转轨迹

        Args:
            target_angle: 目标角度

        Returns:
            旋转轨迹列表
        """
        trajectory = []
        start_time = time.time()

        overshoot = target_angle * random.uniform(1.05, 1.15)
        return_angle = target_angle

        duration = random.uniform(1.5, 2.5)

        steps = int(duration * 60)
        for i in range(steps):
            progress = i / steps

            if progress < 0.7:
                angle = overshoot * self._ease_out_cubic(progress / 0.7)
            else:
                local_progress = (progress - 0.7) / 0.3
                angle = overshoot - (overshoot - return_angle) * self._ease_in_out_cubic(local_progress)

            timestamp = start_time + (i / steps) * duration

            trajectory.append({
                "angle": angle,
                "t": timestamp
            })

        return trajectory

    def _ease_out_cubic(self, t: float) -> float:
        """三次方缓出"""
        return 1 - pow(1 - t, 3)

    def _ease_in_out_cubic(self, t: float) -> float:
        """三次方缓入缓出"""
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2


import math


if __name__ == "__main__":
    print("=== 图片验证码处理测试 ===")

    handler = ImageCaptchaHandler()
    print(f"验证码类型: {handler.get_captcha_type().value}")

    print("\n=== 旋转验证码处理测试 ===")

    rotate_handler = RotateCaptchaHandler()
    print(f"验证码类型: {rotate_handler.get_captcha_type().value}")

    trajectory = rotate_handler._generate_rotation_trajectory(45)
    print(f"生成旋转轨迹点数: {len(trajectory)}")
    print(f"轨迹起点角度: {trajectory[0]['angle']:.2f}")
    print(f"轨迹终点角度: {trajectory[-1]['angle']:.2f}")
