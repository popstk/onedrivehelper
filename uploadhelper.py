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
        os.path.expanduser('~/.onedrive.json'))
    token = od_session.get_access_token(odclient)

    redisclient = get_redis_client()
    while True:
        logger.info("Waiting...")
        _, path = redisclient.blpop(conf["queue"])
        path = path.decode(encoding="utf-8")
        logger.info("Get path %s", path)
        if not os.path.exists(path):
            logger.error("Path not exists: %s", path)
            continue
        try:
            od_uploader.upload_self(
                api_base_url=odclient.base_url,
                token=token,
                source_file=path,
                dest_path="od:/upload")
            redisclient.rpush("success", path)
        except Exception as e:
            logger.error(e)
            redisclient.rpush("fail", path)
        

if __name__ == "__main__":
    upload_from_queue()
