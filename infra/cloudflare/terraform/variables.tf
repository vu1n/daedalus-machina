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

variable "email_domain" {
  description = "Email domain allowed to access (e.g., zangosen.com)"
  type        = string
}

variable "session_duration" {
  description = "Access session duration (e.g., 24h)"
  type        = string
  default     = "24h"
}

