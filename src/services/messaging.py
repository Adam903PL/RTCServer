import asyncio
import json
import logging
from .state import rooms, connections

log = logging.getLogger(__name__)

async def send_message(ws, message: dict, timeout: float = 5.0):
    if not ws or ws.closed:
        log.warning("send_message: ws closed, skip")
        return
    try:
        json.dumps(message)  # sanity
        await asyncio.wait_for(ws.send_json(message), timeout=timeout)
    except Exception as e:
        log.error(f"send_message error: {e}")

async def send_error(ws, msg: str):
    await send_message(ws, {"type": "error", "message": msg})

def find_user_in_room(room_id: str, user_id: str):
    room = rooms.get(room_id)
    if not room:
        return None
    for ws in room['streamers'] + room['viewers']:
        info = connections.get(ws, {})
        if info.get('userId') == user_id:
            return ws
    return None

async def push_to_room(room_id: str, obj, *, roles=('streamers','viewers'), ensure_type=False, event_type="room-push", exclude_user_ids=None):
    if room_id not in rooms: return 0
    exclude_user_ids = set(exclude_user_ids or [])
    sockets = []
    if 'streamers' in roles: sockets += rooms[room_id]['streamers']
    if 'viewers' in roles: sockets += rooms[room_id]['viewers']
    msg = {'type': event_type, 'payload': obj} if (ensure_type and not (isinstance(obj, dict) and 'type' in obj)) else obj
    try: json.dumps(msg)
    except TypeError:
        log.error("push_to_room: not json-serializable")
        return 0
    sent = 0
    for w in list(sockets):
        info = connections.get(w, {})
        if info.get('userId') in exclude_user_ids: continue
        await send_message(w, msg)
        sent += 1
    return sent
