from __future__ import annotations

import logging
import signal
import time

from xray.config import load_settings
from xray.db import Database
from xray.gallery import GalleryBuilder
from xray.metadata import CompositeMetadataProvider
from xray.recognition import OpenCvSFaceBackend


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s operation=gallery-worker %(message)s")
    settings = load_settings()
    database = Database(settings.database.path)
    database.initialize()
    recognizer = OpenCvSFaceBackend(settings)
    builder = GalleryBuilder(settings, database, recognizer, CompositeMetadataProvider(settings))
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        if builder.run_one():
            continue
        time.sleep(2)


if __name__ == "__main__":
    main()
