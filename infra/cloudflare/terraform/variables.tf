variable "api_token" {
  description = "Cloudflare API token (optional, else use CLOUDFLARE_API_TOKEN env var)"
  type        = string
  default     = null
  sensitive   = true
}

variable "account_id" {
  description = "Cloudflare account ID"
  type        = string
}

variable "zone_id" {
  description = "Cloudflare zone ID for zangosen.com"
  type        = string
}

variable "ui_hostname" {
  description = "Hostname protected by Access"
  type        = string
  default     = "n8n.zangosen.com"
}

variable "webhook_hostname" {
  description = "Public webhook hostname"
  type        = string
  default     = "webhook.zangosen.com"
}

variable "scrape_ui_hostname" {
  description = "Scrape UI hostname (behind Access)"
  type        = string
  default     = "n8n-scrape.zangosen.com"
}

variable "scrape_webhook_hostname" {
  description = "Scrape public webhook hostname"
  type        = string
  default     = "scrape.zangosen.com"
}

variable "tunnel_id" {
  description = "Cloudflare Named Tunnel UUID used for CNAME records (e.g., 1234abcd-...)"
  type        = string
}

variable "proxied" {
  description = "Whether Cloudflare should proxy the records (orange cloud)"
  type        = bool
  default     = true
}

variable "email_domain" {
  description = "Email domain allowed to access (e.g., zangosen.com)"
  type        = string
}

variable "session_duration" {
  description = "Access session duration (e.g., 24h)"
  type        = string
  default     = "24h"
}
