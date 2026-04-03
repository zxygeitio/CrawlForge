"""
验证码求解器测试
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.captcha_solver import (
    CaptchaResult,
    BaseCaptchaSolver,
    SliderCaptchaSolver,
    ImageCaptchaSolver,
    GeeTestCaptchaSolver,
    create_solver,
)


class TestCaptchaResult:
    """CaptchaResult 数据类测试"""

    def test_success_result(self):
        """测试成功结果"""
        result = CaptchaResult(
            solved=True,
            solution={"distance": 100},
            confidence=0.9,
            duration=1.5,
        )
        assert result.solved is True
        assert result.solution["distance"] == 100
        assert result.confidence == 0.9
        assert result.error is None

    def test_failure_result(self):
        """测试失败结果"""
        result = CaptchaResult(
            solved=False,
            solution=None,
            error="Image processing failed",
            duration=0.5,
        )
        assert result.solved is False
        assert result.solution is None
        assert result.error == "Image processing failed"


class TestSliderCaptchaSolver:
    """滑块验证码求解器测试"""

    @pytest.fixture
    def solver(self):
        """创建滑块求解器"""
        return SliderCaptchaSolver()

    def test_detect_slider_captcha(self, solver, mock_playwright_page):
        """测试检测滑块验证码"""
        mock_playwright_page.query_selector.return_value = MagicMock()

        result = solver.detect(mock_playwright_page)
        assert result is True

    def test_detect_no_slider_captcha(self, solver, mock_playwright_page):
        """测试未检测到滑块验证码"""
        mock_playwright_page.query_selector.return_value = None

        result = solver.detect(mock_playwright_page)
        assert result is False

    def test_solve_returns_result(self, solver):
        """测试求解返回结果"""
        # Create a real simple image for testing
        from PIL import Image
        img = Image.new('RGB', (300, 200), color='white')

        result = solver.solve(img)

        assert result.solved is True
        assert "distance" in result.solution
        assert "trajectory" in result.solution
        assert result.confidence > 0

    def test_solve_creates_trajectory(self, solver):
        """测试轨迹生成"""
        from PIL import Image
        img = Image.new('RGB', (300, 200), color='white')

        result = solver.solve(img)
        trajectory = result.solution["trajectory"]

        assert isinstance(trajectory, list)
        assert len(trajectory) > 0
        # 轨迹格式: (x, y, timestamp)
        assert len(trajectory[0]) == 3

    def test_solve_trajectory_end_at_distance(self, solver):
        """测试轨迹终点到达指定距离"""
        from PIL import Image
        img = Image.new('RGB', (300, 200), color='white')

        result = solver.solve(img)
        distance = result.solution["distance"]
        trajectory = result.solution["trajectory"]

        # 最后一个点的 x 应该等于 distance
        assert trajectory[-1][0] == distance

    def test_solve_with_offset(self, solver):
        """测试带偏移量求解"""
        from PIL import Image
        img = Image.new('RGB', (300, 200), color='white')

        result = solver.solve(img, offset_x=10)

        assert result.solution["distance"] >= 0

    def test_solve_duration_recorded(self, solver):
        """测试耗时记录"""
        from PIL import Image
        img = Image.new('RGB', (300, 200), color='white')

        result = solver.solve(img)

        assert result.duration > 0
        assert result.duration < 10  # 不应该太长

    def test_solve_pil_not_available(self, solver):
        """测试 PIL 不可用时抛出异常"""
        with patch("src.captcha_solver.PIL_AVAILABLE", False):
            with pytest.raises(ImportError, match="PIL not installed"):
                solver._find_gap_by_edge_detection(None)

    def test_slide_to_position(self, solver, mock_playwright_page):
        """测试滑动到指定位置"""
        slider = MagicMock()
        slider.bounding_box.return_value = {"x": 100, "y": 200, "width": 50, "height": 50}
        mock_playwright_page.query_selector.return_value = slider

        solver.slide_to_position(mock_playwright_page, ".slider", 100)

        mock_playwright_page.mouse.move.assert_called()
        mock_playwright_page.mouse.down.assert_called()
        mock_playwright_page.mouse.up.assert_called()

    def test_slide_to_position_no_slider(self, solver, mock_playwright_page):
        """测试滑块不存在时抛出异常"""
        mock_playwright_page.query_selector.return_value = None

        with pytest.raises(ValueError, match="Slider not found"):
            solver.slide_to_position(mock_playwright_page, ".slider", 100)


class TestImageCaptchaSolver:
    """图片验证码求解器测试"""

    @pytest.fixture
    def solver(self):
        """创建图片求解器"""
        return ImageCaptchaSolver()

    @pytest.fixture
    def mock_image(self):
        """创建模拟图像"""
        from PIL import Image
        return MagicMock(spec=Image.Image)

    def test_detect_image_captcha(self, solver, mock_playwright_page):
        """测试检测图片验证码"""
        mock_playwright_page.query_selector.return_value = MagicMock()

        result = solver.detect(mock_playwright_page)
        assert result is True

    def test_detect_no_image_captcha(self, solver, mock_playwright_page):
        """测试未检测到图片验证码"""
        mock_playwright_page.query_selector.return_value = None

        result = solver.detect(mock_playwright_page)
        assert result is False

    def test_solve_without_ai(self, solver, mock_image):
        """测试非AI求解"""
        # Mock pytesseract to return empty string (simulating successful OCR)
        with patch("src.captcha_solver.ImageCaptchaSolver._simple_ocr", return_value=""):
            result = solver.solve(mock_image)
            assert result.solved is True
            assert result.solution["text"] == ""

    def test_solve_without_pytesseract(self, solver, mock_image):
        """测试pytesseract未安装时返回失败"""
        # Ensure pytesseract raises ImportError
        with patch.dict('sys.modules', {'pytesseract': None}):
            result = solver.solve(mock_image)
            assert result.solved is False
            assert "pytesseract" in result.error.lower() or "not installed" in result.error.lower()

    def test_solve_with_ai_not_implemented(self, solver, mock_image):
        """测试AI求解未实现"""
        solver.use_ai = True
        result = solver.solve(mock_image)

        assert result.solved is False
        assert "AI识别未实现" in result.error


class TestGeeTestCaptchaSolver:
    """极验验证码求解器测试"""

    @pytest.fixture
    def solver(self):
        """创建极验求解器"""
        return GeeTestCaptchaSolver()

    def test_detect_geetest(self, solver, mock_playwright_page):
        """测试检测极验验证码"""
        mock_playwright_page.query_selector.return_value = MagicMock()

        result = solver.detect(mock_playwright_page)
        assert result is True

    def test_detect_no_geetest(self, solver, mock_playwright_page):
        """测试未检测到极验验证码"""
        mock_playwright_page.query_selector.return_value = None

        result = solver.detect(mock_playwright_page)
        assert result is False

    def test_solve_no_bg_image(self, solver, mock_playwright_page):
        """测试背景图不存在时返回失败"""
        mock_playwright_page.query_selector.return_value = None

        result = solver.solve(mock_playwright_page)

        assert result.solved is False
        assert "背景图未找到" in result.error


class TestCreateSolver:
    """工厂函数测试"""

    def test_create_slider_solver(self):
        """测试创建滑块求解器"""
        solver = create_solver("slider")
        assert isinstance(solver, SliderCaptchaSolver)

    def test_create_image_solver(self):
        """测试创建图片求解器"""
        solver = create_solver("image")
        assert isinstance(solver, ImageCaptchaSolver)

    def test_create_geetest_solver(self):
        """测试创建极验求解器"""
        solver = create_solver("geetest")
        assert isinstance(solver, GeeTestCaptchaSolver)

    def test_create_default_solver(self):
        """测试默认创建滑块求解器"""
        solver = create_solver()
        assert isinstance(solver, SliderCaptchaSolver)

    def test_create_unknown_solver_defaults_to_slider(self):
        """测试未知类型默认创建滑块求解器"""
        solver = create_solver("unknown")
        assert isinstance(solver, SliderCaptchaSolver)
