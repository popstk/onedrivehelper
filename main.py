import os
import signal
import logging
import traceback
import json
import logging
import redis
import shutil
from tqdm import tqdm
from urllib.parse import urlparse
from onedrivesdk.error import OneDriveError
from onedrivesdk.error import ErrorCode
from onedriveext.client import OneDriveClient
from onedriveext.persist import RedisPersist


logger = logging.getLogger(__name__)
stopped = False
conf = None


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


def gen_chunk_show(path, chunksize):
    total = os.path.getsize(path)
    bar = None

    def chunk_show(req, this_range):
        nonlocal bar
        if bar is None:
            bar = tqdm(total=total, unit="B",
                       unit_scale=True, initial=this_range[0])
        bar.update(this_range[1]-this_range[0])

    return chunk_show


def ignore(f):
    _, ext = os.path.splitext(f)
    return ext[1:].lower() in conf["ignoreext"]


def filter_files(path):
    if not os.path.exists(path):
        logger.error("Path not exists: %s", path)
        return []

    if os.path.isfile(path):
        return [("/", path)]

    res = []
    directory = '/' + os.path.basename(path)
    for p in os.walk(path):
        dirpath, _, fs = p
        for f in fs:
            if not ignore(f):
                res.append((directory, os.path.join(dirpath, f)))
    logger.info(res)
    return res


def parseRedisUrl(u):
    u = urlparse(u)
    f = list(filter(None, u.path.split('/')))
    return {
        "host": u.hostname,
        "port": u.port,
        "db": int(f[0]) if len(f) > 0 else 0
    }


def upload_from_queue():
    kwargs = parseRedisUrl(conf["url"])
    persist = RedisPersist(**kwargs)
    redisclient = redis.StrictRedis(**kwargs)

    client = OneDriveClient.load_session(conf["session"])
    chunksize = 5*1024*1024
    queue_key = conf["queue"]
    queue_fail_key = "fail"

    while not stopped:
        result = redisclient.blpop(queue_key, 1)
        if result is None:
            continue
        path = result[1].decode(encoding="utf-8")
        logger.info("Get path %s", path)

        try:
            for dest, p in filter_files(path):
                if stopped:
                    raise Exception("break")

                try:
                    client.upload(p, conf["rootpath"]+dest,
                                  persist=persist, chunksize=chunksize,
                                  cancel_func=lambda: stopped,
                                  chunk_func=gen_chunk_show(path, chunksize))

                except OneDriveError as exc:
                    if exc.code != ErrorCode.NameAlreadyExists:
                        raise exc

                logger.info("Done! remove file: %s", p)
                os.remove(p)

            if os.path.isdir(path):
                logger.info("Done! remove directory: %s", path)
                shutil.rmtree(path)

        except Exception:
            redisclient.rpush(queue_fail_key, path)
            logger.error(traceback.format_exc())


def main():
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, handler)
    global conf
    conf = get_config()
    init_logger("upload")
    upload_from_queue()
    logger.info("bye")


if __name__ == "__main__":
    main()
