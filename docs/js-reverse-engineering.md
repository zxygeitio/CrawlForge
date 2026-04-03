# JavaScript逆向工程实战手册

## 1. JS混淆识别

### 1.1 常见混淆模式

```javascript
// 变量名混淆
var a = "hello";    // 原始
var _$br = "hello"; // 混淆后

// 字符串加密
"hello" -> "\x68\x65\x6c\x6c\x6f"  // Hex编码
"hello" -> "h\x65llo"              // 混合格式

// 函数混淆
function foo() {} -> function _$_b() {}

// 对象属性混淆
obj.name -> obj[_$kX(12)]
```

### 1.2 控制流平坦化

```javascript
// 原始代码
if (condition) {
    doA();
} else {
    doB();
}

// 混淆后 (平坦化)
var state = condition ? 1 : 2;
switch(state) {
    case 1:
        state = 3;
        break;
    case 2:
        state = 4;
        break;
    case 3:
        doA(); state = 5; break;
    case 4:
        doB(); state = 5; break;
}
```

## 2. 反调试技术

### 2.1 debugger陷阱

```javascript
// 无限debugger
setInterval(() => { debugger; }, 100);

// 条件debugger
(function() {
    var check = (new Date()).getTime() % 100 === 0;
    if (check) {
        debugger;
    }
})();
```

### 2.2 绕过方法

```python
# Playwright绕过debugger
page.evaluate("""
    setInterval = () => {};
    setTimeout = () => {};
    Object.defineProperty(window, 'debugger', {get: () => {}});
""")
```

## 3. JS逆向工具

### 3.1 浏览器开发者工具

```javascript
// 在Console中执行
// 1. 格式化混淆代码
function formatCode() {
    var code = editor.getValue();
    try {
        var ast = Babel.parse(code);
        var formatted = Babel.generate(ast);
        editor.setValue(formatted);
    } catch(e) {
        console.log("Parse error:", e);
    }
}

// 2. Hook加密函数
var originalEncrypt = window.encrypt;
window.encrypt = function(data) {
    console.log("Encrypt called:", data);
    return originalEncrypt(data);
};

// 3. 监控XHR/Fetch
var originalFetch = window.fetch;
window.fetch = function(url, options) {
    console.log("Fetch:", url);
    return originalFetch(url, options);
};
```

### 3.2 mitmproxy脚本

```python
from mitmproxy import http

def response(flow: http.HTTPFlow):
    # 自动检测加密响应
    if "api" in flow.request.pretty_url:
        print(f"URL: {flow.request.pretty_url}")
        print(f"Response: {flow.response.text[:200]}")

    # 解密特定响应
    if "encrypt" in flow.request.pretty_url:
        decrypted = decrypt(flow.response.text)
        flow.response.text = decrypted
```

### 3.3 Node.js执行环境

```javascript
// 创建一个JS执行沙箱
const vm = require('vm');

const context = {
    console: console,
    setTimeout: setTimeout,
    window: {
        navigator: { userAgent: 'Mozilla/5.0...' }
    },
    document: {
        querySelector: () => ({ innerHTML: '' })
    }
};

vm.createContext(context);

// 执行混淆JS
vm.runInContext(obfuscatedCode, context);
```

## 4. 实战案例

### 4.1 加密参数溯源

```javascript
// 目标: 找出sign参数的生成方式
// URL: https://api.example.com/list?sign=xxx&timestamp=xxx

// 方法1: Hook XMLHttpRequest
var origOpen = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function(method, url, async) {
    console.log("XHR Request:", method, url);
    if (url.includes("sign=")) {
        // 在这里断点, 查看调用栈
        debugger;
    }
    return origOpen.apply(this, arguments);
};

// 方法2: Hook fetch
var origFetch = window.fetch;
window.fetch = function(url, options) {
    console.log("Fetch:", url);
    return origFetch.apply(this, arguments);
};

// 方法3: Hook CryptoJS
var origEncrypt = CryptoJS.AES.encrypt;
CryptoJS.AES.encrypt = function(data, key) {
    console.log("Encrypting:", data.toString());
    return origEncrypt.apply(this, arguments);
};
```

### 4.2 字节码VM分析

```javascript
// 观察VM的关键函数
// $_ts.lcd() - 解码函数
// $_ts.cd - 编码数据
// $_ts.nsd - 数字种子

// 分析执行流程:
// 1. VM初始化,读取字节码
// 2. 解码$_ts.cd得到实际代码
// 3. 执行解码后的代码

// 动态调试:
console.log($_ts);
console.log($_ts.cd);  // 打印编码数据
console.log($_ts.nsd); // 打印种子
```

## 5. Python调用Node.js

```python
import subprocess
import json

def execute_js(js_code: str, args: dict = None) -> str:
    """在Node.js中执行JS代码"""
    # 构建完整的JS执行脚本
    full_script = f"""
    const args = {json.dumps(args) if args else '{}'};
    {js_code}
    """

    result = subprocess.run(
        ['node', '-e', full_script],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        raise Exception(f"JS Error: {result.stderr}")
    return result.stdout

# 使用示例
js_code = """
const crypto = require('crypto');
function md5(data) {{
    return crypto.createHash('md5').update(data).digest('hex');
}}
console.log(md5(args.data));
"""

result = execute_js(js_code, {'data': 'hello'})
print(result)  # 5d41402abc4b2a76b9719d911017c592
```

## 6. AST动态分析

```python
import esprima  # JS AST解析库

def analyze_js(code: str):
    """分析JS代码结构"""
    ast = esprima.parse(code)

    # 找出所有函数调用
    for node in ast.body:
        if node.type == 'ExpressionStatement':
            if node.expression.type == 'CallExpression':
                callee = node.expression.callee
                print(f"Call: {callee.name}(...)")

    # 找出可疑的eval调用
    for node in ast.body:
        if node.type == 'CallExpression':
            if getattr(node.callee, 'name', None) == 'eval':
                print("Warning: eval() detected!")
                print(f"Location: line {node.loc.start.line}")
```

## 7. 常用Hook脚本

```javascript
// ========== 通用Hook脚本 ==========

// 1. Hook所有网络请求
const originalXHR = XMLHttpRequest;
window.XMLHttpRequest = function() {
    const xhr = new originalXHR();
    const originalSend = xhr.send;
    xhr.send = function(data) {
        console.log('XHR Send:', this._url, data);
        return originalSend.apply(this, arguments);
    };
    Object.defineProperty(xhr, 'url', {
        get: () => this._url,
        set: (v) => { this._url = v; }
    });
    return xhr;
};

// 2. Hook WebSocket
const OriginalWebSocket = WebSocket;
window.WebSocket = function(url, protocols) {
    console.log('WebSocket:', url, protocols);
    const ws = new OriginalWebSocket(url, protocols);
    return ws;
};

// 3. Hook Canvas
const origGetContext = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function(type, attributes) {
    console.log('Canvas getContext:', type);
    return origGetContext.call(this, type, attributes);
};

// 4. Hook Cookie/Storage
const origSetItem = Storage.prototype.setItem;
Storage.prototype.setItem = function(key, value) {
    console.log('Storage.setItem:', key, value);
    return origSetItem.call(this, key, value);
};
```

## 8. 反混淆工具

| Tool | Description |
|------|-------------|
| JS Beautifier | 格式化混淆代码 |
| de4js | 在线JS解混淆 |
| JSNice | 变量名还原 |
| Babel | AST解析与操作 |
| ASTExplorer | 可视化AST分析 |
| Bromite | 反混淆浏览器 |

---

*Last Updated: 2026-04-02*
