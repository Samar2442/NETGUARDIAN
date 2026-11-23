from starlette.types import ASGIApp, Receive, Scope, Send
import logging
from app.core.config import settings

logger = logging.getLogger("netguardian.security")

class SecurityHeadersMiddleware:
    """
    Lightweight ASGI middleware enforcing HTTP security headers:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Referrer-Policy: strict-origin-when-cross-origin
    - Content-Security-Policy: separate strict policies for DEV and PROD
    - Strict-Transport-Security (HSTS): strictly conditional on verified HTTPS in PROD
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_https = False
        scheme = scope.get("scheme", "http")
        if scheme == "https":
            is_https = True
        else:
            # Check forwarded proto ONLY if request arrives from an explicitly trusted proxy
            client = scope.get("client")
            client_ip = client[0] if client else None
            if client_ip and client_ip in settings.TRUSTED_PROXIES:
                headers_list = scope.get("headers", [])
                for name, value in headers_list:
                    if name.lower() == b"x-forwarded-proto" and value.lower() == b"https":
                        is_https = True
                        break

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                raw_headers = message.setdefault("headers", [])
                existing_names = {k.lower() for k, _ in raw_headers}

                def set_header(name: str, value: str):
                    name_bytes = name.encode("latin-1")
                    val_bytes = value.encode("latin-1")
                    if name_bytes.lower() not in existing_names:
                        raw_headers.append((name_bytes, val_bytes))
                        existing_names.add(name_bytes.lower())

                set_header("X-Content-Type-Options", "nosniff")
                set_header("X-Frame-Options", "DENY")
                set_header("Referrer-Policy", "strict-origin-when-cross-origin")

                # Build Content-Security-Policy
                allowed_origins_str = " ".join(
                    [o for o in settings.BACKEND_CORS_ORIGINS if o != "*"]
                )
                connect_src = f"'self' ws: wss: {allowed_origins_str}".strip()

                if settings.ENVIRONMENT == "PROD":
                    csp = (
                        "default-src 'self'; "
                        "script-src 'self'; "
                        "style-src 'self' 'unsafe-inline'; "
                        "img-src 'self' data:; "
                        "font-src 'self' data:; "
                        f"connect-src {connect_src}; "
                        "object-src 'none'; "
                        "base-uri 'self'; "
                        "frame-ancestors 'none'"
                    )
                else:
                    # In development, Vite HMR requires inline scripts and eval
                    csp = (
                        "default-src 'self'; "
                        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                        "style-src 'self' 'unsafe-inline'; "
                        "img-src 'self' data:; "
                        "font-src 'self' data:; "
                        f"connect-src {connect_src}; "
                        "object-src 'none'; "
                        "base-uri 'self'; "
                        "frame-ancestors 'none'"
                    )
                set_header("Content-Security-Policy", csp)

                # Strict-Transport-Security: Strictly PROD + Verified HTTPS
                if settings.ENVIRONMENT == "PROD" and is_https:
                    set_header("Strict-Transport-Security", "max-age=31536000")

            await send(message)

        await self.app(scope, receive, send_wrapper)
