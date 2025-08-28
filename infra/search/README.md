# Search Stack (SearXNG + Perplexica + Farfalle)

This adds a private SearXNG instance as a shared metasearch backend, with Perplexica (primary UI/API) and optional Farfalle (alt UI) using SearXNG under the hood. n8n can call Perplexica’s API for LLM‑augmented search, or SearXNG directly for simple queries.

## Topology
- `searxng` (internal only): http://searxng:8080
- `perplexica` (UI/API, behind Access): https://perplexica.zangosen.com
- `farfalle` (UI, behind Access): https://farfalle.zangosen.com

SearXNG is not exposed publicly; Perplexica/Farfalle are behind Cloudflare Access. All run on the same Docker network as n8n so services can reach each other by name.

## Deploy SearXNG
- Configure env in `infra/n8n/.env`:
  - `SEARXNG_TAG=latest`
  - `SEARXNG_INSTANCE_NAME=Daedalus SearXNG`
  - `SEARXNG_BASE_URL=http://searxng:8080`
  - `SEARXNG_SECRET_KEY=<random>` (generate a strong secret)
- (Optional) Edit `infra/n8n/searxng/settings.yml` to add engine keys (Bing/Google/etc.). Limiter and bot detection are already disabled for internal use.
- Start SearXNG:
  - `cd infra/n8n`
  - `docker compose --env-file .env --profile search up -d searxng`
  - Test internal: `docker compose run --rm health-pinger sh -lc 'wget -qS -O- http://searxng:8080 | head -n1'`

## Perplexica
Perplexica ships with its own docker-compose. To integrate cleanly while reusing our network:

- Clone Perplexica upstream in a sibling folder, e.g. `infra/search/perplexica-upstream/`.
- In Perplexica's compose file, add:

```
networks:
  default:
    external: true
    name: ${COMPOSE_PROJECT_NAME}_internal
```

- Set env for Perplexica to use SearXNG:
  - `SEARXNG_BASE_URL=http://searxng:8080`
  - Add your LLM API keys (OpenAI/Gemini, etc.).
- Deploy Perplexica's stack (`docker compose up -d`) and ensure a service named `perplexica` (or change Cloudflare mapping accordingly) is listening internally (commonly port 3000).
- Cloudflare (token mode): add a Public Hostname mapping
  - `perplexica.zangosen.com` → `http://perplexica:3000` (Access on)

## Farfalle (optional)
Farfalle is another UI that uses SearXNG.

- Clone upstream under `infra/search/farfalle-upstream/` and add the same external network stanza as above to join `${COMPOSE_PROJECT_NAME}_internal`.
- Set env pointing to SearXNG:
  - `SEARXNG_URL=http://searxng:8080`
- Deploy Farfalle (`docker compose up -d`), ensure a service named `farfalle` listening (commonly port 3000).
- Cloudflare: add Public Hostname mapping
  - `farfalle.zangosen.com` → `http://farfalle:3000` (Access on)

## Notes
- We keep SearXNG private for security. If you later need public access, add a Cloudflare hostname and consider adding Filtron/Morty.
- n8n can call Perplexica’s API internally via `http://perplexica:3000` or SearXNG via `http://searxng:8080`.
- If you prefer a single compose, you can vendor Perplexica/Farfalle services into `infra/n8n/docker-compose.yml` under the `search` profile. The current approach avoids guessing upstream image tags and keeps maintenance closer to upstream updates.
