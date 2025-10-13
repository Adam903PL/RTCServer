# src/ws/events.py
import logging
from ..services.state import rooms, connections, stream_metadata, now_iso
from ..services.messaging import send_message, send_error, find_user_in_room

logger = logging.getLogger(__name__)

# --- JOIN / LEAVE / CLEANUP --------------------------------------------------

async def handle_join(ws, data):
    room_id = data.get("roomId")
    user_id = data.get("userId")
    role = data.get("role", "viewer")

    logger.info(f"👤 join: user={user_id}, room={room_id}, role={role}")

    if not room_id or not user_id:
        await send_error(ws, "Missing roomId or userId")
        return
    if role not in ("streamer", "viewer"):
        await send_error(ws, "Invalid role. Must be 'streamer' or 'viewer'")
        return

    # zapisz połączenie
    connections[ws] = {
        "roomId": room_id,
        "userId": user_id,
        "role": role,
        "joined_at": now_iso(),
    }

    # utwórz pokój jeśli trzeba
    if room_id not in rooms:
        rooms[room_id] = {"streamers": [], "viewers": []}
        logger.info(f"🆕 utworzono room: {room_id}")

    if role == "streamer":
        rooms[room_id]["streamers"].append(ws)
        logger.info(f"🎥 streamer {user_id} dołączył do {room_id}")

        # powiadom viewerów o nowym streamerze
        for viewer_ws in rooms[room_id]["viewers"]:
            await send_message(viewer_ws, {
                "type": "streamer-joined",
                "streamerId": user_id,
                "roomId": room_id
            })
    else:
        rooms[room_id]["viewers"].append(ws)
        logger.info(f"👁️ viewer {user_id} dołączył do {room_id}")

        # powiadom streamerów o nowym viewerze
        for streamer_ws in rooms[room_id]["streamers"]:
            await send_message(streamer_ws, {
                "type": "user-joined",
                "userId": user_id,
                "role": "viewer",
                "roomId": room_id
            })

        # wyślij listę aktywnych streamerów do tego viewera
        active_streamers = [
            connections[s]["userId"]
            for s in rooms[room_id]["streamers"]
            if s in connections
        ]
        await send_message(ws, {
            "type": "active-streamers",
            "streamers": active_streamers,
            "roomId": room_id
        })

    # potwierdzenie joined
    await send_message(ws, {
        "type": "joined",
        "roomId": room_id,
        "userId": user_id,
        "role": role,
        "streamers_count": len(rooms[room_id]["streamers"]),
        "viewers_count": len(rooms[room_id]["viewers"]),
        "existing_viewers": [
            connections[v]["userId"]
            for v in rooms[room_id]["viewers"]
            if v in connections
        ] if role == "streamer" else []
    })


async def handle_leave(ws, data):
    await cleanup_connection(ws)


async def cleanup_connection(ws):
    if ws not in connections:
        return

    info = connections[ws]
    room_id = info["roomId"]
    user_id = info["userId"]
    role = info["role"]

    logger.info(f"🧹 cleanup: user={user_id}, role={role}, room={room_id}")

    if room_id in rooms:
        if role == "streamer":
            if ws in rooms[room_id]["streamers"]:
                rooms[room_id]["streamers"].remove(ws)

            # powiadom viewerów że streamer wyszedł
            for viewer_ws in rooms[room_id]["viewers"][:]:
                try:
                    await send_message(viewer_ws, {
                        "type": "streamer-left",
                        "streamerId": user_id,
                        "roomId": room_id
                    })
                except Exception:
                    pass

            # usuń metadane streamu
            stream_metadata.pop(room_id, None)
            logger.info(f"🎥❌ streamer {user_id} opuścił {room_id}")
        else:
            if ws in rooms[room_id]["viewers"]:
                rooms[room_id]["viewers"].remove(ws)

            # powiadom streamerów że viewer wyszedł
            for streamer_ws in rooms[room_id]["streamers"][:]:
                try:
                    await send_message(streamer_ws, {
                        "type": "viewer-left",
                        "userId": user_id,
                        "roomId": room_id
                    })
                except Exception:
                    pass
            logger.info(f"👁️❌ viewer {user_id} opuścił {room_id}")

        # usuń pusty pokój
        if not rooms[room_id]["streamers"] and not rooms[room_id]["viewers"]:
            rooms.pop(room_id, None)
            logger.info(f"🗑️ room {room_id} usunięty (pusty)")

    # usuń z connections na końcu
    connections.pop(ws, None)
    logger.info(f"✅ cleanup done for {user_id}")

