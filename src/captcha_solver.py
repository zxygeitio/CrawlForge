"""
验证码识别模块
支持滑块、点选、文字识别等
"""

import base64
import io
import time
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any

import numpy as np

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class CaptchaResult:
    """验证码结果"""
    solved: bool
    solution: Any = None
    confidence: float = 0.0
    duration: float = 0.0
    error: Optional[str] = None


class BaseCaptchaSolver(ABC):
    """验证码求解器基类"""

    @abstractmethod
    def solve(self, image: Any = None, **kwargs) -> CaptchaResult:
        """求解验证码"""
        pass

    @abstractmethod
    def detect(self, page: Any = None) -> bool:
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
        self.slide_distance: int = 0
        self.track_list: List = []
        self.w_encrypt: str = ""

    def detect(self, page: Any = None) -> bool:
        """检测滑块验证码"""
        if page is None:
            return False

        slider_selectors = [
            ".slider", ".nc_wrapper", ".geetest_slider",
            ".yidun_slider", ".jd-captcha-slider",
            "[class*='slider']", "[class*='captcha']",
            ".yundong", "[class*='slide']",
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
        bg_image: Image.Image = None,
        slider_image: Image.Image = None,
        offset_x: int = 0,
        bg_image_bytes: bytes = None,
        slider_image_bytes: bytes = None,
    ) -> CaptchaResult:
        """
        求解滑块验证码

        Args:
            bg_image: 背景图 (PIL Image)
            slider_image: 滑块图 (PIL Image)
            offset_x: 滑块初始偏移
            bg_image_bytes: 背景图原始字节数据
            slider_image_bytes: 滑块图原始字节数据

        Returns:
            滑块距离和轨迹
        """
        start_time = time.time()

        try:
            # 优先使用字节数据解码
            if bg_image_bytes:
                bg_image = Image.open(io.BytesIO(bg_image_bytes))
            if slider_image_bytes:
                slider_image = Image.open(io.BytesIO(slider_image_bytes))

            # 缺口识别 - 优先使用OpenCV模板匹配(更精准)
            if CV2_AVAILABLE and bg_image and slider_image:
                gap_x = self._find_gap_by_template_matching(bg_image, slider_image)
            elif bg_image:
                gap_x = self._find_gap_by_edge_detection(bg_image)
            else:
                raise ValueError("Need bg_image or bg_image_bytes")

            # 滑动距离
            self.slide_distance = gap_x - offset_x

            # 生成人类滑动轨迹 (升级版物理模型)
            self.track_list = self._generate_human_trajectory_v2(self.slide_distance)

            duration = time.time() - start_time

            return CaptchaResult(
                solved=True,
                solution={
                    "distance": self.slide_distance,
                    "gap_x": gap_x,
                    "trajectory": self.track_list,
                    "duration": duration,
                },
                confidence=0.9,
                duration=duration,
            )

        except Exception as e:
            return CaptchaResult(
                solved=False,
                solution=None,
                error=str(e),
                duration=time.time() - start_time,
            )

    def _find_gap_by_template_matching(
        self,
        bg_image: Image.Image,
        slider_image: Image.Image,
    ) -> int:
        """
        OpenCV模板匹配找缺口位置 (更高精度)

        Args:
            bg_image: 背景图
            slider_image: 滑块/缺口图

        Returns:
            缺口X坐标
        """
        if not CV2_AVAILABLE:
            raise ImportError("opencv-python not installed")

        # 解码为灰度图
        bg_gray = cv2.cvtColor(
            np.array(bg_image.convert("RGB")),
            cv2.COLOR_RGB2GRAY
        )
        slider_gray = cv2.cvtColor(
            np.array(slider_image.convert("RGB")),
            cv2.COLOR_RGB2GRAY
        )

        # 模板匹配
        result = cv2.matchTemplate(
            bg_gray,
            slider_gray,
            cv2.TM_CCOEFF_NORMED
        )

        # 找到最佳匹配位置
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val < self.match_threshold:
            # 匹配度不够,回退到边缘检测
            return self._find_gap_by_edge_detection(bg_image)

        return max_loc[0]

    def _find_gap_by_edge_detection(self, image: Image.Image) -> int:
        """
        边缘检测找缺口位置

        使用Canny边缘检测 + 轮廓分析
        """
        if not PIL_AVAILABLE:
            raise ImportError("PIL not installed")

        # 转换为灰度图
        gray = image.convert("L")
        img_array = np.array(gray)

        # 计算每列的边缘强度
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

    def _generate_human_trajectory_v2(
        self,
        distance: int,
        duration: float = None,
    ) -> List[List[float]]:
        """
        生成人类滑动轨迹 V2 (物理模型)

        基于文档中的加速度/减速度模型:
        - 前半段加速 (a=2)
        - 后半段减速 (a=-3)
        - Y轴随机抖动模拟人手偏移

        Args:
            distance: 滑动距离(像素)
            duration: 滑动总时长(秒), 默认随机1.2-2.0

        Returns:
            [[x, y, timestamp], ...]
        """
        if distance <= 0:
            return [[0, 0, time.time()]]

        if duration is None:
            duration = random.uniform(1.2, 2.0)

        track_list = []
        current = 0
        start_time = time.time()

        # 缓动拐点 (3/4位置开始减速)
        mid = distance * 3 / 4
        t = 0.2  # 时间步长
        v = 0    # 初速度
        step = 0

        while current < distance:
            # 加速度: 前半段2, 后半段-3
            a = 2 if current < mid else -3

            # 物理学公式
            v0 = v
            v = v0 + a * t
            move = v0 * t + 0.5 * a * t * t
            current += move

            # Y轴随机抖动 (-2到2像素)
            y_offset = random.randint(-2, 3)

            # 时间戳
            timestamp = start_time + step * t

            track_list.append([round(current, 2), y_offset, round(timestamp, 4)])

            step += 1

            # 防止无限循环
            if step > 500:
                break

        # 确保到达终点
        if track_list and track_list[-1][0] != distance:
            track_list[-1][0] = distance

        return track_list

    def _generate_human_trajectory(
        self,
        distance: int,
        duration: float = 1.5,
        steps: int = 50,
    ) -> List[Tuple[int, int, float]]:
        """
        生成人类滑动轨迹 (旧版本保留兼容)

        特点:
        - 先快后慢
        - 有随机抖动
        - 不完全线性
        """
        trajectory = []
        current_x = 0
        start_time = time.time()

        for step in range(steps):
            progress = step / steps
            ease_out = 1 - (1 - progress) ** 3
            jitter = np.random.normal(0, 1.5)
            target_x = int(distance * ease_out + jitter)

            if target_x > current_x:
                current_x = target_x

            timestamp = start_time + (duration * step / steps)
            trajectory.append((current_x, 0, timestamp))

        if trajectory:
            trajectory[-1] = (distance, 0, start_time + duration)

        return trajectory

    def slide_to_position(self, page, slider_selector: str, distance: int = None):
        """
        执行滑动 (Playwright)

        Args:
            page: Playwright page
            slider_selector: 滑块选择器
            distance: 滑动距离 (若为None则使用self.slide_distance)
        """
        if distance is None:
            distance = self.slide_distance

        slider = page.query_selector(slider_selector)
        if not slider:
            raise ValueError(f"Slider not found: {slider_selector}")

        bbox = slider.bounding_box()
        start_x = bbox["x"] + bbox["width"] / 2
        start_y = bbox["y"] + bbox["height"] / 2

        # 使用升级版轨迹
        if not self.track_list:
            self.track_list = self._generate_human_trajectory_v2(distance)

        # 执行拖动
        page.mouse.move(start_x, start_y)
        page.mouse.down()

        for x, y, _ in self.track_list:
            page.mouse.move(start_x + x, start_y + y)
            time.sleep(0.02)

        page.mouse.up()

    def get_track_list(self) -> List[List[float]]:
        """获取生成的轨迹"""
        return self.track_list

    def get_slide_distance(self) -> int:
        """获取滑动距离"""
        return self.slide_distance


