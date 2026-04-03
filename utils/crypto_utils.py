"""
加密解密工具模块
提供MD5、SHA、AES、DES、RSA等常用加密算法的实现
"""

import base64
import hashlib
import json
import random
import string
from abc import ABC, abstractmethod
from typing import Union


class CryptoBase(ABC):
    """加密算法基类"""

    @abstractmethod
    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """加密数据"""
        pass

    @abstractmethod
    def decrypt(self, data: bytes) -> bytes:
        """解密数据"""
        pass


class MD5:
    """MD5哈希算法"""

    @staticmethod
    def hash(data: Union[str, bytes], encoding: str = "utf-8") -> str:
        """
        计算MD5哈希值

        Args:
            data: 输入数据
            encoding: 字符串编码格式

        Returns:
            32位十六进制哈希字符串
        """
        if isinstance(data, str):
            data = data.encode(encoding)
        return hashlib.md5(data).hexdigest()

    @staticmethod
    def hash_file(file_path: str, chunk_size: int = 8192) -> str:
        """
        计算文件的MD5哈希值

        Args:
            file_path: 文件路径
            chunk_size: 每次读取的块大小

        Returns:
            32位十六进制哈希字符串
        """
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    @staticmethod
    def hmac(data: Union[str, bytes], key: Union[str, bytes], encoding: str = "utf-8") -> str:
        """
        计算HMAC-MD5

        Args:
            data: 输入数据
            key: 密钥
            encoding: 编码格式

        Returns:
            32位十六进制哈希字符串
        """
        if isinstance(data, str):
            data = data.encode(encoding)
        if isinstance(key, str):
            key = key.encode(encoding)
        return hashlib.hmac_new(key, data, hashlib.md5).hexdigest()


class SHA:
    """SHA系列哈希算法"""

    @staticmethod
    def sha1(data: Union[str, bytes], encoding: str = "utf-8") -> str:
        """计算SHA1哈希值"""
        if isinstance(data, str):
            data = data.encode(encoding)
        return hashlib.sha1(data).hexdigest()

    @staticmethod
    def sha256(data: Union[str, bytes], encoding: str = "utf-8") -> str:
        """计算SHA256哈希值"""
        if isinstance(data, str):
            data = data.encode(encoding)
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def sha512(data: Union[str, bytes], encoding: str = "utf-8") -> str:
        """计算SHA512哈希值"""
        if isinstance(data, str):
            data = data.encode(encoding)
        return hashlib.sha512(data).hexdigest()

    @staticmethod
    def hmac_sha256(data: Union[str, bytes], key: Union[str, bytes], encoding: str = "utf-8") -> str:
        """计算HMAC-SHA256"""
        if isinstance(data, str):
            data = data.encode(encoding)
        if isinstance(key, str):
            key = key.encode(encoding)
        return hashlib.hmac_new(key, data, hashlib.sha256).hexdigest()


