"""
验证码识别模块
支持滑块、点选、文字识别等
"""

import base64
import io
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple, List

import numpy as np

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


@dataclass
class CaptchaResult:
    """验证码结果"""
    solved: bool
    solution: any  # 解决方案（类型根据验证码类型而定）
    confidence: float = 0.0  # 置信度 0-1
    duration: float = 0.0  # 耗时(秒)
    error: Optional[str] = None


class BaseCaptchaSolver(ABC):
    """验证码求解器基类"""

    @abstractmethod
    def solve(self, image: any) -> CaptchaResult:
        """求解验证码"""
        pass

    @abstractmethod
    def detect(self, page: any) -> bool:
        """检测页面是否存在验证码"""
        pass


class SliderCaptchaSolver(BaseCaptchaSolver):
    """
    滑块验证码求解器

    策略:
    1. 缺口识别 (边缘检测/模板匹配)
    2. 滑动轨迹生成 (人类轨迹模拟)
    3. 缺口距离计算
    """

    def __init__(self):
        self.match_threshold = 0.8

    def detect(self, page: any) -> bool:
        """检测滑块验证码"""
        slider_selectors = [
            ".slider", ".nc_wrapper", ".geetest_slider",
            ".yidun_slider", ".jd-captcha-slider",
            "[class*='slider']", "[class*='captcha']",
        ]

        for selector in slider_selectors:
            try:
                element = page.query_selector(selector)
                if element:
                    return True
            except Exception:
                pass

        return False

    def solve(
        self,
        bg_image: Image.Image,
        slider_image: Image.Image = None,
        offset_x: int = 0,
    ) -> CaptchaResult:
        """
        求解滑块验证码

        Args:
            bg_image: 背景图
            slider_image: 滑块图
            offset_x: 滑块初始偏移

        Returns:
            滑块距离和轨迹
        """
        start_time = time.time()

        try:
            # 边缘检测找缺口
            gap_x = self._find_gap_by_edge_detection(bg_image)

            # 生成人类滑动轨迹
            trajectory = self._generate_human_trajectory(gap_x - offset_x)

            duration = time.time() - start_time

            return CaptchaResult(
                solved=True,
                solution={
                    "distance": gap_x - offset_x,
                    "gap_x": gap_x,
                    "trajectory": trajectory,
                    "duration": duration,
                },
                confidence=0.85,
                duration=duration,
            )

        except Exception as e:
            return CaptchaResult(
                solved=False,
                solution=None,
                error=str(e),
                duration=time.time() - start_time,
            )

    def _find_gap_by_edge_detection(self, image: Image.Image) -> int:
        """
        边缘检测找缺口位置

        使用Canny边缘检测 + 轮廓分析
        """
        if not PIL_AVAILABLE:
            raise ImportError("PIL not installed")

        # 转换为灰度图
        gray = image.convert("L")

        # 边缘检测 (简化版)
        img_array = np.array(gray)

        # 计算每列的边缘强度
        # 缺口处的边缘强度会有明显变化
        edge_strength = np.abs(np.diff(img_array, axis=1))
        col_strength = edge_strength.sum(axis=0)

        # 找到边缘最强的位置 (排除边缘)
        start = int(len(col_strength) * 0.1)
        end = int(len(col_strength) * 0.9)

        max_idx = start + col_strength[start:end].argmax()

        # 平滑处理
        window = 5
        smoothed = np.convolve(
            col_strength[max(0, max_idx-window):min(len(col_strength), max_idx+window)],
            np.ones(window)/window,
            mode='valid'
        )

        return max_idx + smoothed.argmax()

    def _generate_human_trajectory(
        self,
        distance: int,
        duration: float = 1.5,
        steps: int = 50,
    ) -> List[Tuple[int, int, float]]:
        """
        生成人类滑动轨迹

        特点:
        - 先快后慢
        - 有随机抖动
        - 不完全线性
        """
        trajectory = []
        current_x = 0
        start_time = time.time()

        # 使用缓动函数模拟人类加减速
        # 先快后慢，中间有抖动
        for step in range(steps):
            # 进度 (0 -> 1)
            progress = step / steps

            # 缓动函数 (ease-out)
            ease_out = 1 - (1 - progress) ** 3

            # 添加随机抖动
            jitter = np.random.normal(0, 1.5)

            # 计算目标位置
            target_x = int(distance * ease_out + jitter)

            # 确保不倒退
            if target_x > current_x:
                current_x = target_x

            # 时间戳
            timestamp = start_time + (duration * step / steps)

            trajectory.append((current_x, 0, timestamp))

        # 确保最后一个点到达终点
        if trajectory:
            trajectory[-1] = (distance, 0, start_time + duration)

        return trajectory

    def slide_to_position(self, page, slider_selector: str, distance: int):
        """
        执行滑动

        Args:
            page: Playwright page
            slider_selector: 滑块选择器
            distance: 滑动距离
        """
        slider = page.query_selector(slider_selector)
        if not slider:
            raise ValueError(f"Slider not found: {slider_selector}")

        # 获取滑块当前位置
        bbox = slider.bounding_box()
        start_x = bbox["x"] + bbox["width"] / 2
        start_y = bbox["y"] + bbox["height"] / 2

        # 生成轨迹
        trajectory = self._generate_human_trajectory(distance)

        # 执行拖动
        page.mouse.move(start_x, start_y)
        page.mouse.down()

        for x, y, timestamp in trajectory:
            page.mouse.move(x, y)
            time.sleep(0.01)

        page.mouse.up()


