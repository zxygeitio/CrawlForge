"""
AI页面分析器
使用AI能力分析页面结构、检测反爬机制
"""

import base64
import io
import json
import logging
import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from enum import Enum

from bs4 import BeautifulSoup


class CaptchaType(Enum):
    """验证码类型"""
    NONE = "none"
    SLIDER = "slider"
    CLICK = "click"
    IMAGE_SELECT = "image_select"
    TEXT_INPUT = "text_input"
    GEETEST = "geetest"
    HCAPTCHA = "hcaptcha"
    RECAPTCHA = "recaptcha"
    UNKNOWN = "unknown"


class AntiBotMeasure(Enum):
    """反爬措施"""
    NONE = "none"
    TLS_FINGERPRINT = "tls_fingerprint"
    JA3_FINGERPRINT = "ja3_fingerprint"
    JS_FINGERPRINT = "js_fingerprint"
    CANVAS_FINGERPRINT = "canvas_fingerprint"
    WEBGL_FINGERPRINT = "webgl_fingerprint"
    BEHAVIOR_DETECTION = "behavior_detection"
    RATE_LIMIT = "rate_limit"
    IP_BLOCK = "ip_block"
    USER_AGENT_BLOCK = "user_agent_block"
    COOKIE_CHALLENGE = "cookie_challenge"
    JS_CHALLENGE = "js_challenge"
    CAPTCHA = "captcha"
    CLOUDFLARE = "cloudflare"
    INCAPSULA = "incapsula"
    UNKNOWN = "unknown"


@dataclass
class PageElement:
    """页面元素"""
    tag: str
    selector: str
    attributes: Dict[str, str]
    text: Optional[str] = None


@dataclass
class PageAnalysis:
    """页面分析结果"""
    url: str
    title: Optional[str]
    main_content_type: str  # article/listing/form/login/captcha/redirect
    detected_captchas: List[CaptchaType]
    detected_anti_bot: List[AntiBotMeasure]
    captcha_details: Dict[str, Any]
    recommended_method: str  # requests/curl_cffi/playwright
    extraction_hints: Dict[str, Any]
    raw_analysis: Optional[str] = None


@dataclass
class DataExtraction:
    """数据提取结果"""
    fields: Dict[str, Any]
    confidence: float
    raw_data: Optional[Dict] = None


