# n8n on Netcup RS2000 (Cloudflare Tunnel, Autoscaling, S3 backups)

This stack runs a hardened n8n with queue workers, Redis, Postgres, Cloudflare Tunnel ingress, an autoscaler that scales workers based on queue depth, and automated S3 backups. It avoids exposed host ports; access is through Cloudflare only. UI is intended to be protected with Cloudflare Access.

## Layout
- `docker-compose.yml` — services
- `.env.example` — copy to `.env` and fill
- `cloudflared/` — tunnel config + credentials JSON
- `redis/redis.conf` — hardened Redis
- `autoscaler/` — queue-length autoscaler
 - `postgres/init/` — init SQL (creates `n8n_scrape` DB on first bootstrap)
 - `postgres/init/` — init SQL for creating the scrape DB

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
   - Two modes supported (auto-detected by the container):
     - Token mode: set `CLOUDFLARE_TUNNEL_TOKEN` in `.env`, and configure Public Hostnames in the Cloudflare UI (no JSON needed).
     - JSON mode: place tunnel credentials as `cloudflared/credentials.json`, set `CLOUDFLARE_TUNNEL_ID` and `CLOUDFLARE_TUNNEL_CREDENTIALS_FILE` in `.env`. Hostnames are templated from `.env` into `cloudflared/config.tmpl.yml` at runtime.
   - Configure Cloudflare Access on `${N8N_HOST}` and `${N8N_SCRAPE_HOST}` (SSO, MFA). Do NOT put Access in front of `${N8N_WEBHOOK_HOST}` or `${N8N_SCRAPE_WEBHOOK_HOST}`.
4. Backups to S3:
   - Set `S3_BUCKET`, `S3_REGION`, and AWS creds in `.env`.
   - Enable the backup profile when starting: `docker compose --profile backup up -d db-backup`.

## Start
Docker will create an isolated network and volumes. No host ports are published.

- docker compose --env-file .env up -d

Wait until `postgres` and `redis` are healthy, then `n8n-main` starts. Cloudflared establishes the tunnel and serves:
- UI: https://n8n.zangosen.com (behind Cloudflare Access)
- Webhooks: https://webhook.zangosen.com
- Scrape UI: https://n8n-scrape.zangosen.com (behind Cloudflare Access)
- Scrape Webhooks: https://scrape.zangosen.com
 - Perplexica: https://perplexica.zangosen.com (behind Cloudflare Access)

## Autoscaling
- Smarter scaling using SMA + rate-of-change:
  - Up when sustained backlog (SMA ≥ threshold)
  - Down only when backlog low AND draining (negative rate)
  - Asymmetric cooldowns (fast up, slow down) and minimum worker lifetime
- Two autoscalers: `autoscaler` (main) and `autoscaler-scrape` (scraping)
- Tune via `.env`: `SMA_WINDOW`, `SCALE_UP_*`, `SCALE_DOWN_*`, `RATE_DOWN_THRESHOLD`, cooldowns, min lifetime, and steps

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
- Scraping runs on a separate n8n instance with its own DB (`POSTGRES_SCRAPE_DB`) and Redis (`redis-scrape`). Keep its UI behind Access and only expose webhooks.

## Cloudflare Access
- Create an Access application for `n8n.zangosen.com`.
- Enforce SSO/MFA and restrict by email or group.
- Do not place Access in front of `webhook.zangosen.com` unless your flows explicitly handle authenticated hooks.

## Metrics
- `cadvisor` exposes container metrics on port 8080 internally.
- `node-exporter` exposes node metrics on port 9100 internally.
- Optionally add Cloudflare tunnel routes for a private metrics hostname behind Access if you need remote dashboards.

## Calling the scraping instance (Scrape-as-a-Service)
- Preferred: Main n8n calls scraping workflows via HTTP Request node to `https://scrape.zangosen.com/webhook/<id>`. For long scrapes, use `Respond to Webhook` pattern and a callback to a main-instance webhook when done.
- Keep browser usage in scraping instance by calling the `browserless` service from scraping workflows. Avoid running browser in the main instance.

## Restore and Test-Restore
- Backups: `db-backup` uploads compressed dumps to S3 on a schedule.
- Test-restore: `docker compose --profile restore up -d postgres-restore && docker compose --profile restore run --rm restore` then inspect the `postgres-restore` DB. Tear down with `docker compose --profile restore down`.
- If Postgres volume existed before adding scrape DB init, create once: `docker compose exec -T postgres psql -U "$POSTGRES_USER" -c "CREATE DATABASE n8n_scrape OWNER $POSTGRES_USER;"`

## Workflow Health Pings
- Set `HEALTHCHECK_URLS` in `.env` to a comma-separated list (e.g., Healthchecks.io URLs) and start `health-pinger` (included by default). It pings every `PING_INTERVAL_SECONDS`.
- For per-workflow monitoring, add HTTP nodes in n8n to ping start/success/failure endpoints of your monitoring service.


## Sizing Tips (RS2000: 6 vCPU, 16 GB)
- Start workers at 2–4 min, max 6–8.
- Prefer more workers with lower per-worker concurrency for stability.
- Keep the browserless concurrency modest (5–10) to avoid memory spikes.
## Search (SearXNG + Perplexica + Farfalle)
- Private SearXNG instance is included under the `search` profile.
- Perplexica and Qdrant are vendored into this compose under the `search` profile; Farfalle remains optional via upstream.
- Start SearXNG + Qdrant + Perplexica:
  - `docker compose --env-file .env --profile search up -d searxng qdrant perplexica`
- Internal tests:
  - `docker compose run --rm health-pinger sh -lc 'wget -qS -O- http://searxng:8080 | head -n1'`
  - `docker compose run --rm health-pinger sh -lc 'wget -qS -O- http://perplexica:3000 | head -n1'`
- Cloudflare: add Public Hostnames (token mode) or use JSON-mode mappings
  - `perplexica.zangosen.com` → `http://perplexica:3000`
  - Restart tunnel: `docker compose restart cloudflared`
