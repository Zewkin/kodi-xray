import json
import urllib.error
import urllib.parse
import urllib.request


class ApiError(RuntimeError):
    pass


class XRayApi:
    def __init__(self, base_url, token, timeout=5.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def post(self, path, payload):
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
                "User-Agent": "Kodi-XRay/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("detail", "request failed")
            except Exception:
                detail = "request failed"
            raise ApiError("backend returned {}: {}".format(exc.code, detail))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise ApiError("backend unavailable: {}".format(exc))

    def download_portrait(self, actor_id, target):
        path = "/api/v1/people/{}/portrait".format(urllib.parse.quote(actor_id, safe=""))
        request = urllib.request.Request(
            self.base_url + path,
            headers={"Authorization": "Bearer " + self.token, "User-Agent": "Kodi-XRay/0.1"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                data = response.read(3 * 1024 * 1024 + 1)
            if not content_type.startswith("image/") or len(data) > 3 * 1024 * 1024:
                raise ApiError("portrait response is invalid")
            with open(target, "wb") as handle:
                handle.write(data)
        except urllib.error.HTTPError as exc:
            raise ApiError("portrait unavailable: {}".format(exc.code))
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            raise ApiError("portrait unavailable: {}".format(exc))
