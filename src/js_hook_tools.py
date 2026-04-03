"""
JS逆向Hook工具箱 v2
提供更完善的浏览器Hook脚本
"""

# ============== 网络请求Hook ==============

NETWORK_HOOKS = """
// Hook XMLHttpRequest, fetch, WebSocket
(function() {
    'use strict';

    // XHR Hook
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url, async, user, password) {
        console.log('[XHR]', method, url);
        this._requestUrl = url;
        this._requestMethod = method;
        return origOpen.apply(this, arguments);
    };

    XMLHttpRequest.prototype.send = function(data) {
        console.log('[XHR] Send:', this._requestUrl, data ? data.toString().substring(0, 200) : '');
        this.addEventListener('load', function() {
            try {
                console.log('[XHR] Response:', this._requestUrl, this.status,
                    this.responseText ? this.responseText.substring(0, 300) : '');
            } catch(e) {}
        });
        this.addEventListener('error', function() {
            console.log('[XHR] Error:', this._requestUrl);
        });
        return origSend.apply(this, arguments);
    };
    var origSend = XMLHttpRequest.prototype.send;

    // Fetch Hook
    var origFetch = window.fetch;
    window.fetch = function(url, options) {
        console.log('[Fetch]', url);
        var startTime = Date.now();
        return origFetch.apply(this, arguments).then(function(response) {
            console.log('[Fetch] Response:', url, response.status, Date.now() - startTime + 'ms');
            return response;
        }).catch(function(error) {
            console.log('[Fetch] Error:', url, error.message);
            throw error;
        });
    };

    // WebSocket Hook
    var OrigWebSocket = window.WebSocket;
    window.WebSocket = function(url, protocols) {
        console.log('[WebSocket] Connect:', url);
        var ws = new OrigWebSocket(url, protocols);
        ws.addEventListener('open', function() { console.log('[WebSocket] Opened:', url); });
        ws.addEventListener('close', function() { console.log('[WebSocket] Closed:', url); });
        ws.addEventListener('error', function(e) { console.log('[WebSocket] Error:', url); });
        ws.addEventListener('message', function(e) {
            console.log('[WebSocket] Message:', url, e.data.substring ? e.data.substring(0, 100) : '');
        });
        return ws;
    };

    console.log('[Hook] Network hooks installed');
})();
"""

# ============== 加密函数Hook ==============

