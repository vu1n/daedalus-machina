import os
import time
import logging
import subprocess
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Tuple

import redis
import docker
from dateutil import parser as dateparser
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


@dataclass
class PoolConfig:
    name: str
    queue_patterns: List[str]
    min_replicas: int
    max_replicas: int
    sma_window: int
    up_sma_threshold: int
    down_sma_threshold: int
    rate_down_threshold: float
    cooldown_up: int
    cooldown_down: int
    min_lifetime: int
    step_up: int
    step_down: int


class PoolState:
    def __init__(self, cfg: PoolConfig):
        self.cfg = cfg
        self.hist = deque(maxlen=cfg.sma_window)  # backlog samples
        self.last_point: Optional[Tuple[float, int]] = None  # (ts, backlog)
        self.last_scale_up = 0.0
        self.last_scale_down = 0.0


REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

COMPOSE_PROJECT_NAME = os.getenv('COMPOSE_PROJECT_NAME', 'n8n')
COMPOSE_FILE_PATH = os.getenv('COMPOSE_FILE_PATH', '/app/docker-compose.yml')
POLLING_INTERVAL_SECONDS = int(os.getenv('POLLING_INTERVAL_SECONDS', '20'))


def get_redis_connection():
    logging.info(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}")
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)


def scan_queue_backlog(r: redis.Redis, patterns: List[str]) -> int:
    total = 0
    for pattern in patterns:
        try:
            for key in r.scan_iter(match=pattern, count=1000):
                try:
                    total += r.llen(key)
                except redis.exceptions.ResponseError:
                    # Not a list; ignore
                    continue
        except Exception as e:
            logging.warning(f"Error scanning pattern {pattern}: {e}")
    return total


def current_replicas_and_min_uptime(dc: docker.DockerClient, service: str, project: str) -> Tuple[int, Optional[float]]:
    try:
        filters = {
            "label": [
                f"com.docker.compose.service={service}",
                f"com.docker.compose.project={project}",
            ],
            "status": "running",
        }
        containers = dc.containers.list(filters=filters, all=True)
        running = [c for c in containers if c.status == 'running']
        if not running:
            return 0, None
        now = time.time()
        uptimes = []
        for c in running:
            try:
                started = c.attrs.get('State', {}).get('StartedAt')
                # Example: 2024-08-26T20:59:48.555254829Z
                if started:
                    dt = dateparser.parse(started)
                    uptimes.append((now - dt.timestamp()))
            except Exception:
                continue
        min_uptime = min(uptimes) if uptimes else None
        return len(running), min_uptime
    except Exception as e:
        logging.error(f"Error reading replicas/uptime for {service}: {e}")
        return 0, None


def scale_service(service_name: str, replicas: int, compose_file: str, project_name: str) -> bool:
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


def load_pool_from_env(prefix: str) -> Optional[Tuple[PoolConfig, PoolState]]:
    name = os.getenv(f'{prefix}_SERVICE_NAME')
    if not name:
        return None

    patterns_raw = os.getenv(f'{prefix}_QUEUE_PATTERNS', '')
    patterns = [p.strip() for p in patterns_raw.split(',') if p.strip()]
    if not patterns:
        # Fallback to BullMQ defaults for n8n
        qprefix = os.getenv('QUEUE_NAME_PREFIX', 'bull')
        qname = os.getenv('QUEUE_NAME', 'jobs')
        patterns = [f"{qprefix}:{qname}:wait", f"{qprefix}:{qname}:waiting", f"{qprefix}:{qname}"]

    cfg = PoolConfig(
        name=name,
        queue_patterns=patterns,
        min_replicas=int(os.getenv(f'{prefix}_MIN_REPLICAS', os.getenv('MIN_REPLICAS', '1'))),
        max_replicas=int(os.getenv(f'{prefix}_MAX_REPLICAS', os.getenv('MAX_REPLICAS', '6'))),
        sma_window=int(os.getenv(f'{prefix}_SMA_WINDOW', '5')),
        up_sma_threshold=int(os.getenv(f'{prefix}_UP_SMA_THRESHOLD', os.getenv('SCALE_UP_QUEUE_THRESHOLD', '5'))),
        down_sma_threshold=int(os.getenv(f'{prefix}_DOWN_SMA_THRESHOLD', os.getenv('SCALE_DOWN_QUEUE_THRESHOLD', '1'))),
        rate_down_threshold=float(os.getenv(f'{prefix}_RATE_DOWN_THRESHOLD', '-0.25')),
        cooldown_up=int(os.getenv(f'{prefix}_COOLDOWN_UP', os.getenv('SCALE_UP_COOLDOWN_SECONDS', '30'))),
        cooldown_down=int(os.getenv(f'{prefix}_COOLDOWN_DOWN', os.getenv('SCALE_DOWN_COOLDOWN_SECONDS', '300'))),
        min_lifetime=int(os.getenv(f'{prefix}_MIN_LIFETIME', os.getenv('MIN_WORKER_LIFETIME_SECONDS', '300'))),
        step_up=int(os.getenv(f'{prefix}_STEP_UP', '1')),
        step_down=int(os.getenv(f'{prefix}_STEP_DOWN', '1')),
    )
    return cfg, PoolState(cfg)


