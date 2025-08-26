# n8n on Netcup RS2000 (Cloudflare Tunnel, Autoscaling, S3 backups)

This stack runs a hardened n8n with queue workers, Redis, Postgres, Cloudflare Tunnel ingress, an autoscaler that scales workers based on queue depth, and automated S3 backups. It avoids exposed host ports; access is through Cloudflare only. UI is intended to be protected with Cloudflare Access.

## Layout
- `docker-compose.yml` — services
- `.env.example` — copy to `.env` and fill
- `cloudflared/` — tunnel config + credentials JSON
- `redis/redis.conf` — hardened Redis
- `autoscaler/` — queue-length autoscaler

## Prereqs
- Docker + Docker Compose v2
- Cloudflare Zero Trust (Named Tunnel)
- AWS S3 credentials for backups

## Configure
1. Copy env:
   cp .env.example .env
2. Set secrets in `.env`:
   - `POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY` (32 chars), `N8N_USER_MANAGEMENT_JWT_SECRET`, `REDIS_PASSWORD`
   - Domains: `N8N_HOST=n8n.zangosen.com`, `N8N_WEBHOOK_HOST=webhook.zangosen.com`
3. Cloudflare Tunnel (recommended best practice):
   - Create a Named Tunnel in Cloudflare Zero Trust.
   - Download the tunnel credentials JSON and place it into `cloudflared/`.
   - Set `CLOUDFLARE_TUNNEL_ID` and `CLOUDFLARE_TUNNEL_CREDENTIALS_FILE` in `.env`.
   - Configure Cloudflare Access on n8n.zangosen.com (SSO, MFA, group policy). Do NOT put Access in front of webhooks.
4. Backups to S3:
   - Set `S3_BUCKET`, `S3_REGION`, and AWS creds in `.env`.
   - Enable the backup profile when starting: `docker compose --profile backup up -d db-backup`.

## Start
Docker will create an isolated network and volumes. No host ports are published.

- docker compose --env-file .env up -d

Wait until `postgres` and `redis` are healthy, then `n8n-main` starts. Cloudflared establishes the tunnel and serves:
- UI: https://n8n.zangosen.com (behind Cloudflare Access)
- Webhooks: https://webhook.zangosen.com

## Autoscaling
- The autoscaler checks Redis queue length (BullMQ) every `POLLING_INTERVAL_SECONDS`.
- Scales `n8n-worker` by 1 within `[MIN_REPLICAS, MAX_REPLICAS]` with cooldown `COOLDOWN_PERIOD_SECONDS`.
- Tune thresholds depending on your workload.

## Updates
- Watchtower updates only services with label `com.centurylinklabs.watchtower.enable=true` (n8n, cloudflared, browserless, autoscaler, db-backup). Datastores (postgres, redis) are excluded to avoid surprise upgrades.
- Schedule: `WATCHTOWER_SCHEDULE` (default: 3am daily). Adjust as needed.

## Backups
- `db-backup` dumps Postgres on a cron and uploads to S3. Verify bucket ACLs and lifecycle policies. Test recovery monthly.
 - Test-restore: `docker compose --profile restore up -d postgres-restore && docker compose --profile restore run --rm restore` then inspect the `postgres-restore` DB. Tear down with `docker compose --profile restore down`.

## Security Notes
- No host ports exposed; ingress via Cloudflare Tunnel only.
- Redis requires password, is internal-only.
- Postgres is internal-only with SCRAM auth.
- n8n runs as non-root and with read-only root FS and tmpfs.
- Set strong secrets and rotate periodically.

## Cloudflare Access
- Create an Access application for `n8n.zangosen.com`.
- Enforce SSO/MFA and restrict by email or group.
- Do not place Access in front of `webhook.zangosen.com` unless your flows explicitly handle authenticated hooks.

## Metrics
- `cadvisor` exposes container metrics on port 8080 internally.
- `node-exporter` exposes node metrics on port 9100 internally.
- Optionally add Cloudflare tunnel routes for a private metrics hostname behind Access if you need remote dashboards.

## Workflow Health Pings
- Set `HEALTHCHECK_URLS` in `.env` to a comma-separated list (e.g., Healthchecks.io URLs) and start `health-pinger` (included by default). It pings every `PING_INTERVAL_SECONDS`.
- For per-workflow monitoring, add HTTP nodes in n8n to ping start/success/failure endpoints of your monitoring service.


## Sizing Tips (RS2000: 6 vCPU, 16 GB)
- Start workers at 2–4 min, max 6–8.
- Prefer more workers with lower per-worker concurrency for stability.
- Keep the browserless concurrency modest (5–10) to avoid memory spikes.
