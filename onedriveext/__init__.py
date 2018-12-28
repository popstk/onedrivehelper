import os
import logging
import requests
from onedrivecmd.utils import session as od_session
from . import upload

logger = logging.getLogger(__name__)
default_session_file = "~/.onedrive.json"


class OneDriveClient(object):
    def __init__(self, client):
        self.client = client

    def upload(self, src, dest="/", chunksize=1024*1024*10, persist=None,
               cancel_func=None, chunk_func=None):
        od_session.refresh_token(self.client)
        token = od_session.get_access_token(self.client)

        logger.debug("Got token %s", token)

        session = None
        if persist is not None:
            result = persist.Get(src)
            if result:
                session = upload.resume_session(result)

        if session is None:
            session = upload.create_session(
                self.client.base_url, token, src, dest)
        
        if "error" in session:
            logger.error(session["error"])
            return False

        requests_session = requests.Session()
        uploadUrl = session["uploadUrl"]
        total = os.path.getsize(src)
        offset = upload.parse_session_offset(session)

        # save session
        persist.Set(src, session)
        logger.debug("session_conf = %s", session)

        while offset < total:
            if cancel_func and cancel_func():
                break

            this_range = [offset, min(offset+chunksize-1, total-1)]
            respond = upload.upload_piece(uploadUrl, token, src,
                                          this_range, total, requests_session)
            chunk_func(respond, this_range)
            offset += chunksize

        else:
            persist.Del(src)
            return True

        return False

    @staticmethod
    def load_session(path):
        if path is None or path == "":
            path = default_session_file
        return OneDriveClient(
            od_session.load_session(None, os.path.expanduser(path)))
