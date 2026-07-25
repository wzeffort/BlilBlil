import json
import os

DEFAULT_CONFIG = {
    "download_dir": "./downloads",
    "ffmpeg_path": "",
    "language": "zh",
    "max_threads": 7
}


class Config:
    def __init__(self, path: str = "config.json"):
        self.path = path
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()
