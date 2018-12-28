import os
import logging
import json
import signal
import requests
from onedrivecmd.utils.helper_file import file_read_seek_len
from onedrivecmd.utils import convert_utf8_dict_to_dict
from onedrivecmd.utils import session as od_session

logger = logging.getLogger(__name__)

def handler(signum, _):
    logger.warn('received SIGQUIT, doing graceful shutting down..')
    global stopped
    stopped = True


def create_session(api_base_url, token, source_file, dest_path):
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


def resume_session(data):
    req = requests.get(data["uploadUrl"])
    if req.status_code != 200:
        return None

    result = convert_utf8_dict_to_dict(req.json())
    for k in ("expirationDateTime", "nextExpectedRanges"):
        data[k] = result[k]
    return data


def upload_piece(uploadUrl, token, source_file, range_this, file_size, requests_session):
    content_length = range_this[1] - range_this[0] + 1
    file_piece = file_read_seek_len(source_file, range_this[0], content_length)
    headers = {
        'Authorization': 'bearer {access_token}'.format(access_token=token),
        'Content-Range': 'bytes {start}-{to}/{total}'.format(
            start=range_this[0], to=range_this[1],  total=str(file_size)),
        'Content-Length': str(content_length)
    }
    req = requests_session.put(uploadUrl, data=file_piece, headers=headers)
    return req


def parse_session_offset(session_conf):
    if "nextExpectedRanges" in session_conf:
        ranges = session_conf["nextExpectedRanges"]
        if len(ranges) > 0:
            start, _ = ranges[0].split('-')
            return int(start)
    return 0
