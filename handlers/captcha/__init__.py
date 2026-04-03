"""
验证码处理模块
"""

from .base import (
    BaseCaptchaHandler,
    CaptchaResult,
    CaptchaType,
    CaptchaRecognizer
)
from .slider import SliderCaptchaHandler
from .image import ImageCaptchaHandler, RotateCaptchaHandler

__all__ = [
    "BaseCaptchaHandler",
    "CaptchaResult",
    "CaptchaType",
    "CaptchaRecognizer",
    "SliderCaptchaHandler",
    "ImageCaptchaHandler",
    "RotateCaptchaHandler",
]