CRYPTO_HOOKS = """
// Hook CryptoJS, WebCrypto, MD5, SHA
(function() {
    'use strict';

    // CryptoJS Hook
    if (typeof CryptoJS !== 'undefined') {
        var origAES = CryptoJS.AES.encrypt;
        CryptoJS.AES.encrypt = function(data, key, cfg) {
            console.log('[CryptoJS] AES.encrypt', {data: data.toString ? data.toString().substring(0, 100) : data});
            return origAES.apply(this, arguments);
        };

        var origAESDecrypt = CryptoJS.AES.decrypt;
        CryptoJS.AES.decrypt = function(data, key, cfg) {
            console.log('[CryptoJS] AES.decrypt');
            return origAESDecrypt.apply(this, arguments);
        };

        var origMD5 = CryptoJS.MD5;
        CryptoJS.MD5 = function(data) {
            console.log('[CryptoJS] MD5:', data);
            return origMD5.apply(this, arguments);
        };

        var origSHA1 = CryptoJS.SHA1;
        CryptoJS.SHA1 = function(data) {
            console.log('[CryptoJS] SHA1:', data);
            return origSHA1.apply(this, arguments);
        };

        var origSHA256 = CryptoJS.SHA256;
        CryptoJS.SHA256 = function(data) {
            console.log('[CryptoJS] SHA256:', data);
            return origSHA256.apply(this, arguments);
        };

        var origSHA512 = CryptoJS.SHA512;
        CryptoJS.SHA512 = function(data) {
            console.log('[CryptoJS] SHA512:', data);
            return origSHA512.apply(this, arguments);
        };

        var origHmacSHA256 = CryptoJS.HmacSHA256;
        CryptoJS.HmacSHA256 = function(data, key) {
            console.log('[CryptoJS] HmacSHA256:', data, key);
            return origHmacSHA256.apply(this, arguments);
        };

        var origRC4 = CryptoJS.RC4.encrypt;
        CryptoJS.RC4.encrypt = function(data, key) {
            console.log('[CryptoJS] RC4.encrypt:', data);
            return origRC4.apply(this, arguments);
        };

        var origRabbit = CryptoJS.Rabbit.encrypt;
        CryptoJS.Rabbit.encrypt = function(data, key) {
            console.log('[CryptoJS] Rabbit.encrypt:', data);
            return origRabbit.apply(this, arguments);
        };
    }

    // WebCrypto Hook
    if (window.crypto && window.crypto.subtle) {
        var origEncrypt = window.crypto.subtle.encrypt;
        window.crypto.subtle.encrypt = function(algorithm, key, data) {
            console.log('[SubtleCrypto] encrypt:', algorithm.name);
            return origEncrypt.apply(this, arguments);
        };

        var origDecrypt = window.crypto.subtle.decrypt;
        window.crypto.subtle.decrypt = function(algorithm, key, data) {
            console.log('[SubtleCrypto] decrypt:', algorithm.name);
            return origDecrypt.apply(this, arguments);
        };

        var origDigest = window.crypto.subtle.digest;
        window.crypto.subtle.digest = function(algorithm, data) {
            console.log('[SubtleCrypto] digest:', algorithm);
            return origDigest.apply(this, arguments);
        };

        var origSign = window.crypto.subtle.sign;
        window.crypto.subtle.sign = function(algorithm, key, data) {
            console.log('[SubtleCrypto] sign:', algorithm.name);
            return origSign.apply(this, arguments);
        };
    }

    // 原生MD5/SHA实现Hook
    if (typeof window.md5 === 'function') {
        var origMD5 = window.md5;
        window.md5 = function(str) {
            console.log('[JS] md5:', str);
            return origMD5.apply(this, arguments);
        };
    }

    console.log('[Hook] Crypto hooks installed');
})();
"""

# ============== 存储Hook ==============

STORAGE_HOOKS = """
// Hook localStorage, sessionStorage, cookies
(function() {
    'use strict';

    // Storage Hook
    var methods = ['setItem', 'getItem', 'removeItem', 'clear', 'key'];
    methods.forEach(function(method) {
        var orig = Storage.prototype[method];
        if (!orig) return;

        Storage.prototype[method] = function(key, value) {
            if (method === 'setItem') {
                console.log('[Storage] setItem:', key, value ? value.toString().substring(0, 100) : '');
            } else if (method === 'getItem') {
                console.log('[Storage] getItem:', key);
            } else if (method === 'removeItem') {
                console.log('[Storage] removeItem:', key);
            } else {
                console.log('[Storage]', method);
            }
            return orig.apply(this, arguments);
        };
    });

    // Cookie Hook
    var cookieDesc = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie');
    if (cookieDesc) {
        var origCookieGetter = cookieDesc.get;
        var origCookieSetter = cookieDesc.set;

        Object.defineProperty(document, 'cookie', {
            get: function() {
                console.log('[Cookie] Read');
                return origCookieGetter.call(this);
            },
            set: function(value) {
                console.log('[Cookie] Set:', value.toString().substring(0, 100));
                return origCookieSetter.call(this, value);
            },
            configurable: true
        });
    }

    // IndexedDB Hook
    if (window.indexedDB) {
        var origOpen = indexedDB.open;
        indexedDB.open = function(name, version) {
            console.log('[IndexedDB] Open:', name, version);
            return origOpen.apply(this, arguments);
        };
    }

    console.log('[Hook] Storage hooks installed');
})();
"""

# ============== Canvas/WebGL指纹Hook ==============