class PageStructureAnalyzer:
    """
    页面结构分析器

    通过HTML/截图分析页面结构，检测反爬机制
    """

    # 验证码特征选择器
    CAPTCHA_SELECTORS = {
        CaptchaType.SLIDER: [
            ".slider", ".nc_wrapper", ".geetest_slider", ".yidun_slider",
            ".jd-captcha-slider", ".captcha-slider", "[class*='slider']",
            ".nc_iconfont_slider", ".wgt-slider", ".tcaptcha-slide",
            "[id*='tcaptcha']", ".youyi-slider",
        ],
        CaptchaType.CLICK: [
            ".captcha-click", ".点选", "[class*='click-captcha']",
            ".image-captcha", ".pic-captcha",
        ],
        CaptchaType.IMAGE_SELECT: [
            "[class*='image-select']", ".select-images", ".captcha-image-grid",
            ".inno-captcha", ".select-image",
        ],
        CaptchaType.TEXT_INPUT: [
            ".captcha-input", ".text-captcha", "[class*='input-captcha']",
            ".captcha-text",
        ],
        CaptchaType.GEETEST: [
            ".geetest_panel", ".geetest_box", "[class*='geetest']",
            "#geetest-wrap",
        ],
        CaptchaType.HCAPTCHA: [
            ".h-captcha", "[data-sitekey]", "#hcapcha",
        ],
        CaptchaType.RECAPTCHA: [
            ".g-recaptcha", "[data-sitekey]", "#recaptcha",
        ],
    }

    # 反爬特征
    ANTIBOT_SELECTORS = {
        AntiBotMeasure.TLS_FINGERPRINT: [],  # 通过网络层面检测
        AntiBotMeasure.JS_FINGERPRINT: [
            "__fp", "fingerprint", "Fingerprint", "fingerprintjs",
        ],
        AntiBotMeasure.CANVAS_FINGERPRINT: [
            "canvas", "Canvas", "toDataURL", "getImageData",
        ],
        AntiBotMeasure.WEBGL_FINGERPRINT: [
            "webgl", "WebGL", "UNMASKED_VENDOR", "UNMASKED_RENDERER",
        ],
        AntiBotMeasure.BEHAVIOR_DETECTION: [
            "mousedown", "mousemove", "mouseup", "touchstart",
            "scroll", "keydown", "keystroke",
        ],
        AntiBotMeasure.COOKIE_CHALLENGE: [
            "cookie", "challenge", "_cf_challenge", "__cf_challenge",
        ],
        AntiBotMeasure.JS_CHALLENGE: [
            "eval", "unescape", "atob", "btoa", "fromCharCode",
        ],
        AntiBotMeasure.CLOUDFLARE: [
            "cloudflare", "cf-content-type-generator", "cf-browser-verification",
            "_cf_unblock", "challenge-platform",
        ],
        AntiBotMeasure.INCAPSULA: [
            "incapsula", "_Incapsula_Resource", "incapsulacaptcha",
        ],
    }

    # 内容类型特征
    CONTENT_TYPE_PATTERNS = {
        "article": [
            r"<article", r"<main", r"<post", r"<content",
            r"class='article'", r"class='post'", r"class='content'",
        ],
        "listing": [
            r"<ul", r"<ol", r"<table", r"class='list'",
            r"class='items'", r"class='product'", r"class='result'",
        ],
        "form": [
            r"<form", r"<input", r"<button.*type=['\"]submit['\"]",
            r"class='login'", r"class='signin'", r"class='form'",
        ],
        "login": [
            r"password", r"username", r"login", r"signin",
            r"class='login'", r"class='signin'", r"class='auth'",
        ],
    }

    def __init__(self):
        self.analysis_cache: Dict[str, PageAnalysis] = {}

    def analyze_html(self, html: str, url: str = "") -> PageAnalysis:
        """
        分析HTML页面结构

        Args:
            html: HTML内容
            url: 页面URL

        Returns:
            页面分析结果
        """
        # 提取title
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else None

        # 检测验证码
        captchas = self._detect_captchas(html)

        # 检测反爬措施
        anti_bots = self._detect_anti_bot_measures(html)

        # 检测内容类型
        content_type = self._detect_content_type(html)

        # 验证码详情
        captcha_details = self._get_captcha_details(html, captchas)

        # 推荐方法
        recommended = self._recommend_method(captchas, anti_bots)

        # 提取提示
        extraction_hints = self._get_extraction_hints(html, content_type)

        return PageAnalysis(
            url=url,
            title=title,
            main_content_type=content_type,
            detected_captchas=captchas,
            detected_anti_bot=anti_bots,
            captcha_details=captcha_details,
            recommended_method=recommended,
            extraction_hints=extraction_hints,
        )

    def _detect_captchas(self, html: str) -> List[CaptchaType]:
        """检测验证码类型"""
        detected = []
        html_lower = html.lower()

        for captcha_type, selectors in self.CAPTCHA_SELECTORS.items():
            for selector in selectors:
                matched = False

                if selector.startswith("."):
                    # Class selector: 匹配完整的class属性值（词边界）
                    class_name = selector[1:]
                    # 匹配 class="xxx slider xxx" 或 class='xxx slider xxx'
                    pattern = rf'''class=["'][^"']*\b{re.escape(class_name)}\b[^"']*["']'''
                    if re.search(pattern, html_lower):
                        matched = True
                elif selector.startswith("#"):
                    # ID selector: 匹配完整的id属性值
                    id_name = selector[1:]
                    pattern = rf'''id=["']\b{re.escape(id_name)}\b["']'''
                    if re.search(pattern, html_lower):
                        matched = True
                elif selector.startswith("["):
                    # 属性选择器 [attr*='value']: 转为正则
                    # 提取属性名和值
                    attr_match = re.match(r"\[([^=]+)[*~^$]?=['\"]([^'\"]+)['\"]\]", selector)
                    if attr_match:
                        attr, value = attr_match.groups()
                        pattern = rf'''{re.escape(attr)}=["'][^"']*{re.escape(value)}[^"']*["']'''
                        if re.search(pattern, html_lower):
                            matched = True

                if matched:
                    detected.append(captcha_type)
                    break

        return list(set(detected))

    def _detect_anti_bot_measures(self, html: str) -> List[AntiBotMeasure]:
        """检测反爬措施"""
        detected = []
        html_lower = html.lower()

        for measure, keywords in self.ANTIBOT_SELECTORS.items():
            for keyword in keywords:
                if keyword.lower() in html_lower:
                    detected.append(measure)
                    break

        # 检查Cloudflare特殊标记
        if "cloudflare" in html_lower or "_cf_challenge" in html_lower:
            if AntiBotMeasure.CLOUDFLARE not in detected:
                detected.append(AntiBotMeasure.CLOUDFLARE)

        # 检查Incapsula
        if "incapsula" in html_lower or "_Incapsula_Resource" in html_lower:
            if AntiBotMeasure.INCAPSULA not in detected:
                detected.append(AntiBotMeasure.INCAPSULA)

        return list(set(detected))

    def _detect_content_type(self, html: str) -> str:
        """检测内容类型"""
        for content_type, patterns in self.CONTENT_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    return content_type
        return "unknown"

    def _get_captcha_details(self, html: str, captchas: List[CaptchaType]) -> Dict:
        """获取验证码详细信息"""
        details = {}

        if CaptchaType.SLIDER in captchas:
            # 查找滑块相关元素
            slider_patterns = [
                r'<div[^>]*class=["\'][^"\']*slider[^"\']*["\'][^>]*>',
                r'<img[^>]*class=["\'][^"\']*(bg|background)[^"\']*["\'][^>]*>',
                r'<img[^>]*class=["\'][^"\']*(slice|piece|缺口)[^"\']*["\'][^>]*>',
            ]
            for pattern in slider_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    details["slider_element"] = match.group(0)[:200]

        if CaptchaType.GEETEST in captchas:
            # 查找极验特定元素
            geetest_patterns = [
                r'class=["\'][^"\']*geetest[^"\']*["\']',
                r'class=["\'][^"\']*gt[^"\']*["\']',
            ]
            for pattern in geetest_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    details["geetest_element"] = match.group(0)[:200]

        return details

    def _recommend_method(
        self,
        captchas: List[CaptchaType],
        anti_bots: List[AntiBotMeasure],
    ) -> str:
        """推荐爬取方法"""
        # 需要浏览器渲染的情况
        browser_required = [
            CaptchaType.SLIDER,
            CaptchaType.CLICK,
            CaptchaType.IMAGE_SELECT,
            CaptchaType.GEETEST,
        ]

        for captcha in captchas:
            if captcha in browser_required:
                return "playwright"

        # 复杂的JS反爬
        complex_js = [
            AntiBotMeasure.JS_FINGERPRINT,
            AntiBotMeasure.CANVAS_FINGERPRINT,
            AntiBotMeasure.WEBGL_FINGERPRINT,
            AntiBotMeasure.CLOUDFLARE,
            AntiBotMeasure.INCAPSULA,
        ]

        for measure in complex_js:
            if measure in anti_bots:
                return "playwright"

        # TLS指纹
        if AntiBotMeasure.TLS_FINGERPRINT in anti_bots:
            return "curl_cffi"

        # 简单页面
        return "requests"

    def _get_extraction_hints(self, html: str, content_type: str) -> Dict:
        """获取数据提取提示"""
        hints = {
            "content_type": content_type,
            "selectors": {},
        }

        if content_type == "article":
            hints["selectors"] = {
                "title": ["article h1", "h1.title", ".article-title", "h1"],
                "content": ["article", ".article-content", ".post-content", ".entry-content"],
                "author": [".author", ".byline", "[rel='author']"],
                "date": [".date", ".time", "[datetime]"],
            }
        elif content_type == "listing":
            hints["selectors"] = {
                "items": ["ul li", "ol li", ".item", ".product", "table tr"],
                "pagination": [".pagination", ".pager", ".page"],
                "next_button": [".next", ".next-page", "a[rel='next']"],
            }
        elif content_type == "form":
            hints["selectors"] = {
                "inputs": ["input", "textarea"],
                "buttons": ["button[type='submit']", "input[type='submit']"],
            }

        return hints


