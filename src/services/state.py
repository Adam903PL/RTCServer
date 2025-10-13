from datetime import datetime
from typing import Dict, Any

# roomId -> {streamers: [ws], viewers: [ws]}
rooms: Dict[str, Dict[str, list]] = {}

# ws -> {roomId, userId, role, joined_at}
connections: Dict[Any, Dict[str, str]] = {}

# roomId -> {streamer_id, resolution, fps, started_at}
stream_metadata: Dict[str, Dict[str, str]] = {}

def now_iso() -> str:
    return datetime.now().isoformat()
