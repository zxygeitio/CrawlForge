"""
TLS指纹分析器
帮助分析目标网站的TLS指纹特征
"""

import hashlib
import json
import socket
import struct
import ssl
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum


class TLSVersion(Enum):
    """TLS版本"""
    SSL3 = (3, 0)
    TLS1_0 = (3, 1)
    TLS1_1 = (3, 2)
    TLS1_2 = (3, 3)
    TLS1_3 = (3, 4)


@dataclass
class TLSCipherSuite:
    """TLS加密套件"""
    id: int
    name: str
    strength: str  # weak/medium/strong


@dataclass
class TLSExtension:
    """TLS扩展"""
    id: int
    name: str
    critical: bool


@dataclass
class TLSEllipticCurve:
    """TLS椭圆曲线"""
    id: int
    name: str


@dataclass
class TLSFingerprint:
    """TLS指纹"""
    ja3: str
    ja3_hash: str
    ja4: Optional[str]
    tls_version: str
    cipher_suites: List[TLSCipherSuite]
    extensions: List[TLSExtension]
    elliptic_curves: List[TLSEllipticCurve]
    elliptic_curve_point_formats: List[int]
    supported_versions: List[str]
    session_tickets: bool
    ssl_pucture: bool


class JA3Calculator:
    """
    JA3 TLS指纹计算器

    JA3格式: TLSVersion,CipherSuites,Extensions,EllipticCurves,EllipticCurvePointFormats
    """

    # TLS 1.3 cipher suites (RFC 8446)
    TLS13_CIPHER_SUITES = {
        0x1301: "TLS_AES_128_GCM_SHA256",
        0x1302: "TLS_AES_256_GCM_SHA384",
        0x1303: "TLS_CHACHA20_POLY1305_SHA256",
        0x1304: "TLS_AES_128_CCM_SHA256",
        0x1305: "TLS_AES_128_CCM_8_SHA256",
    }

    # TLS 1.2 cipher suites
    CIPHER_SUITES = {
        0x0001: ("SSL_RSA_WITH_NULL_MD5", "weak"),
        0x0002: ("SSL_RSA_WITH_NULL_SHA", "weak"),
        0x0003: ("SSL_RSA_WITH_NULL_SHA256", "weak"),
        0x0004: ("SSL_RSA_WITH_RC4_128_MD5", "weak"),
        0x0005: ("SSL_RSA_WITH_RC4_128_SHA", "weak"),
        0x000A: ("SSL_RSA_WITH_3DES_EDE_CBC_SHA", "weak"),
        0x002F: ("TLS_RSA_WITH_AES_128_CBC_SHA", "medium"),
        0x0035: ("TLS_RSA_WITH_AES_256_CBC_SHA", "medium"),
        0x003C: ("TLS_RSA_WITH_AES_128_CBC_SHA256", "medium"),
        0x003D: ("TLS_RSA_WITH_AES_256_CBC_SHA256", "medium"),
        0x002B: ("TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA", "strong"),
        0x002C: ("TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA", "strong"),
        0x0035: ("TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA", "strong"),
        0xC00A: ("TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA", "strong"),
        0xC009: ("TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA", "strong"),
        0xC013: ("TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA", "strong"),
        0xC014: ("TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA", "strong"),
        0xC012: ("TLS_ECDHE_RSA_WITH_3DES_EDE_CBC_SHA", "weak"),
        0xC02F: ("TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256", "strong"),
        0xC030: ("TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384", "strong"),
        0xC02B: ("TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256", "strong"),
        0xC02E: ("TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256", "strong"),
        0xC02F: ("TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256", "strong"),
        0xC030: ("TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384", "strong"),
        0xCCA9: ("TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256", "strong"),
        0xCCAA: ("TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256", "strong"),
    }

    # TLS扩展
    EXTENSIONS = {
        0x0000: ("server_name", True),
        0x0001: ("max_fragment_length", True),
        0x0002: ("client_certificate_url", True),
        0x0003: ("trusted_ca_keys", True),
        0x0004: ("truncated_hmac", True),
        0x0005: ("status_request", False),  # OCSP
        0x0006: ("user_agent", False),
        0x0007: ("authz", True),
        0x0008: ("geoip", True),
        0x0009: ("app_layer_protocol_negotiation", False),  # ALPN
        0x000A: ("extra", True),
        0x000B: ("compress_certificate", False),
        0x000C: ("record_size_limit", False),
        0x000D: ("sig_algorithms", False),
        0x000E: ("use_srtp", False),
        0x000F: ("heartbeat", False),
        0x0010: ("application_layer_protocol_negotiation", False),
        0x0011: ("signed_certificate_timestamp", False),
        0x0012: ("client_certificate_type", True),
        0x0013: ("grease", True),
        0x0014: ("encrypted_client_hellos", True),
        0x0015: ("post_handshake_auth", False),
        0x0016: ("signature_algorithms_cert", False),
        0x0017: ("key_share", False),
        0x0018: ("quic_transport_parameters", False),
        0x0029: ("application_settings", False),
        0x002B: ("supported_versions", False),
        0x002D: ("cookie", False),
        0x002F: ("psk_key_exchange_modes", False),
        0x0031: ("unassigned_31", True),
        0x0032: ("pre_shared_key", False),
        0x3374: ("GREASE", False),
    }

    # 椭圆曲线
    ELLIPTIC_CURVES = {
        0x0017: ("sect163k1", "weak"),
        0x0018: ("sect163r1", "weak"),
        0x0019: ("sect163r2", "weak"),
        0x001D: ("secp160k1", "weak"),
        0x001E: ("secp160r1", "weak"),
        0x001F: ("secp160r2", "weak"),
        0x0020: ("secp192k1", "weak"),
        0x0021: ("secp192r1", "weak"),  # NIST P-192
        0x0022: ("secp224k1", "weak"),
        0x0023: ("secp224r1", "weak"),  # NIST P-224
        0x0024: ("secp256k1", "medium"),
        0x0025: ("secp256r1", "strong"),  # NIST P-256
        0x0026: ("secp384r1", "strong"),  # NIST P-384
        0x0027: ("secp521r1", "strong"),  # NIST P-521
        0x002D: ("brainpoolP256r1", "medium"),
        0x002E: ("brainpoolP384r1", "medium"),
        0x002F: ("brainpoolP512r1", "medium"),
        0x0100: ("ffdhe2048", "medium"),
        0x0101: ("ffdhe3072", "medium"),
        0x0102: ("ffdhe4096", "strong"),
        0x0103: ("ffdhe6144", "strong"),
        0x0104: ("ffdhe8192", "strong"),
        0xFF01: ("GREASE", False),
        0x0A0A: ("GREASE", False),
        0x1A1A: ("GREASE", False),
        0x2A2A: ("GREASE", False),
        0x3A3A: ("GREASE", False),
        0x4A4A: ("GREASE", False),
        0x5A5A: ("GREASE", False),
        0x6A6A: ("GREASE", False),
        0x7A7A: ("GREASE", False),
        0x8A8A: ("GREASE", False),
        0x9A9A: ("GREASE", False),
        0xAAAA: ("GREASE", False),
        0xBABA: ("GREASE", False),
        0xCACA: ("GREASE", False),
        0xDADA: ("GREASE", False),
        0xEAEA: ("GREASE", False),
        0xFAFA: ("GREASE", False),
    }

    # 椭圆曲线点格式
    EC_POINT_FORMATS = {
        0x00: "uncompressed",
        0x01: "ansiX962_compressed_prime",
        0x02: "ansiX962_compressed_char2",
    }

    @classmethod
    def parse_tls_client_hello(cls, data: bytes) -> Dict:
        """
        解析TLS ClientHello数据

        Args:
            data: TLS ClientHello原始字节

        Returns:
            解析后的TLS参数
        """
        try:
            # 跳过TLS record header (至少5字节)
            if len(data) < 6:
                return {}

            result = {
                "tls_version": None,
                "cipher_suites": [],
                "extensions": [],
                "elliptic_curves": [],
                "elliptic_curve_point_formats": [],
            }

            # 解析handshake
            # ContentType (1) + ProtocolVersion (2) + Length (2) = 5 bytes header
            offset = 5

            if len(data) < offset + 4:
                return result

            # HandshakeType (1) + Length (3)
            handshake_type = data[offset]
            handshake_len = struct.unpack(">I", b'\x00' + data[offset+1:offset+4])[0]

            offset += 4

            if handshake_type != 0x01:  # ClientHello
                return result

            # ClientVersion (2)
            if offset + 2 > len(data):
                return result

            result["tls_version"] = (data[offset], data[offset+1])
            offset += 2

            # Random (32 bytes)
            if offset + 32 > len(data):
                return result
            result["client_random"] = data[offset:offset+32].hex()
            offset += 32

            # SessionID
            if offset >= len(data):
                return result
            session_id_len = data[offset]
            offset += 1
            if session_id_len > 0 and offset + session_id_len <= len(data):
                result["session_id"] = data[offset:offset+session_id_len].hex()
                offset += session_id_len

            # CipherSuites
            if offset + 2 > len(data):
                return result
            cipher_suites_len = struct.unpack(">H", data[offset:offset+2])[0]
            offset += 2

            if offset + cipher_suites_len <= len(data):
                for i in range(0, cipher_suites_len, 2):
                    if i + 2 <= cipher_suites_len:
                        cipher_id = struct.unpack(">H", data[offset+i:offset+i+2])[0]
                        result["cipher_suites"].append(cipher_id)
            offset += cipher_suites_len

            # CompressionMethods
            if offset >= len(data):
                return result
            compression_len = data[offset]
            offset += 1
            if offset + compression_len <= len(data):
                result["compression_methods"] = list(data[offset:offset+compression_len])
            offset += compression_len

            # Extensions
            if offset + 2 > len(data):
                return result
            extensions_len = struct.unpack(">H", data[offset:offset+2])[0]
            offset += 2

            if offset + extensions_len <= len(data):
                ext_data = data[offset:offset+extensions_len]
                ext_offset = 0

                while ext_offset + 4 <= len(ext_data):
                    ext_id = struct.unpack(">H", ext_data[ext_offset:ext_offset+2])[0]
                    ext_len = struct.unpack(">H", ext_data[ext_offset+2:ext_offset+4])[0]
                    ext_offset += 4

                    if ext_offset + ext_len > len(ext_data):
                        break

                    ext_content = ext_data[ext_offset:ext_offset+ext_len]

                    # 特殊处理某些扩展
                    if ext_id == 0x000A:  # EllipticCurves
                        if len(ext_content) >= 2:
                            curves_len = struct.unpack(">H", ext_content[0:2])[0]
                            for i in range(0, curves_len, 2):
                                if i + 2 <= len(ext_content):
                                    result["elliptic_curves"].append(
                                        struct.unpack(">H", ext_content[2+i:2+i+2])[0]
                                    )
                    elif ext_id == 0x000B:  # ECPointFormats
                        if len(ext_content) >= 1:
                            result["elliptic_curve_point_formats"] = list(ext_content[1:])

                    result["extensions"].append(ext_id)
                    ext_offset += ext_len

            return result

        except Exception as e:
            return {"error": str(e)}

    @classmethod
    def calculate_ja3(cls, tls_params: Dict) -> Tuple[str, str]:
        """
        计算JA3指纹

        Args:
            tls_params: TLS参数字典

        Returns:
            (ja3_string, ja3_hash)
        """
        if "error" in tls_params:
            return "", ""

        # TLS版本
        tls_version = tls_params.get("tls_version")
        if tls_version:
            version_str = f"{tls_version[0]},{tls_version[1]}"
        else:
            version_str = "0,0"

        # Cipher Suites
        cipher_suites = tls_params.get("cipher_suites", [])
        cipher_str = "-".join(str(c) for c in cipher_suites)

        # Extensions
        extensions = tls_params.get("extensions", [])
        ext_str = "-".join(str(e) for e in extensions)

        # Elliptic Curves
        curves = tls_params.get("elliptic_curves", [])
        curves_str = "-".join(str(c) for c in curves)

        # EC Point Formats
        ec_formats = tls_params.get("elliptic_curve_point_formats", [])
        ec_format_str = "-".join(str(f) for f in ec_formats)

        # 组合JA3字符串
        ja3_string = f"{version_str},{cipher_str},{ext_str},{curves_str},{ec_format_str}"

        # 计算MD5哈希
        ja3_hash = hashlib.md5(ja3_string.encode()).hexdigest()

        return ja3_string, ja3_hash

    @classmethod
    def calculate_ja4(cls, tls_params: Dict) -> Optional[str]:
        """
        计算JA4 TLS指纹 (TLS 1.3)

        JA4格式: t13d1516h2_8f6e9c1d3_b69304c1d80
        """
        if "error" in tls_params:
            return None

        try:
            version = tls_params.get("tls_version")
            if version and version[0] == 3 and version[1] == 4:
                # TLS 1.3
                prefix = "t"
            else:
                prefix = "r"

            # Cipher suites
            cipher_suites = tls_params.get("cipher_suites", [])
            if not cipher_suites:
                return None

            # 第一个和最后一个cipher
            first_cipher = f"{cipher_suites[0]:04x}" if cipher_suites else "0000"
            last_cipher = f"{cipher_suites[-1]:04x}" if cipher_suites else "0000"

            # Extensions数量
            extensions = tls_params.get("extensions", [])
            ext_count = f"{len(extensions):02d}"

            # 构建JA4
            ja4 = f"{prefix}{version[0]}{version[1]}{first_cipher[:2]}{last_cipher[:2]}"
            ja4 += f"_{ext_count}{first_cipher[2:]}"

            # 添加随机部分
            session_id = tls_params.get("session_id", "")
            if session_id:
                random_part = session_id[:8]
            else:
                random_part = "00000000"

            ja4 += f"_{random_part[:4]}{random_part[4:8]}"

            return ja4.upper()

        except Exception:
            return None

    @classmethod
    def format_cipher_suite(cls, cipher_id: int) -> Optional[Tuple[str, str]]:
        """获取cipher suite名称和强度"""
        if cipher_id in cls.TLS13_CIPHER_SUITES:
            return cls.TLS13_CIPHER_SUITES[cipher_id], "strong"
        return cls.CIPHER_SUITES.get(cipher_id)

    @classmethod
    def format_extension(cls, ext_id: int) -> Tuple[str, bool]:
        """获取扩展名称和是否关键"""
        return cls.EXTENSIONS.get(ext_id, (f"unknown_{ext_id}", True))

    @classmethod
    def format_curve(cls, curve_id: int) -> Optional[Tuple[str, str]]:
        """获取曲线名称和强度"""
        return cls.ELLIPTIC_CURVES.get(curve_id)


