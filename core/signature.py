"""
签名生成器模块
提供各种签名算法的Python实现
"""

import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Union

from utils.logger import Logger, get_logger
from utils.crypto_utils import MD5, SHA


class SignatureAlgorithm(Enum):
    """签名算法枚举"""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"
    HMAC_MD5 = "hmac_md5"
    HMAC_SHA256 = "hmac_sha256"
    CUSTOM = "custom"


from enum import Enum


@dataclass
class SignatureConfig:
    """签名配置"""
    algorithm: SignatureAlgorithm = SignatureAlgorithm.MD5
    secret_key: str = ""
    sign_param_name: str = "sign"
    timestamp_param_name: str = "timestamp"
    nonce_param_name: str = "nonce"
    include_underscore_params: bool = True
    upper_case: bool = True
    custom_sort: Callable[[dict], list] = None


@dataclass
class SignatureResult:
    """签名结果"""
    sign: str
    params: dict
    timestamp: int
    nonce: str


class SignatureGenerator:
    """
    签名生成器

    支持多种签名算法，提供灵活的参数配置，
    用于生成与目标网站一致的签名参数。
    """

    def __init__(
        self,
        config: SignatureConfig = None,
        logger: Logger = None
    ):
        """
        初始化签名生成器

        Args:
            config: 签名配置
            logger: 日志记录器
        """
        self._config = config or SignatureConfig()
        self._logger = logger or get_logger("SignatureGenerator")

    def generate(
        self,
        params: dict,
        secret_key: str = None,
        include_timestamp: bool = True,
        include_nonce: bool = False
    ) -> SignatureResult:
        """
        生成签名

        Args:
            params: 原始参数字典
            secret_key: 密钥（如果配置中未指定）
            include_timestamp: 是否包含时间戳
            include_nonce: 是否包含随机数

        Returns:
            签名结果对象
        """
        params = self._prepare_params(params)
        secret = secret_key or self._config.secret_key

        timestamp = 0
        nonce = ""

        if include_timestamp:
            timestamp = int(time.time() * 1000)
            params[self._config.timestamp_param_name] = str(timestamp)

        if include_nonce:
            nonce = self._generate_nonce()
            params[self._config.nonce_param_name] = nonce

        sign_string = self._build_sign_string(params)
        sign = self._compute_sign(sign_string, secret)

        return SignatureResult(
            sign=sign,
            params=params,
            timestamp=timestamp,
            nonce=nonce
        )

    def _prepare_params(self, params: dict) -> dict:
        """
        预处理参数

        - 移除空值
        - 移除下划线开头的参数（如果配置）
        - 复制原始字典（不可变性）

        Args:
            params: 原始参数

        Returns:
            处理后的参数字典
        """
        result = {}

        for key, value in params.items():
            if value is None or value == "":
                continue

            if not self._config.include_underscore_params and key.startswith("_"):
                continue

            result[key] = value

        return result

    def _build_sign_string(self, params: dict) -> str:
        """
        构建签名字符串

        Args:
            params: 参数字典

        Returns:
            排序后的参数字符串
        """
        keys = sorted(params.keys())

        if self._config.custom_sort:
            keys = self._config.custom_sort(params)

        pairs = []
        for key in keys:
            value = params[key]
            if isinstance(value, (dict, list)):
                import json
                value = json.dumps(value, ensure_ascii=False)
            else:
                value = str(value)
            pairs.append(f"{key}={value}")

        return "&".join(pairs)

    def _compute_sign(self, sign_string: str, secret: str) -> str:
        """
        计算签名

        Args:
            sign_string: 签名字符串
            secret: 密钥

        Returns:
            签名结果
        """
        algorithm = self._config.algorithm

        if algorithm == SignatureAlgorithm.MD5:
            raw = f"{secret}{sign_string}{secret}"
            sign = MD5.hash(raw)

        elif algorithm == SignatureAlgorithm.SHA1:
            raw = f"{secret}{sign_string}{secret}"
            sign = SHA.sha1(raw)

        elif algorithm == SignatureAlgorithm.SHA256:
            raw = f"{secret}{sign_string}{secret}"
            sign = SHA.sha256(raw)

        elif algorithm == SignatureAlgorithm.SHA512:
            raw = f"{secret}{sign_string}{secret}"
            sign = SHA.sha512(raw)

        elif algorithm == SignatureAlgorithm.HMAC_MD5:
            sign = MD5.hmac(sign_string, secret)

        elif algorithm == SignatureAlgorithm.HMAC_SHA256:
            sign = SHA.hmac_sha256(sign_string, secret)

        elif algorithm == SignatureAlgorithm.CUSTOM:
            raw = f"{secret}{sign_string}{secret}"
            sign = hashlib.md5(raw.encode("utf-8")).hexdigest()

        else:
            raw = f"{secret}{sign_string}{secret}"
            sign = MD5.hash(raw)

        if self._config.upper_case:
            sign = sign.upper()

        return sign

    def _generate_nonce(self, length: int = 16) -> str:
        """
        生成随机数

        Args:
            length: 随机数长度

        Returns:
            随机数字符串
        """
        return uuid.uuid4().hex[:length]

    def add_signature_to_params(self, params: dict, **kwargs) -> dict:
        """
        为参数字典添加签名

        Args:
            params: 原始参数字典
            **kwargs: 其他参数

        Returns:
            包含签名的参数字典
        """
        result = self.generate(params, **kwargs)
        params_copy = dict(params)
        params_copy[self._config.sign_param_name] = result.sign

        if result.timestamp:
            params_copy[self._config.timestamp_param_name] = str(result.timestamp)

        if result.nonce:
            params_copy[self._config.nonce_param_name] = result.nonce

        return params_copy


