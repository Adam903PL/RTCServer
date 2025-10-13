import logging
from aiohttp import web
from ..services.state import rooms, connections, stream_metadata
from ..config import INDEX_PATH, VIEWER_PATH

logger = logging.getLogger(__name__)

async def index(request: web.Request):
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/html")
    except FileNotFoundError:
        return web.Response(text="index.html not found", status=404)

async def viewer_page(request: web.Request):
    try:
        with open(VIEWER_PATH, "r", encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/html")
    except FileNotFoundError:
        return web.Response(text="viewer.html not found", status=404)

async def health_check(request: web.Request):
    total_streamers = sum(len(r['streamers']) for r in rooms.values())
    total_viewers = sum(len(r['viewers']) for r in rooms.values())
    logger.info(f"💚 Health: rooms={len(rooms)} connections={len(connections)}")
    return web.json_response({
        "status": "ok",
        "rooms": len(rooms),
        "total_connections": len(connections),
        "streamers": total_streamers,
        "viewers": total_viewers,
        "active_streams": len(stream_metadata)
    })

async def get_rooms(request: web.Request):
    rooms_list = [{
        "roomId": room_id,
        "streamers": len(rd['streamers']),
        "viewers": len(rd['viewers']),
        "has_active_stream": room_id in stream_metadata
    } for room_id, rd in rooms.items()]
    return web.json_response({"rooms": rooms_list})

async def debug_info(request: web.Request):
    debug_data = {
        "rooms": {
            rid: {
                "streamers": [connections.get(s, {}).get("userId", "unknown") for s in data["streamers"]],
                "viewers": [connections.get(v, {}).get("userId", "unknown") for v in data["viewers"]],
            }
            for rid, data in rooms.items()
        },
        "connections": {
            info["userId"]: {
                "role": info["role"],
                "roomId": info["roomId"],
                "joined_at": info["joined_at"],
                "ws_closed": ws.closed,
            }
            for ws, info in connections.items()
        },
        "stream_metadata": stream_metadata,
    }
    return web.json_response(debug_data)
