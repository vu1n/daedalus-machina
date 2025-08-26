import os
import time
import logging
import subprocess

import redis
import docker
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
QUEUE_NAME_PREFIX = os.getenv('QUEUE_NAME_PREFIX', 'bull')
QUEUE_NAME = os.getenv('QUEUE_NAME', 'jobs')

N8N_WORKER_SERVICE_NAME = os.getenv('N8N_WORKER_SERVICE_NAME', 'n8n-worker')
COMPOSE_PROJECT_NAME = os.getenv('COMPOSE_PROJECT_NAME', 'n8n')
COMPOSE_FILE_PATH = os.getenv('COMPOSE_FILE_PATH', '/app/docker-compose.yml')

MIN_REPLICAS = int(os.getenv('MIN_REPLICAS', '1'))
MAX_REPLICAS = int(os.getenv('MAX_REPLICAS', '6'))
SCALE_UP_QUEUE_THRESHOLD = int(os.getenv('SCALE_UP_QUEUE_THRESHOLD', '5'))
SCALE_DOWN_QUEUE_THRESHOLD = int(os.getenv('SCALE_DOWN_QUEUE_THRESHOLD', '1'))

POLLING_INTERVAL_SECONDS = int(os.getenv('POLLING_INTERVAL_SECONDS', '20'))
COOLDOWN_PERIOD_SECONDS = int(os.getenv('COOLDOWN_PERIOD_SECONDS', '120'))

last_scale_time = 0


def get_redis_connection():
    logging.info(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}")
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)


def get_queue_length(r_conn):
    # BullMQ list names vary by version
    keys = [
        f"{QUEUE_NAME_PREFIX}:{QUEUE_NAME}:wait",
        f"{QUEUE_NAME_PREFIX}:{QUEUE_NAME}:waiting",  # v4+
        f"{QUEUE_NAME_PREFIX}:{QUEUE_NAME}",          # legacy
    ]
    for key in keys:
        try:
            length = r_conn.llen(key)
            if isinstance(length, int):
                return length
        except redis.exceptions.ResponseError:
            continue
        except Exception as e:
            logging.warning(f"Queue length check error on {key}: {e}")
    return 0


def get_current_replicas(docker_client, service_name, project_name):
    try:
        filters = {
            "label": [
                f"com.docker.compose.service={service_name}",
                f"com.docker.compose.project={project_name}",
            ],
            "status": "running",
        }
        containers = docker_client.containers.list(filters=filters, all=True)
        return len([c for c in containers if c.status == 'running'])
    except Exception as e:
        logging.error(f"Error reading current replicas: {e}")
        return MAX_REPLICAS + 1  # prevent scaling on error


def scale_service(service_name, replicas, compose_file, project_name):
    cmd = [
        "docker", "compose",
        "-f", compose_file,
        "--project-name", project_name,
        "up", "-d", "--no-deps",
        "--scale", f"{service_name}={replicas}",
        service_name,
    ]
    logging.info(f"Scaling: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stdout:
            logging.info(result.stdout.strip())
        if result.stderr:
            logging.info(result.stderr.strip())
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Scale failed rc={e.returncode}: {e.stderr}")
        return False


def main():
    global last_scale_time

    if not COMPOSE_PROJECT_NAME:
        logging.error("COMPOSE_PROJECT_NAME is required")
        return

    try:
        r = get_redis_connection()
        docker_cl = docker.from_env()
        docker_cl.ping()
        logging.info("Docker daemon reachable")
    except Exception as e:
        logging.error(f"Startup connectivity error: {e}")
        return

    logging.info(
        f"Autoscaler monitoring '{N8N_WORKER_SERVICE_NAME}' in project '{COMPOSE_PROJECT_NAME}' | "
        f"min={MIN_REPLICAS} max={MAX_REPLICAS} up>{SCALE_UP_QUEUE_THRESHOLD} down<{SCALE_DOWN_QUEUE_THRESHOLD}\n"
        f"poll={POLLING_INTERVAL_SECONDS}s cooldown={COOLDOWN_PERIOD_SECONDS}s"
    )

    while True:
        try:
            now = time.time()
            if (now - last_scale_time) < COOLDOWN_PERIOD_SECONDS:
                time.sleep(POLLING_INTERVAL_SECONDS)
                continue

            qlen = get_queue_length(r)
            current = get_current_replicas(docker_cl, N8N_WORKER_SERVICE_NAME, COMPOSE_PROJECT_NAME)
            logging.info(f"queue={qlen} replicas={current}")

            target = current
            if qlen > SCALE_UP_QUEUE_THRESHOLD and current < MAX_REPLICAS:
                target = min(current + 1, MAX_REPLICAS)
            elif qlen < SCALE_DOWN_QUEUE_THRESHOLD and current > MIN_REPLICAS:
                target = max(current - 1, MIN_REPLICAS)

            if target != current:
                if scale_service(N8N_WORKER_SERVICE_NAME, target, COMPOSE_FILE_PATH, COMPOSE_PROJECT_NAME):
                    last_scale_time = now
            else:
                logging.info("no scale")
        except Exception as e:
            logging.error(f"Loop error: {e}")

        time.sleep(POLLING_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

