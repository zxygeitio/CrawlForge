"""
隐身浏览器配置
反检测浏览器的各项配置
"""

from typing import Optional
from playwright.async_api import Browser, BrowserContext, Page

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

    // Hook getUserMedia - 保护性判断，避免 headless Chromium 中 undefined 导致崩溃
    if (navigator.getUserMedia) {
        const origGetUserMedia = navigator.getUserMedia.bind(navigator);
        navigator.getUserMedia = function(constraints, successCallback, errorCallback) {
            // 模拟成功
            successCallback({
                getTracks: () => [],
                getAudioTracks: () => [],
                getVideoTracks: () => []
            });
        };
    }
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

# ============== 深度反检测：CDP 协议特征清除 ==============
# Playwright/Puppeteer 会向 window 注入 __cdc__, __FST__ 等 CDP 协议相关全局变量
# 小红书/Bilibili 等站点直接检测这些属性是否存在

CDP_HOOK_INJECT = """
// 清除 Playwright CDP 协议暴露的全局属性
(function() {
    'use strict';

    // 1. 删除所有可疑的 __cdc* / __FST* 等 Playwright 注入属性
    const cdcPatterns = [
        '__FST__', '__STREAMING__', '__INITIAL_STATE__',
        '__APM_COMBO_CACHE_GROUP_V2__', '__APM_COMBO_CACHE_GROUP__',
        '__VUE_INSTANCE_SETTERS__', '__VUE_SSR_SETTERS__',
        '__APM__ClientResourceError__', '__APM__ClientResourceError__Buffer__',
        '__vueuse_ssr_handlers__', '__VUE__', '__APM__',
        '__$c', '__pure_keys', '__XHS_AI_DEBUG__',
        '__debugger', '__bc', 'SDK__SESSION__ID',
        'chrome',  // Playwright 暴露的 chrome 对象
    ];

    cdcPatterns.forEach(function(key) {
        try {
            if (key in window) {
                // 尝试删掉，如果删不掉就尝试设为 undefined
                if (window[key] && typeof window[key] === 'object') {
                    // 对于对象，尝试清空其属性
                    try {
                        Object.keys(window[key]).forEach(function(subKey) {
                            try {
                                delete window[key][subKey];
                            } catch(e) {}
                        });
                    } catch(e) {}
                }
                // 尝试直接删除 configurable 的属性
                const descriptor = Object.getOwnPropertyDescriptor(window, key);
                if (descriptor && descriptor.configurable) {
                    delete window[key];
                } else {
                    // 不可删除的，设为空
                    try { window[key] = undefined; } catch(e) {}
                }
            }
        } catch(e) {}
    });

    // 2. 拦截 window 对象上所有包含 'cdc' 或 'playwright' 的属性并删除
    Object.getOwnPropertyNames(window).forEach(function(key) {
        try {
            if (key.toLowerCase().includes('cdc') ||
                key.toLowerCase().includes('playwright') ||
                key.toLowerCase().includes('puppeteer') ||
                key.toLowerCase().includes('fft') ||
                key.toLowerCase().includes('fst')) {
                const descriptor = Object.getOwnPropertyDescriptor(window, key);
                if (descriptor && descriptor.configurable) {
                    delete window[key];
                }
            }
        } catch(e) {}
    });

    console.log('[Stealth] CDP protocol globals cleared');
})();
"""

# ============== 深度反检测：navigator.webdriver 保护 ==============
# 很多站点反复检查 navigator.webdriver，如果我们在注入时用了 configurable: true
# 站点 JS 可以 later 重新 define 为 true。用 get + defineProperty 双重保护

WEBDRIVER_PROTECT_INJECT = """
// 深度保护 navigator.webdriver - 防止被重定义
(function() {
    'use strict';

    // 先尝试删掉现有的
    try {
        delete navigator.webdriver;
    } catch(e) {}

    // 用 Object.defineProperty 重新定义，禁止重写
    Object.defineProperty(navigator, 'webdriver', {
        get: function() { return false; },
        set: function() {},
        configurable: false,   // 关键：禁止重新 defineProperty
        enumerable: true
    });

    // 同时保护 window.webdriver
    try {
        delete window.webdriver;
    } catch(e) {}
    Object.defineProperty(window, 'webdriver', {
        get: function() { return false; },
        set: function() {},
        configurable: false,
        enumerable: true
    });

    console.log('[Stealth] navigator.webdriver protected');
})();
"""