class MultiplatformSignatureFactory:
    """
    多平台签名工厂

    针对不同平台的签名算法提供预设配置
    """

    @staticmethod
    def create_taobao_signature(app_secret: str) -> SignatureGenerator:
        """
        创建淘宝/天猫签名生成器

        淘宝签名算法使用 HMAC-SHA1
        """
        config = SignatureConfig(
            algorithm=SignatureAlgorithm.HMAC_SHA256,
            secret_key=app_secret,
            sign_param_name="sign",
            timestamp_param_name="timestamp",
            include_underscore_params=False,
            upper_case=True
        )
        return SignatureGenerator(config)

    @staticmethod
    def create_jd_signature(app_secret: str) -> SignatureGenerator:
        """
        创建京东签名生成器

        京东签名算法使用 MD5
        """
        config = SignatureConfig(
            algorithm=SignatureAlgorithm.MD5,
            secret_key=app_secret,
            sign_param_name="sign",
            timestamp_param_name="timestamp",
            include_underscore_params=True,
            upper_case=True
        )
        return SignatureGenerator(config)

    @staticmethod
    def create_pinduoduo_signature(app_secret: str) -> SignatureGenerator:
        """
        创建拼多多签名生成器

        拼多多签名算法较为复杂，使用多次MD5
        """
        config = SignatureConfig(
            algorithm=SignatureAlgorithm.MD5,
            secret_key=app_secret,
            sign_param_name="sign",
            timestamp_param_name="timestamp",
            nonce_param_name="nonce",
            include_underscore_params=False,
            upper_case=True
        )
        return SignatureGenerator(config)

    @staticmethod
    def create_wechat_signature(token: str) -> SignatureGenerator:
        """
        创建微信签名生成器

        微信JS-SDK签名使用SHA1
        """
        config = SignatureConfig(
            algorithm=SignatureAlgorithm.SHA1,
            secret_key=token,
            sign_param_name="signature",
            timestamp_param_name="timestamp",
            include_underscore_params=False,
            upper_case=False
        )
        return SignatureGenerator(config)


class SignatureValidator:
    """
    签名验证器

    验证请求中的签名是否合法
    """

    def __init__(self, generator: SignatureGenerator):
        """
        初始化签名验证器

        Args:
            generator: 签名生成器
        """
        self._generator = generator

    def validate(self, params: dict, sign: str) -> bool:
        """
        验证签名

        Args:
            params: 参数字典
            sign: 要验证的签名

        Returns:
            签名是否有效
        """
        sign_param_name = self._generator._config.sign_param_name
        params_copy = dict(params)
        params_copy.pop(sign_param_name, None)

        result = self._generator.generate(params_copy)
        return result.sign == sign


if __name__ == "__main__":
    print("=== 基本签名生成测试 ===")

    config = SignatureConfig(
        algorithm=SignatureAlgorithm.MD5,
        secret_key="your_secret_key",
        upper_case=True
    )
    generator = SignatureGenerator(config)

    params = {
        "app_id": "123456",
        "method": "user.info",
        "format": "json",
        "v": "1.0"
    }

    result = generator.generate(params)
    print(f"签名: {result.sign}")
    print(f"参数: {result.params}")

    print("\n=== 添加签名到参数 ===")

    params_with_sign = generator.add_signature_to_params(params)
    print(f"带签名的参数: {params_with_sign}")

    print("\n=== 多平台签名工厂测试 ===")

    taobao_gen = MultiplatformSignatureFactory.create_taobao_signature("taobao_secret")
    taobao_result = taobao_gen.generate(params)
    print(f"淘宝签名: {taobao_result.sign}")

    jd_gen = MultiplatformSignatureFactory.create_jd_signature("jd_secret")
    jd_result = jd_gen.generate(params)
    print(f"京东签名: {jd_result.sign}")

    print("\n=== 签名验证测试 ===")

    validator = SignatureValidator(generator)
    is_valid = validator.validate(params, result.sign)
    print(f"签名验证结果: {is_valid}")
