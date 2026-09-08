import hashlib
import os
import queue
import threading
import time
import uuid

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from .api import ApiError, XRayApi
from .kodi import active_video_player_id, current_media, kodi_version, platform_name, playback_position
from .overlay import create_overlay
from .theme import load_adapter


HOME = xbmcgui.Window(10000)


class Controller:
    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.client_id = self._client_id()
        self.generation = 0
        self.due_at = None
        self.results = queue.Queue()
        self.overlay = None
        self._set_state("idle", active=False, count=0)

    def _client_id(self):
        label = xbmc.getInfoLabel("System.FriendlyName") or platform_name()
        return "{}-{}".format(label.replace(" ", "-").lower(), uuid.getnode())[:128]

    def settings(self):
        api_token = self.addon.getSetting("api_token")
        if api_token == "__not_configured__":
            api_token = ""
        return {
            "backend_url": self.addon.getSetting("backend_url").rstrip("/"),
            "api_token": api_token,
            "timeout": float(self.addon.getSetting("timeout") or 5),
            "display_mode": self.addon.getSetting("display_mode") or "auto",
            "show_actor": self._bool_setting("show_actor", True),
            "show_character": self._bool_setting("show_character", True),
            "show_portrait": self._bool_setting("show_portrait", False),
            "show_unknown": self._bool_setting("show_unknown", False),
            "debug": self._bool_setting("debug_overlay", False),
        }

    def _bool_setting(self, setting_id, default):
        value = self.addon.getSetting(setting_id)
        if not value:
            return default
        return value.strip().lower() in ("true", "1", "yes", "on")

    def session_start(self):
        media = current_media()
        if not media:
            return
        payload = {
            "client_id": self.client_id,
            "kodi_version": kodi_version(),
            "platform": platform_name(),
            "media": media,
        }
        self._spawn("session", self.generation, "/api/v1/session/start", payload)

    def pause(self, manual=False):
        self.close_overlay()
        if not manual and not self._bool_setting("auto_pause", True):
            return
        self.generation += 1
        debounce = 0 if manual else int(self.addon.getSetting("pause_debounce_ms") or 350)
        self.due_at = time.monotonic() + debounce / 1000.0
        self._set_state("waiting", active=False, count=0)

    def resume(self):
        self.generation += 1
        self.due_at = None
        self.close_overlay()
        self._set_state("idle", active=False, count=0)

    def seek(self):
        self.resume()
        if xbmc.getCondVisibility("Player.Paused"):
            self.pause()

    def stop(self):
        self.resume()

    def tick(self):
        if HOME.getProperty("XRay.Manual") == "true":
            HOME.clearProperty("XRay.Manual")
            self.pause(manual=True)
        if self.overlay and not xbmc.getCondVisibility(load_adapter().visibility_condition()):
            self.close_overlay()
        if self.due_at is not None and time.monotonic() >= self.due_at:
            self.due_at = None
            self._request_scene()
        while True:
            try:
                kind, generation, result, error = self.results.get_nowait()
            except queue.Empty:
                break
            if kind == "session":
                if not error:
                    HOME.setProperty("XRay.Ready", "true")
                continue
            if generation != self.generation or not xbmc.getCondVisibility("Player.Paused"):
                continue
            if error:
                self._set_state("unavailable", active=False, count=0)
                xbmcgui.Dialog().notification("X-RAY", "Unavailable", xbmcgui.NOTIFICATION_WARNING, 1800, False)
                continue
            self._show(result)

    def _request_scene(self):
        media = current_media()
        if not media:
            return
        payload = {
            "client_id": self.client_id,
            "media": media,
            "playback": {"position": playback_position()},
        }
        self._set_state("analyzing", active=False, count=0)
        self._spawn("xray", self.generation, "/api/v1/xray", payload)

    def _spawn(self, kind, generation, path, payload):
        settings = self.settings()

        def work():
            try:
                if not settings["api_token"]:
                    raise ApiError("API token is not configured")
                api = XRayApi(settings["backend_url"], settings["api_token"], settings["timeout"])
                result = api.post(path, payload)
                if kind == "xray" and settings["show_portrait"]:
                    self._add_portraits(api, result)
                self.results.put((kind, generation, result, None))
            except Exception as exc:
                self.results.put((kind, generation, None, str(exc)))

        threading.Thread(target=work, name="kodi-xray-{}".format(kind), daemon=True).start()

    @staticmethod
    def _add_portraits(api, result):
        portrait_dir = xbmcvfs.translatePath("special://profile/addon_data/script.kodi.xray/portraits")
        os.makedirs(portrait_dir, exist_ok=True)
        for person in result.get("people", []):
            actor_id = person.get("actor", {}).get("id")
            if not actor_id:
                continue
            name = hashlib.sha256(actor_id.encode("utf-8")).hexdigest() + ".jpg"
            target = os.path.join(portrait_dir, name)
            try:
                if not os.path.isfile(target):
                    api.download_portrait(actor_id, target)
                person["portrait"] = target
            except ApiError:
                continue

    def _show(self, result):
        self.close_overlay()
        people = result.get("people", [])
        if not people and not self.settings()["show_unknown"]:
            self._set_state("ready", active=False, count=0)
            return
        self.overlay = create_overlay(result, load_adapter(), self.settings())
        self.overlay.show()
        self._set_state("ready", active=True, count=len(people))
        HOME.setProperty("XRay.MediaKey", result.get("media_key", ""))

    def close_overlay(self):
        if self.overlay:
            try:
                self.overlay.close()
            except RuntimeError:
                pass
            self.overlay = None

    @staticmethod
    def _set_state(state, active, count):
        HOME.setProperty("XRay.State", state)
        HOME.setProperty("XRay.Active", "true" if active else "false")
        HOME.setProperty("XRay.Count", str(count))
        if not active:
            HOME.clearProperty("XRay.MediaKey")


class XRayPlayer(xbmc.Player):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

    def onAVStarted(self):
        self.controller.session_start()

    def onPlayBackPaused(self):
        self.controller.pause()

    def onPlayBackResumed(self):
        self.controller.resume()

    def onPlayBackSeek(self, _time, _seek_offset):
        self.controller.seek()

    def onPlayBackStopped(self):
        self.controller.stop()

    def onPlayBackEnded(self):
        self.controller.stop()


def run_service():
    monitor = xbmc.Monitor()
    controller = Controller()
    player = XRayPlayer(controller)
    HOME.setProperty("XRay.Service", "true")
    try:
        if active_video_player_id() is not None:
            controller.session_start()
            if xbmc.getCondVisibility("Player.Paused"):
                controller.pause()
        while not monitor.abortRequested():
            controller.tick()
            if monitor.waitForAbort(0.1):
                break
    finally:
        controller.close_overlay()
        HOME.clearProperty("XRay.Service")
        HOME.setProperty("XRay.Active", "false")
        HOME.setProperty("XRay.Count", "0")


def run_manual():
    if HOME.getProperty("XRay.Service") == "true":
        HOME.setProperty("XRay.Manual", "true")
        return
    controller = Controller()
    controller.pause(manual=True)
    monitor = xbmc.Monitor()
    deadline = time.monotonic() + controller.settings()["timeout"] + 2
    while time.monotonic() < deadline and not monitor.abortRequested():
        controller.tick()
        if controller.overlay:
            while xbmc.getCondVisibility("Player.Paused") and not monitor.waitForAbort(0.1):
                controller.tick()
            break
        monitor.waitForAbort(0.1)
    controller.close_overlay()
