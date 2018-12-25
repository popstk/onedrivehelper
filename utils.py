import logging
import json
import redis
from urllib.parse import urlparse

ch = logging.StreamHandler()
fh = logging.FileHandler("uploader.log", encoding="utf-8")
formatter = logging.Formatter(
    "[%(asctime)-15s] [%(levelname)s] - %(message)s (%(filename)s:%(lineno)s)")
for h in (ch, fh):
    h.setFormatter(formatter)
    h.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(h)
    logging.getLogger().setLevel(logging.DEBUG)

config_file = "config.json"


def get_config():
    with open(config_file) as f:
        return json.loads(f.read(), encoding="utf-8")


def get_redis_client():
    u = urlparse(conf["host"])
    return redis.StrictRedis(host=u.hostname, port=u.port, db=conf["db"])


conf = get_config()
