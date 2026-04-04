"""
验证码处理基类模块
定义验证码处理的抽象基类和通用接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from utils.logger import Logger, get_logger


class CaptchaType(Enum):
    """验证码类型枚举"""
    SLIDER = "slider"
    IMAGE_CLICK = "image_click"
    ICON_CLICK = "icon_click"
    ROTATE = "rotate"
    SPACING = "spacing"
    UNKNOWN = "unknown"


@dataclass
class CaptchaResult:
    """验证码识别结果"""
    success: bool
    solution: any = None
    confidence: float = 0.0
    message: str = ""
    raw_data: any = None


class BaseCaptchaHandler(ABC):
    """
    验证码处理器基类

    所有具体验证码处理器应继承此类并实现识别方法
    """

    def __init__(self, logger: Logger = None):
        """
        初始化验证码处理器

        Args:
            logger: 日志记录器
        """
        self._logger = logger or get_logger("BaseCaptchaHandler")

    @abstractmethod
    async def recognize(self, image_data: bytes) -> CaptchaResult:
        """
        识别验证码

        Args:
            image_data: 验证码图片数据

        Returns:
            识别结果
        """
        pass

    @abstractmethod
    def get_captcha_type(self) -> CaptchaType:
        """
        获取验证码类型

        Returns:
            验证码类型
        """
        pass

    def validate_result(self, result: CaptchaResult) -> bool:
        """
        验证识别结果

        Args:
            result: 识别结果

        Returns:
            结果是否有效
        """
        return result.success and result.confidence > 0.5


class CaptchaRecognizer:
    """
    验证码识别管理器

    自动识别验证码类型并调用对应的处理器
    """

    def __init__(self, logger: Logger = None):
        """
        初始化验证码识别器

        Args:
            logger: 日志记录器
        """
        self._logger = logger or get_logger("CaptchaRecognizer")
        self._handlers: dict[CaptchaType, BaseCaptchaHandler] = {}

    def register_handler(
        self,
        captcha_type: CaptchaType,
        handler: BaseCaptchaHandler
    ) -> None:
        """
        注册验证码处理器

        Args:
            captcha_type: 验证码类型
            handler: 处理器实例
        """
        self._handlers[captcha_type] = handler
        self._logger.info(f"注册处理器: {captcha_type.value}")

    def unregister_handler(self, captcha_type: CaptchaType) -> None:
        """
        移除验证码处理器

        Args:
            captcha_type: 验证码类型
        """
        self._handlers.pop(captcha_type, None)

    async def recognize(
        self,
        image_data: bytes,
        captcha_type: CaptchaType = None
    ) -> CaptchaResult:
        """
        识别验证码

        Args:
            image_data: 验证码图片数据
            captcha_type: 验证码类型，如果为None则自动检测

        Returns:
            识别结果
        """
        if captcha_type is None:
            captcha_type = await self._detect_captcha_type(image_data)

        handler = self._handlers.get(captcha_type)
        if not handler:
            return CaptchaResult(
                success=False,
                message=f"没有找到处理 {captcha_type.value} 的处理器"
            )

        return await handler.recognize(image_data)

    async def _detect_captcha_type(self, image_data: bytes) -> CaptchaType:
        """
        自动检测验证码类型

        Args:
            image_data: 验证码图片数据

        Returns:
            检测到的验证码类型
        """
        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(image_data))
            width, height = img.size

            if width > height * 2:
                return CaptchaType.SLIDER

            if height > width * 1.5:
                return CaptchaType.IMAGE_CLICK

            return CaptchaType.UNKNOWN

        except ImportError:
            self._logger.warning("PIL未安装，无法自动检测验证码类型")
            return CaptchaType.UNKNOWN


if __name__ == "__main__":
    class DummyCaptchaHandler(BaseCaptchaHandler):
        def get_captcha_type(self) -> CaptchaType:
            return CaptchaType.SLIDER

        async def recognize(self, image_data: bytes) -> CaptchaResult:
            return CaptchaResult(
                success=True,
                solution={"x": 100, "y": 50},
                confidence=0.95,
                message="识别成功"
            )

    handler = DummyCaptchaHandler()
    recognizer = CaptchaRecognizer()
    recognizer.register_handler(CaptchaType.SLIDER, handler)

    print(f"处理器类型: {handler.get_captcha_type().value}")
