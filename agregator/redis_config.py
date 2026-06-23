import json

import redis

REDIS_HOST = 'archeology-redis-1'  # 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

redis_client = redis.StrictRedis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)


def get_progress_json(task_id):
    progress_json = redis_client.get(task_id)
    if progress_json is None:
        progress_json = redis_client.get('celery-task-meta-' + str(task_id))
    if progress_json is not None:
        progress_json = json.loads(progress_json)
    else:
        return None
    return progress_json