FINGERPRINT_HOOKS = """
// Hook Canvas/WebGL fingerprinting
(function() {
    'use strict';

    // Canvas Hook
    var origGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, attributes) {
        console.log('[Canvas] getContext:', type);
        var ctx = origGetContext.call(this, type, attributes);

        if (type === '2d' && ctx) {
            var origFillText = ctx.fillText;
            ctx.fillText = function(text, x, y, maxWidth) {
                // console.log('[Canvas] fillText:', text.toString().substring(0, 50));
                return origFillText.apply(this, arguments);
            };

            var origStrokeText = ctx.strokeText;
            ctx.strokeText = function(text, x, y, maxWidth) {
                // console.log('[Canvas] strokeText:', text.toString().substring(0, 50));
                return origStrokeText.apply(this, arguments);
            };

            // 噪声toDataURL
            var origToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type, encoderOptions) {
                console.log('[Canvas] toDataURL');
                return origToDataURL.apply(this, arguments);
            };

            // 噪声getImageData
            var origGetImageData = ctx.getImageData;
            ctx.getImageData = function(sx, sy, sw, sh) {
                var data = origGetImageData.apply(this, arguments);
                // 添加少量噪声防指纹
                for (var i = 0; i < data.data.length; i += 4) {
                    data.data[i] += (Math.random() - 0.5) * 2;
                    data.data[i+1] += (Math.random() - 0.5) * 2;
                    data.data[i+2] += (Math.random() - 0.5) * 2;
                }
                return data;
            };
        }

        return ctx;
    };

    // WebGL Hook
    var origWebGLGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, attributes) {
        var ctx = origWebGLGetContext.call(this, type, attributes);

        if ((type === 'webgl' || type === 'experimental-webgl') && ctx) {
            var origGetParameter = ctx.getParameter;
            ctx.getParameter = function(pname) {
                // 伪装WebGL指纹
                if (pname === 37445) return 'Intel Inc.'; // UNMASKED_VENDOR
                if (pname === 37446) return 'Intel Iris OpenGL Engine'; // UNMASKED_RENDERER
                if (pname === 7938) return 'WebGL 2.0'; // VERSION
                return origGetParameter.apply(this, arguments);
            };

            // 支持所有GL参数
            ctx.getExtension = function(name) {
                console.log('[WebGL] Extension:', name);
                return null;
            };

            // 添加渲染噪声
            var origReadPixels = ctx.readPixels;
            ctx.readPixels = function(x, y, w, h, format, type, pixels) {
                return origReadPixels.apply(this, arguments);
            };
        }

        return ctx;
    };

    console.log('[Hook] Fingerprint hooks installed');
})();
"""

# ============== 反调试Hook ==============

ANTI_DEBUG_HOOKS = """
// Anti-debug, anti-trace hooks
(function() {
    'use strict';

    // 1. 禁用debugger语句
    var noop = function() {};
    Object.defineProperty(window, 'debugger', { get: noop, set: noop });

    // 2. setTimeout/setInterval debugger过滤
    var origSetTimeout = window.setTimeout;
    var origSetInterval = window.setInterval;

    window.setTimeout = function(func, delay, ...args) {
        var funcStr = func.toString();
        if (funcStr.includes('debugger') || funcStr.includes('debug')) {
            console.log('[AntiDebug] Blocked debugger setTimeout');
            return origSetTimeout(noop, delay, ...args);
        }
        return origSetTimeout.apply(this, arguments);
    };

    window.setInterval = function(func, delay, ...args) {
        var funcStr = func.toString();
        if (funcStr.includes('debugger') || funcStr.includes('debug')) {
            console.log('[AntiDebug] Blocked debugger setInterval');
            return origSetInterval(noop, delay, ...args);
        }
        return origSetInterval.apply(this, arguments);
    };

    // 3. 开发者工具检测
    var threshold = 100;
    var lastTime = Date.now();
    var checkDevTools = function() {
        var now = Date.now();
        if (now - lastTime > threshold) {
            console.log('[AntiDebug] DevTools possibly opened, time delta:', now - lastTime);
        }
        lastTime = now;
        setTimeout(checkDevTools, 1000);
    };
    setTimeout(checkDevTools, 1000);

    // 4. 函数toString检测
    var origToString = Function.prototype.toString;
    Function.prototype.toString = function() {
        var str = origToString.apply(this, arguments);
        if (str.includes('native code') || str.includes('debugger')) {
            console.log('[AntiDebug] Function toString intercepted');
        }
        return str;
    };

    // 5. console方法监控
    ['log', 'debug', 'info', 'warn', 'error'].forEach(function(method) {
        var orig = console[method];
        console[method] = function(...args) {
            // 过滤敏感调用
            if (args.some(function(a) { return a && a.toString && a.toString().includes('debugger'); })) {
                return;
            }
            return orig.apply(console, args);
        };
    });

    console.log('[Hook] Anti-debug hooks installed');
})();
"""