# ============== 深度反检测：window.chrome 完整伪装 ==============
# 小红书等检测 window.chrome 对象是否存在 + 特定方法实现
# 已有 AUTOMATION_HOOK_INJECT 只覆盖 chrome.runtime，这里补充完整 chrome 对象

CHROME_OBJECT_DEEP_INJECT = """
// 完整伪装 window.chrome 对象（模拟真实 Chrome 浏览器）
(function() {
    'use strict';

    // 如果已有 chrome，先彻底清空
    if (window.chrome) {
        try {
            Object.keys(window.chrome).forEach(function(key) {
                try { delete window.chrome[key]; } catch(e) {}
            });
        } catch(e) {}
    }

    // 完整重建 chrome 对象（真实 Chrome 的结构）
    window.chrome = {
        runtime: {
            connect: function() { return { port: { onMessage: { addListener: function() {} }, postMessage: function() {} } }; },
            sendMessage: function() { return Promise.resolve({}); },
            sendNativeMessage: function() { return Promise.resolve({}); },
            getManifest: function() { return { manifest_version: 3, name: 'Chrome', version: '120.0.0.0' }; },
            getURL: function(path) { return 'chrome-extension://fake_extension/' + path; },
            lastError: null,
            onConnect: { addListener: function() {} },
            onMessage: { addListener: function() {} },
            onInstalled: { addListener: function() {} },
        },
        storage: {
            local: {
                get: function(keys, callback) {
                    if (callback) callback({});
                },
                set: function(data, callback) {
                    if (callback) callback();
                },
                remove: function(keys, callback) {
                    if (callback) callback();
                },
                clear: function(callback) {
                    if (callback) callback();
                }
            },
            session: {
                get: function(keys, callback) {
                    if (callback) callback({});
                },
                set: function(data, callback) {
                    if (callback) callback();
                }
            },
            managed: {
                get: function(keys, callback) {
                    if (callback) callback({});
                }
            }
        },
        identity: {
            getRedirectURL: function() { return 'https://fake-chrome-identity.appspot.com'; },
            launchWebAuthFlow: function() { return Promise.resolve('fake_token'); }
        },
        permissions: {
            request: function() { return Promise.resolve({ granted: true }); },
            contains: function() { return Promise.resolve({ granted: true }); }
        },
        power: {
            requestKeepAwake: function() {},
            releaseKeepAwake: function() {}
        },
        fileSystem: {
            isRetina: function() { return false; }
        },
        app: {
            getDetails: function() { return { id: 'fake', name: 'Chrome' }; },
            isInstalled: function() { return false; },
            launchState: 'unknown'
        },
        webstore: {
            onInlineInstallStarted: { addListener: function() {} },
            onWebstoreStatusChanged: { addListener: function() {} }
        },
        debugging: {
            attach: function() {},
            detach: function() {},
            getTargets: function() { return []; }
        },
        // 确保 chrome.csi() 和 chrome.loadTimes() 不报错
        csi: function() {
            return {
                pageT: Date.now(),
                onloadT: Date.now() - 1000,
                startT: Date.now() - 2000,
                transfered: 0,
                dnEndT: Date.now() - 500
            };
        },
        loadTimes: function() {
            return {
                commitLoadTime: 0.1,
                connectionInfo: 'http/1.1',
                navigationType: 'Other',
                numberOfResources: 10,
                numberOfRobotedResources: 0,
                numberOfSniffedAutomaticResources: 0,
                responseTime: 0.05,
                startLoadTime: Date.now() - 1000,
                wasAlternateProtocolAvailable: false,
                wasFetchedViaSpdy: false,
                wasNpnNegotiated: false,
                wasProtQuic: false
            };
        },
        // 禁用特性
        getPlatformInfo: function() { return { os: 'win', arch: 'x64' }; },
        experimental: {},
        forceAppInstalled: false,
        inIncognitoContext: false,
        installedApps: {
            get: function() {},
            launch: function() {},
            status: 'not_installed'
        },
        management: {
            get: function() { return Promise.resolve({ id: 'fake', name: 'App' }); },
            getAll: function() { return Promise.resolve([]); },
            getPermissionWarnings: function() { return Promise.resolve([]); },
            launchApp: function() {},
            requestPermissions: function() { return Promise.resolve({ granted: true }); },
            setEnabled: function() {},
            uninstall: function() { return Promise.resolve(); }
        },
        commands: {
            getAll: function() { return Promise.resolve([]); },
            onCommand: { addListener: function() {} }
        },
        notifications: {
            create: function() { return 'fake_notification_id'; },
            getAll: function() { return Promise.resolve({}); },
            clear: function() { return Promise.resolve(true); },
            onClosed: { addListener:function(){} },
            onClicked: { addListener:function(){} },
            onPermissionLevelChanged: { addListener:function(){} },
            onShowSettings: { addListener:function(){} }
        },
        tabs: {
            create: function() {},
            get: function() { return Promise.resolve({ id: 1, url: '' }); },
            query: function() { return Promise.resolve([]); },
            sendMessage: function() {},
            onActivated: { addListener: function() {} },
            onCreated: { addListener: function() {} },
            onRemoved: { addListener: function() {} },
            onUpdated: { addListener: function() {} }
        },
        windows: {
            create: function() {},
            get: function() { return Promise.resolve({ id: 1 }); },
            getAll: function() { return Promise.resolve([]); },
            onCreated: { addListener: function() {} },
            onRemoved: { addListener: function() {} }
        },
        browsingData: {
            settings: function() { return Promise.resolve({options: {}, dataToRemove: {}}); },
            remove: function() { return Promise.resolve(); },
            removeAppcache: function() { return Promise.resolve(); },
            removeCache: function() { return Promise.resolve(); },
            removeCookies: function() { return Promise.resolve(); },
            removeDownloads: function() { return Promise.resolve(); },
            removeFileSystems: function() { return Promise.resolve(); },
            removeFormData: function() { return Promise.resolve(); },
            removeHistory: function() { return Promise.resolve(); },
            removeIndexedDB: function() { return Promise.resolve(); },
            removeLocalStorage: function() { return Promise.resolve(); },
            removePluginData: function() { return Promise.resolve(); },
            removePasswords: function() { return Promise.resolve(); },
            removeServiceWorkers: function() { return Promise.resolve(); },
            removeWebSQL: function() { return Promise.resolve(); }
        },
        contentSettings: {
            getResourceIdentifiers: function() { return Promise.resolve([]); },
            get: function() { return Promise.resolve({ setting: 'allow' }); },
            set: function() {},
            clear: function() {},
            onChange: { addListener: function() {} }
        },
        contextMenus: {
            create: function() { return 'fake_menu_id'; },
            update: function() {},
            remove: function() {},
            removeAll: function() {},
            onClicked: { addListener: function() {} }
        },
        cookieStore: {
            getAll: function() { return Promise.resolve([]); },
            getAllCookieStores: function() { return Promise.resolve([]); }
        },
        downloads: {
            download: function() { return Promise.resolve(1); },
            search: function() { return Promise.resolve([]); },
            pause: function() {},
            resume: function() {},
            cancel: function() {},
            erase: function() { return Promise.resolve([]); },
            open: function() {},
            show: function() {},
            onCreated: { addListener: function() {} },
            onErased: { addListener: function() {} },
            onChanged: { addListener: function() {} }
        },
        fontSettings: {
            getFontList: function() { return Promise.resolve([]); },
            getDefaultFontSize: function() { return Promise.resolve({ pixelSize: 16 }); },
            setDefaultFontSize: function() {},
            getFontScale: function() { return Promise.resolve({ fontScale: 1.0 }); },
            setFontScale: function() {},
            getMinimumFontSize: function() { return Promise.resolve({ pixelSize: 0 }); },
            setMinimumFontSize: function() {},
            onDefaultFontSizeChanged: { addListener: function() {} },
            onFontChanged: { addListener: function() {} }
        },
        gcm: {
            register: function() {},
            unregister: function() {},
            getInboundId: function() { return Promise.resolve('fake_inbound_id'); },
            onMessage: { addListener: function() {} },
            onSinkAvailable: { addListener: function() {} }
        },
        history: {
            search: function() { return Promise.resolve([]); },
            getVisits: function() { return Promise.resolve([]); },
            addUrl: function() {},
            deleteUrl: function() {},
            deleteRange: function() {},
            deleteAll: function() {},
            setUrlVisitTime: function() {},
            onVisited: { addListener: function() {} },
            onVisitRemoved: { addListener: function() {} }
        },
        i18n: {
            getAcceptLanguages: function() { return Promise.resolve(['zh-CN', 'zh', 'en']); },
            getMessage: function() { return ''; },
            getUILanguage: function() { return 'zh-CN'; }
        },
        identity: {
            getProfileUserInfo: function() { return Promise.resolve({ id: 'fake', email: '' }); }
        },
        instanceID: {
            get: function() { return Promise.resolve({ id: 'fake_instance_id' }); },
            getCreationTime: function() { return Promise.resolve(Date.now()); },
            getToken: function() { return Promise.resolve('fake_token'); },
            tokenCache: {
                remove: function() {},
                addListener: function() {}
            },
            onTokenRefresh: { addListener: function() {} }
        },
        loginState: {
            get: function() { return Promise.resolve({ account: null, isExpanded: false, isLoggedIn: false }); }
        },
        metrics: {
            getBucket: function() { return 0; },
            recordBoolean: function() {},
            recordCount: function() {},
            recordCountHistogram: function() {},
            recordCurrency: function() {},
            recordEvent: function() {},
            recordMediumCount: function() {},
            recordPercentage: function() {},
            recordSparseCount: function() {},
            recordSparseHistogram: function() {},
            recordTime: function() {},
            recordTimeHistogram: function() {},
            recordUserAction: function() {}
        },
        networking: {
            config: {
                getProxySettings: function() { return Promise.resolve({ proxyRules: '' }); },
                addProxyOptions: function() {},
                onProxyError: { addListener: function() {} }
            }
        },
        platformKeys: {
            getClientCertificate: function() { return Promise.resolve(null); },
            selectClientCertificates: function() { return Promise.resolve([]); },
            verifyTLSServerCertificate: function() { return Promise.resolve({ valid: true }); }
        },
        printerProvider: {
            onPrintJobCancelled: { addListener: function() {} },
            onPrintJobError: { addListener: function() {} },
            onPrintJobStarted: { addListener: function() {} },
            onPrintJobsUpdated: { addListener: function() {} },
            getPrinters: function() { return Promise.resolve([]); },
            getPrinterInfo: function() { return Promise.resolve({}); }
        },
        privacy: {
            websites: {
                getThirdPartyBlockingEnabled: function() { return Promise.resolve({ value: false }); },
                setThirdPartyBlockingEnabled: function() {},
                getTrackingProtectionEnabled: function() { return Promise.resolve({ value: false }); }
            },
            network: {
                getPredictionEnabled: function() { return Promise.resolve({ value: true }); },
                setPredictionEnabled: function() {},
                getPrivacyBadgingEnabled: function() { return Promise.resolve({ value: false }); },
                setPrivacyBadgingEnabled: function() {},
                getWebRTCIPHandlingPolicy: function() { return Promise.resolve({ value: 'default' }); },
                setWebRTCIPHandlingPolicy: function() {}
            },
            services: {
                getAlternateErrorPagesEnabled: function() { return Promise.resolve({ value: false }); },
                setAlternateErrorPagesEnabled: function() {},
                getAutofillAddressEnabled: function() { return Promise.resolve({ value: true }); },
                setAutofillAddressEnabled: function() {},
                getAutofillCreditCardEnabled: function() { return Promise.resolve({ value: true }); },
                setAutofillCreditCardEnabled: function() {},
                getPasswordLeakDetectionEnabled: function() { return Promise.resolve({ value: false }); },
                setPasswordLeakDetectionEnabled: function() {},
                getSafeBrowsingEnabled: function() { return Promise.resolve({ value: true }); },
                setSafeBrowsingEnabled: function() {},
                getSearchSuggestEnabled: function() { return Promise.resolve({ value: true }); },
                setSearchSuggestEnabled: function() {},
                getSpellingServiceEnabled: function() { return Promise.resolve({ value: false }); },
                setSpellingServiceEnabled: function() {},
                getTranslationServiceEnabled: function() { return Promise.resolve({ value: false }); },
                setTranslationServiceEnabled: function() {}
            },
            onChange: { addListener: function() {} }
        },
        proxy: {
            getSettings: function() { return Promise.resolve({ proxyRules: '' }); },
            setSettings: function() {},
            onProxyError: { addListener: function() {} }
        },
        scriptPermissions: {
            getAllowed: function() { return Promise.resolve([]); },
            request: function() { return Promise.resolve({ granted: true }); }
        },
        session: {
            get: function() { return Promise.resolve({ id: 'fake_session_id' }); },
            getTab: function() { return Promise.resolve({ id: 1 }); },
            getWindow: function() { return Promise.resolve({ id: 1 }); },
            setTabValue: function() {},
            getTabValue: function() { return Promise.resolve(null); },
            removeTabValue: function() {},
            setWindowValue: function() {},
            getWindowValue: function() { return Promise.resolve(null); },
            removeWindowValue: function() {},
            onChanged: { addListener: function() {} }
        },
        socket: {
            create: function() { return { id: 'fake_socket_id' }; },
            connect: function() {},
            send: function() {},
            read: function() {},
            disconnect: function() {},
            destroy: function() {},
            setKeepAlive: function() {},
            setNoDelay: function() {},
            getInfo: function() { return Promise.resolve({}); },
            getSockets: function() { return Promise.resolve([]); },
            onData: { addListener: function() {} },
            onDisconnected: { addListener: function() {} }
        },
        system: {
            cpu: {
                getInfo: function() { return Promise.resolve({ processors: [] }); },
                onUpdated: { addListener: function() {} }
            },
            memory: {
                getInfo: function() { return Promise.resolve({ capacity: 8589934592, availableCapacity: 4294967296 }); }
            },
            storage: {
                getInfo: function() { return Promise.resolve([]); },
                ejectDevice: function() { return Promise.resolve('ejected'); },
                onAttached: { addListener: function() {} },
                onDetached: { addListener: function() {} }
            },
            display: {
                getInfo: function() { return Promise.resolve([]); },
                onDisplayChanged: { addListener: function() {} }
            }
        },
        tabGroups: {
            get: function() { return Promise.resolve(null); },
            getAll: function() { return Promise.resolve([]); },
            move: function() {},
            update: function() {},
            onCreated: { addListener: function() {} },
            onMoved: { addListener: function() {} },
            onRemoved: { addListener: function() {} },
            onUpdated: { addListener: function() {} },
            onGroupCreated: { addListener: function() {} },
            onGroupClosed: { addListener: function() {} },
            onGroupMoved: { addListener: function() {} },
            onGroupUpdated: { addListener: function() {} },
            onGroupUserActionChanged: { addListener: function() {} }
        },
        topSites: {
            get: function() { return Promise.resolve([]); },
            onNewTopSite: { addListener: function() {} }
        },
        tts: {
            speak: function() {},
            stop: function() {},
            pause: function() {},
            resume: function() {},
            isSpeaking: function() { return Promise.resolve(false); },
            getVoices: function() { return Promise.resolve([]); },
            onEvent: { addListener: function() {} }
        },
        vpnProvider: {
            createConfig: function() {},
            destroyConfig: function() {},
            setParameters: function() {},
            sendPacket: function() {},
            onConfigRemoved: { addListener: function() {} },
            onPacketReceived: { addListener: function() {} },
            onShowBubble: { addListener: function() {} }
        },
        wallpaper: {
            setWallpaper: function() {},
            onWallpaperChanged: { addListener: function() {} }
        },
        webNavigation: {
            getFrame: function() { return Promise.resolve({}); },
            getFrameForTab: function() { return Promise.resolve({}); },
            getAllFrames: function() { return Promise.resolve([]); },
            onBeforeNavigate: { addListener: function() {} },
            onCommitted: { addListener: function() {} },
            onDOMContentLoaded: { addListener: function() {} },
            onCompleted: { addListener: function() {} },
            onErrorOccurred: { addListener: function() {} },
            onNavigationBlocked: { addListener: function() {} },
            onCreatedNavigationTarget: { addListener: function() {} },
            onReferenceFragmentUpdated: { addListener: function() {} },
            onTabReplaced: { addListener: function() {} },
            onHistoryStateUpdated: { addListener: function() {} }
        },
        webRequest: {
            onBeforeRequest: { addListener: function() {} },
            onBeforeSendHeaders: { addListener: function() {} },
            onSendHeaders: { addListener: function() {} },
            onHeadersReceived: { addListener: function() {} },
            onAuthRequired: { addListener: function() {} },
            onBeforeRedirect: { addListener: function() {} },
            onResponseStarted: { addListener: function() {} },
            onCompleted: { addListener: function() {} },
            onErrorOccurred: { addListener: function() {} },
            onActionTriggered: { addListener: function() {} }
        }
    };

    // 冻结 chrome 对象防止被添加/删除属性
    try {
        Object.preventExtensions(window.chrome);
    } catch(e) {}

    console.log('[Stealth] window.chrome fully mocked');
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

    async def launch(self) -> Browser:
        """启动隐身浏览器（AsyncPlaywright，避免在 asyncio loop 中崩溃）"""
        from playwright.async_api import async_playwright

        # 关闭旧实例防止资源泄漏
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        self._playwright = await async_playwright().start()

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

        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
            args=args
        )
        return self._browser

    async def create_context(self) -> BrowserContext:
        """创建隐身上下文"""
        if not self._browser:
            raise RuntimeError("Browser not launched")

        context_args = get_stealth_context_args()

        context = await self._browser.new_context(
            **{**context_args}
        )

        # 设置用户代理
        if self.config.user_agent:
            await context.set_extra_http_headers({"User-Agent": self.config.user_agent})

        return context

    async def create_page(self, context: BrowserContext = None) -> Page:
        """创建注入反检测脚本的页面"""
        if not context:
            context = await self.create_context()

        page = await context.new_page()

        # ========== 深度反检测（按执行顺序）==========
        # 1. 清除 Playwright CDP 协议暴露的全局变量（必须在最前）
        await page.evaluate(CDP_HOOK_INJECT)

        # 2. 保护 navigator.webdriver 禁止重定义
        await page.evaluate(WEBDRIVER_PROTECT_INJECT)

        # 3. 完整伪装 window.chrome 对象
        await page.evaluate(CHROME_OBJECT_DEEP_INJECT)

        # 注入基础反检测脚本
        await page.evaluate(STealth_JS_INJECT)

        # 根据配置注入增强版脚本
        if self.config.randomize_webgl:
            await page.evaluate(CANVAS_HOOK_V2)

        if self.config.randomize_canvas:
            await page.evaluate(CANVAS_FONT_INJECT)

        if self.config.fake_media_devices:
            await page.evaluate(MEDIA_DEVICES_INJECT)

        if self.config.fake_battery:
            await page.evaluate(BATTERY_INJECT)

        # 注入额外反检测脚本 (默认全部开启)
        await page.evaluate(AUTOMATION_HOOK_INJECT)
        await page.evaluate(HARDWARE_FP_HOOK_INJECT)
        await page.evaluate(CONNECTION_HOOK_INJECT)
        await page.evaluate(TIMING_HOOK_INJECT)
        await page.evaluate(WASM_HOOK_INJECT)
        await page.evaluate(SERVICE_WORKER_HOOK_INJECT)
        await page.evaluate(SPEECH_HOOK_INJECT)

        return page

    async def close(self):
        """关闭浏览器"""
        try:
            if self._browser:
                await self._browser.close()
        finally:
            self._browser = None
        try:
            if self._playwright:
                await self._playwright.stop()
        finally:
            self._playwright = None