class AIAnalysisPrompt:
    """AI分析提示词生成"""

    CAPTCHA_ANALYSIS_PROMPT = """
你是一个专业的爬虫工程师。请分析这个网页截图中的验证码类型。

验证码类型包括:
- slider: 滑块验证码，需要拖动滑块到缺口位置
- click: 点选验证码，需要点击指定图片
- image_select: 图片选择验证码，需要选择符合要求的图片
- text_input: 文字验证码，需要输入文字
- geetest: 极验验证码
- hcaptcha: HCaptcha
- recaptcha: Google reCaptcha

请返回JSON格式:
{{
    "captcha_type": "slider/click/image_select/text/geetest/hcaptcha/recaptcha/none",
    "confidence": 0.0-1.0,
    "details": {{
        "description": "描述你看到的内容",
        "elements": ["找到的关键元素"],
        "difficulty": "easy/medium/hard"
    }}
}}
"""

    PAGE_STRUCTURE_PROMPT = """
你是一个专业的爬虫工程师。请分析这个网页截图的页面结构。

请返回JSON格式:
{{
    "page_type": "article/listing/form/login/search/results/unknown",
    "main_content_area": {{"x": 0, "y": 0, "width": 0, "height": 0}},
    "key_elements": [
        {{"type": "button/link/form", "text": "文字", "location": {{"x": 0, "y": 0}}}}
    ],
    "data_location": {{"x": 0, "y": 0, "width": 0, "height": 0}},
    "anti_bot_measures": ["captcha", "cloudflare", "login_required", "rate_limit"]
}}
"""

    EXTRACTION_PROMPT = """
你是一个专业的爬虫工程师。请从以下HTML内容中提取结构化数据。

请返回JSON格式:
{{
    "data": {{
        "title": "标题",
        "content": "内容",
        "items": [{{"field1": "value1", "field2": "value2"}}]
    }},
    "confidence": 0.0-1.0,
    "missing_fields": ["缺失的字段"]
}}
"""