# ============== 滑块验证Hook ==============

SLIDER_HOOKS = """
// Slider captcha detection and tracking
(function() {
    'use strict';

    // 1. 滑块元素检测
    var sliderPatterns = [
        '.slider', '.nc_wrapper', '.geetest_slider', '.yidun_slider',
        '.jd-captcha-slider', '.captcha-slider', '[class*="slider"]',
        '.nc_iconfont_slider', '.wgt-slider'
    ];

    var checkSlider = function() {
        for (var i = 0; i < sliderPatterns.length; i++) {
            var el = document.querySelector(sliderPatterns[i]);
            if (el) {
                console.log('[Slider] Found:', sliderPatterns[i], el.className);
                return el;
            }
        }
        return null;
    };

    // 2. DOM变化监听
    var observer = new MutationObserver(function(mutations) {
        var slider = checkSlider();
        if (slider) {
            console.log('[Slider] Captcha appeared');
            window._captchaSlider = slider;
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class', 'style']
    });

    // 3. 背景图片检测
    var bgPatterns = [
        '.bg-img', '.geetest_bg', '.bg-image', '.jigsaw-bg',
        '[class*="bg-img"]', '[class*="captcha-bg"]'
    ];

    var getBackgroundImage = function() {
        for (var i = 0; i < bgPatterns.length; i++) {
            var el = document.querySelector(bgPatterns[i]);
            if (el) {
                var style = window.getComputedStyle(el);
                var bg = style.backgroundImage;
                if (bg && bg !== 'none') {
                    console.log('[Slider] Background found:', bgPatterns[i], bg.substring(0, 100));
                    return bg;
                }
            }
        }
        return null;
    };

    // 4. 拼图块检测
    var getPuzzlePiece = function() {
        var pieces = document.querySelectorAll('[class*="puzzle"], [class*="piece"], .jd-captcha-img');
        for (var i = 0; i < pieces.length; i++) {
            console.log('[Slider] Puzzle piece found:', pieces[i].className);
        }
        return pieces.length > 0 ? pieces[0] : null;
    };

    // 5. 拖动事件追踪
    var trackMouseMove = function() {
        var positions = [];
        document.addEventListener('mousemove', function(e) {
            if (window._captchaSlider && e.buttons === 1) {
                positions.push({x: e.clientX, y: e.clientY, t: Date.now()});
                if (positions.length > 1000) positions.shift();
            }
        }, true);

        document.addEventListener('mouseup', function(e) {
            if (window._captchaSlider && positions.length > 0) {
                console.log('[Slider] Drag轨迹:', JSON.stringify(positions.slice(-20)));
                window._lastDragTrajectory = positions.slice();
                positions = [];
            }
        }, true);
    };

    trackMouseMove();

    // 6. 滑块距离获取
    window.getSliderDistance = function() {
        var slider = checkSlider();
        if (!slider) return null;

        var track = slider.querySelector('.nc_track') || slider.querySelector('[class*="track"]');
        if (track) {
            var style = window.getComputedStyle(track);
            console.log('[Slider] Track:', track.className, style.width);
        }

        return slider;
    };

    // 7. 初始化检测
    checkSlider();

    console.log('[Hook] Slider captcha hooks installed');
})();
"""

# ============== 设备信息Hook ==============