# --- STREAM START/STOP -------------------------------------------------------

async def handle_start_stream(ws, data):
    sender_info = connections.get(ws)
    if not sender_info:
        await send_error(ws, "Not connected")
        return
    if sender_info["role"] != "streamer":
        await send_error(ws, "Only streamers can start streaming")
        return

    room_id = sender_info["roomId"]
    user_id = sender_info["userId"]

    stream_metadata[room_id] = {
        "streamer_id": user_id,
        "started_at": now_iso(),
        "resolution": data.get("resolution", "unknown"),
        "fps": data.get("fps", "unknown"),
    }

    logger.info(f"🔴 stream start: {user_id} in {room_id} meta={stream_metadata[room_id]}")

    # powiadom viewerów
    for viewer_ws in rooms.get(room_id, {}).get("viewers", []):
        await send_message(viewer_ws, {
            "type": "stream-started",
            "streamerId": user_id,
            "roomId": room_id,
            "metadata": stream_metadata[room_id]
        })

    await send_message(ws, {"type": "stream-started-ack", "status": "success"})


async def handle_stop_stream(ws, data):
    sender_info = connections.get(ws)
    if not sender_info:
        return
    room_id = sender_info["roomId"]
    user_id = sender_info["userId"]

    stream_metadata.pop(room_id, None)
    logger.info(f"⏹️ stream stop: {user_id} in {room_id}")

    for viewer_ws in rooms.get(room_id, {}).get("viewers", []):
        await send_message(viewer_ws, {
            "type": "stream-stopped",
            "streamerId": user_id,
            "roomId": room_id
        })

    await send_message(ws, {"type": "stream-stopped-ack", "status": "success"})

# --- WEBRTC SYGNALIZACJA ----------------------------------------------------

async def handle_offer(ws, data):
    target_id = data.get("targetId")
    offer = data.get("offer")
    if not target_id or not offer:
        await send_error(ws, "Missing targetId or offer")
        return

    sender_info = connections.get(ws)
    if not sender_info:
        await send_error(ws, "Not connected")
        return

    room_id = sender_info["roomId"]
    sender_id = sender_info["userId"]

    logger.info(f"📤 OFFER {sender_id}->{target_id} room={room_id}")

    target_ws = find_user_in_room(room_id, target_id)
    if not target_ws:
        await send_error(ws, f"Target user {target_id} not found")
        return

    await send_message(target_ws, {
        "type": "offer",
        "offer": offer,
        "senderId": sender_id
    })
    logger.info("✅ offer sent")


async def handle_answer(ws, data):
    target_id = data.get("targetId")
    answer = data.get("answer")
    if not target_id or not answer:
        await send_error(ws, "Missing targetId or answer")
        return

    sender_info = connections.get(ws)
    if not sender_info:
        await send_error(ws, "Not connected")
        return

    room_id = sender_info["roomId"]
    sender_id = sender_info["userId"]

    target_ws = find_user_in_room(room_id, target_id)
    if not target_ws:
        await send_error(ws, f"Target user {target_id} not found")
        return

    await send_message(target_ws, {
        "type": "answer",
        "answer": answer,
        "senderId": sender_id
    })
    logger.info("📥 answer forwarded")


async def handle_ice_candidate(ws, data):
    target_id = data.get("targetId")
    candidate = data.get("candidate")
    if not target_id or not candidate:
        await send_error(ws, "Missing targetId or candidate")
        return

    sender_info = connections.get(ws)
    if not sender_info:
        await send_error(ws, "Not connected")
        return

    room_id = sender_info["roomId"]
    sender_id = sender_info["userId"]

    target_ws = find_user_in_room(room_id, target_id)
    if not target_ws:
        await send_error(ws, f"Target user {target_id} not found")
        return

    await send_message(target_ws, {
        "type": "ice-candidate",
        "candidate": candidate,
        "senderId": sender_id
    })
    logger.info("🧊 ice forwarded")

# --- LISTA STREAMÓW ----------------------------------------------------------

async def handle_get_active_streams(ws, data):
    active_streams = []
    for rid, rdata in rooms.items():
        for streamer_ws in rdata["streamers"]:
            info = connections.get(streamer_ws)
            if not info:
                continue
            entry = {
                "roomId": rid,
                "streamerId": info["userId"],
                "viewers_count": len(rdata["viewers"]),
            }
            if rid in stream_metadata:
                entry["metadata"] = stream_metadata[rid]
            active_streams.append(entry)

    await send_message(ws, {"type": "active-streams", "streams": active_streams})
