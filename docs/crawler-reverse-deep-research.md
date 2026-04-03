# 爬虫逆向技术深度研究报告

## 一、浏览器工作原理

### 1.1 HTTP请求流程

```
DNS Resolution -> TCP Connection -> TLS Handshake -> HTTP Request -> Response
   域名解析        三次握手        TLS协商加密      发送请求        返回响应
```

### 1.2 TLS握手与JA3指纹

JA3指纹计算基于TLS ClientHello包:
1. **TLS Version** - 协议版本
2. **Cipher Suites** - 加密套件列表
3. **Extensions** - 扩展列表
4. **Elliptic Curves** - 椭圆曲线

```python
# JA3 Example
# Chrome 122: 773bd0ef3e969669343a田田田田田田田77147347c99a2ad4c9田田田田田田田田田
# Firefox:    田田田田田田田田田田田田田田田田田田田田田田田
```

### 1.3 curl_cffi impersonate原理

```python
from curl_cffi import requests

# impersonate参数模拟特定浏览器的TLS指纹
session = requests.Session(impersonate="chrome")
session.get("https://example.com")

# 原理:
# 1. 读取Chrome的TLS ClientHello数据
# 2. 在curl中模拟这些数据进行握手
# 3. 服务器认为请求来自真实Chrome
```

---

## 二、反爬机制与绕过技术

### 2.1 TLS指纹检测

| Level | Detection | Bypass |
|-------|-----------|--------|
| Basic | JA3 hash | curl_cffi |
| Medium | JA3N (HTTP/3) | 暂无完美方案 |
| Hard | TLS 1.3 GREASE | 手动实现 |

### 2.2 浏览器指纹检测

```python
# Playwright反检测配置
browser = p.chromium.launch(
    args=[
        '--disable-blink-features=AutomationControlled',  # 核心
        '--disable-dev-shm-usage',                       # 避免共享内存检测
        '--no-sandbox',                                  # Docker环境
        '--disable-setuid-sandbox',
    ]
)
context = browser.new_context(
    user_agent='Mozilla/5.0 (Windows NT 10.0...) Chrome/123...',
    viewport={'width': 1920, 'height': 1080},  # 固定值也可能是指纹
    locale='zh-CN',
    timezone_id='Asia/Shanghai',
    permissions=['geolocation'],
)
```

### 2.3 JavaScript动态渲染

| Method | Pros | Cons |
|--------|------|------|
| requests | Fast | No JS |
| curl_cffi | TLS bypass | No JS |
| Playwright | Full browser | Slow |
| Selenium | Full browser | Slow + detectable |

---

## 三、JavaScript逆向工程

### 3.1 混淆类型

```
1. 变量名混淆: a -> _$_v -> _$br
2. 字符串加密: "hello" -> "\x68\x65\x6c\x6c\x6f"
3. 控制流平坦化: if/else -> switch/case打乱
4. 字节码VM: 自定义解释器执行混淆字节码
5. 反调试: debugger陷阱, 时间检测
```

### 3.2 VM逆向工程流程

```python
# jwc.sptc.edu.cn案例分析

# 混淆数据
$_ts.cd = "qoTErrAloGGkWPGlcq3ntqWErramcqWntqA7qqlP..."

# 特征:
# - $_ts.nsd = 58801 (seed?)
# - $_ts.lcd = 函数 (解码函数?)
# - 外部JS: /g0ItD0HTXsMo/VD7jcVszZsL5.b4c45da.js

# VM结构推测:
"""
var vm = {
    memory: [],      // 内存
    registers: {},    // 寄存器
    pc: 0,           // 程序计数器
    stack: []        // 栈
}

function vm_exec(opcode, args) {
    switch(opcode) {
        case 0: return LOAD(args[0])      // 加载
        case 1: return STORE(args[0])      // 存储
        case 2: return JMP(args[0])        // 跳转
        case 3: return CALL(args[0])       // 调用
        // ...
    }
}
"""
```

### 3.3 解混淆方法

| Method | Tool | Use Case |
|--------|------|----------|
| Dynamic execution | Browser DevTools | 执行JS获取结果 |
| AST analysis | Babel parser | 控制流还原 |
| Pattern matching | Regex/script | 已知混淆模式 |
| ML detection | TensorFlow | 未知模式识别 |

