import json
import os

import xbmc
import xbmcaddon
import xbmcvfs

from .adapters import GenericAdapter, PellucidAdapter


def _merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_adapter():
    addon = xbmcaddon.Addon()
    addon_path = xbmcvfs.translatePath(addon.getAddonInfo("path"))
    requested = addon.getSetting("theme") or "auto"
    current_skin = xbmc.getSkinDir()
    pellucid_skins = {"skin.pellucid", "skin.pellucidRemix"}
    pellucid = requested == "pellucid" or (requested == "auto" and current_skin in pellucid_skins)
    name = "pellucid" if pellucid else "generic"
    with open(os.path.join(addon_path, "resources", "themes", name + ".json"), "r", encoding="utf-8") as handle:
        theme = json.load(handle)
    override_path = xbmcvfs.translatePath("special://profile/addon_data/script.kodi.xray/theme-overrides.json")
    if os.path.isfile(override_path):
        try:
            with open(override_path, "r", encoding="utf-8") as handle:
                theme = _merge(theme, json.load(handle))
        except (OSError, ValueError):
            xbmc.log("Kodi X-Ray: invalid theme override ignored", xbmc.LOGWARNING)
    return PellucidAdapter(theme) if pellucid else GenericAdapter(theme)