class AES(CryptoBase):
    """
    AES加密算法

    支持CBC模式，需要PKCS7填充
    """

    def __init__(self, key: Union[str, bytes], iv: Union[str, bytes] = None, mode: int = 1):
        """
        初始化AES加密器

        Args:
            key: 密钥（16、24或32字节）
            iv: 初始向量（16字节），CBC模式必需
            mode: 加密模式（1=CBC, 2=ECB, 3=CFB, 4=OFB）
        """
        try:
            from Crypto.Cipher import AES as PyAES
        except ImportError:
            raise ImportError("请安装 pycryptodome: pip install pycryptodome")

        if isinstance(key, str):
            key = key.encode("utf-8")
        if isinstance(iv, str):
            iv = iv.encode("utf-8")

        self._key = self._pad_key(key)
        self._iv = iv
        self._mode = mode

    def _pad_key(self, key: bytes) -> bytes:
        """将密钥填充到16、24或32字节"""
        if len(key) < 32:
            key = key.ljust(32, b'\0')
        elif len(key) < 24:
            key = key.ljust(24, b'\0')
        elif len(key) < 16:
            key = key.ljust(16, b'\0')
        return key[:32]

    def _pad_data(self, data: bytes) -> bytes:
        """PKCS7填充"""
        block_size = 16
        padding_length = block_size - (len(data) % block_size)
        return data + bytes([padding_length] * padding_length)

    def _unpad_data(self, data: bytes) -> bytes:
        """移除PKCS7填充"""
        padding_length = data[-1]
        return data[:-padding_length]

    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """
        加密数据

        Args:
            data: 要加密的数据

        Returns:
            加密后的数据
        """
        from Crypto.Cipher import AES as PyAES

        if isinstance(data, str):
            data = data.encode("utf-8")

        data = self._pad_data(data)

        if self._mode == 1:
            cipher = PyAES.new(self._key, PyAES.MODE_CBC, self._iv or b'\0' * 16)
        elif self._mode == 2:
            cipher = PyAES.new(self._key, PyAES.MODE_ECB)
        else:
            raise ValueError(f"不支持的加密模式: {self._mode}")

        return cipher.encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        """
        解密数据

        Args:
            data: 要解密的数据

        Returns:
            解密后的数据
        """
        from Crypto.Cipher import AES as PyAES

        if self._mode == 1:
            cipher = PyAES.new(self._key, PyAES.MODE_CBC, self._iv or b'\0' * 16)
        elif self._mode == 2:
            cipher = PyAES.new(self._key, PyAES.MODE_ECB)
        else:
            raise ValueError(f"不支持的加密模式: {self._mode}")

        decrypted = cipher.decrypt(data)
        return self._unpad_data(decrypted)

    def encrypt_base64(self, data: Union[str, bytes]) -> str:
        """加密并返回Base64编码字符串"""
        return base64.b64encode(self.encrypt(data)).decode("utf-8")

    def decrypt_base64(self, data: Union[str, bytes]) -> bytes:
        """解密Base64编码的字符串"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        return self.decrypt(base64.b64decode(data))


class DES(CryptoBase):
    """
    DES加密算法

    支持CBC模式，需要PKCS7填充
    """

    def __init__(self, key: Union[str, bytes], iv: Union[str, bytes] = None):
        """
        初始化DES加密器

        Args:
            key: 密钥（8字节）
            iv: 初始向量（8字节），CBC模式必需
        """
        try:
            from Crypto.Cipher import DES as PyDES
        except ImportError:
            raise ImportError("请安装 pycryptodome: pip install pycryptodome")

        if isinstance(key, str):
            key = key.encode("utf-8")
        if isinstance(iv, str):
            iv = iv.encode("utf-8")

        self._key = key[:8].ljust(8, b'\0')
        self._iv = iv[:8].ljust(8, b'\0') if iv else b'\0' * 8
        self._cipher = PyDES

    def _pad_data(self, data: bytes) -> bytes:
        """PKCS7填充"""
        padding_length = 8 - (len(data) % 8)
        return data + bytes([padding_length] * padding_length)

    def _unpad_data(self, data: bytes) -> bytes:
        """移除PKCS7填充"""
        padding_length = data[-1]
        return data[:-padding_length]

    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """加密数据"""
        if isinstance(data, str):
            data = data.encode("utf-8")

        data = self._pad_data(data)
        cipher = self._cipher.new(self._key, self._cipher.MODE_CBC, self._iv)
        return cipher.encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        """解密数据"""
        cipher = self._cipher.new(self._key, self._cipher.MODE_CBC, self._iv)
        decrypted = cipher.decrypt(data)
        return self._unpad_data(decrypted)


class RSA(CryptoBase):
    """
    RSA加密算法

    支持公钥加密、私钥解密或私钥加密、公钥解密
    """

    def __init__(
        self,
        public_key: str = None,
        private_key: str = None,
        passphrase: str = None
    ):
        """
        初始化RSA加密器

        Args:
            public_key: PEM格式的公钥字符串或文件路径
            private_key: PEM格式的私钥字符串或文件路径
            passphrase: 私钥口令（如果有）
        """
        try:
            from Crypto.PublicKey import RSA
            from Crypto.Cipher import PKCS1_v1_5
            from Crypto.Signature import pkcs1_15
            from Crypto.Hash import SHA
        except ImportError:
            raise ImportError("请安装 pycryptodome: pip install pycryptodome")

        self._public_key_obj = None
        self._private_key_obj = None
        self._cipher = PKCS1_v1_5
        self._signer = pkcs1_15
        self._hash = SHA

        if public_key:
            if public_key.startswith("-----BEGIN"):
                self._public_key_obj = RSA.import_key(public_key)
            else:
                with open(public_key, "rb") as f:
                    self._public_key_obj = RSA.import_key(f.read())

        if private_key:
            if private_key.startswith("-----BEGIN"):
                self._private_key_obj = RSA.import_key(private_key, passphrase)
            else:
                with open(private_key, "rb") as f:
                    self._private_key_obj = RSA.import_key(f.read(), passphrase)

    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """
        使用公钥加密数据

        Args:
            data: 要加密的数据

        Returns:
            加密后的数据
        """
        if not self._public_key_obj:
            raise ValueError("公钥未设置")

        if isinstance(data, str):
            data = data.encode("utf-8")

        cipher = self._cipher.new(self._public_key_obj)
        return cipher.encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        """
        使用私钥解密数据

        Args:
            data: 要解密的数据

        Returns:
            解密后的数据
        """
        if not self._private_key_obj:
            raise ValueError("私钥未设置")

        cipher = self._cipher.new(self._private_key_obj)
        sentinel = b''
        return cipher.decrypt(data, sentinel)

    def sign(self, data: Union[str, bytes]) -> bytes:
        """
        使用私钥签名数据

        Args:
            data: 要签名的数据

        Returns:
            签名字节数据
        """
        if not self._private_key_obj:
            raise ValueError("私钥未设置")

        if isinstance(data, str):
            data = data.encode("utf-8")

        h = self._hash.new(data)
        signer = self._signer.new(self._private_key_obj)
        return signer.sign(h)

    def verify(self, data: Union[str, bytes], signature: bytes) -> bool:
        """
        使用公钥验证签名

        Args:
            data: 原始数据
            signature: 签名数据

        Returns:
            签名是否有效
        """
        if not self._public_key_obj:
            raise ValueError("公钥未设置")

        if isinstance(data, str):
            data = data.encode("utf-8")

        h = self._hash.new(data)
        verifier = self._signer.new(self._public_key_obj)
        try:
            verifier.verify(h, signature)
            return True
        except ValueError:
            return False


class URLEncoder:
    """URL编码工具"""

    @staticmethod
    def encode(data: str, safe: str = "") -> str:
        """
        URL编码

        Args:
            data: 要编码的字符串
            safe: 不需要编码的字符

        Returns:
            编码后的字符串
        """
        from urllib.parse import quote
        return quote(data, safe=safe)

    @staticmethod
    def decode(data: str) -> str:
        """
        URL解码

        Args:
            data: 要解码的字符串

        Returns:
            解码后的字符串
        """
        from urllib.parse import unquote
        return unquote(data)


class Base64Encoder:
    """Base64编码工具"""

    @staticmethod
    def encode(data: Union[str, bytes]) -> str:
        """
        Base64编码

        Args:
            data: 要编码的数据

        Returns:
            编码后的字符串
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        return base64.b64encode(data).decode("utf-8")

    @staticmethod
    def decode(data: Union[str, bytes]) -> bytes:
        """
        Base64解码

        Args:
            data: 要解码的数据

        Returns:
            解码后的字节数据
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        return base64.b64decode(data)


def generate_random_string(length: int, charset: str = None) -> str:
    """
    生成随机字符串

    Args:
        length: 字符串长度
        charset: 字符集，默认字母+数字

    Returns:
        随机字符串
    """
    if charset is None:
        charset = string.ascii_letters + string.digits
    return ''.join(random.choice(charset) for _ in range(length))


if __name__ == "__main__":
    print("=== MD5 测试 ===")
    md5_result = MD5.hash("Hello, World!")
    print(f"MD5('Hello, World!') = {md5_result}")

    print("\n=== SHA256 测试 ===")
    sha_result = SHA.sha256("Hello, World!")
    print(f"SHA256('Hello, World!') = {sha_result}")

    print("\n=== AES 测试 ===")
    aes = AES("0123456789abcdef", "0123456789abcdef")
    encrypted = aes.encrypt_base64("Hello, World!")
    print(f"加密: {encrypted}")
    decrypted = aes.decrypt_base64(encrypted).decode("utf-8")
    print(f"解密: {decrypted}")

    print("\n=== DES 测试 ===")
    des = DES("12345678", "12345678")
    encrypted = des.encrypt("Hello, World!")
    print(f"加密: {base64.b64encode(encrypted).decode()}")
    decrypted = des.decrypt(encrypted).decode("utf-8")
    print(f"解密: {decrypted}")

    print("\n=== Base64 测试 ===")
    encoded = Base64Encoder.encode("Hello, World!")
    print(f"Base64编码: {encoded}")
    decoded = Base64Encoder.decode(encoded).decode("utf-8")
    print(f"Base64解码: {decoded}")

    print("\n=== 随机字符串生成 ===")
    random_str = generate_random_string(16)
    print(f"随机字符串: {random_str}")
