"""
分布式任务支持
基于 Redis + Celery 的异步任务队列
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

try:
    from celery import Celery, Task
    from celery.signals import task_prerun, task_postrun, task_failure
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    status: str  # pending, success, failure
    result: Any = None
    error: Optional[str] = None
    created_at: str = None
    completed_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()


class CrawlerCelery:
    """
    分布式爬虫任务

    使用 Celery 进行异步任务分发
    支持:
    - 异步爬取
    - 任务状态追踪
    - 结果回调
    - 失败重试
    """

    def __init__(
        self,
        broker_url: str = "redis://localhost:6379/0",
        result_backend: str = "redis://localhost:6379/0",
        task_name: str = "crawler.tasks",
    ):
        if not CELERY_AVAILABLE:
            raise ImportError("Celery not installed. Run: pip install celery")

        self.broker_url = broker_url
        self.result_backend = result_backend
        self.task_name = task_name

        self.celery = Celery(
            task_name,
            broker=broker_url,
            backend=result_backend,
        )

        self._setup_config()
        self._crawl_task = self._create_crawl_task()

    def _setup_config(self):
        """配置 Celery"""
        self.celery.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="Asia/Shanghai",
            enable_utc=True,
            task_track_started=True,
            task_time_limit=300,  # 5分钟超时
            task_soft_time_limit=240,  # 4分钟软超时
            worker_prefetch_multiplier=1,
            worker_max_tasks_per_child=100,  # 每100个任务重启worker
        )

    def _create_crawl_task(self):
        """创建爬虫任务（在初始化时注册一次）"""

        @self.celery.task(bind=True)
        def crawl_task(self, url: str, config: dict = None, parser_name: str = "default"):
            """爬虫任务"""
            from src.advanced_crawler import AdvancedCrawler, CrawlerConfig, RequestMethod

            # 重建爬虫实例
            if config:
                crawler_config = CrawlerConfig(**config)
            else:
                crawler_config = CrawlerConfig()

            crawler = AdvancedCrawler(crawler_config)

            try:
                result = crawler.crawl_page(url, lambda r: r.json(), RequestMethod.CURL_CFFI)
                return {"status": "success", "data": result}
            except Exception as e:
                return {"status": "error", "error": str(e)}
            finally:
                crawler.close()

        return crawl_task

    def register_task(self, func: Callable = None, **kwargs):
        """注册爬虫任务（返回预注册的任务）"""
        return self._crawl_task

    def add_task(
        self,
        url: str,
        config: dict = None,
        parser_name: str = "default",
        callback: Callable = None,
    ) -> str:
        """添加爬虫任务"""
        task = self.register_task()

        def wrapped_callback(result):
            try:
                if callback:
                    callback(result)
            except Exception as e:
                logger.warning(f"Task callback failed: {e}")

        result = task.apply_async(
            args=[url, config, parser_name],
            callbacks=[wrapped_callback] if callback else None,
        )
        return result.id

    def get_task_result(self, task_id: str) -> TaskResult:
        """获取任务结果"""
        result = self.celery.AsyncResult(task_id)

        return TaskResult(
            task_id=task_id,
            status=result.state.lower(),
            result=result.result if result.ready() else None,
            error=str(result.info) if result.failed() else None,
            completed_at=datetime.utcnow().isoformat() if result.ready() else None,
        )

    def get_task_status(self, task_id: str) -> str:
        """获取任务状态"""
        result = self.celery.AsyncResult(task_id)
        return result.state

    def is_task_ready(self, task_id: str) -> bool:
        """检查任务是否完成"""
        return self.celery.AsyncResult(task_id).ready()

    def is_task_success(self, task_id: str) -> bool:
        """检查任务是否成功"""
        result = self.celery.AsyncResult(task_id)
        return result.successful()

    def revoke_task(self, task_id: str, terminate: bool = False):
        """撤销任务"""
        self.celery.control.revoke(task_id, terminate=terminate)


class RedisQueueManager:
    """
    Redis 队列管理器

    用于:
    - URL 去重
    - 任务队列
    - 结果缓存
    - 分布式锁
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        prefix: str = "crawler:",
    ):
        if not REDIS_AVAILABLE:
            raise ImportError("redis not installed. Run: pip install redis")

        self.prefix = prefix
        self.redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
        )

    def _key(self, name: str) -> str:
        """生成带前缀的键名"""
        return f"{self.prefix}{name}"

    # URL 去重
    def is_url_seen(self, url: str) -> bool:
        """检查URL是否已爬取"""
        try:
            key = self._key("seen_urls")
            url_hash = hashlib.md5(url.encode()).hexdigest()
            return self.redis.sismember(key, url_hash)
        except redis.exceptions.ConnectionError:
            logger.warning("Redis unavailable, skipping URL dedup check")
            return False  # 降级：未见过

    def check_and_mark_seen(self, url: str) -> bool:
        """原子地检查并标记 URL 已见。返回 True 表示是新 URL（已标记），False 表示已见过。"""
        try:
            key = self._key("seen_urls")
            url_hash = hashlib.md5(url.encode()).hexdigest()
            # SETNX 返回 True 只有在 key 不存在时（即第一次设置）
            return bool(self.redis.set(key, url_hash, nx=True))
        except redis.exceptions.ConnectionError:
            logger.warning("Redis unavailable, skipping URL dedup check")
            return False  # 降级：未见过

    def mark_url_seen(self, url: str) -> bool:
        """标记URL已爬取"""
        try:
            key = self._key("seen_urls")
            url_hash = hashlib.md5(url.encode()).hexdigest()
            return self.redis.sadd(key, url_hash) == 1
        except redis.exceptions.ConnectionError:
            logger.warning("Redis unavailable, skipping URL mark")
            return False  # 降级：标记失败

    def get_seen_count(self) -> int:
        """获取已爬取URL数量"""
        try:
            key = self._key("seen_urls")
            return self.redis.scard(key)
        except redis.exceptions.ConnectionError:
            logger.warning("Redis unavailable, returning 0 for seen count")
            return 0  # 降级：返回0

    # 任务队列
    def push_task(self, url: str, priority: int = 0) -> bool:
        """
        添加任务到队列

        Args:
            url: 目标URL
            priority: 优先级 (0=低, 1=中, 2=高)

        Returns:
            是否成功添加
        """
        key = self._key("task_queue")
        task_data = json.dumps({"url": url, "priority": priority, "added_at": datetime.utcnow().isoformat()})

        if priority > 0:
            # 高优先级放入有序集合
            score = 100 - priority  # 分数越小优先级越高
            self.redis.zadd(self._key("priority_queue"), {task_data: score})
            return True
        else:
            # 普通任务放入列表
            return bool(self.redis.rpush(key, task_data))

    def pop_task(self, timeout: int = 0) -> Optional[dict]:
        """
        取出任务

        Args:
            timeout: 阻塞等待时间(秒)

        Returns:
            任务数据或None
        """
        # 使用 Lua 脚本原子化 ZPOPMIN（Redis 7.0 以下兼容）
        # 防止 ZRANGEBYSCORE + ZREM 之间的竞态条件导致同一任务被多个 worker 重复取出
        priority_key = self._key("priority_queue")
        lua_script = """
        local candidates = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', '+inf', 'LIMIT', 0, 1)
        if #candidates > 0 then
            redis.call('ZREM', KEYS[1], candidates[1])
            return candidates[1]
        end
        return nil
        """
        result = self.redis.eval(lua_script, 1, priority_key)
        if result:
            return json.loads(result)

        # 再检查普通队列
        key = self._key("task_queue")
        if timeout > 0:
            task_data = self.redis.blpop(key, timeout=timeout)
            if task_data:
                return json.loads(task_data[1])
        else:
            task_data = self.redis.lpop(key)
            if task_data:
                return json.loads(task_data)

        return None

    def get_queue_size(self) -> int:
        """获取队列大小"""
        try:
            return self.redis.llen(self._key("task_queue")) + self.redis.zcard(self._key("priority_queue"))
        except redis.exceptions.ConnectionError:
            logger.warning("Redis unavailable, returning 0 for queue size")
            return 0  # 降级：返回0

    # 结果缓存
    def cache_result(self, url: str, result: dict, ttl: int = 3600):
        """
        缓存爬取结果

        Args:
            url: URL
            result: 结果数据
            ttl: 过期时间(秒)
        """
        key = self._key(f"result:{hashlib.md5(url.encode()).hexdigest()}")
        self.redis.setex(key, ttl, json.dumps(result))

    def get_cached_result(self, url: str) -> Optional[dict]:
        """获取缓存的结果"""
        key = self._key(f"result:{hashlib.md5(url.encode()).hexdigest()}")
        data = self.redis.get(key)
        return json.loads(data) if data else None

    # 分布式锁
    def acquire_lock(self, name: str, timeout: int = 10, owner: str = None) -> bool:
        """
        获取分布式锁

        Args:
            name: 锁名称
            timeout: 超时时间
            owner: 锁持有者标识（默认为 id(self)）

        Returns:
            是否获取成功
        """
        key = self._key(f"lock:{name}")
        owner = owner or str(id(self))
        return bool(self.redis.set(key, owner, nx=True, ex=timeout))

    def release_lock(self, name: str, owner: str = None):
        """释放锁（仅持有者可释放）"""
        key = self._key(f"lock:{name}")
        if owner is None:
            owner = str(id(self))
        # 使用 Lua 脚本原子检查 owner 并删除
        lua = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('DEL', KEYS[1])
        else
            return 0
        end
        """
        self.redis.eval(lua, 1, key, owner)

    # 统计
    def get_stats(self) -> dict:
        """获取统计信息"""
        try:
            return {
                "seen_urls": self.get_seen_count(),
                "queue_size": self.get_queue_size(),
                "redis_info": self.redis.info(),
            }
        except redis.exceptions.ConnectionError:
            logger.warning("Redis unavailable, returning partial stats")
            return {
                "seen_urls": self.get_seen_count(),
                "queue_size": self.get_queue_size(),
                "redis_info": None,
            }


def start_worker(
    broker_url: str = "redis://localhost:6379/0",
    task_name: str = "crawler.tasks",
    concurrency: int = 4,
    loglevel: str = "INFO",
):
    """
    启动 Celery Worker

    Args:
        broker_url: Redis连接URL
        task_name: 任务名称
        concurrency: 并发数
        loglevel: 日志级别
    """
    import subprocess

    cmd = [
        "celery",
        "-A", "src.distributed_tasks",
        "worker",
        "--broker", broker_url,
        "--loglevel", loglevel,
        "--concurrency", str(concurrency),
        "--pool", "prefork",
    ]

    subprocess.run(cmd)
