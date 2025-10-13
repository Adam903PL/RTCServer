import json
import logging
from .state import rooms, connections
from .messaging import send_message

logger = logging.getLogger(__name__)

async def push_to_room(room_id: str, obj, *,
                       ensure_type: bool = False,
                       event_type: str = "room-push",
                       roles=('streamers', 'viewers'),
                       exclude_user_ids=None) -> int:
    if room_id not in rooms:
        logger.warning(f"push_to_room: brak pokoju: {room_id}")
        return 0

    exclude_user_ids = set(exclude_user_ids or [])
    sockets = []
    if 'streamers' in roles:
        sockets += rooms[room_id]['streamers']
    if 'viewers' in roles:
        sockets += rooms[room_id]['viewers']

    message = {'type': event_type, 'payload': obj} if (
        ensure_type and not (isinstance(obj, dict) and 'type' in obj)
    ) else obj

    try:
        json.dumps(message)
    except TypeError:
        logger.error("push_to_room: obiekt nie jest JSON-serializowalny")
        return 0

    sent = 0
    for ws in list(sockets):
        info = connections.get(ws, {})
        if info.get('userId') in exclude_user_ids:
            continue
        try:
            await send_message(ws, message)
            sent += 1
        except Exception as e:
            logger.error(f"push_to_room: błąd wysyłki do {info.get('userId')}: {e}")
    return sent