DEVICE_HOOKS = """
// Device information hooks
(function() {
    'use strict';

    // 1. Navigator属性伪装
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: function() { return 8; },
        configurable: true
    });

    Object.defineProperty(navigator, 'deviceMemory', {
        get: function() { return 8; },
        configurable: true
    });

    Object.defineProperty(navigator, 'maxTouchPoints', {
        get: function() { return 10; },
        configurable: true
    });

    Object.defineProperty(navigator, 'platform', {
        get: function() { return 'Win32'; },
        configurable: true
    });

    // 2. 电池API模拟
    if (!navigator.battery) {
        var fakeBattery = {
            charging: true,
            chargingTime: 0,
            dischargingTime: Infinity,
            level: 1.0,
            addEventListener: function() {},
            removeEventListener: function() {},
            dispatchEvent: function() { return true; }
        };
        Object.defineProperty(navigator, 'battery', {
            get: function() { return fakeBattery; },
            configurable: true
        });
    }

    // 3. 媒体设备模拟
    if (navigator.mediaDevices) {
        navigator.mediaDevices.enumerateDevices = function() {
            return Promise.resolve([
                { deviceId: 'default', kind: 'audioinput', label: 'Microphone', groupId: 'group_0' },
                { deviceId: 'default', kind: 'videoinput', label: 'Camera', groupId: 'group_1' }
            ]);
        };
    }

    // 4. 连接信息模拟
    if (navigator.connection) {
        Object.defineProperty(navigator.connection, 'effectiveType', {
            get: function() { return '4g'; },
            configurable: true
        });
        Object.defineProperty(navigator.connection, 'downlink', {
            get: function() { return 10; },
            configurable: true
        });
        Object.defineProperty(navigator.connection, 'rtt', {
            get: function() { return 50; },
            configurable: true
        });
    }

    // 5. 传感器模拟 (如陀螺仪)
    if (window.DeviceOrientationEvent) {
        window.addEventListener('deviceorientation', function(e) {
            e.alpha = 0;
            e.beta = 90;
            e.gamma = 0;
        });
    }

    console.log('[Hook] Device info hooks installed');
})();
"""

# ============== WebAssembly Hook ==============

WASM_HOOKS = """
// WebAssembly 函数Hook
(function() {
    'use strict';

    // 1. WebAssembly.compile
    if (typeof WebAssembly !== 'undefined') {
        var origCompile = WebAssembly.compile;
        WebAssembly.compile = function(bytecode, importObject) {
            console.log('[WASM] Compiling bytecode, length:', bytecode ? bytecode.length : 0);
            return origCompile.apply(this, arguments);
        };

        // 2. WebAssembly.compileStreaming
        if (WebAssembly.compileStreaming) {
            var origCompileStreaming = WebAssembly.compileStreaming;
            WebAssembly.compileStreaming = function(source, importObject) {
                console.log('[WASM] Compiling from streaming source');
                return origCompileStreaming.apply(this, arguments);
            };
        }

        // 3. WebAssembly.instantiate
        var origInstantiate = WebAssembly.instantiate;
        WebAssembly.instantiate = function(module, importObject) {
            console.log('[WASM] Instantiating module');
            return origInstantiate.apply(this, arguments);
        };

        // 4. WebAssembly.instantiateStreaming
        if (WebAssembly.instantiateStreaming) {
            var origInstantiateStreaming = WebAssembly.instantiateStreaming;
            WebAssembly.instantiateStreaming = function(source, importObject) {
                console.log('[WASM] Instantiating from streaming');
                return origInstantiateStreaming.apply(this, arguments);
            };
        }

        // 5. WebAssembly.Memory
        var origMemory = WebAssembly.Memory;
        WebAssembly.Memory = function(descriptor) {
            console.log('[WASM] Creating Memory:', descriptor);
            return new origMemory(descriptor);
        };

        // 6. WebAssembly.Table
        var origTable = WebAssembly.Table;
        WebAssembly.Table = function(descriptor) {
            console.log('[WASM] Creating Table:', descriptor);
            return new origTable(descriptor);
        };

        // 7. 监控wasm函数调用
        var origExecute = undefined;
        if (typeof window.wasmExec === 'function') {
            origExecute = window.wasmExec;
            window.wasmExec = function() {
                console.log('[WASM] Executing wasm function');
                return origExecute.apply(this, arguments);
            };
        }
    }

    console.log('[Hook] WebAssembly hooks installed');
})();
"""

# ============== Service Worker Hook ==============

