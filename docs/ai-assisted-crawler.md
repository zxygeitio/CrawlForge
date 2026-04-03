# AI辅助爬虫技术

## 1. AI在爬虫中的应用场景

```
┌─────────────────────────────────────────────────────────┐
│                    AI爬虫技术栈                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  验证码识别  │  │  页面理解    │  │  轨迹生成   │  │
│  │  (CNN/YOLO) │  │  (GPT-4V)   │  │  (RL)       │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  反爬检测  │  │  数据抽取    │  │  异常检测   │  │
│  │  (随机森林) │  │  (NER/BERT) │  │  (LSTM)     │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 2. 验证码识别模型

### 2.1 滑块缺口检测 (YOLO)

```python
# 训练数据准备
"""
1. 收集大量滑块验证码图片
2. 标注缺口位置 (x, y, width, height)
3. 使用YOLO训练目标检测模型
"""

# 模型推理
import cv2
import torch
import numpy as np

class SliderCaptchaSolver:
    def __init__(self, model_path: str):
        self.model = torch.load(model_path)
        self.model.eval()

    def detect_gap(self, bg_image: np.ndarray, slider_image: np.ndarray) -> int:
        """
        检测滑块缺口位置
        Returns: gap_x (缺口左上角x坐标)
        """
        # 预处理
        bg = cv2.cvtColor(bg_image, cv2.COLOR_BGR2RGB)
        slider = cv2.cvtColor(slider_image, cv2.COLOR_BGR2RGB)

        # 推理
        with torch.no_grad():
            results = self.model([bg, slider])

        # 解析结果
        gap_x = results[0].boxes[0].xyxy[0][0].item()
        return int(gap_x)

    def generate_track(self, distance: int, style: str = "human") -> list:
        """
        生成人类滑动轨迹
        style: "fast", "normal", "slow"
        """
        tracks = []
        current = 0
        velocity = 8 if style == "fast" else 5 if style == "normal" else 3

        while current < distance:
            # 添加随机抖动
            jitter = np.random.randint(-2, 3)
            move = velocity + jitter

            # 减速机制
            if current > distance * 0.7:
                move = max(1, move - 2)

            current = min(current + move, distance)
            tracks.append(move)

        return tracks
```

### 2.2 文字识别 (CRNN+CTC)

```python
import torch
import torch.nn as nn

class CRNN(nn.Module):
    """CNN + RNN + CTC 文字识别模型"""

    def __init__(self, num_classes: int):
        super().__init__()
        # CNN backbone
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 64, 3, 1, 1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),  # 32x
            nn.Conv2d(64, 128, 3, 1, 1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),  # 16x
            # ...
        )

        # RNN
        self.rnn = nn.LSTM(128, 256, bidirectional=True, batch_first=True)

        # CTC Head
        self.fc = nn.Linear(512, num_classes)

    def forward(self, x):
        # x: (batch, channels, height, width)
        conv = self.cnn(x)  # (batch, 512, H, W)
        conv = conv.squeeze(2)  # (batch, 512, W)
        conv = conv.permute(0, 2, 1)  # (batch, W, 512)

        rnn_out, _ = self.rnn(conv)  # (batch, W, 512)
        output = self.fc(rnn_out)  # (batch, W, num_classes)
        output = torch.log_softmax(output, dim=2)

        return output  # 用于CTC loss

# 推理
def recognize_text(model, image: np.ndarray) -> str:
    """识别图片中的文字"""
    # 预处理: 灰度化, 缩放到固定高度
    processed = preprocess_for_crnn(image)

    # 推理
    with torch.no_grad():
        output = model(processed)

    # CTC解码
    pred = torch.argmax(output, dim=2)  # (batch, W)
    pred = pred.permute(1, 0)  # (W, batch)

    # CTC解码 (贪婪或束搜索)
    text = ctc_decode(pred)  # "hello"

    return text
```

## 3. 页面理解与结构化

### 3.1 GPT-4V页面分析

```python
import base64
import openai

