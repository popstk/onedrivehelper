import os
import sys
import logging
from utils import get_redis_client
from utils import conf
from utils import init_logger

logger = logging.getLogger(__name__)

def filter_files(path):
    client = get_redis_client()
    if os.path.isfile(path):
        logger.info("enqueue %s: %s" % (conf["queue"], path))
        client.rpush(conf["queue"], path)
        return

    for p in os.walk(path):
        dirpath, _, fs = p
        for f in fs:
            # https://stackoverflow.com/questions/541390/extracting-extension-from-filename-in-python
            _, ext = os.path.splitext(f)
            if ext[1:].lower() not in conf["ignoreext"]:
                filepath = os.path.join(dirpath, f)
                logger.info("enqueue %s: %s" % (conf["queue"], filepath))
                client.rpush(conf["queue"], filepath)

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print("file path is empty")
        exit(-1)

    filter_files(sys.argv[1])