SW_HOOKS = """
// Service Worker Hook
(function() {
    'use strict';

    if ('serviceWorker' in navigator) {
        // 1. register
        var origRegister = navigator.serviceWorker.register;
        navigator.serviceWorker.register = function(scriptURL, options) {
            console.log('[SW] Registering service worker:', scriptURL);
            if (options) {
                console.log('[SW] Options:', JSON.stringify(options));
            }
            return origRegister.apply(this, arguments);
        };

        // 2. getRegistration
        var origGetRegistration = navigator.serviceWorker.getRegistration;
        navigator.serviceWorker.getRegistration = function(options) {
            console.log('[SW] Getting registration');
            return origGetRegistration.apply(this, arguments);
        };

        // 3. getRegistrations
        var origGetRegistrations = navigator.serviceWorker.getRegistrations;
        navigator.serviceWorker.getRegistrations = function() {
            console.log('[SW] Getting all registrations');
            return origGetRegistrations.apply(this, arguments);
        };

        // 4. ready
        Object.defineProperty(navigator.serviceWorker, 'ready', {
            get: function() {
                console.log('[SW] Getting ready');
                return Promise.resolve();
            },
            configurable: true
        });

        // 5. controller
        var origControllerDesc = Object.getOwnPropertyDescriptor(navigator.serviceWorker, 'controller');
        if (origControllerDesc) {
            Object.defineProperty(navigator.serviceWorker, 'controller', {
                get: function() {
                    console.log('[SW] Getting controller');
                    return origControllerDesc.get.apply(this);
                },
                configurable: true
            });
        }

        // 6. message event监听
        if (navigator.serviceWorker.addEventListener) {
            var origAddListener = navigator.serviceWorker.addEventListener;
            navigator.serviceWorker.addEventListener = function(type, listener, options) {
                if (type === 'message') {
                    console.log('[SW] Adding message listener');
                }
                return origAddListener.apply(this, arguments);
            };
        }
    }

    console.log('[Hook] Service Worker hooks installed');
})();
"""

# ============== 更多加密算法Hook ==============

EXTENDED_CRYPTO_HOOKS = """
// 扩展加密算法Hook
(function() {
    'use strict';

    // 1. RSA加密
    if (typeof window.RSAKey === 'function') {
        var origConstruct = window.RSAKey;
        window.RSAKey = function() {
            console.log('[Crypto] Creating RSAKey');
            return new origConstruct();
        };
    }

    // 2. Jose (JWS/JWE) Hook
    if (typeof window.jose === 'object') {
        console.log('[Crypto] Jose library detected');
        var origJWS = window.jose.JWS.create;
        if (origJWS) {
            window.jose.JWS.create = function() {
                console.log('[Crypto] JWS created');
                return origJWS.apply(this, arguments);
            };
        }
    }

    // 3. Node.js crypto模块 (如果有)
    if (typeof require === 'function' && typeof module !== 'undefined') {
        try {
            var nodeCrypto = require('crypto');
            if (nodeCrypto) {
                var origCreateCipher = nodeCrypto.createCipher;
                nodeCrypto.createCipher = function(algorithm, password) {
                    console.log('[Crypto] Node createCipher:', algorithm);
                    return origCreateCipher.apply(this, arguments);
                };

                var origCreateDecipher = nodeCrypto.createDecipher;
                nodeCrypto.createDecipher = function(algorithm, password) {
                    console.log('[Crypto] Node createDecipher:', algorithm);
                    return origCreateDecipher.apply(this, arguments);
                };

                var origCreateHash = nodeCrypto.createHash;
                nodeCrypto.createHash = function(algorithm) {
                    console.log('[Crypto] Node createHash:', algorithm);
                    return origCreateHash.apply(this, arguments);
                };

                var origCreateSign = nodeCrypto.createSign;
                nodeCrypto.createSign = function(algorithm) {
                    console.log('[Crypto] Node createSign:', algorithm);
                    return origCreateSign.apply(this, arguments);
                };

                var origCreateVerify = nodeCrypto.createVerify;
                nodeCrypto.createVerify = function(algorithm) {
                    console.log('[Crypto] Node createVerify:', algorithm);
                    return origCreateVerify.apply(this, arguments);
                };
            }
        } catch(e) {}
    }

    // 4. ASN1编码 Hook
    if (typeof window.asn1 === 'object') {
        console.log('[Crypto] ASN1 library detected');
    }

    // 5. Base64编码 Hook
    if (typeof window.Base64 === 'object') {
        var origEncode = window.Base64.encode;
        if (origEncode) {
            window.Base64.encode = function(str) {
                console.log('[Crypto] Base64 encode:', str.substring ? str.substring(0, 50) : 'binary');
                return origEncode.apply(this, arguments);
            };
        }
    }

    // 6. URL编码 Hook
    var origEncodeURIComponent = window.encodeURIComponent;
    window.encodeURIComponent = function(str) {
        // 只对包含敏感关键词的编码进行日志
        if (str && str.toString().match(/(token|sign|key|auth|password|secret)/i)) {
            console.log('[Crypto] encodeURIComponent:', str.toString().substring(0, 50));
        }
        return origEncodeURIComponent.apply(this, arguments);
    };

    var origDecodeURIComponent = window.decodeURIComponent;
    window.decodeURIComponent = function(str) {
        console.log('[Crypto] decodeURIComponent');
        return origDecodeURIComponent.apply(this, arguments);
    };

    // 7. btoa/atob Hook
    var origBtoa = window.btoa;
    window.btoa = function(str) {
        console.log('[Crypto] btoa');
        return origBtoa.apply(this, arguments);
    };

    var origAtob = window.atob;
    window.atob = function(str) {
        console.log('[Crypto] atob');
        return origAtob.apply(this, arguments);
    };

    console.log('[Hook] Extended crypto hooks installed');
})();
"""

