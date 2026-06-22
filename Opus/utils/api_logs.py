import io
import os
from datetime import datetime

_logs = []
_LOG_FILE = "logs/api.txt"

def log_api(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    _logs.append(formatted)
    
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass
        
    # Keep up to 1000 logs in memory
    if len(_logs) > 1000:
        _logs.pop(0)

def get_logs() -> str:
    if not _logs:
        return "No API logs captured yet."
    return "\n".join(_logs)

def get_logs_file() -> io.BytesIO:
    content = get_logs()
    bio = io.BytesIO(content.encode("utf-8"))
    bio.name = "logs.txt"
    return bio
