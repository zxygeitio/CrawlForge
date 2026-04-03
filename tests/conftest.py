"""
pytest 配置和公共 fixture
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp.ClientSession"""
    session = AsyncMock()
    session.get = AsyncMock()
    session.post = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_playwright_page():
    """Mock Playwright page"""
    page = MagicMock()
    page.query_selector = MagicMock()
    page.screenshot = MagicMock()
    page.mouse = MagicMock()
    page.mouse.move = MagicMock()
    page.mouse.down = MagicMock()
    page.mouse.up = MagicMock()
    return page


@pytest.fixture
def mock_pil_image():
    """Mock PIL Image"""
    from PIL import Image
    img = MagicMock(spec=Image.Image)
    img.convert = MagicMock(return_value=img)
    img.resize = MagicMock(return_value=img)
    return img


@pytest.fixture
def sample_proxy_url():
    """Sample proxy URL"""
    return "127.0.0.1:8080"


@pytest.fixture
def sample_proxy_tags():
    """Sample proxy tags"""
    return {"country": "CN", "type": "http"}


@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir(tmp_path):
    """Provide temporary directory path as string for compatibility"""
    return str(tmp_path)