class ProtocolSliderCaptchaSolver(SliderCaptchaSolver):
    """
    协议层滑块验证码求解器 (无浏览器依赖)

    完整流程:
    1. 获取验证码资源 (背景图/缺口图/校验参数)
    2. 图像识别计算滑动距离
    3. 生成人类化鼠标轨迹
    4. 调用JS加密生成w参数
    5. 构造验证请求并校验结果
    """

    def __init__(self, session=None):
        super().__init__()
        self.session = session  # requests.Session
        self.encrypt_js = None   # 编译后的JS加密代码
        self.base_params: Dict = {}

    def load_encrypt_js(self, js_file_path: str):
        """加载本地JS加密代码 (用于execjs)"""
        try:
            import execjs
            with open(js_file_path, "r", encoding="utf-8") as f:
                self.encrypt_js = execjs.compile(f.read())
        except ImportError:
            raise ImportError("PyExecJS not installed. Install: pip install pyexecjs")

    def set_session(self, session):
        """设置HTTP会话"""
        self.session = session

    def get_captcha_resource(self, load_url: str, captcha_id: str = None, **kwargs) -> Dict:
        """
        步骤1: 获取验证码资源

        Args:
            load_url: 验证码资源接口URL
            captcha_id: 验证码ID
            **kwargs: 其他请求参数

        Returns:
            基础校验参数字典
        """
        if not self.session:
            import requests
            self.session = requests.Session()

        params = {"id": captcha_id} if captcha_id else {}
        params.update(kwargs)

        res = self.session.get(load_url, params=params)
        res_data = res.json()

        # 提取背景图、缺口图URL与基础校验参数
        self.bg_img_url = res_data.get("bg_img_url") or res_data.get("bg")
        self.slice_img_url = res_data.get("slice_img_url") or res_data.get("slice") or res_data.get("front")

        self.base_params = {
            "note": res_data.get("note"),
            "number": res_data.get("number"),
            "payload": res_data.get("payload"),
            "talking": res_data.get("talking"),
            "chlorophyll": res_data.get("chlorophyll"),
        }

        # 额外参数
        for k, v in res_data.items():
            if k not in ["bg_img_url", "slice_img_url", "bg", "slice", "front"]:
                if v and k not in self.base_params:
                    self.base_params[k] = v

        return self.base_params

    def download_images(self) -> Tuple[bytes, bytes]:
        """
        步骤2: 下载背景图和缺口图

        Returns:
            (bg_image_bytes, slice_image_bytes)
        """
        if not self.session:
            import requests
            self.session = requests.Session()

        bg_bytes = self.session.get(self.bg_img_url).content
        slice_bytes = self.session.get(self.slice_img_url).content

        return bg_bytes, slice_bytes

    def solve(self, bg_image: Image.Image = None, **kwargs) -> CaptchaResult:
        """
        求解滑块验证码

        支持通过协议获取图片后识别
        """
        start_time = time.time()

        try:
            # 如果传的是字节数据
            if isinstance(bg_image, bytes):
                bg_image = Image.open(io.BytesIO(bg_image))

            # 边缘检测找缺口
            gap_x = self._find_gap_by_edge_detection(bg_image)

            self.slide_distance = gap_x

            # 生成人类轨迹
            self.track_list = self._generate_human_trajectory_v2(self.slide_distance)

            duration = time.time() - start_time

            return CaptchaResult(
                solved=True,
                solution={
                    "distance": self.slide_distance,
                    "trajectory": self.track_list,
                    "base_params": self.base_params,
                },
                confidence=0.9,
                duration=duration,
            )

        except Exception as e:
            return CaptchaResult(
                solved=False,
                solution=None,
                error=str(e),
                duration=time.time() - start_time,
            )

    def generate_encrypt_w(self, encrypt_method: str = "getW", **kwargs) -> str:
        """
        步骤4: 调用JS代码生成加密参数w

        Args:
            encrypt_method: JS中的加密方法名
            **kwargs: 额外的加密参数

        Returns:
            加密后的w参数
        """
        if not self.encrypt_js:
            raise ValueError("encrypt_js not loaded. Call load_encrypt_js first")

        # 构造加密入参
        encrypt_params = {
            "track": self.track_list,
            "distance": self.slide_distance,
            **self.base_params,
            **kwargs,
        }

        # 调用JS加密方法
        self.w_encrypt = self.encrypt_js.call(encrypt_method, encrypt_params)
        return self.w_encrypt

    def submit_verify_request(
        self,
        verify_url: str,
        w: str = None,
        method: str = "POST",
    ) -> Tuple[bool, Dict]:
        """
        步骤5: 提交验证请求

        Args:
            verify_url: 验证接口URL
            w: 加密参数 (若为None则使用self.w_encrypt)
            method: 请求方法

        Returns:
            (是否成功, 响应数据)
        """
        if not self.session:
            import requests
            self.session = requests.Session()

        if w is None:
            w = self.w_encrypt

        verify_params = {
            **self.base_params,
            "w": w,
        }

        if method.upper() == "POST":
            res = self.session.post(verify_url, data=verify_params)
        else:
            res = self.session.get(verify_url, params=verify_params)

        res_data = res.json()

        # 校验验证结果
        if "pass_token" in res_data or "pasturkey" in res_data:
            return True, res_data
        if res_data.get("result") == "success" or res_data.get("result") == "true":
            return True, res_data
        if res_data.get("success"):
            return True, res_data

        return False, res_data

    def run_crack(
        self,
        load_url: str,
        verify_url: str,
        captcha_id: str = None,
        encrypt_method: str = "getW",
    ) -> Tuple[bool, Dict]:
        """
        执行完整的验证码破解流程

        Args:
            load_url: 验证码资源接口
            verify_url: 验证提交接口
            captcha_id: 验证码ID
            encrypt_method: JS加密方法名

        Returns:
            (是否成功, 响应数据)
        """
        try:
            # 1. 获取验证码资源
            self.get_captcha_resource(load_url, captcha_id)

            # 2. 下载图片
            bg_bytes, slice_bytes = self.download_images()

            # 3. 图像识别计算距离
            bg_image = Image.open(io.BytesIO(bg_bytes))
            slice_image = Image.open(io.BytesIO(slice_bytes))
            self.solve(bg_image)

            # 4. 生成加密参数w
            if self.encrypt_js:
                self.generate_encrypt_w(encrypt_method)

            # 5. 提交验证
            return self.submit_verify_request(verify_url)

        except Exception as e:
            print(f"破解流程执行失败: {str(e)}")
            return False, {"error": str(e)}