# ============== WebSocket扩展Hook ==============

WEBSOCKET_HOOKS = """
// WebSocket扩展Hook
(function() {
    'use strict';

    var OrigWebSocket = window.WebSocket;
    var wsConnections = [];

    window.WebSocket = function(url, protocols) {
        console.log('[WS] Creating connection to:', url);
        if (protocols) {
            console.log('[WS] Protocols:', protocols);
        }

        var ws = new OrigWebSocket(url, protocols);
        wsConnections.push({url: url, ws: ws, readyState: ws.readyState});

        // Hook send
        var origSend = ws.send;
        ws.send = function(data) {
            console.log('[WS] Sending data:', data ? (data.substring ? data.substring(0, 100) : '[binary]') : '');
            return origSend.apply(this, arguments);
        };

        // Hook close
        var origClose = ws.close;
        ws.close = function(code, reason) {
            console.log('[WS] Closing:', code, reason);
            return origClose.apply(this, arguments);
        };

        // Hook binaryType
        Object.defineProperty(ws, 'binaryType', {
            get: function() { return this._binaryType || 'arraybuffer'; },
            set: function(val) {
                console.log('[WS] binaryType set to:', val);
                this._binaryType = val;
            },
            configurable: true
        });

        // 事件hook
        ws.addEventListener = (function(origAddEventListener) {
            return function(type, listener, options) {
                if (type === 'message') {
                    console.log('[WS] Message listener added');
                } else if (type === 'open') {
                    console.log('[WS] Open listener added');
                } else if (type === 'error') {
                    console.log('[WS] Error listener added');
                }
                return origAddEventListener.apply(this, arguments);
            };
        })(ws.addEventListener.bind(ws));

        return ws;
    };

    // 复制静态属性
    window.WebSocket.CONNECTING = OrigWebSocket.CONNECTING;
    window.WebSocket.OPEN = OrigWebSocket.OPEN;
    window.WebSocket.CLOSING = OrigWebSocket.CLOSING;
    window.WebSocket.CLOSED = OrigWebSocket.CLOSED;

    // 获取所有连接
    window._getWSConnections = function() {
        return wsConnections;
    };

    console.log('[Hook] WebSocket hooks installed');
})();
"""

# ============== IndexedDB Hook ==============

