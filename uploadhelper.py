import os
import logging
import onedrivesdk
from onedrivecmd.utils import session as od_session
from onedrivecmd.utils import uploader as od_uploader
from utils import conf
from utils import get_redis_client

logger = logging.getLogger(__name__)


def upload_from_queue():
    odclient = od_session.load_session(
        onedrivesdk.OneDriveClient,
        os.path.expanduser(conf["session"]))
    token = od_session.get_access_token(odclient)

    redisclient = get_redis_client()
    while True:
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
        except Exception as e:
            logger.error(e)
            return

        try:
            succ = od_uploader.upload_self(
                api_base_url=odclient.base_url,
                token=token,
                source_file=path,
                dest_path="od:/upload")
            if succ:
                os.remove(path)
        except KeyboardInterrupt:
            redisclient.rpush("pending", path)
        except Exception as e:
            logger.error(e)
        finally:
            key = "success" if succ else "fail"
            redisclient.rpush(key, path)


if __name__ == "__main__":
    upload_from_queue()
    logger.info("bye")
