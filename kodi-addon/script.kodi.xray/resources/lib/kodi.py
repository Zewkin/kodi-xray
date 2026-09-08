import json
import re

import xbmc
import xbmcgui


def json_rpc(method, params=None):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    try:
        result = json.loads(xbmc.executeJSONRPC(json.dumps(payload)))
        return result.get("result", {})
    except (TypeError, ValueError):
        return {}


def active_video_player_id():
    for player in json_rpc("Player.GetActivePlayers"):
        if player.get("type") == "video":
            return player.get("playerid")
    return None


def current_media():
    player_id = active_video_player_id()
    if player_id is None:
        return None
    properties = ["file", "title", "year", "showtitle", "season", "episode", "uniqueid", "cast", "art"]
    item = json_rpc("Player.GetItem", {"playerid": player_id, "properties": properties}).get("item", {})
    file_path = item.get("file") or xbmc.Player().getPlayingFile()
    if not file_path:
        return None
    item_type = item.get("type")
    media_type = "episode" if item_type == "episode" else "movie" if item_type == "movie" else "video"
    cast = []
    for member in item.get("cast", [])[:50]:
        images = [member.get("thumbnail")] if member.get("thumbnail") else []
        cast.append(
            {
                "name": member.get("name") or member.get("label") or "Unknown",
                "roles": [member.get("role")] if member.get("role") else [],
                "image_urls": images,
            }
        )
    season = item.get("season")
    episode = item.get("episode")
    return {
        "file": file_path,
        "media_type": media_type,
        "title": item.get("title") or item.get("label"),
        "year": item.get("year") or None,
        "show": item.get("showtitle") or None,
        "season": season if isinstance(season, int) and season >= 0 else None,
        "episode": episode if isinstance(episode, int) and episode >= 0 else None,
        "unique_ids": item.get("uniqueid") or {},
        "cast": cast,
    }


def playback_position():
    try:
        return max(0.0, float(xbmc.Player().getTime()))
    except RuntimeError:
        return 0.0


def view_mode():
    if active_video_player_id() is None:
        return {}
    result = json_rpc("Player.GetViewMode")
    return result if isinstance(result, dict) else {}


def platform_name():
    for condition, name in (
        ("System.Platform.Android", "android"),
        ("System.Platform.Linux", "linux"),
        ("System.Platform.Windows", "windows"),
        ("System.Platform.OSX", "macos"),
    ):
        if xbmc.getCondVisibility(condition):
            return name
    return "unknown"


def kodi_version():
    value = xbmc.getInfoLabel("System.BuildVersion")
    match = re.match(r"([0-9]+(?:\.[0-9]+)*)", value or "")
    return match.group(1) if match else value


def gui_size():
    try:
        fullscreen = xbmcgui.Window(12005)
        width, height = int(fullscreen.getWidth()), int(fullscreen.getHeight())
        if width > 0 and height > 0:
            return width, height
    except (AttributeError, RuntimeError, TypeError):
        pass
    try:
        return int(xbmcgui.getScreenWidth()), int(xbmcgui.getScreenHeight())
    except (AttributeError, TypeError):
        return 1920, 1080