class PageAnalyzer:
    """使用GPT-4V理解页面结构"""

    def __init__(self, api_key: str):
        openai.api_key = api_key

    def analyze_page(self, screenshot: bytes, task: str) -> dict:
        """
        分析页面截图
        task: "extract_links", "find_captcha", "understand_layout"
        """
        # 图片转base64
        img_b64 = base64.b64encode(screenshot).decode()

        response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": f"""分析这个网页截图。
                        任务: {task}

                        请返回:
                        1. 页面主要内容
                        2. 关键元素的位置(如按钮、输入框)
                        3. 可能的反爬机制
                        4. 如何完成给定任务"""
                    }
                ]
            }]
        )

        return response.choices[0].message.content

    def extract_links(self, screenshot: bytes) -> list:
        """提取页面所有链接"""
        result = self.analyze_page(screenshot, "extract_links")

        # 解析返回结果
        # "1. https://example.com/page1 - 标题1
        #  2. https://example.com/page2 - 标题2"

        links = []
        for line in result.split('\n'):
            if 'http' in line:
                url = line.split(' - ')[0].strip()
                title = line.split(' - ')[1].strip() if ' - ' in line else ''
                links.append({'url': url, 'title': title})

        return links

    def detect_captcha(self, screenshot: bytes) -> dict:
        """检测是否存在验证码"""
        result = self.analyze_page(screenshot, "find_captcha")

        captcha_types = ['滑块', '点选', '文字', '图片']
        detected = any(t in result for t in captcha_types)

        return {
            'has_captcha': detected,
            'type': [t for t in captcha_types if t in result],
            'details': result
        }
```

### 3.2 轻量级替代 (LLaVA)

```python
from llava.model import LlavaProcessor
from llava.conversation import conv_templates

class LocalPageAnalyzer:
    """使用LLaVA本地分析页面"""

    def __init__(self, model_path: str):
        self.processor = LlavaProcessor.from_pretrained(model_path)
        self.model = load_model(model_path)

    def analyze(self, image, prompt: str) -> str:
        """本地页面分析"""
        inputs = self.processor(
            images=image,
            texts=prompt,
            return_tensors="pt"
        )

        output = self.model.generate(**inputs)
        return self.processor.batch_decode(output, skip_special_tokens=True)[0]
```

## 4. 数据抽取AI

### 4.1 NER命名实体识别

```python
from transformers import AutoTokenizer, AutoModelForTokenClassification
import torch

class HouseDataExtractor:
    """从房源页面抽取结构化数据"""

    def __init__(self, model_path: str):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForTokenClassification.from_pretrained(model_path)
        self.labels = ['O', 'B-PRICE', 'I-PRICE', 'B-AREA', 'I-AREA',
                       'B-LOCATION', 'I-LOCATION', 'B-TITLE', 'I-TITLE']

    def extract(self, text: str) -> dict:
        """从文本中抽取房源信息"""
        # 分词
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True)

        # 推理
        with torch.no_grad():
            outputs = self.model(**inputs)

        # 解码
        predictions = torch.argmax(outputs.logits, dim=2)
        tokens = self.tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])

        # 提取实体
        entities = self.decode_entities(tokens, predictions[0])

        return {
            'title': entities.get('TITLE', [''])[0],
            'price': entities.get('PRICE', [''])[0],
            'area': entities.get('AREA', [''])[0],
            'location': entities.get('LOCATION', [''])[0],
        }

    def decode_entities(self, tokens, predictions) -> dict:
        entities = {}
        current_entity = []
        current_label = None

        for token, pred in zip(tokens, predictions):
            label = self.labels[pred]

            if label.startswith('B-'):
                # 保存上一个实体
                if current_label and current_entity:
                    key = current_label.replace('B-', '')
                    if key not in entities:
                        entities[key] = []
                    entities[key].append(''.join(current_entity).replace('##', ''))

                # 开始新实体
                current_label = label
                current_entity = [token]

            elif label.startswith('I-') and current_label == label:
                current_entity.append(token)
            else:
                # 实体结束
                if current_label and current_entity:
                    key = current_label.replace('B-', '')
                    if key not in entities:
                        entities[key] = []
                    entities[key].append(''.join(current_entity).replace('##', ''))
                current_entity = []
                current_label = None

        return entities
```

## 5. 强化学习轨迹生成

```python
import torch
import torch.nn as nn
import numpy as np

class TrajectoryPolicy(nn.Module):
    """强化学习策略网络 - 生成人类滑动轨迹"""

    def __init__(self, hidden_dim: int = 128):
        super().__init__()

        # 状态编码器
        self.state_encoder = nn.Sequential(
            nn.Linear(2, hidden_dim),  # 输入: 当前位置, 目标距离
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU()
        )

        # LSTM时序建模
        self.lstm = nn.LSTM(hidden_dim, hidden_dim, batch_first=True)

        # 策略输出
        self.policy_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Tanh()  # 输出: 移动距离 (-1, 1)
        )

        # 价值网络
        self.value_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

    def forward(self, state, hidden=None):
        """
        state: (batch, seq_len, 2) - 位置和目标
        Returns: action, log_prob, value, hidden
        """
        x = self.state_encoder(state)
        x, hidden = self.lstm(x, hidden)

        action = self.policy_head(x)  # 策略
        value = self.value_head(x)   # 价值

        return action, log_prob, value, hidden

class HumanTrajectoryGenerator:
    """人类轨迹生成器"""

    def __init__(self, model_path: str):
        self.model = TrajectoryPolicy()
        self.model.load_state_dict(torch.load(model_path))
        self.model.eval()

    def generate(self, distance: int, style: str = "normal") -> list:
        """
        生成人类滑动轨迹
        distance: 滑动距离
        style: "fast", "normal", "slow"
        """
        seq_len = 20  # 生成20步
        trajectory = []

        state = torch.tensor([[0.0, float(distance)]])  # 初始状态
        hidden = None

        for step in range(seq_len):
            with torch.no_grad():
                action, _, _, hidden = self.model(state, hidden)

            # 将(-1,1)映射到实际移动距离
            move = int(action.item() * 10 + 5)  # 基础移动
            current_pos = trajectory[-1] if trajectory else 0

            # 减速
            if current_pos > distance * 0.7:
                move = max(1, move - 2)

            new_pos = min(current_pos + move, distance)
            trajectory.append(new_pos)

            # 更新状态
            state = torch.tensor([[new_pos, distance]]).unsqueeze(1)

        return trajectory
```

## 6. 端到端AI代理

```python
class AIAgentCrawler:
    """
    端到端AI代理爬虫
    输入URL, 输出结构化数据
    """

    def __init__(self, config: dict):
        self.vision = PageAnalyzer(config['openai_key'])
        self.captcha_solver = SliderCaptchaSolver(config['yolo_model'])
        self.trajectory_gen = HumanTrajectoryGenerator(config['rl_model'])
        self.extractor = HouseDataExtractor(config['ner_model'])

        self.browser = sync_playwright().start().chromium

    def crawl(self, url: str) -> dict:
        """主流程"""
        page = self.browser.new_page()

        try:
            # 1. 访问页面
            page.goto(url)

            # 2. AI分析页面
            screenshot = page.screenshot()

            page_analysis = self.vision.analyze_page(screenshot, "understand_layout")

            # 3. 检查验证码
            captcha = self.vision.detect_captcha(screenshot)
            if captcha['has_captcha']:
                self.handle_captcha(page, captcha)

            # 4. 滚动加载
            self.scroll_and_load(page)

            # 5. 提取数据
            html = page.content()
            data = self.extractor.extract(html)

            return {
                'url': url,
                'data': data,
                'status': 'success'
            }

        except Exception as e:
            return {
                'url': url,
                'error': str(e),
                'status': 'failed'
            }

        finally:
            page.close()

    def handle_captcha(self, page, captcha_info):
        """处理验证码"""
        if '滑块' in captcha_info['type']:
            # 滑块验证
            bg = page.locator('.bg-img').screenshot()
            slider = page.locator('.slider').screenshot()

            gap = self.captcha_solver.detect_gap(bg, slider)
            track = self.trajectory_gen.generate(gap)

            # 执行滑动
            page.locator('.slider').hover()
            page.mouse.down()
            for move in track:
                page.mouse.move(page.mouse.position.x + move,
                               page.mouse.position.y)
            page.mouse.up()
```

---

## 7. AI模型训练数据

### 7.1 数据收集

```python
# 滑块验证码数据收集
class CaptchaDataCollector:
    """收集训练数据"""

    def __init__(self, db):
        self.db = db
        self.collection = db['captcha_samples']

    def collect(self, url: str, bg: bytes, slider: bytes, gap_x: int):
        """收集样本"""
        self.collection.insert_one({
            'url': url,
            'bg': bg,  # 原始图片
            'slider': slider,
            'gap_x': gap_x,  # 标注
            'collected_at': datetime.utcnow()
        })

    def augment(self, image: np.ndarray) -> list:
        """数据增强"""
        augmented = []

        # 旋转
        for angle in [-5, -3, 0, 3, 5]:
            rotated = rotate(image, angle)
            augmented.append(rotated)

        # 亮度
        for brightness in [0.8, 1.0, 1.2]:
            brightened = adjust_brightness(image, brightness)
            augmented.append(brightened)

        # 噪声
        noisy = add_noise(image, sigma=5)
        augmented.append(noisy)

        return augmented
```

### 7.2 模型训练

```python
# YOLO训练
"""
训练命令:
yolo detect train data=captcha.yaml model=yolov8n.pt epochs=100

captcha.yaml:
path: ./data
train: images/train
val: images/val

nc: 1  # 缺口类别数
names: ['gap']
"""

# CRNN训练
"""
训练命令:
python train.py --data_path ./text_captcha --epochs 100

loss = CTCLoss(blank=0, reduction='mean')
optimizer = Adam(lr=0.001)
"""
```

---

*Last Updated: 2026-04-02*