class SimpleAIPageAnalyzer:
    """
    简化的AI页面分析器

    不依赖外部API的本地分析
    """

    def __init__(self):
        self.structure_analyzer = PageStructureAnalyzer()

    def analyze_from_html(self, html: str, url: str = "") -> PageAnalysis:
        """从HTML分析页面"""
        return self.structure_analyzer.analyze_html(html, url)

    def analyze_from_screenshot(self, screenshot_bytes: bytes) -> Dict:
        """
        从截图分析页面 (需要外部AI服务)

        这里返回基础分析，实际需要GPT-4V等
        """
        # 基本截图信息
        import struct

        width, height = 0, 0
        try:
            # 简单的PNG尺寸读取
            if screenshot_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                width = struct.unpack(">I", screenshot_bytes[16:20])[0]
                height = struct.unpack(">I", screenshot_bytes[20:24])[0]
        except Exception:
            pass

        return {
            "screenshot_size": {"width": width, "height": height},
            "note": "Use analyze_from_html for basic analysis, or GPT-4V for vision-based analysis",
        }

    def generate_gpt4v_prompt(self, task: str) -> str:
        """
        生成GPT-4V分析的提示词

        Args:
            task: 分析任务 (captcha_analysis/page_structure/data_extraction)

        Returns:
            提示词
        """
        prompts = {
            "captcha_analysis": AIAnalysisPrompt.CAPTCHA_ANALYSIS_PROMPT,
            "page_structure": AIAnalysisPrompt.PAGE_STRUCTURE_PROMPT,
            "data_extraction": AIAnalysisPrompt.EXTRACTION_PROMPT,
        }
        return prompts.get(task, "")

    def suggest_extraction_method(self, html: str) -> Dict:
        """
        建议数据提取方法

        Returns:
            提取建议
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # 检测JSON-LD
            json_ld = soup.find("script", type="application/ld+json")
            if json_ld:
                try:
                    # 校验JSON合法性，防止畸形数据泄露
                    json.loads(json_ld.string)
                    return {
                        "method": "json_ld",
                        "data": json_ld.string,
                    }
                except (json.JSONDecodeError, TypeError) as e:
                    logging.warning(f"Invalid JSON-LD found: {e}")
                    return {"method": "json_ld", "data": None, "error": "malformed JSON-LD"}

            # 检测Microdata
            itemscope = soup.find(attrs={"itemscope": True})
            if itemscope:
                return {
                    "method": "microdata",
                    "selector": "[itemscope]",
                }

            # 检测常见结构
            article = soup.find("article")
            if article:
                return {
                    "method": "article",
                    "selector": "article",
                }

            items = soup.find_all("li", class_=re.compile(r"item|product"))
            if items:
                return {
                    "method": "listing",
                    "selector": "li.item, li.product",
                    "count": len(items),
                }

            return {"method": "generic", "selector": "body"}

        except Exception as e:
            return {"method": "error", "error": str(e)}


# 示例用法
if __name__ == "__main__":
    # 测试页面分析
    html_sample = """
    <html>
    <head><title>Test Page</title></head>
    <body>
        <div class="slider">
            <div class="bg-img"></div>
            <div class="slice-img"></div>
        </div>
        <article>
            <h1 class="title">Article Title</h1>
            <p class="content">Article content...</p>
        </article>
    </body>
    </html>
    """

    analyzer = SimpleAIPageAnalyzer()
    result = analyzer.analyze_from_html(html_sample, "https://example.com")

    print(f"URL: {result.url}")
    print(f"Title: {result.title}")
    print(f"Content Type: {result.main_content_type}")
    print(f"Captchas: {[c.value for c in result.detected_captchas]}")
    print(f"Anti-bot: {[m.value for m in result.detected_anti_bot]}")
    print(f"Recommended: {result.recommended_method}")
    print(f"Extraction Hints: {result.extraction_hints}")
