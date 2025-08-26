# Cloudflare Access (Terraform Boilerplate)

This Terraform config manages a Cloudflare Access application and policy to protect the n8n UI at `n8n.zangosen.com` with SSO/MFA. Do not apply Access to the webhook domain.

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
- By default, allows emails under a specified domain (e.g. `@zangosen.com`). You can also allow specific emails or a Cloudflare group ID.
- Session duration defaults to `24h`.
- This only configures Access for the UI hostname `n8n.zangosen.com`.