INDEXEDDB_HOOKS = """
// IndexedDB Hook
(function() {
    'use strict';

    if (window.indexedDB) {
        // 1. open
        var origOpen = indexedDB.open;
        indexedDB.open = function(name, version) {
            console.log('[IDB] Opening database:', name, 'version:', version);
            var request = origOpen.apply(this, arguments);

            request.addEventListener('success', function(e) {
                console.log('[IDB] Database opened successfully');
            });

            request.addEventListener('error', function(e) {
                console.log('[IDB] Database open error');
            });

            return request;
        };

        // 2. deleteDatabase
        var origDeleteDatabase = indexedDB.deleteDatabase;
        indexedDB.deleteDatabase = function(name) {
            console.log('[IDB] Deleting database:', name);
            return origDeleteDatabase.apply(this, arguments);
        };

        // 3. databases (Chrome 71+)
        if (indexedDB.databases) {
            var origDatabases = indexedDB.databases;
            indexedDB.databases = function() {
                console.log('[IDB] Listing all databases');
                return origDatabases.apply(this, arguments);
            };
        }

        // 4. IDBFactory原型hook
        var origGetConnection = IDBFactory.prototype.open;
        IDBFactory.prototype.open = function(name, version) {
            console.log('[IDB] Factory open:', name);
            return origGetConnection.apply(this, arguments);
        };
    }

    console.log('[Hook] IndexedDB hooks installed');
})();
"""

# ============== 完整Hook管理器 ==============

class JSHookManager:
    """JS Hook脚本管理器"""

    HOOKS = {
        'network': NETWORK_HOOKS,
        'crypto': CRYPTO_HOOKS,
        'storage': STORAGE_HOOKS,
        'fingerprint': FINGERPRINT_HOOKS,
        'antidebug': ANTI_DEBUG_HOOKS,
        'slider': SLIDER_HOOKS,
        'device': DEVICE_HOOKS,
        'wasm': WASM_HOOKS,
        'service_worker': SW_HOOKS,
        'extended_crypto': EXTENDED_CRYPTO_HOOKS,
        'websocket': WEBSOCKET_HOOKS,
        'indexeddb': INDEXEDDB_HOOKS,
    }

    @classmethod
    def get_hook(cls, name: str) -> str:
        """获取指定Hook脚本"""
        return cls.HOOKS.get(name, '')

    @classmethod
    def get_all_hooks(cls) -> str:
        """获取所有Hook脚本"""
        return '\n'.join(cls.HOOKS.values())

    @classmethod
    def install_hooks(cls, page, hook_names: list = None):
        """
        在Playwright页面中安装Hook

        Args:
            page: Playwright page对象
            hook_names: 要安装的hook列表
        """
        if hook_names is None:
            script = cls.get_all_hooks()
        else:
            scripts = [cls.HOOKS.get(name, '') for name in hook_names]
            script = '\n'.join(scripts)

        page.evaluate(script)
        print(f"[JSHook] Installed hooks: {hook_names or 'all'}")

    @classmethod
    def install_network_hook(cls, page):
        """安装网络Hook"""
        cls.install_hooks(page, ['network'])

    @classmethod
    def install_crypto_hook(cls, page):
        """安装加密Hook"""
        cls.install_hooks(page, ['crypto'])

    @classmethod
    def install_full_hook(cls, page):
        """安装完整Hook (除slider外)"""
        cls.install_hooks(page, ['network', 'crypto', 'storage', 'fingerprint', 'antidebug', 'device'])

    @classmethod
    def install_captcha_hook(cls, page):
        """安装滑块验证码Hook"""
        cls.install_hooks(page, ['slider'])

    @classmethod
    def install_wasm_hook(cls, page):
        """安装WebAssembly Hook"""
        cls.install_hooks(page, ['wasm'])

    @classmethod
    def install_sw_hook(cls, page):
        """安装Service Worker Hook"""
        cls.install_hooks(page, ['service_worker'])

    @classmethod
    def install_websocket_hook(cls, page):
        """安装WebSocket Hook"""
        cls.install_hooks(page, ['websocket'])

    @classmethod
    def install_indexeddb_hook(cls, page):
        """安装IndexedDB Hook"""
        cls.install_hooks(page, ['indexeddb'])

    @classmethod
    def install_extended_crypto_hook(cls, page):
        """安装扩展加密Hook"""
        cls.install_hooks(page, ['extended_crypto'])

    @classmethod
    def install_full_hook(cls, page):
        """安装完整Hook (除slider外)"""
        cls.install_hooks(page, [
            'network', 'crypto', 'storage', 'fingerprint', 'antidebug', 'device',
            'wasm', 'service_worker', 'extended_crypto', 'websocket', 'indexeddb'
        ])