---

## 四、大规模数据采集

### 4.1 增量爬取

```python
class IncrementalCrawler:
    def __init__(self, db):
        self.db = db
        self.crawled = self.load_crawled()

    def is_new(self, url):
        return url not in self.crawled

    def mark_done(self, url):
        self.crawled.add(url)
        self.db.save(url)

    def load_crawled(self):
        return set(self.db.get_all_urls())
```

### 4.2 分布式架构

```
┌────────────┐     ┌────────────┐     ┌────────────┐
│  Scraper   │────▶│   Redis    │────▶│  MongoDB   │
│  Node 1    │     │  (Queue)   │     │ (Storage) │
└────────────┘     └────────────┘     └────────────┘
       │                                      ▲
       │           ┌────────────┐             │
       └─────────▶│   Celery   │─────────────┘
                   │  (Workers) │
                   └────────────┘
```

### 4.3 存储方案

| Storage | Use Case | Query |
|---------|----------|-------|
| MongoDB | 爬虫数据 | Aggregation |
| MySQL | 关系数据 | SQL |
| Elasticsearch | 全文检索 | Full-text |
| S3/OSS | 文件/图片 | Object |
| HDF5 | 训练数据 | ML dataset |

---

## 五、AI辅助爬虫

### 5.1 验证码识别

```python
# YOLO-based滑块检测
model = YOLO('slider_detector.pt')
gap_x = model.predict(background_img, slider_img)

# 轨迹生成
class HumanTrajectory:
    def generate(self, distance):
        # 强化学习训练的轨迹生成器
        return rl_agent.sample(distance)
```

### 5.2 页面理解

```python
# GPT-4V分析页面结构
response = openai.ChatCompletion.create(
    model="gpt-4-vision",
    messages=[{
        "role": "user",
        "content": f"""Analyze this page:
        1. What anti-bot measures exist?
        2. What's the data structure?
        3. How to extract the data?
        URL: {url}"""
    }]
)
```

### 5.3 端到端代理

```
Input: URL + Task
    ↓
AI Vision: 理解页面结构
    ↓
AI Planning: 规划爬取策略
    ↓
AI Action: 执行操作序列
    ↓
AI Extract: 提取数据
    ↓
Output: Structured Data
```

---

## 六、实战案例

### 6.1 jwc.sptc.edu.cn

**问题**: 字节码VM反爬

**绕过方案**:
1. curl_cffi绕过TLS检测 → 获取初始页面
2. Playwright渲染JS → 执行VM字节码
3. 通过MCP获取渲染后内容

### 6.2 lianjia.com

**问题**: 验证码墙 + TLS指纹

**绕过方案**:
1. curl_cffi模拟chrome指纹 → 部分可用
2. Chrome DevTools MCP → 绕过验证码
3. Playwright → 提取房源数据

### 6.3 通用反爬

**策略**:
```python
class HybridCrawler:
    def try_methods(self, url):
        # 1. 先试简单请求
        if r := self.try_requests(url):
            return r

        # 2. 再试curl_cffi
        if r := self.try_curl_cffi(url):
            return r

        # 3. 最后用Playwright
        if r := self.try_playwright(url):
            return r

        # 4. 失败
        return None
```

---

## 七、工具链

| Tool | Purpose |
|------|---------|
| curl_cffi | TLS指纹绕过 |
| Playwright | 浏览器自动化 |
| selenium | 备用浏览器 |
| mitmproxy | 抓包分析 |
| Wireshark | 网络协议分析 |
| Node.js | JS动态执行 |
| 超级鹰 | 验证码平台 |

---

## 八、未来趋势

1. **AI vs AI**: 反爬和反反爬都会越来越智能化
2. **TLS 1.3普及**: 指纹检测更困难
3. **WebAssembly**: 代码混淆更强
4. **端到端自动化**: AI自主爬取

---

## 九、最佳实践

1. **渐进式绕过**: 从简单到复杂
2. **保持低调**: 限速 + 随机延迟
3. **增量优先**: 记录已爬URL
4. **数据持久化**: 定期保存
5. **日志记录**: 便于调试

---

*Report generated: 2026-04-02*
*Author: Claude AI*
