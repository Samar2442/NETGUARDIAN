import time
import math
import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple
from fastapi import Request
from app.core.config import settings

logger = logging.getLogger("netguardian.ratelimit")

class BaseRateLimiter(ABC):
    @abstractmethod
    def is_blocked(self, key: str) -> Tuple[bool, int]:
        """Return (is_blocked, retry_after_seconds)."""
        pass

    @abstractmethod
    def record_failure(self, key: str) -> Tuple[bool, int]:
        """Record a failed attempt. Return (is_now_blocked, retry_after_seconds)."""
        pass

    @abstractmethod
    def reset(self, key: str) -> None:
        """Reset failed attempt counters upon successful authentication."""
        pass

class MemoryRateLimiter(BaseRateLimiter):
    """
    In-memory, thread-safe rate limiter implementing sliding-window failure tracking
    and temporary cooldown periods.

    NOTE: Single-process in-memory implementation. In multi-worker or distributed
    cluster deployments, configure LOGIN_RATE_LIMIT_BACKEND="redis".
    """

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 60,
        cooldown_seconds: int = 300
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._attempts: Dict[str, List[float]] = {}
        self._cooldowns: Dict[str, float] = {}

    def _cleanup_old_attempts(self, key: str, now: float):
        if key in self._attempts:
            cutoff = now - self.window_seconds
            self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]
            if not self._attempts[key]:
                del self._attempts[key]

    def is_blocked(self, key: str) -> Tuple[bool, int]:
        now = time.time()
        with self._lock:
            # Check cooldown
            if key in self._cooldowns:
                cooldown_until = self._cooldowns[key]
                if now < cooldown_until:
                    retry_after = int(math.ceil(cooldown_until - now))
                    return True, max(1, retry_after)
                else:
                    del self._cooldowns[key]

            self._cleanup_old_attempts(key, now)
            attempts = self._attempts.get(key, [])
            if len(attempts) >= self.max_attempts:
                # Trigger new cooldown
                self._cooldowns[key] = now + self.cooldown_seconds
                return True, self.cooldown_seconds

            return False, 0

    def record_failure(self, key: str) -> Tuple[bool, int]:
        now = time.time()
        with self._lock:
            self._cleanup_old_attempts(key, now)
            if key not in self._attempts:
                self._attempts[key] = []
            self._attempts[key].append(now)

            if len(self._attempts[key]) >= self.max_attempts:
                self._cooldowns[key] = now + self.cooldown_seconds
                logger.warning(
                    f"Rate limit triggered for key='{key}'. "
                    f"Attempts: {len(self._attempts[key])}. Cooldown: {self.cooldown_seconds}s."
                )
                return True, self.cooldown_seconds

            return False, 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)
            self._cooldowns.pop(key, None)

    def clear_all(self) -> None:
        """Reset all rate limiter state (used in testing and maintenance)."""
        with self._lock:
            self._attempts.clear()
            self._cooldowns.clear()

# Global rate limiter instance
login_rate_limiter = MemoryRateLimiter(
    max_attempts=settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
    window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    cooldown_seconds=settings.LOGIN_RATE_LIMIT_COOLDOWN_SECONDS,
)

def get_client_ip(request: Request) -> str:
    """
    Resolve client IP address securely.
    Only honors X-Forwarded-For if client directly connects from an IP
    explicitly listed in settings.TRUSTED_PROXIES.
    Otherwise, returns direct socket client IP to prevent IP spoofing attacks.
    """
    direct_ip = request.client.host if request.client else "127.0.0.1"
    if direct_ip in settings.TRUSTED_PROXIES:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Format: client, proxy1, proxy2
            ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
            if ips:
                return ips[0]
    return direct_ip

def normalize_username(username: str) -> str:
    """Case-insensitive normalized username identifier for rate limiting."""
    return username.strip().lower()
