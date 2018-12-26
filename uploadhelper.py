import os
import logging
import json
import signal
import traceback
import requests
import onedrivesdk
from onedrivecmd.utils import session as od_session
from onedrivecmd.utils import uploader as od_uploader
from onedrivecmd.utils import convert_utf8_dict_to_dict
from utils import conf
from utils import get_redis_client
from tqdm import tqdm

logger = logging.getLogger(__name__)
stopped = False
redisclient = get_redis_client()
pending_session_key = "pending"


def handler(signum, _):
    logger.warn('received SIGQUIT, doing graceful shutting down..')
    global stopped
    stopped = True


def create_upload_session(api_base_url, token, source_file, dest_path):
    filename = os.path.basename(source_file)
    if not dest_path.endswith('/'):
        dest_path += '/'
    dest_path += filename

    api_url = api_base_url + \
        'drive/root:{dest_path}:/upload.createSession'.format(
            dest_path=dest_path)
    headers = {
        'Authorization': 'bearer {access_token}'.format(access_token=token),
        'content-type': 'application/json'
    }
    info_json = json.dumps({'item': {
        '@name.conflictBehavior': 'fail',
        'name': filename
    }}, sort_keys=True)

    # logger.debug("headers: %s, request data: %s" % (headers, info_json))
    req = requests.post(api_url, data=info_json, headers=headers)
    if req.status_code > 201:
        logger.error("status code: %d, respond: %s" %
                     (req.status_code, req.json()))
        return None

    logger.info(req.json())
    return convert_utf8_dict_to_dict(req.json())


def resume_session(source_file):
    result = redisclient.hget(pending_session_key, source_file)
    if result is None:
        return None

    data = json.loads(result, encoding="utf-8")
    req = requests.get(data["uploadUrl"])
    if req.status_code != 200:
        return None

    result = convert_utf8_dict_to_dict(req.json())
    for k in ("expirationDateTime", "nextExpectedRanges"):
        data[k] = result[k]
    return data


def parse_session_offset(session_conf):
    if "nextExpectedRanges" in session_conf:
        ranges = session_conf["nextExpectedRanges"]
        if len(ranges) > 0:
            start, _ = ranges[0].split('-')
            return int(start)
    return 0


def upload(api_base_url, token, source_file, dest_path, chunksize=1024*1024):
    """
    str, str, str, str, int -> bool

    Upload a file via the API, instead of the SDK.
    """
    session_conf = resume_session(source_file)
    if session_conf is None:
        session_conf = create_upload_session(
            api_base_url, token, source_file, dest_path)

    # logger.debug("session_conf = %s", session_conf)
    total = os.path.getsize(source_file)
    offset = parse_session_offset(session_conf)
    if offset > 0:
        logger.info("Resuming %s [%d -> %d]" % (source_file, offset, total))

    requests_session = requests.Session()
    uploadUrl = session_conf["uploadUrl"]

    with tqdm(total=total, unit="B", unit_scale=True, initial=offset) as bar:
        while bar.n < total:
            if stopped:
                break

            i = [bar.n, min(bar.n+chunksize-1, total-1)]
            od_uploader.upload_one_piece(
                uploadUrl=uploadUrl, token=token,
                source_file=source_file, range_this=i,
                file_size=total, requests_session=requests_session)
            bar.update(chunksize)

    if bar.n < total:
        del session_conf["nextExpectedRanges"]
        redisclient.hset(pending_session_key, source_file,
                         json.dumps(session_conf))
        return False

    redisclient.hdel(pending_session_key, source_file)
    return True


def upload_from_queue():
    odclient = od_session.load_session(
        onedrivesdk.OneDriveClient,
        os.path.expanduser(conf["session"]))

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
        except Exception as e:
            logger.error(traceback.format_exc())
            return

        succ = False
        try:
            od_session.refresh_token(odclient)
            token = od_session.get_access_token(odclient)
            succ = upload(
                api_base_url=odclient.base_url,
                token=token,
                source_file=path,
                dest_path="/upload")

        except KeyboardInterrupt:
            redisclient.rpush("pending", path)
        except Exception as e:
            logger.error(traceback.format_exc())
        finally:
            key = "success" if succ else "fail"
            redisclient.rpush(key, path)

        if succ:
            logger.info("Done! remove file: %s", path)
            os.remove(path)


if __name__ == "__main__":
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, handler)
    upload_from_queue()
    logger.info("bye")
