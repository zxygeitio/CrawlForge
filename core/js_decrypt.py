"""
JS加密算法还原模块
提供从JavaScript代码中识别和还原加密算法的功能
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..utils.logger import Logger, get_logger
from ..utils.crypto_utils import MD5, SHA, AES, DES, RSA, Base64Encoder


class CryptoType(Enum):
    """加密类型枚举"""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"
    AES = "aes"
    DES = "des"
    RSA = "rsa"
    BASE64 = "base64"
    HMAC = "hmac"
    UNKNOWN = "unknown"


@dataclass
class CryptoMatch:
    """加密匹配结果"""
    crypto_type: CryptoType
    pattern: str
    code_snippet: str
    confidence: float


class JSDecryptor:
    """
    JavaScript加密算法还原器

    从JS代码中识别常见的加密模式，并提供Python实现
    """

    def __init__(self, logger: Logger = None):
        """
        初始化JS解密器

        Args:
            logger: 日志记录器
        """
        self._logger = logger or get_logger("JSDecryptor")
        self._crypto_patterns = self._init_patterns()

    def _init_patterns(self) -> dict[CryptoType, list[str]]:
        """初始化加密模式匹配正则"""
        return {
            CryptoType.MD5: [
                r"md5\s*\(",
                r"CryptoJS\.MD5",
                r"createHash\s*\(\s*['\"]md5['\"]\s*\)",
                r"\.hash\s*\(\s*['\"]md5['\"]\s*\)",
            ],
            CryptoType.SHA1: [
                r"sha1\s*\(",
                r"CryptoJS\.SHA1",
                r"createHash\s*\(\s*['\"]sha1['\"]\s*\)",
            ],
            CryptoType.SHA256: [
                r"sha256\s*\(",
                r"CryptoJS\.SHA256",
                r"createHash\s*\(\s*['\"]sha256['\"]\s*\)",
            ],
            CryptoType.SHA512: [
                r"sha512\s*\(",
                r"CryptoJS\.SHA512",
                r"createHash\s*\(\s*['\"]sha512['\"]\s*\)",
            ],
            CryptoType.AES: [
                r"AES\.encrypt",
                r"CryptoJS\.AES",
                r"aes\.encrypt",
                r"new\s+AES",
            ],
            CryptoType.DES: [
                r"DES\.encrypt",
                r"CryptoJS\.DES",
                r"des\.encrypt",
                r"new\s+DES",
            ],
            CryptoType.RSA: [
                r"RSA\.encrypt",
                r"CryptoJS\.RSA",
                r"jsEncrypt",
                r"new\s+JSEncrypt",
                r"RSA\.publicEncrypt",
                r"window\.RSA",
            ],
            CryptoType.BASE64: [
                r"btoa\s*\(",
                r"atob\s*\(",
                r"Base64\.encode",
                r"base64_encode",
                r"cryptojs\.enc\.Base64",
            ],
            CryptoType.HMAC: [
                r"createHmac\s*\(",
                r"HmacMD5",
                r"HmacSHA256",
                r"CryptoJS\.HmacMD5",
                r"CryptoJS\.HmacSHA",
            ],
        }

    def detect_crypto(self, js_code: str) -> list[CryptoMatch]:
        """
        检测JS代码中的加密算法

        Args:
            js_code: JavaScript源代码

        Returns:
            检测到的加密算法列表
        """
        matches: list[CryptoMatch] = []

        for crypto_type, patterns in self._crypto_patterns.items():
            for pattern in patterns:
                regex = re.compile(pattern, re.IGNORECASE)
                found = regex.finditer(js_code)
                for match in found:
                    start = max(0, match.start() - 50)
                    end = min(len(js_code), match.end() + 50)
                    snippet = js_code[start:end]

                    confidence = self._calculate_confidence(crypto_type, snippet, js_code)

                    matches.append(CryptoMatch(
                        crypto_type=crypto_type,
                        pattern=pattern,
                        code_snippet=snippet,
                        confidence=confidence
                    ))

        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches

    def _calculate_confidence(
        self,
        crypto_type: CryptoType,
        snippet: str,
        full_code: str
    ) -> float:
        """
        计算匹配置信度

        Args:
            crypto_type: 加密类型
            snippet: 代码片段
            full_code: 完整代码

        Returns:
            置信度分数 (0-1)
        """
        confidence = 0.5

        snippet_lower = snippet.lower()

        if crypto_type == CryptoType.MD5:
            if "md5" in snippet_lower:
                confidence += 0.3
            if "hex" in snippet_lower or "digest" in snippet_lower:
                confidence += 0.1

        elif crypto_type == CryptoType.AES:
            if "aes" in snippet_lower:
                confidence += 0.2
            if "encrypt" in snippet_lower:
                confidence += 0.2
            if "iv" in snippet_lower or "mode" in snippet_lower:
                confidence += 0.1
            if "pkcs7" in snippet_lower or "pksc5" in snippet_lower:
                confidence += 0.1

        elif crypto_type == CryptoType.RSA:
            if "rsa" in snippet_lower:
                confidence += 0.2
            if "public" in snippet_lower or "private" in snippet_lower:
                confidence += 0.2
            if "key" in snippet_lower:
                confidence += 0.1

        elif crypto_type == CryptoType.HMAC:
            if "hmac" in snippet_lower:
                confidence += 0.3

        occurrences = len(re.findall(
            self._crypto_patterns[crypto_type][0] if self._crypto_patterns[crypto_type] else "",
            full_code,
            re.IGNORECASE
        ))
        if occurrences > 1:
            confidence += min(0.1 * (occurrences - 1), 0.2)

        return min(confidence, 1.0)

    def extract_key_from_code(self, js_code: str) -> Optional[str]:
        """
        从代码中提取可能的密钥

        Args:
            js_code: JavaScript源代码

        Returns:
            提取的密钥，如果未找到则返回None
        """
        key_patterns = [
            r"(?:key|secret|password|passwd|pwd)\s*[=:]\s*['\"]([a-zA-Z0-9+/=]{8,})['\"]",
            r"(?:key|secret)\s*[=:]\s*['\"]([^'\"]{8,32})['\"]",
            r"\.setPublicKey\s*\(\s*['\"]([^'\"]+)['\"]",
            r"\.importKey\s*\(\s*['\"]([^'\"]+)['\"]",
        ]

        for pattern in key_patterns:
            match = re.search(pattern, js_code)
            if match:
                return match.group(1)
        return None

    def extract_iv_from_code(self, js_code: str) -> Optional[str]:
        """
        从代码中提取可能的IV向量

        Args:
            js_code: JavaScript源代码

        Returns:
            提取的IV，如果未找到则返回None
        """
        iv_patterns = [
            r"(?:iv|IV)\s*[=:]\s*['\"]([a-zA-Z0-9+/=]{8,})['\"]",
            r"\.createIV\s*\(\s*['\"]([^'\"]+)['\"]",
        ]

        for pattern in iv_patterns:
            match = re.search(pattern, js_code)
            if match:
                return match.group(1)
        return None

    def decrypt_with_python(
        self,
        encrypted_data: str,
        crypto_type: CryptoType,
        key: str = None,
        iv: str = None
    ) -> str:
        """
        使用Python还原的加密算法解密

        Args:
            encrypted_data: 加密的数据
            crypto_type: 加密类型
            key: 密钥
            iv: IV向量

        Returns:
            解密后的字符串
        """
        try:
            if crypto_type == CryptoType.MD5:
                return MD5.hash(encrypted_data)

            elif crypto_type == CryptoType.SHA1:
                return SHA.sha1(encrypted_data)

            elif crypto_type == CryptoType.SHA256:
                return SHA.sha256(encrypted_data)

            elif crypto_type == CryptoType.SHA512:
                return SHA.sha512(encrypted_data)

            elif crypto_type == CryptoType.BASE64:
                if iv:
                    return Base64Encoder.decode(encrypted_data).decode("utf-8")
                else:
                    return Base64Encoder.decode(encrypted_data).decode("utf-8")

            elif crypto_type == CryptoType.AES:
                if not key:
                    raise ValueError("AES解密需要密钥")
                aes = AES(key, iv)
                return aes.decrypt_base64(encrypted_data).decode("utf-8")

            elif crypto_type == CryptoType.DES:
                if not key:
                    raise ValueError("DES解密需要密钥")
                des = DES(key, iv)
                return des.decrypt(Base64Encoder.decode(encrypted_data)).decode("utf-8")

            else:
                raise ValueError(f"不支持的加密类型: {crypto_type}")

        except Exception as e:
            self._logger.error(f"解密失败: {e}")
            raise


class SignatureReconstructor:
    """
    签名算法重建器

    分析JS代码中的签名生成逻辑，重建等效的Python实现
    """

    def __init__(self, logger: Logger = None):
        """
        初始化签名重建器

        Args:
            logger: 日志记录器
        """
        self._logger = logger or get_logger("SignatureReconstructor")

    def extract_sign_params(self, js_code: str) -> dict:
        """
        提取签名相关参数

        Args:
            js_code: JavaScript源代码

        Returns:
            参数字典
        """
        params: dict = {
            "app_key": None,
            "app_secret": None,
            "sign_method": None,
            "timestamp_param": None,
            "nonce_param": None,
        }

        app_key_patterns = [
            r"(?:appKey|app_key|appkey)\s*[=:]\s*['\"]([^'\"]{8,})['\"]",
            r"(?:appId|app_id|appid)\s*[=:]\s*['\"]([^'\"]{8,})['\"]",
        ]
        for pattern in app_key_patterns:
            match = re.search(pattern, js_code)
            if match:
                params["app_key"] = match.group(1)
                break

        timestamp_patterns = [
            r"(?:timestamp|timeStamp)\s*[=:]\s*['\"]?([a-zA-Z0-9]+)['\"]?",
            r"Date\.now\s*\(\s*\)",
        ]
        for pattern in timestamp_patterns:
            if re.search(pattern, js_code):
                params["timestamp_param"] = "timestamp"
                break

        nonce_patterns = [
            r"(?:nonce|random)\s*[=:]\s*['\"]([^'\"]{4,})['\"]",
            r"Math\.random\s*\(\s*\)",
        ]
        for pattern in nonce_patterns:
            if re.search(pattern, js_code):
                params["nonce_param"] = "nonce"
                break

        sign_method_patterns = [
            r"(?:signMethod|sign_method|signMethod)\s*[=:]\s*['\"]([^'\"]{3,})['\"]",
            r"(?:method|algo)\s*[=:]\s*['\"](md5|sha1|sha256|hmac)['\"]",
        ]
        for pattern in sign_method_patterns:
            match = re.search(pattern, js_code, re.IGNORECASE)
            if match:
                params["sign_method"] = match.group(1).lower()
                break

        return params

    def build_signature_string(self, params: dict, separator: str = "&") -> str:
        """
        构建签名字符串

        Args:
            params: 参数字典
            separator: 分隔符

        Returns:
            排序后的参数字符串
        """
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        return separator.join(f"{k}={v}" for k, v in sorted_params if v is not None)

    def generate_signature(
        self,
        params: dict,
        secret: str,
        method: str = "md5",
        upper_case: bool = True
    ) -> str:
        """
        生成签名

        Args:
            params: 参数字典
            secret: 密钥
            method: 签名方法
            upper_case: 是否转大写

        Returns:
            签名结果
        """
        sign_string = self.build_signature_string(params)

        if method == "hmac" or method == "hmac-md5":
            sig = MD5.hmac(sign_string, secret)
        elif method == "hmac-sha256":
            sig = SHA.hmac_sha256(sign_string, secret)
        elif method == "md5":
            sig = MD5.hash(secret + sign_string + secret)
        elif method == "sha256":
            sig = SHA.sha256(secret + sign_string + secret)
        else:
            sig = MD5.hash(secret + sign_string + secret)

        return sig.upper() if upper_case else sig


if __name__ == "__main__":
    js_code = """
    function sign(params) {
        var appKey = 'your_app_key';
        var appSecret = 'your_app_secret';
        var timestamp = Date.now();
        var nonce = Math.random().toString(36).substr(2);

        params.appKey = appKey;
        params.timestamp = timestamp;
        params.nonce = nonce;

        var signStr = '';
        var keys = Object.keys(params).sort();
        for (var i = 0; i < keys.length; i++) {
            signStr += keys[i] + '=' + params[keys[i]] + '&';
        }
        signStr = signStr.slice(0, -1);

        return CryptoJS.MD5(signStr + appSecret).toString();
    }

    var encrypted = CryptoJS.AES.encrypt(data, key, {
        iv: iv,
        mode: CryptoJS.mode.CBC,
        padding: CryptoJS.pad.Pkcs7
    });
    """

    detector = JSDecryptor()
    matches = detector.detect_crypto(js_code)
    print("检测到的加密算法:")
    for match in matches:
        print(f"  - {match.crypto_type.value}: 置信度 {match.confidence:.2f}")
        print(f"    片段: {match.code_snippet[:60]}...")

    reconstructor = SignatureReconstructor()
    sign_params = reconstructor.extract_sign_params(js_code)
    print(f"\n提取的签名参数: {sign_params}")
