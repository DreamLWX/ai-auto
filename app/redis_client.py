"""
Redis 客户端模块
提供 Redis 连接、黑名单管理、任务列表缓存等操作
"""
import redis
import json
from typing import Optional, List, Any


class RedisClient:
    """Redis 客户端封装类"""

    def __init__(self, url: str = "redis://localhost:6379/0"):
        """
        初始化 Redis 连接

        Args:
            url: Redis 连接 URL，格式 redis://host:port/db
        """
        self.redis = redis.from_url(url, decode_responses=True)

    # ==================== Token 黑名单管理 ====================

    def add_to_blacklist(self, jti: str, expires_in: int) -> None:
        """
        将 JWT 的 JTI 加入黑名单

        Args:
            jti: JWT 的唯一标识 ID
            expires_in: 剩余有效期秒数，与 token 过期时间一致
        """
        self.redis.setex(f"blacklist:{jti}", expires_in, "1")

    def is_blacklisted(self, jti: str) -> bool:
        """
        检查某个 JTI 是否在黑名单中

        Args:
            jti: JWT 的唯一标识 ID

        Returns:
            True 表示已被拉黑（无效），False 表示有效
        """
        return self.redis.exists(f"blacklist:{jti}") == 1

    # ==================== 任务列表缓存 ====================

    def get_tasks_cache(self, user_id: int, page: int, per_page: int = 10) -> Optional[dict]:
        """
        获取用户任务列表的缓存

        Args:
            user_id: 用户 ID
            page: 页码
            per_page: 每页条数，默认10

        Returns:
            缓存数据（dict）或 None（未命中）
        """
        key = f"tasks:user:{user_id}:page:{page}:size:{per_page}"
        data = self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    def set_tasks_cache(self, user_id: int, page: int, per_page: int, data: dict, ttl: int = 60) -> None:
        """
        缓存用户任务列表

        Args:
            user_id: 用户 ID
            page: 页码
            per_page: 每页条数
            data: 要缓存的分页数据
            ttl: 过期秒数，默认60秒
        """
        key = f"tasks:user:{user_id}:page:{page}:size:{per_page}"
        self.redis.setex(key, ttl, json.dumps(data))

    def invalidate_user_tasks_cache(self, user_id: int) -> None:
        """
        清除某个用户的所有任务列表缓存
        在创建、更新、删除任务时调用

        Args:
            user_id: 用户 ID
        """
        pattern = f"tasks:user:{user_id}:*"
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)

    # ==================== 通用操作 ====================

    def ping(self) -> bool:
        """
        检查 Redis 连接是否正常

        Returns:
            True 正常，False 异常
        """
        try:
            return self.redis.ping()
        except redis.ConnectionError:
            return False

    def close(self) -> None:
        """关闭 Redis 连接"""
        self.redis.close()


# 全局单例
_redis_client: Optional[RedisClient] = None


def init_redis(url: str = "redis://localhost:6379/0") -> RedisClient:
    """
    初始化全局 Redis 客户端（单例模式）

    Args:
        url: Redis 连接 URL

    Returns:
        RedisClient 实例
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient(url)
    return _redis_client


def get_redis() -> RedisClient:
    """
    获取全局 Redis 客户端

    Returns:
        已初始化的 RedisClient 实例

    Raises:
        RuntimeError: 如果尚未初始化
    """
    if _redis_client is None:
        raise RuntimeError("Redis 未初始化，请先调用 init_redis()")
    return _redis_client