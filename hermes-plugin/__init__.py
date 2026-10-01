"""Optional Hermes observer bridge for OmaPets; never exports conversation data."""
import json
import os
import queue
import re
import subprocess
import threading

_TARGET = "io.github.zombie-w33d.omapets"
_SCRIPT = "/usr/share/omarchy/bin/omarchy-shell"
_EVENTS = queue.Queue(maxsize=16)
_WORKER_LOCK = threading.Lock()
_WORKER = None
_HOOKS = (
    "pre_llm_call", "pre_tool_call", "post_tool_call", "post_llm_call",
    "pre_approval_request", "post_approval_response", "api_request_error",
    "on_session_end",
)


def event_for(name, payload):
    """Read only status fields; never classify user/assistant/tool text."""
    mapping = {
        "pre_llm_call": "thinking", "pre_tool_call": "waiting_on_task",
        "post_llm_call": "finished", "pre_approval_request": "waiting_on_you",
        "api_request_error": "failed",
    }
    if name == "post_tool_call":
        return "failed" if payload.get("status") in ("error", "blocked") else None
    if name == "post_approval_response":
        return "failed" if payload.get("choice") in ("deny", "timeout") else "thinking"
    if name == "on_session_end":
        return "waiting_on_task" if payload.get("interrupted") else None
    return mapping.get(name)


def _profile_id():
    # The callback runs in Hermes' profile-bound context. Resolve it *before*
    # passing the two safe string identifiers to the asynchronous IPC worker.
    from hermes_constants import get_hermes_home, profile_name_for_home
    return profile_name_for_home(get_hermes_home())


def _valid_profile(value):
    return isinstance(value, str) and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", value) is not None


def build_hook_callback(name, send, profile_id):
    def callback(**kwargs):
        category = event_for(name, kwargs)
        if category:
            try:
                profile = profile_id()
                if _valid_profile(profile):
                    send(profile, category)
            except Exception:
                # Observer failure must never interrupt the user's agent turn.
                pass
        return None
    return callback


def build_signal_handler(send, profile_id):
    def handler(arguments, **_kwargs):
        if not isinstance(arguments, dict) or set(arguments) != {"category"}:
            return '{"queued": false}'
        if arguments["category"] not in ("yes", "no", "success"):
            return '{"queued": false}'
        try:
            profile = profile_id()
            if not _valid_profile(profile):
                return '{"queued": false}'
            return json.dumps({"queued": send(profile, arguments["category"]) is not False})
        except Exception:
            return '{"queued": false}'
    return handler


def _worker():
    while True:
        profile, category = _EVENTS.get()
        environment = {
            "HOME": os.path.expanduser("~"), "PATH": "/usr/bin:/bin",
            "OMARCHY_PATH": os.environ.get("OMARCHY_PATH", "/usr/share/omarchy"),
            "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""),
            "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", ""),
        }
        try:
            subprocess.run([_SCRIPT, "-q", _TARGET, "event", profile, category],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=4, env=environment,
                           check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
        finally:
            _EVENTS.task_done()


def _send(profile, category):
    global _WORKER
    if not _valid_profile(profile):
        return False
    try:
        _EVENTS.put_nowait((profile, category))
    except queue.Full:
        return False
    with _WORKER_LOCK:
        if _WORKER is None or not _WORKER.is_alive():
            _WORKER = threading.Thread(target=_worker, name="omapets-ipc", daemon=True)
            _WORKER.start()
    return True


def register(ctx):
    for name in _HOOKS:
        ctx.register_hook(name, build_hook_callback(name, _send, _profile_id))
    ctx.register_tool(
        name="omapets_signal", toolset="omapets",
        schema={
            "name": "omapets_signal",
            "description": "Explicitly show an OmaPets yes, no, or success reaction. Do not infer a category from text. Success means something worked, not that the turn ended.",
            "parameters": {
                "type": "object", "properties": {
                    "category": {"type": "string", "enum": ["yes", "no", "success"]},
                }, "required": ["category"], "additionalProperties": False,
            },
        },
        handler=build_signal_handler(_send, _profile_id),
    )
