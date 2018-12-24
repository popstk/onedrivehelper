import os
import sys
import logging
import onedrivesdk
import redis
from onedrivecmd.utils import session as od_session
from onedrivecmd.utils import uploader as od_uploader

upload_key = "uploadqueue"
ignore_exts = ["html", "htm", "url", "torrent"]

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
logger.addHandler(ch)


def filter_files(path):
    client = redis.StrictRedis()
    files = []
    for p in os.walk(path):
        dirpath, _, fs = p
        for f in fs:
            # https://stackoverflow.com/questions/541390/extracting-extension-from-filename-in-python
            _, ext = os.path.splitext(f)
            if ext[1:].lower() not in ignore_exts:
                client.rpush(upload_key, os.path.join(dirpath, f))


def upload_from_queue():
    odclient = od_session.load_session(
        onedrivesdk.OneDriveClient,
        os.path.expanduser('~/.onedrive.json'))
    token = od_session.get_access_token(odclient)

    redisclient = redis.StrictRedis()
    while True:
        logger.info("Waiting...")
        key, path = redisclient.blpop("uploadqueue")
        path = path.decode(encoding="utf-8")
        logger.info("Get path %s", path)
        if not os.path.exists(path):
            logger.error("Path not exists: %s", path)
            continue
        od_uploader.upload_self(
            api_base_url=odclient.base_url,
            token=token,
            source_file=path,
            dest_path="od:/")


def main():
    if len(sys.argv) > 1:
        filter_files(sys.argv[1])
        return
    upload_from_queue()


if __name__ == "__main__":
    main()
