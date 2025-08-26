locals {
  tunnel_target = "${var.tunnel_id}.cfargotunnel.com"
}

resource "cloudflare_record" "n8n_ui" {
  zone_id = var.zone_id
  name    = var.ui_hostname
  type    = "CNAME"
  content = local.tunnel_target
  proxied = var.proxied
  allow_overwrite = true
}

resource "cloudflare_record" "n8n_webhook" {
  zone_id = var.zone_id
  name    = var.webhook_hostname
  type    = "CNAME"
  content = local.tunnel_target
  proxied = var.proxied
  allow_overwrite = true
}

resource "cloudflare_record" "scrape_ui" {
  zone_id = var.zone_id
  name    = var.scrape_ui_hostname
  type    = "CNAME"
  content = local.tunnel_target
  proxied = var.proxied
  allow_overwrite = true
}

resource "cloudflare_record" "scrape_webhook" {
  zone_id = var.zone_id
  name    = var.scrape_webhook_hostname
  type    = "CNAME"
  content = local.tunnel_target
  proxied = var.proxied
  allow_overwrite = true
}

