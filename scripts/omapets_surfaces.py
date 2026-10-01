"""Sanitized local top edges of visible Hyprland windows and the Omarchy bar."""
import json
import math
import subprocess


def _rect(x, y, width, monitor):
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y, width)):
        return None
    scale = monitor.get("scale", 1)
    if not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        return None
    left = max(0, round(x - monitor["x"]))
    right = min(round(monitor["width"] / scale), round(x + width - monitor["x"]))
    top = round(y - monitor["y"])
    if right - left < 8 or top < 0 or top >= round(monitor["height"] / scale):
        return None
    return {"x": left, "y": top, "width": right - left}


def surfaces_by_monitor(monitors, clients, layers):
    """Do not expose window titles, process names or addresses to the shell."""
    result = {}
    if not isinstance(monitors, list) or not isinstance(clients, list) or not isinstance(layers, dict):
        return result
    for monitor in monitors[:8]:
        try:
            name = monitor["name"]
            ident = monitor["id"]
            workspace = monitor["activeWorkspace"]["id"]
            special = monitor.get("specialWorkspace", {}).get("id", 0)
            if not isinstance(name, str):
                continue
            edges = []
            for client in clients[:256]:
                if client.get("monitor") != ident or client.get("mapped") is not True or client.get("hidden") is True:
                    continue
                client_workspace = client.get("workspace", {}).get("id")
                if client_workspace != workspace and (not special or client_workspace != special):
                    continue
                rect = _rect(client["at"][0], client["at"][1], client["size"][0], monitor)
                if rect and rect not in edges:
                    edges.append(rect)
            levels = layers.get(name, {}).get("levels", {})
            for group in levels.values():
                for layer in group:
                    if layer.get("namespace") == "omarchy-bar":
                        rect = _rect(layer["x"], layer["y"] + layer["h"], layer["w"], monitor)
                        if rect and rect not in edges:
                            edges.append(rect)
            result[name] = edges[:64]
        except (KeyError, IndexError, TypeError, ValueError, OverflowError):
            continue
    return result


def live_surfaces():
    def query(command):
        completed = subprocess.run(["hyprctl", "-j", command], capture_output=True,
                                   text=True, timeout=1.5, check=True)
        if len(completed.stdout) > 524288:
            raise ValueError("desktop geometry too large")
        return json.loads(completed.stdout)
    return surfaces_by_monitor(query("monitors"), query("clients"), query("layers"))
