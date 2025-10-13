from aiohttp import web
import aiohttp_cors
from .routes import setup_routes
from .logging_conf import setup_logging

def create_app() -> web.Application:
    setup_logging()
    app = web.Application()

    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True, expose_headers="*",
            allow_headers="*", allow_methods="*"
        )
    })

    setup_routes(app)

    # podłącz CORS do każdej trasy
    for route in list(app.router.routes()):
        try:
            cors.add(route)
        except Exception:
            pass
    return app
