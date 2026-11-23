from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.responses import Response
from typing import Callable
from app.core.config import settings

class SecurityHeadersMiddleware:
    """Add common security headers to every response.
    HSTS is added only when the request is HTTPS and the environment is PROD.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                headers = message.setdefault('headers', [])
                # Helper to add header bytes
                def add(name: str, value: str):
                    headers.append((name.encode('latin-1'), value.encode('latin-1')))

                add('X-Content-Type-Options', 'nosniff')
                add('X-Frame-Options', 'DENY')
                add('Referrer-Policy', 'strict-origin-when-cross-origin')
                # Basic CSP – allow self and development API origins
                csp = (
                    "default-src 'self'; "
                    "script-src 'self'; "
                    "style-src 'self'; "
                    "connect-src 'self' "
                    + ' '.join(settings.BACKEND_CORS_ORIGINS)
                )
                add('Content-Security-Policy', csp)
                # HSTS only for HTTPS in production
                if settings.ENVIRONMENT == 'PROD' and scope.get('scheme') == 'https':
                    add('Strict-Transport-Security', 'max-age=31536000')
            await send(message)
        await self.app(scope, receive, send_wrapper)