class TLSFingerprintAnalyzer:
    """
    TLS指纹分析器

    分析目标服务器的TLS指纹特征
    """

    def __init__(self):
        self.ja3_calc = JA3Calculator()

    def connect_and_capture(self, host: str, port: int = 443, timeout: int = 5) -> Optional[bytes]:
        """
        连接目标并捕获TLS ClientHello

        Args:
            host: 目标主机
            port: 端口
            timeout: 超时时间

        Returns:
            TLS ClientHello数据或None
        """
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            with socket.create_connection((host, port), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    # 获取选定的cipher和版本
                    cipher = ssock.cipher()
                    print(f"[TLS] Connected to {host}:{port}")
                    print(f"[TLS] Cipher: {cipher}")

                    # 尝试发送ClientHello并获取响应
                    # 这里主要获取服务器端hello
                    pass

            return None

        except ssl.SSLError as e:
            print(f"[TLS] SSL Error: {e}")
            return None
        except socket.timeout:
            print(f"[TLS] Connection timeout")
            return None
        except socket.gaierror:
            print(f"[TLS] DNS resolution failed")
            return None
        except Exception as e:
            print(f"[TLS] Connection error: {e}")
            return None

    def analyze_from_url(self, url: str) -> Dict:
        """
        从URL分析TLS指纹

        Args:
            url: 目标URL (https://example.com)

        Returns:
            TLS指纹分析结果
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or 443

        return self.analyze(host, port)

    def analyze(self, host: str, port: int = 443) -> Dict:
        """
        分析目标TLS指纹

        Args:
            host: 目标主机
            port: 端口

        Returns:
            TLS指纹分析结果
        """
        result = {
            "host": host,
            "port": port,
            "ja3": None,
            "ja3_hash": None,
            "ja4": None,
            "tls_version": None,
            "cipher_suites": [],
            "extensions": [],
            "elliptic_curves": [],
            "recommendations": [],
        }

        # 模拟常见浏览器的TLS指纹
        # 实际使用需要通过mitmproxy等工具捕获真实ClientHello

        # 常见Chrome TLS 1.3指纹
        chrome_tls13 = {
            "tls_version": (3, 4),
            "cipher_suites": [
                0x1301, 0x1302, 0x1303, 0x1304, 0x1305,
                0x002F, 0x0035, 0x003C, 0x003D,
                0xC02F, 0xC030, 0xCCA9, 0xC02B, 0xC02C, 0xC013, 0xC014,
            ],
            "extensions": [
                0x0000, 0x0005, 0x000A, 0x000B, 0x000D, 0x0010,
                0x0012, 0x0013, 0x0015, 0x0016, 0x0017, 0x0018,
                0x001B, 0x001D, 0x001F, 0x0021, 0x0023, 0x0025,
                0x0029, 0x002B, 0x002D, 0x0031, 0x0033,
            ],
            "elliptic_curves": [
                0x0017, 0x0018, 0x0019, 0x001D, 0x001E, 0x001F,
                0x0020, 0x0021, 0x0022, 0x0023, 0x0024, 0x0025,
                0x0026, 0x0027, 0x002D, 0x002E, 0x002F,
            ],
            "elliptic_curve_point_formats": [0x00],
        }

        # 计算JA3
        ja3_string, ja3_hash = self.ja3_calc.calculate_ja3(chrome_tls13)
        result["ja3"] = ja3_string
        result["ja3_hash"] = ja3_hash
        result["ja4"] = self.ja3_calc.calculate_ja4(chrome_tls13)
        result["tls_version"] = f"TLS {chrome_tls13['tls_version'][0]}.{chrome_tls13['tls_version'][1]}"

        # 格式化cipher suites
        for cipher_id in chrome_tls13["cipher_suites"]:
            info = self.ja3_calc.format_cipher_suite(cipher_id)
            if info:
                result["cipher_suites"].append({
                    "id": f"0x{cipher_id:04X}",
                    "name": info[0],
                    "strength": info[1],
                })

        # 格式化extensions
        for ext_id in chrome_tls13["extensions"]:
            info = self.ja3_calc.format_extension(ext_id)
            result["extensions"].append({
                "id": f"0x{ext_id:04X}",
                "name": info[0],
                "critical": info[1],
            })

        # 格式化curves
        for curve_id in chrome_tls13["elliptic_curves"]:
            info = self.ja3_calc.format_curve(curve_id)
            if info:
                result["elliptic_curves"].append({
                    "id": f"0x{curve_id:04X}",
                    "name": info[0],
                    "strength": info[1] if len(info) > 1 else "unknown",
                })

        # 生成建议
        result["recommendations"] = self._generate_recommendations(result)

        return result

    def _generate_recommendations(self, fingerprint: Dict) -> List[str]:
        """生成绕过建议"""
        recommendations = []

        # 检查弱加密套件
        weak_ciphers = [c for c in fingerprint["cipher_suites"] if c["strength"] == "weak"]
        if weak_ciphers:
            recommendations.append(
                f"目标支持 {len(weak_ciphers)} 个弱加密套件，考虑使用curl_cffi的impersonate功能"
            )

        # 检查TLS版本
        if "TLS 1.0" in fingerprint["tls_version"] or "TLS 1.1" in fingerprint["tls_version"]:
            recommendations.append(
                "目标支持旧版TLS，建议使用支持TLS 1.3的现代浏览器指纹"
            )

        # JA3指纹
        if fingerprint["ja3_hash"]:
            recommendations.append(
                f"JA3指纹: {fingerprint['ja3_hash']} - 可用于识别目标"
            )
            recommendations.append(
                "使用curl_cffi的impersonate参数可绕过标准JA3检测"
            )

        # JA4指纹
        if fingerprint["ja4"]:
            recommendations.append(
                f"JA4指纹: {fingerprint['ja4']}"
            )

        return recommendations


def detect_tls_fingerprint() -> str:
    """
    快速检测当前环境的TLS指纹

    Returns:
        JA3指纹字符串
    """
    try:
        from curl_cffi import requests
        import json

        # 连接到某个检测网站
        response = requests.get(
            "https://www.howsmyssl.com/a/check",
            impersonate="chrome"
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("ja3_fingerprint", "unknown")

    except Exception as e:
        return f"error: {e}"

    return "unknown"


# 示例用法
if __name__ == "__main__":
    analyzer = TLSFingerprintAnalyzer()

    # 分析example.com
    print("=" * 60)
    print("TLS Fingerprint Analysis")
    print("=" * 60)

    result = analyzer.analyze("www.google.com")

    print(f"\nHost: {result['host']}:{result['port']}")
    print(f"TLS Version: {result['tls_version']}")
    print(f"JA3: {result['ja3']}")
    print(f"JA3 Hash: {result['ja3_hash']}")
    print(f"JA4: {result['ja4']}")

    print(f"\nCipher Suites ({len(result['cipher_suites'])}):")
    for cipher in result["cipher_suites"][:5]:
        print(f"  {cipher['id']}: {cipher['name']} ({cipher['strength']})")

    print(f"\nExtensions ({len(result['extensions'])}):")
    for ext in result["extensions"][:5]:
        critical = "(critical)" if ext["critical"] else ""
        print(f"  {ext['id']}: {ext['name']} {critical}")

    print(f"\nRecommendations:")
    for rec in result["recommendations"]:
        print(f"  - {rec}")
