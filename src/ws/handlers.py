import json
import logging
from aiohttp import web
from ..services.messaging import send_error
from . import events  # Twoje funkcje handle_*

logger = logging.getLogger(__name__)

async def websocket_handler(request: web.Request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    client_ip = request.remote
    logger.info(f"🔌 Nowe WS z: {client_ip}")
    logger.info(f"📊 Headers: {dict(request.headers)}")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await handle_message(ws, data)
                except json.JSONDecodeError:
                    await send_error(ws, "Invalid JSON format")
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"❌ WS error: {ws.exception()}")
            elif msg.type == web.WSMsgType.CLOSE:
                logger.info("👋 WS zamknięty przez klienta")
    except Exception as e:
        logger.error(f"❌ Wyjątek w WS handler: {e}", exc_info=True)
    finally:
        await events.cleanup_connection(ws)
    return ws

async def handle_message(ws, data: dict):
    msg_type = data.get("type")
    logger.info(f"🎯 msg type: {msg_type}")

    handlers = {
        "join": events.handle_join,
        "start-stream": events.handle_start_stream,
        "stop-stream": events.handle_stop_stream,
        "offer": events.handle_offer,
        "answer": events.handle_answer,
        "ice-candidate": events.handle_ice_candidate,
        "leave": events.handle_leave,
        "get-active-streams": events.handle_get_active_streams
        
    }

    handler = handlers.get(msg_type)
    if not handler:
        logger.warning(f"⚠️ Unknown message type: {msg_type}")
        await send_error(ws, f"Unknown message type: {msg_type}")
        return

    try:
        await handler(ws, data)
    except Exception as e:
        logger.error(f"❌ Błąd w handlerze {msg_type}: {e}", exc_info=True)
        await send_error(ws, f"Error handling {msg_type}: {str(e)}")


