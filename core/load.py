import json
from pathlib import Path

from core.path import APPLIED_PATH, POOL_PATH



def __load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def load_applied():
    return __load(APPLIED_PATH)

def load_pool():
    return __load(POOL_PATH)
