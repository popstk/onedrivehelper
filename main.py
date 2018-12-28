import os
import signal
import logging
import traceback
import json
import logging
import redis
from tqdm import tqdm
from urllib.parse import urlparse
from onedriveext import OneDriveClient
from onedriveext.upload import upload
from onedriveext.persist import RedisPersist

logger = logging.getLogger(__name__)
stopped = False
conf = get_config()


def init_logger(name):
    ch = logging.StreamHandler()
    fh = logging.FileHandler("%s.log" % name, encoding="utf-8")
    formatter = logging.Formatter(
        "[%(asctime)-15s] [%(levelname)s] - %(message)s (%(filename)s:%(lineno)s)")
    for h in (ch, fh):
        h.setFormatter(formatter)
        h.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(h)
        logging.getLogger().setLevel(logging.DEBUG)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_config(config_file="config.json"):
    with open(config_file) as f:
        return json.loads(f.read(), encoding="utf-8")


def handler(signum, _):
    logger.warn('received SIGQUIT, doing graceful shutting down..')
    global stopped
    stopped = True


def cancel():
    return stopped


def generate_chunk_show(path):
    total = os.path.getsize(path)
    with tqdm(total=total, unit="B", unit_scale=True, initial=offset) as bar:
        bar.update(chunksize)


def upload_from_queue():
    u = urlparse(conf["host"])
    persist = RedisPersist(host=u.hostname, port=u.port, db=conf["db"])
    redisclient = redis.StrictRedis(
        host=u.hostname, port=u.port, db=conf["db"])
    client = OneDriveClient.load_session(conf["session"])

    while not stopped:
        try:
            result = redisclient.blpop(conf["queue"], 1)
            if result is None:
                continue
            path = result[1].decode(encoding="utf-8")
            logger.info("Get path %s", path)
            if not os.path.exists(path):
                logger.error("Path not exists: %s", path)
                continue
        except KeyboardInterrupt:
            return
        except Exception:
            logger.error(traceback.format_exc())
            return

        try:
            ret = client.upload(path, "/upload", persist=persist,
                                cancel_func=cancel, chunk_func=chunk_show)
            if ret:
                logger.info("Done! remove file: %s", path)
                os.remove(path)
        except KeyboardInterrupt:
            redisclient.rpush("pending", path)
        except Exception:
            logger.error(traceback.format_exc())


if __name__ == "__main__":
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, handler)
    upload_from_queue()
    logger.info("bye")
