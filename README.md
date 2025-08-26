# Daedalus Machina — n8n Automation Stack

This repo contains a hardened, Cloudflare-first n8n deployment for Netcup RS2000. It runs two n8n instances: a main automation hub and a dedicated scraping instance, each with autoscaled workers, backed by Postgres and Redis, and fronted by Cloudflare Tunnel. It includes optional S3 backups, metrics, and a smarter autoscaler using SMA + rate-of-change.

## Highlights
- Secure ingress via Cloudflare Tunnel; no host ports exposed
- Main n8n for general workflows + separate scraping n8n for browser-heavy tasks
- Autoscalers using SMA + rate-of-change, asymmetric cooldowns, min worker lifetime
- Redis (passworded), Postgres (SCRAM), non-root containers with read-only root FS
- Browserless/Chromium service for reliable scraping
- Optional automated S3 backups and test-restore profile
- Metrics via cAdvisor and node-exporter; health pinger for externals

## Layout
- `infra/n8n/` — Compose stack, env template, autoscaler, redis config, backups, restore scripts
- `infra/cloudflare/terraform/` — Cloudflare Access Terraform boilerplate for protecting the UI

## Architecture (at a glance)
- Postgres (single container) with two databases: `n8n` (main) and `n8n_scrape` (scraping)
- Redis x2: `redis` for main, `redis-scrape` for scraping
- n8n main: `n8n-main` (UI) + `n8n-webhook` + autoscaled `n8n-worker`
- n8n scraping: `n8n-scrape-main` (UI) + `n8n-scrape-webhook` + autoscaled `n8n-scrape-worker`
- Cloudflared tunnel routing:
  - `n8n.zangosen.com` → main UI (behind Cloudflare Access)
  - `webhook.zangosen.com` → main webhooks (public)
  - `n8n-scrape.zangosen.com` → scrape UI (behind Access)
  - `scrape.zangosen.com` → scrape webhooks (public)
- Browserless/Chromium for headless browser tasks

## Requirements
- Linux host with Docker + Docker Compose v2
- Cloudflare Zero Trust (Named Tunnel) and DNS for zangosen.com
- AWS S3 bucket and credentials (if enabling backups)

## Quick Start
1) Configure env
- cd `infra/n8n` and copy `.env.example` to `.env`.
- Set strong secrets: `POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY`, `N8N_USER_MANAGEMENT_JWT_SECRET`, `REDIS_PASSWORD`, and the scrape equivalents (`N8N_SCRAPE_*`, `REDIS_SCRAPE_PASSWORD`).
- Ensure domains match: `n8n.zangosen.com`, `webhook.zangosen.com`, `n8n-scrape.zangosen.com`, `scrape.zangosen.com`.

2) Cloudflare Tunnel
- Place the Named Tunnel credentials JSON in `infra/n8n/cloudflared/credentials.json`.
- Edit `infra/n8n/cloudflared/config.yml` and set your tunnel ID.
- Protect `n8n.zangosen.com` and `n8n-scrape.zangosen.com` with Cloudflare Access. Keep `webhook` and `scrape` public.

3) Start the stack
- From `infra/n8n`: `docker compose --env-file .env up -d`
- Wait for Postgres/Redis to be healthy; UIs become available via Cloudflare.

4) Backups (optional)
- Fill S3 variables in `.env` and start: `docker compose --profile backup up -d db-backup`
- Test restore regularly (see infra/n8n/README.md).

## Autoscaling
- The autoscaler samples Redis backlog, computes an SMA and rate-of-change, and scales:
  - Up: when SMA ≥ threshold (sustained backlog)
  - Down: when SMA ≤ low threshold AND rate is negative (queue draining)
  - Asymmetric cooldowns (fast up, slow down) and a minimum worker lifetime to prevent flapping
- Two autoscalers run independently (main vs scrape) with separate thresholds and windows.

## Operating Notes
- Updates: Watchtower updates labeled services nightly; stateful stores (Postgres/Redis) are excluded.
- Metrics: cAdvisor and node-exporter run internally; add a private metrics hostname if you want external dashboards.
- Security: No host ports; Cloudflare Access on UIs; strong secrets; non-root containers and read-only root FS.
- Scrape-as-a-Service: Call `https://scrape.zangosen.com/webhook/<id>` from main workflows. For long scrapes, use Respond to Webhook + callback.

## Next Steps
- Add Cloudflare Access via Terraform in `infra/cloudflare/terraform` (optional)
- Add alerts for persistent backlog (via Healthchecks.io or your tooling)
- Pin n8n images to a chosen version and only bump intentionally

