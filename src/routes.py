from aiohttp import web
from .http.views import index, viewer_page, health_check, get_rooms, debug_info
from .ws.handlers import websocket_handler

def setup_routes(app: web.Application):
    app.router.add_get("/", index)
    app.router.add_get("/viewer", viewer_page)
    app.router.add_get("/health", health_check)
    app.router.add_get("/rooms", get_rooms)
    app.router.add_get("/debug", debug_info)
    app.router.add_get("/ws", websocket_handler)