class ImageCaptchaSolver(BaseCaptchaSolver):
    """
    图片验证码求解器

    支持:
    - 数字字母识别 (OCR)
    - 点选验证 (目标检测)
    """

    def __init__(self, use_ai: bool = False):
        self.use_ai = use_ai

    def detect(self, page: any) -> bool:
        """检测图片验证码"""
        captcha_selectors = [
            "img[class*='captcha']",
            "#captcha",
            ".captcha-img",
            "img[alt*='captcha']",
        ]

        for selector in captcha_selectors:
            try:
                if page.query_selector(selector):
                    return True
            except Exception:
                pass

        return False

    def solve(self, image: Image.Image) -> CaptchaResult:
        """识别图片验证码"""
        start_time = time.time()

        try:
            if self.use_ai:
                # TODO: 使用AI模型识别
                return CaptchaResult(
                    solved=False,
                    solution=None,
                    error="AI识别未实现",
                    duration=time.time() - start_time,
                )
            else:
                # 使用简单阈值分割
                text = self._simple_ocr(image)
                return CaptchaResult(
                    solved=True,
                    solution={"text": text},
                    confidence=0.6,
                    duration=time.time() - start_time,
                )

        except Exception as e:
            return CaptchaResult(
                solved=False,
                solution=None,
                error=str(e),
                duration=time.time() - start_time,
            )

    def _simple_ocr(self, image: Image.Image) -> str:
        """简单OCR (用于干净的数字字母)"""
        try:
            import pytesseract
            return pytesseract.image_to_string(image, config='--psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz').strip()
        except ImportError:
            raise NotImplementedError("pytesseract not installed. Install with: pip install pytesseract")


class GeeTestCaptchaSolver(BaseCaptchaSolver):
    """
    极验验证码求解器

    步骤:
    1. 获取背景图和滑块图
    2. 计算缺口位置
    3. 生成滑动轨迹
    4. 提交验证
    """

    def __init__(self):
        self.slider_solver = SliderCaptchaSolver()

    def detect(self, page: any) -> bool:
        """检测极验验证码"""
        gee_test_selectors = [
            ".geetest_panel",
            ".geetest_box",
            "[class*='geetest']",
        ]

        for selector in gee_test_selectors:
            try:
                if page.query_selector(selector):
                    return True
            except Exception:
                pass

        return False

    def solve(self, page: any) -> CaptchaResult:
        """求解极验验证码"""
        start_time = time.time()

        try:
            # 获取背景图
            bg_selector = ".geetest_bg"
            bg_element = page.query_selector(bg_selector)
            if not bg_element:
                bg_selector = "[class*='bg-img']"
                bg_element = page.query_selector(bg_selector)

            if not bg_element:
                return CaptchaResult(
                    solved=False,
                    solution=None,
                    error="背景图未找到",
                    duration=time.time() - start_time,
                )

            # 截图
            bg_image = bg_element.screenshot()

            # 解码为 PIL Image
            if PIL_AVAILABLE:
                bg_image = Image.open(io.BytesIO(bg_image))

            # 使用滑块求解器
            result = self.slider_solver.solve(bg_image)

            if result.solved:
                distance = result.solution["distance"]
                trajectory = result.solution["trajectory"]

                # 找到滑块
                slider_selector = ".geetest_slider"
                slider = page.query_selector(slider_selector)

                if slider:
                    # 执行滑动
                    page.mouse.move(slider.bounding_box()["x"], slider.bounding_box()["y"])

                    for x, _, _ in trajectory:
                        page.mouse.move(
                            slider.bounding_box()["x"] + x,
                            slider.bounding_box()["y"]
                        )
                        page.mouse.down()
                        page.mouse.up()

                return CaptchaResult(
                    solved=True,
                    solution={"distance": distance},
                    confidence=result.confidence,
                    duration=time.time() - start_time,
                )

            return result

        except Exception as e:
            return CaptchaResult(
                solved=False,
                solution=None,
                error=str(e),
                duration=time.time() - start_time,
            )


def create_solver(solver_type: str = "slider") -> BaseCaptchaSolver:
    """
    工厂函数: 创建验证码求解器

    Args:
        solver_type: solver类型 (slider/image/geetest)

    Returns:
        对应的求解器实例
    """
    solvers = {
        "slider": SliderCaptchaSolver,
        "image": ImageCaptchaSolver,
        "geetest": GeeTestCaptchaSolver,
    }

    solver_class = solvers.get(solver_type, SliderCaptchaSolver)
    return solver_class()
