"""
隐身浏览器配置
反检测浏览器的各项配置
"""

from typing import Optional
from playwright.sync_api import Browser, BrowserContext, Page


class StealthConfig:
    """
    浏览器隐身配置

    用于绕过:
    - WebDriver检测
    - Canvas指纹
    - WebGL指纹
    - 字体枚举
    - 自动化特性检测
    """

    def __init__(
        self,
        # 基础配置
        headless: bool = True,
        load_extensions: list = None,

        # 浏览器特性
        disable_automation: bool = True,
        randomize_webgl: bool = True,
        randomize_canvas: bool = True,
        hide_fonts: bool = False,
        fake_media_devices: bool = True,
        fake_battery: bool = True,
        fake_timezone: bool = True,

        # 时区配置
        timezone: str = "Asia/Shanghai",
        locale: str = "zh-CN",
        user_agent: str = None,
        viewport: dict = None,

        # 代理配置
        proxy: dict = None,
    ):
        self.headless = headless
        self.load_extensions = load_extensions or []

        self.disable_automation = disable_automation
        self.randomize_webgl = randomize_webgl
        self.randomize_canvas = randomize_canvas
        self.hide_fonts = hide_fonts
        self.fake_media_devices = fake_media_devices
        self.fake_battery = fake_battery
        self.fake_timezone = fake_timezone

        self.timezone = timezone
        self.locale = locale
        self.user_agent = user_agent
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self.proxy = proxy


# ============== 启动参数 ==============

def get_stealth_browser_args() -> list:
    """
    获取浏览器启动参数

    这些参数用于绕过自动化检测
    """
    return [
        # 禁用自动化检测特征
        "--disable-blink-features=AutomationControlled",
        "--disable-automation",

        # 禁用扩展
        "--disable-extensions",
        "--disable-component-extensions-with-background-pages",

        # 禁用提示条
        "--disable-infobars",

        # 性能优化
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-gpu",

        # 禁用一些可能泄露信息的功能
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-sync",
        "--disable-translate",

        # 字体相关
        "--disable-fonts",
        "--disable-font-subpixel-positioning",

        # 关闭铎声
        "--mute-audio",
    ]


def get_stealth_context_args() -> dict:
    """
    获取浏览器上下文参数
    """
    return {
        # 权限
        "permissions": ["geolocation", "notifications"],

        # 不记录日志
        "java_script_enabled": True,
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",

        # 视口
        "viewport": {"width": 1920, "height": 1080},

        # 不忽略证书错误(开发用)
        "ignore_https_errors": True,
    }


# ============== JS注入脚本 ==============

STealth_JS_INJECT = """
// 注入反检测脚本
(function() {
    'use strict';

    // 1. 修改navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true
    });

    // 2. 修改navigator.plugins
    const fakePlugins = [
        {
            name: 'Chrome PDF Plugin',
            description: 'Portable Document Format',
            filename: 'internal-pdf-viewer'
        },
        {
            name: 'Chrome PDF Viewer',
            description: '',
            filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'
        },
        {
            name: 'Native Client',
            description: '',
            filename: 'internal-nacl-plugin'
        }
    ];

    Object.defineProperty(navigator, 'plugins', {
        get: () => fakePlugins,
        configurable: true
    });

    // 3. 修改languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en-US', 'en'],
        configurable: true
    });

    // 4. 移除automation检测
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };

    // 5. Canvas指纹随机化
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type, encoderOptions) {
        const ctx = this.getContext('2d');
        if (ctx) {
            const imageData = ctx.getImageData(0, 0, this.width, this.height);
            // 添加随机噪声
            for (let i = 0; i < imageData.data.length; i += 4) {
                imageData.data[i] += Math.random() * 0.1;
                imageData.data[i + 1] += Math.random() * 0.1;
                imageData.data[i + 2] += Math.random() * 0.1;
            }
            ctx.putImageData(imageData, 0, 0);
        }
        return origToDataURL.apply(this, arguments);
    };

    // 6. WebGL指纹随机化
    const origGetParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(pname) {
        // UNMASKED_VENDOR
        if (pname === 37445) {
            return 'Intel Inc.';
        }
        // UNMASKED_RENDERER
        if (pname === 37446) {
            return 'Intel Iris OpenGL Engine';
        }
        return origGetParameter.apply(this, arguments);
    };

    // 7. AudioContext指纹处理
    const origGetChannelData = AudioContext.prototype.decodeAudioData;
    AudioContext.prototype.decodeAudioData = function(data) {
        return origGetChannelData.apply(this, arguments);
    };

    // 8. 定时器偏差校正
    const origSetTimeout = window.setTimeout;
    window.setTimeout = function(func, delay, ...args) {
        // 添加小量随机偏移
        const jitter = Math.random() * 5;
        return origSetTimeout(func, delay + jitter, ...args);
    };

    console.log('[Stealth] Anti-detection scripts injected');
})();
"""

