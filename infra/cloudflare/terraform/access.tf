data "cloudflare_zone" "this" {
  zone_id = var.zone_id
}

resource "cloudflare_access_application" "n8n_ui" {
  account_id = var.account_id
  name       = "n8n-ui"
  domain     = var.ui_hostname
  session_duration = var.session_duration
  type       = "self_hosted"
}

resource "cloudflare_access_policy" "n8n_ui_allow_domain" {
  account_id     = var.account_id
  application_id = cloudflare_access_application.n8n_ui.id
  name           = "allow-${var.email_domain}"
  decision       = "allow"

  include {
    email_domain = [var.email_domain]
  }
}

