import os
import logging
import json
import signal
import requests
import onedrivesdk
from onedrivecmd.utils import session as od_session
from onedrivecmd.utils import uploader as od_uploader
from onedrivecmd.utils import convert_utf8_dict_to_dict
from utils import conf
from utils import get_redis_client
from progress.bar import Bar

logger = logging.getLogger(__name__)
stopped = False
redisclient = get_redis_client()
pending_session_key = "pending"


def handler(signum, _):
    logger.warn('received SIGQUIT, doing graceful shutting down..')
    global stopped
    stopped = True


def create_upload_session(api_base_url, token, source_file, dest_path):
    # Prepare API call
    dest_path = od_uploader.path_to_remote_path(
        dest_path) + '/' + od_uploader.path_to_name(source_file)
    info_json = json.dumps({'item': {
        '@name.conflictBehavior': 'fail',
        'name': od_uploader.path_to_name(source_file)
    }}, sort_keys=True)

    api_url = api_base_url + \
        'drive/root:{dest_path}:/upload.createSession'.format(
            dest_path=dest_path)
    headers = {
        'Authorization': 'bearer {access_token}'.format(access_token=token),
        'content-type': 'application/json'
    }

    logger.debug("headers: %s, request data: %s" % (headers, info_json))
    req = requests.post(api_url, data=info_json, headers=headers)
    if req.status_code > 201:
        logger.error("status code: %d, respond: %s" %
                     (req.status_code, req.json()))
        return False

    logger.info(req.json())
    return convert_utf8_dict_to_dict(req.json())


def resume_session(source_file):
    result = redisclient.hget(pending_session_key, source_file)
    if result is None:
        return None

    logger.info("Resuming %s", source_file)
    data = json.loads(result, encoding="utf-8")
    req = requests.get(data["uploadUrl"])
    if req.status_code != 200:
        return None

    result = convert_utf8_dict_to_dict(req.json())
    for k in ("expirationDateTime", "nextExpectedRanges"):
        data[k] = result[k]
    return data


def upload(api_base_url='', token='', source_file='', dest_path='', chunksize=10247680):
    if not dest_path.endswith('/'):
        dest_path += '/'

    session_conf = resume_session(source_file)
    if session_conf is None:
        session_conf = create_upload_session(
            api_base_url, token, source_file, dest_path)

    start = 0
    if "nextExpectedRanges" in session_conf:
        start, _ = session_conf["nextExpectedRanges"].split('-')
        start = int(start)

    file_size = os.path.getsize(source_file)
    logger.info("Start from %d/%d" % (start, file_size))

    range_list = [[i, i + chunksize - 1]
                  for i in range(start, file_size, chunksize)]
    range_list[-1][-1] = file_size - 1

    bar = Bar('Uploading', max=len(range_list),
              suffix='%(percent).1f%% - %(eta)ds')
    bar.next()  # nessesery to init the Bar

    logger.info("Start uploading..")
    uploadUrl = session_conf['uploadUrl']
    requests_session = requests.Session()

    for i in range_list:
        if stopped:
            return False
        od_uploader.upload_one_piece(
            uploadUrl=uploadUrl, token=token, source_file=source_file,
            range_this=i, file_size=file_size, requests_session=requests_session)
        bar.next()

    bar.finish()
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
            logger.error(e)
            return

        succ = False
        try:
            od_session.refresh_token(odclient)
            token = od_session.get_access_token(odclient)
            succ = upload(
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
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, handler)
    upload_from_queue()
    logger.info("bye")