WEBGL_NOISE_INJECT = """
// WebGL噪声注入
(function() {
    'use strict';

    // 存储原始函数
    const origGetContext = HTMLCanvasElement.prototype.getContext;

    HTMLCanvasElement.prototype.getContext = function(type, attributes) {
        const context = origGetContext.call(this, type, attributes);

        if (type === 'webgl' || type === 'experimental-webgl') {
            // 添加噪声到渲染结果
            const origGetParameter = context.getParameter;
            context.getParameter = function(pname) {
                const value = origGetParameter.apply(this, arguments);

                // 对某些参数添加随机偏移
                if (typeof value === 'number') {
                    return value + (Math.random() - 0.5) * 0.01;
                }
                return value;
            };

            // 噪声到像素数据
            const origReadPixels = context.readPixels;
            context.readPixels = function(x, y, width, height, format, type, pixels) {
                const result = origReadPixels.apply(this, arguments);
                if (pixels && pixels instanceof Uint8Array) {
                    for (let i = 0; i < pixels.length; i++) {
                        pixels[i] = Math.min(255, pixels[i] + Math.floor(Math.random() * 3) - 1);
                    }
                }
                return result;
            };
        }

        return context;
    };
})();
"""

CANVAS_FONT_INJECT = """
// Canvas字体枚举混淆
(function() {
    'use strict';

    // 拦截measureText
    const origMeasureText = CanvasRenderingContext2D.prototype.measureText;
    CanvasRenderingContext2D.prototype.measureText = function(text, font) {
        // 随机化返回值的小数部分
        const result = origMeasureText.apply(this, arguments);
        if (result && typeof result.width === 'number') {
            const jitter = (Math.random() - 0.5) * 0.1;
            result.width = result.width + jitter;
        }
        return result;
    };
})();
"""

MEDIA_DEVICES_INJECT = """
// 模拟媒体设备
(function() {
    'use strict';

    if (!navigator.mediaDevices) {
        navigator.mediaDevices = {};
    }

    const fakeDevices = [
        {
            deviceId: 'default',
            groupId: 'group_0',
            kind: 'audioinput',
            label: 'Built-in Microphone'
        },
        {
            deviceId: 'default',
            groupId: 'group_1',
            kind: 'videoinput',
            label: 'Built-in Camera'
        }
    ];

    navigator.mediaDevices.enumerateDevices = function() {
        return Promise.resolve(fakeDevices);
    };

    // Hook getUserMedia
    const origGetUserMedia = navigator.getUserMedia.bind(navigator);
    navigator.getUserMedia = function(constraints, successCallback, errorCallback) {
        // 模拟成功
        successCallback({
            getTracks: () => [],
            getAudioTracks: () => [],
            getVideoTracks: () => []
        });
    };
})();
"""

BATTERY_INJECT = """
// Battery API模拟
(function() {
    'use strict';

    const fakeBattery = {
        charging: true,
        chargingTime: 0,
        dischargingTime: Infinity,
        level: 1.0,
        addEventListener: function() {},
        removeEventListener: function() {},
        dispatchEvent: function() { return true; }
    };

    Object.defineProperty(navigator, 'battery', {
        get: () => fakeBattery,
        configurable: true
    });
})();
"""


class StealthBrowser:
    """
    隐身浏览器管理器

    使用示例:
        stealth = StealthBrowser()
        browser = stealth.launch(headless=True)
        page = stealth.create_page(browser)
        page.goto('https://example.com')
    """

    def __init__(self, config: StealthConfig = None):
        self.config = config or StealthConfig()
        self._browser: Optional[Browser] = None
        self._playwright = None

    def launch(self) -> Browser:
        """启动隐身浏览器"""
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()

        args = get_stealth_browser_args()

        # 添加代理支持
        if self.config.proxy:
            proxy = self.config.proxy
            args.append(f"--proxy-server={proxy.get('server', '')}")

        self._browser = self._playwright.chromium.launch(
            headless=self.config.headless,
            args=args
        )

        return self._browser

    def create_context(self) -> BrowserContext:
        """创建隐身上下文"""
        if not self._browser:
            raise RuntimeError("Browser not launched")

        context_args = get_stealth_context_args()

        context = self._browser.new_context(
            **{**context_args}
        )

        # 设置用户代理
        if self.config.user_agent:
            context.set_extra_http_headers({"User-Agent": self.config.user_agent})

        return context

    def create_page(self, context: BrowserContext = None) -> Page:
        """创建注入反检测脚本的页面"""
        if not context:
            context = self.create_context()

        page = context.new_page()

        # 注入基础反检测脚本
        page.evaluate(STealth_JS_INJECT)

        # 根据配置注入其他脚本
        if self.config.randomize_webgl:
            page.evaluate(WEBGL_NOISE_INJECT)

        if self.config.randomize_canvas:
            page.evaluate(CANVAS_FONT_INJECT)

        if self.config.fake_media_devices:
            page.evaluate(MEDIA_DEVICES_INJECT)

        if self.config.fake_battery:
            page.evaluate(BATTERY_INJECT)

        return page

    def close(self):
        """关闭浏览器"""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
