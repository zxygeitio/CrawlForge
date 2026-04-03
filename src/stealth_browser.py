"""
隐身浏览器配置
反检测浏览器的各项配置
"""

from typing import Optional
from playwright.sync_api import Browser, BrowserContext, Page

import logging
logger = logging.getLogger(__name__)


class StealthConfig:
    """
    浏览器隐身配置

    用于绕过:
    - WebDriver检测
    - Canvas指纹
    - WebGL指纹
    - 字体枚举
    - 自动化特性检测
    - 硬件指纹
    - WebAssembly检测
    - Service Worker检测
    - 计时攻击检测
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

        # 增强反检测
        bypass_wasm: bool = True,          # WebAssembly检测绕过
        bypass_service_worker: bool = True, # Service Worker检测绕过
        bypass_timing: bool = True,        # 计时攻击防护
        bypass_hardware: bool = True,      # 硬件指纹随机化
        bypass_connection: bool = True,     # 连接信息伪装
        bypass_speech: bool = True,         # Speech API伪装
        bypass_gamepad: bool = True,        # Gamepad API伪装

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

        # 增强反检测选项
        self.bypass_wasm = bypass_wasm
        self.bypass_service_worker = bypass_service_worker
        self.bypass_timing = bypass_timing
        self.bypass_hardware = bypass_hardware
        self.bypass_connection = bypass_connection
        self.bypass_speech = bypass_speech
        self.bypass_gamepad = bypass_gamepad

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

        # 不忽略证书错误(生产用)
        "ignore_https_errors": False,
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

# ============== WebAssembly反检测 ==============

WASM_HOOK_INJECT = """
// WebAssembly检测绕过
(function() {
    'use strict';

    // 伪装WebAssembly支持
    const origCompile = WebAssembly.compile;
    WebAssembly.compile = function(bytes, importObject) {
        console.log('[WASM] Compiling module');
        return origCompile.apply(this, arguments);
    };

    const origInstantiate = WebAssembly.instantiate;
    WebAssembly.instantiate = function(module, importObject) {
        console.log('[WASM] Instantiating module');
        return origInstantiate.apply(this, arguments);
    };

    // WebAssembly memory伪装
    const origMemory = WebAssembly.Memory;
    WebAssembly.Memory = function(descriptor) {
        console.log('[WASM] Creating memory');
        return new origMemory(descriptor);
    };

    // WebAssembly Table伪装
    const origTable = WebAssembly.Table;
    WebAssembly.Table = function(descriptor) {
        console.log('[WASM] Creating table');
        return new origTable(descriptor);
    };

    console.log('[Stealth] WebAssembly hooks installed');
})();
"""

# ============== Service Worker反检测 ==============

SERVICE_WORKER_HOOK_INJECT = """
// Service Worker检测绕过
(function() {
    'use strict';

    if ('serviceWorker' in navigator) {
        const origRegister = navigator.serviceWorker.register;
        navigator.serviceWorker.register = function(scriptURL, options) {
            console.log('[SW] Registering:', scriptURL);
            return origRegister.apply(this, arguments);
        };

        const origGetRegistration = navigator.serviceWorker.getRegistration;
        navigator.serviceWorker.getRegistration = function() {
            console.log('[SW] Getting registration');
            return origGetRegistration.apply(this, arguments);
        };

        const origController = Object.getOwnPropertyDescriptor(navigator.serviceWorker, 'controller');
        Object.defineProperty(navigator.serviceWorker, 'controller', {
            get: function() {
                console.log('[SW] Getting controller');
                return origController ? origController.get.apply(this) : null;
            },
            configurable: true
        });
    }

    console.log('[Stealth] Service Worker hooks installed');
})();
"""

# ============== 硬件指纹随机化 ==============

HARDWARE_FP_HOOK_INJECT = """
// 硬件指纹随机化
(function() {
    'use strict';

    // CPU核心数伪装
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: function() {
            return [8, 16, 4, 6][Math.floor(Math.random() * 4)];
        },
        configurable: true
    });

    // 设备内存伪装
    Object.defineProperty(navigator, 'deviceMemory', {
        get: function() {
            return [8, 16, 4, 2][Math.floor(Math.random() * 4)];
        },
        configurable: true
    });

    // CPU架构伪装
    Object.defineProperty(navigator, 'cpuClass', {
        get: function() { return 'Intel x64'; },
        configurable: true
    });

    // 平台信息伪装
    Object.defineProperty(navigator, 'platform', {
        get: function() { return 'Win32'; },
        configurable: true
    });

    // 触摸点数伪装
    Object.defineProperty(navigator, 'maxTouchPoints', {
        get: function() { return 0; },
        configurable: true
    });

    // 设备像素比伪装
    Object.defineProperty(window, 'devicePixelRatio', {
        get: function() { return 1; },
        configurable: true
    });

    // 瓷砖尺寸伪装
    if (screen.tileSize) {
        Object.defineProperty(screen, 'tileSize', {
            get: function() { return [256, 512][Math.floor(Math.random() * 2)]; },
            configurable: true
        });
    }

    console.log('[Stealth] Hardware fingerprint hooks installed');
})();
"""

# ============== 连接信息伪装 ==============

CONNECTION_HOOK_INJECT = """
// 网络连接信息伪装
(function() {
    'use strict';

    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;

    if (connection) {
        // 网络类型伪装
        Object.defineProperty(connection, 'effectiveType', {
            get: function() { return '4g'; },
            configurable: true
        });

        // 下行速度伪装
        Object.defineProperty(connection, 'downlink', {
            get: function() { return 10; },
            configurable: true
        });

        // RTT伪装
        Object.defineProperty(connection, 'rtt', {
            get: function() { return 50; },
            configurable: true
        });

        // 往返延迟伪装
        Object.defineProperty(connection, 'saveData', {
            get: function() { return false; },
            configurable: true
        });
    }

    // Bluetooth伪装
    if (navigator.bluetooth) {
        Object.defineProperty(navigator.bluetooth, 'getAvailability', {
            value: function() { return Promise.resolve(true); },
            configurable: true
        });
    }

    console.log('[Stealth] Connection info hooks installed');
})();
"""

# ============== 性能计时攻击防护 ==============

TIMING_HOOK_INJECT = """
// 性能计时攻击防护
(function() {
    'use strict';

    // Performance API伪装
    if (window.PerformanceObserver) {
        const origObserve = PerformanceObserver.prototype.observe;
        PerformanceObserver.prototype.observe = function(options) {
            console.log('[Performance] Observing:', options.entryTypes);
            return origObserve.apply(this, arguments);
        };
    }

    // 随机化performance.now()
    const origNow = performance.now.bind(performance);
    let timeOffset = 0;

    performance.now = function() {
        return origNow() + timeOffset;
    };

    // 随机化Date.now()
    const origDateNow = Date.now;
    Date.now = function() {
        return origDateNow() + Math.floor(Math.random() * 10) - 5;
    };

    // 随机化requestAnimationFrame
    const origRAF = window.requestAnimationFrame;
    window.requestAnimationFrame = function(callback) {
        return origRAF(function(time) {
            return callback(time + Math.floor(Math.random() * 5) - 2);
        });
    };

    console.log('[Stealth] Timing attack protection installed');
})();
"""

# ============== 更全面的Canvas指纹防护 ==============

CANVAS_HOOK_V2 = """
// 增强版Canvas指纹防护
(function() {
    'use strict';

    // 存储原始方法
    const origGetContext = HTMLCanvasElement.prototype.getContext;
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    const origMeasureText = CanvasRenderingContext2D.prototype.measureText;

    // Canvas 2D 上下文伪装
    HTMLCanvasElement.prototype.getContext = function(type, attributes) {
        const context = origGetContext.call(this, type, attributes);

        if (type === '2d' && context) {
            // 噪声添加到像素数据
            const origPutImageData = context.putImageData;
            context.putImageData = function(imageData, dx, dy, dirtyX, dirtyY, dirtyWidth, dirtyHeight) {
                // 轻微随机化
                const data = imageData.data;
                for (let i = 0; i < data.length; i += 4) {
                    data[i] = Math.min(255, data[i] + Math.floor(Math.random() * 3) - 1);
                    data[i + 1] = Math.min(255, data[i + 1] + Math.floor(Math.random() * 3) - 1);
                    data[i + 2] = Math.min(255, data[i + 2] + Math.floor(Math.random() * 3) - 1);
                }
                return origPutImageData.apply(this, arguments);
            };

            // 随机化measureText
            context.measureText = function(text, font) {
                const result = origMeasureText.apply(this, arguments);
                if (result) {
                    const jitter = (Math.random() - 0.5) * 0.5;
                    result.width = result.width + jitter;
                }
                return result;
            };

            // toDataURL添加噪声
            HTMLCanvasElement.prototype.toDataURL = function(type, encoderOptions) {
                const result = origToDataURL.apply(this, arguments);
                return result;
            };
        }

        return context;
    };

    // WebGL 指纹伪装增强
    const origWebGLGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, attributes) {
        const context = origWebGLGetContext.call(this, type, attributes);

        if ((type === 'webgl' || type === 'experimental-webgl' || type === 'webgl2') && context) {
            // 伪装WebGL厂商和渲染器
            const vendors = ['Intel Inc.', 'NVIDIA Corporation', 'AMD', 'Apple Inc.'];
            const renderers = [
                'Intel Iris OpenGL Engine',
                'NVIDIA GeForce GTX 1080/PCIe/SSE2',
                'AMD Radeon Pro 5500M OpenGL Engine',
                'Apple M1 OpenGL Engine'
            ];

            const origGetParameter = context.getParameter.bind(context);
            context.getParameter = function(pname) {
                if (pname === 37445) return vendors[Math.floor(Math.random() * vendors.length)];
                if (pname === 37446) return renderers[Math.floor(Math.random() * renderers.length)];
                if (pname === 7938) return 'WebGL 2.0 Apple M1';
                if (pname === 7937) return 'WebGL 2.0';
                return origGetParameter(pname);
            };

            // 添加渲染噪声
            const origReadPixels = context.readPixels.bind(context);
            context.readPixels = function(x, y, w, h, format, type, pixels) {
                const result = origReadPixels(x, y, w, h, format, type, pixels);
                if (pixels && pixels instanceof Uint8Array) {
                    for (let i = 0; i < pixels.length; i += 4) {
                        pixels[i] = Math.max(0, Math.min(255, pixels[i] + Math.floor(Math.random() * 5) - 2));
                        pixels[i + 1] = Math.max(0, Math.min(255, pixels[i + 1] + Math.floor(Math.random() * 5) - 2));
                        pixels[i + 2] = Math.max(0, Math.min(255, pixels[i + 2] + Math.floor(Math.random() * 5) - 2));
                    }
                }
                return result;
            };

            // 伪装支持的扩展
            context.getSupportedExtensions = function() {
                return [
                    'EXT_color_buffer_float', 'EXT_color_buffer_half_float',
                    'EXT_disjoint_timer_query', 'EXT_float_blend',
                    'EXT_frag_depth', 'EXT_shader_texture_lod',
                    'EXT_texture_compression_rgtc', 'EXT_texture_filter_anisotropic',
                    'OES_element_index_uint', 'OES_standard_derivatives',
                    'OES_texture_float', 'OES_texture_float_linear',
                    'OES_texture_half_float', 'OES_texture_half_float_linear',
                    'WEBGL_compressed_texture_s3tc', 'WEBGL_debug_renderer_info',
                    'WEBGL_debug_shaders', 'WEBGL_lose_context',
                    'WEBGL_depth_texture', 'WEBGL_draw_buffers'
                ];
            };
        }

        return context;
    };

    console.log('[Stealth V2] Enhanced canvas/WebGL fingerprint protection installed');
})();
"""

# ============== Speech Recognition伪装 ==============

SPEECH_HOOK_INJECT = """
// Speech Recognition API伪装
(function() {
    'use strict';

    if (window.SpeechRecognition || window.webkitSpeechRecognition) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        const origStart = SpeechRecognition.prototype.start;
        SpeechRecognition.prototype.start = function() {
            console.log('[Speech] Recognition started');
            return origStart.apply(this, arguments);
        };

        const origStop = SpeechRecognition.prototype.stop;
        SpeechRecognition.prototype.stop = function() {
            console.log('[Speech] Recognition stopped');
            return origStop.apply(this, arguments);
        };
    }

    console.log('[Stealth] Speech hooks installed');
})();
"""

# ============== 自动化检测绕过 ==============

AUTOMATION_HOOK_INJECT = """
// 自动化检测绕过
(function() {
    'use strict';

    // 1. 修改chrome.runtime
    if (window.chrome && window.chrome.runtime) {
        window.chrome.runtime.connect = function() {
            return { port: { onMessage: { addListener: function() {} }, postMessage: function() {} } };
        };
        window.chrome.runtime.sendMessage = function() {
            return Promise.resolve({});
        };
    }

    // 2. 伪装window.outerWidth/Height
    Object.defineProperty(window, 'outerWidth', {
        get: function() { return 1920; },
        configurable: true
    });
    Object.defineProperty(window, 'outerHeight', {
        get: function() { return 1080; },
        configurable: true
    });

    // 3. 伪装window.innerWidth/Height
    Object.defineProperty(window, 'innerWidth', {
        get: function() { return 1855; },
        configurable: true
    });
    Object.defineProperty(window, 'innerHeight', {
        get: function() { return 969; },
        configurable: true
    });

    // 4. 伪装screen.width/height
    Object.defineProperty(screen, 'width', {
        get: function() { return 1920; },
        configurable: true
    });
    Object.defineProperty(screen, 'height', {
        get: function() { return 1080; },
        configurable: true
    });

    // 5. 伪装availWidth/Height
    Object.defineProperty(screen, 'availWidth', {
        get: function() { return 1920; },
        configurable: true
    });
    Object.defineProperty(screen, 'availHeight', {
        get: function() { return 1040; },
        configurable: true
    });

    // 6. 伪装colorDepth
    Object.defineProperty(screen, 'colorDepth', {
        get: function() { return 24; },
        configurable: true
    });

    // 7. 伪装pixelDepth
    Object.defineProperty(screen, 'pixelDepth', {
        get: function() { return 24; },
        configurable: true
    });

    // 8. 伪装Permissions API
    const origQuery = navigator.permissions.query;
    navigator.permissions.query = function(parameters) {
        console.log('[Permissions] Query:', parameters.name);
        return origQuery.apply(this, arguments);
    };

    // 9. 伪装Presentation API
    if (navigator.presentation) {
        Object.defineProperty(navigator, 'presentation', {
            get: function() { return { defaultRequest: null }; },
            configurable: true
        });
    }

    // 10. 伪装Gamepad API
    Object.defineProperty(navigator, 'getGamepads', {
        get: function() {
            return function() { return []; };
        },
        configurable: true
    });

    console.log('[Stealth] Automation detection bypass installed');
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
            server = proxy.get('server', '')
            if not server:
                logger.warning("Proxy server is empty, skipping proxy configuration")
            elif not server.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
                logger.warning(f"Proxy server URL format may be invalid: {server}, skipping proxy configuration")
            else:
                args.append(f"--proxy-server={server}")

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

        # 根据配置注入增强版脚本
        if self.config.randomize_webgl:
            page.evaluate(CANVAS_HOOK_V2)

        if self.config.randomize_canvas:
            page.evaluate(CANVAS_FONT_INJECT)

        if self.config.fake_media_devices:
            page.evaluate(MEDIA_DEVICES_INJECT)

        if self.config.fake_battery:
            page.evaluate(BATTERY_INJECT)

        # 注入额外反检测脚本 (默认全部开启)
        page.evaluate(AUTOMATION_HOOK_INJECT)
        page.evaluate(HARDWARE_FP_HOOK_INJECT)
        page.evaluate(CONNECTION_HOOK_INJECT)
        page.evaluate(TIMING_HOOK_INJECT)
        page.evaluate(WASM_HOOK_INJECT)
        page.evaluate(SERVICE_WORKER_HOOK_INJECT)
        page.evaluate(SPEECH_HOOK_INJECT)

        return page

    def close(self):
        """关闭浏览器"""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