class ImageCaptchaSolver(BaseCaptchaSolver):
    """
    图片验证码求解器

    支持:
    - 数字字母识别 (OCR)
    - 点选验证 (目标检测)
    """

    def __init__(self, use_ai: bool = False):
        self.use_ai = use_ai

    def detect(self, page: Any = None) -> bool:
        """检测图片验证码"""
        if page is None:
            return False

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

    def solve(self, image: Image.Image = None, image_bytes: bytes = None) -> CaptchaResult:
        """识别图片验证码"""
        start_time = time.time()

        try:
            if image_bytes:
                image = Image.open(io.BytesIO(image_bytes))

            if self.use_ai:
                # TODO: 使用AI模型识别
                return CaptchaResult(
                    solved=False,
                    solution=None,
                    error="AI识别未实现",
                    duration=time.time() - start_time,
                )
            else:
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
            return pytesseract.image_to_string(
                image,
                config='--psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            ).strip()
        except ImportError:
            raise NotImplementedError(
                "pytesseract not installed. Install: pip install pytesseract"
            )


class GeeTestCaptchaSolver(BaseCaptchaSolver):
    """
    极验验证码求解器
    """

    def __init__(self):
        self.slider_solver = SliderCaptchaSolver()

    def detect(self, page: Any = None) -> bool:
        """检测极验验证码"""
        if page is None:
            return False

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

    def solve(self, page: Any = None) -> CaptchaResult:
        """求解极验验证码"""
        start_time = time.time()

        try:
            if page is None:
                return CaptchaResult(
                    solved=False,
                    solution=None,
                    error="Page is required",
                    duration=time.time() - start_time,
                )

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

            bg_image = bg_element.screenshot()

            if PIL_AVAILABLE:
                bg_image = Image.open(io.BytesIO(bg_image))

            result = self.slider_solver.solve(bg_image)

            if result.solved:
                distance = result.solution["distance"]
                trajectory = result.solution["trajectory"]

                slider_selector = ".geetest_slider"
                slider = page.query_selector(slider_selector)

                if slider:
                    bbox = slider.bounding_box()
                    page.mouse.move(bbox["x"], bbox["y"])
                    page.mouse.down()

                    for x, y, _ in trajectory:
                        page.mouse.move(bbox["x"] + x, bbox["y"] + y)
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


def create_solver(solver_type: str = "slider", **kwargs) -> BaseCaptchaSolver:
    """
    工厂函数: 创建验证码求解器

    Args:
        solver_type: solver类型 (slider/image/geetest/protocol)
        **kwargs: 传递给求解器的参数

    Returns:
        对应的求解器实例
    """
    solvers = {
        "slider": SliderCaptchaSolver,
        "image": ImageCaptchaSolver,
        "geetest": GeeTestCaptchaSolver,
        "protocol": ProtocolSliderCaptchaSolver,
    }

    solver_class = solvers.get(solver_type, SliderCaptchaSolver)
    return solver_class(**kwargs)
