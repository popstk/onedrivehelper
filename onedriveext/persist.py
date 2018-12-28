import redis
import json
pending_session_key = "pending"


class RedisPersist(object):
    def __init__(self, host, port, db):
        self.client = redis.StrictRedis(host, port, db)

    def Get(self, key):
        result = self.client.hget(pending_session_key, key)
        if result:
            return json.loads(result, encoding="utf-8")

    def Set(self, key, value):
        return self.client.hset(pending_session_key, key, json.dumps(value))

    def Del(self, key):
        return self.client.hdel(pending_session_key, key)
