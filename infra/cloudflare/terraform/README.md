# Cloudflare Access (Terraform Boilerplate)

This Terraform config manages:
- Cloudflare Access for the n8n UIs (SSO/MFA)
- DNS records for the Cloudflare Tunnel hostnames (CNAMEs to `<tunnel_id>.cfargotunnel.com`)
Do not apply Access to the webhook domains.

## Prerequisites
- Cloudflare account with Zero Trust enabled
- Zone onboarded (zangosen.com)
- API token with minimal scopes:
  - Account: Access: Organizations, Applications, Policies (Edit)
  - Zone: Read

## Usage
1. Copy `terraform.tfvars.example` to `terraform.tfvars` and fill values.
2. Export the API token (or put in tfvars via `api_token`, but env var preferred):
   export CLOUDFLARE_API_TOKEN=your_token
3. Plan and apply:
   terraform init
   terraform plan
   terraform apply

## Notes
- By default, Access allows emails under a specified domain (e.g. `@zangosen.com`). You can also allow specific emails or a Cloudflare group ID.
- Session duration defaults to `24h`.
- DNS records created:
  - `ui_hostname` (default `n8n.zangosen.com`)
  - `webhook_hostname` (default `webhook.zangosen.com`)
  - `scrape_ui_hostname` (default `n8n-scrape.zangosen.com`)
  - `scrape_webhook_hostname` (default `scrape.zangosen.com`)
  All CNAME to `<tunnel_id>.cfargotunnel.com` with `proxied = true` by default.