def decide_and_scale(dc: docker.DockerClient, r: redis.Redis, pool: PoolState):
    now = time.time()
    # Check current replicas first to enforce a baseline immediately
    current, min_uptime = current_replicas_and_min_uptime(dc, pool.cfg.name, COMPOSE_PROJECT_NAME)
    if current < pool.cfg.min_replicas:
        desired = pool.cfg.min_replicas
        if scale_service(pool.cfg.name, desired, COMPOSE_FILE_PATH, COMPOSE_PROJECT_NAME):
            pool.last_scale_up = now
            logging.info(f"Baseline enforced for {pool.cfg.name}: {current} -> {desired}")
        return

    backlog = scan_queue_backlog(r, pool.cfg.queue_patterns)
    pool.hist.append(backlog)
    sma = sum(pool.hist) / len(pool.hist)

    rate = 0.0
    if pool.last_point is not None:
        last_ts, last_val = pool.last_point
        dt = max(1e-6, now - last_ts)
        rate = (backlog - last_val) / dt
    pool.last_point = (now, backlog)
    desired = current

    can_scale_up = (now - pool.last_scale_up) >= pool.cfg.cooldown_up
    can_scale_down = (now - pool.last_scale_down) >= pool.cfg.cooldown_down

    # Scale up: sustained backlog
    if can_scale_up and current < pool.cfg.max_replicas and sma >= pool.cfg.up_sma_threshold:
        desired = min(current + pool.cfg.step_up, pool.cfg.max_replicas)
        if desired != current and scale_service(pool.cfg.name, desired, COMPOSE_FILE_PATH, COMPOSE_PROJECT_NAME):
            pool.last_scale_up = now
            logging.info(f"Up-scaled {pool.cfg.name}: {current} -> {desired} | backlog={backlog} sma={sma:.2f} rate={rate:.2f}")
            return

    # Scale down: low backlog and draining, and workers old enough
    young_block = (min_uptime is not None and min_uptime < pool.cfg.min_lifetime)
    if (can_scale_down and current > pool.cfg.min_replicas and
            sma <= pool.cfg.down_sma_threshold and rate <= pool.cfg.rate_down_threshold and not young_block):
        desired = max(current - pool.cfg.step_down, pool.cfg.min_replicas)
        if desired != current and scale_service(pool.cfg.name, desired, COMPOSE_FILE_PATH, COMPOSE_PROJECT_NAME):
            pool.last_scale_down = now
            logging.info(f"Down-scaled {pool.cfg.name}: {current} -> {desired} | backlog={backlog} sma={sma:.2f} rate={rate:.2f}")
            return

    min_uptime_s = int(min_uptime) if min_uptime is not None else -1
    logging.info(
        f"No scale {pool.cfg.name} | replicas={current} backlog={backlog} sma={sma:.2f} rate={rate:.2f} "
        f"uptime.min={min_uptime_s}s"
    )


def main():
    if not COMPOSE_PROJECT_NAME:
        logging.error("COMPOSE_PROJECT_NAME is required")
        return

    try:
        r = get_redis_connection()
        dc = docker.from_env()
        dc.ping()
        logging.info("Docker daemon reachable")
    except Exception as e:
        logging.error(f"Startup connectivity error: {e}")
        return

    primary = load_pool_from_env('PRIMARY')
    if not primary:
        # Backward-compat: infer from legacy envs
        os.environ.setdefault('PRIMARY_SERVICE_NAME', os.getenv('N8N_WORKER_SERVICE_NAME', 'n8n-worker'))
        primary = load_pool_from_env('PRIMARY')

    secondary = load_pool_from_env('SECONDARY')

    pools = [p for p in [primary, secondary] if p]
    if not pools:
        logging.error("No pools configured. Set PRIMARY_SERVICE_NAME (and optionally SECONDARY_SERVICE_NAME).")
        return

    info = [f"{cfg.name}[{cfg.min_replicas}-{cfg.max_replicas}] up>={cfg.up_sma_threshold} down<={cfg.down_sma_threshold} "
            f"rate_down<={cfg.rate_down_threshold}/s window={cfg.sma_window} upCooldown={cfg.cooldown_up}s downCooldown={cfg.cooldown_down}s minLife={cfg.min_lifetime}s"
            for cfg, _ in pools]
    logging.info("Autoscaler pools: " + "; ".join(info))

    while True:
        for cfg, state in pools:
            try:
                decide_and_scale(dc, r, state)
            except Exception as e:
                logging.error(f"Pool {cfg.name} error: {e}")
        time.sleep(POLLING_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
