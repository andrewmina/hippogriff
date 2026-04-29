data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                        = var.name
  location                    = var.location
  resource_group_name         = var.resource_group_name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"
  soft_delete_retention_days  = 7
  purge_protection_enabled    = false

  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id

    secret_permissions = ["Get", "List", "Set", "Delete", "Purge"]
  }

  tags = var.tags
}

resource "azurerm_key_vault_secret" "dd_api_key" {
  name         = "dd-api-key"
  value        = var.dd_api_key
  key_vault_id = azurerm_key_vault.main.id
}

resource "azurerm_key_vault_secret" "dd_app_key" {
  name         = "dd-app-key"
  value        = var.dd_app_key
  key_vault_id = azurerm_key_vault.main.id
}

resource "azurerm_key_vault_secret" "anthropic_api_key" {
  name         = "anthropic-api-key"
  value        = var.anthropic_api_key
  key_vault_id = azurerm_key_vault.main.id
}

variable "name" { type = string }
variable "resource_group_name" { type = string }
variable "location" { type = string }
variable "dd_api_key" { type = string; sensitive = true }
variable "dd_app_key" { type = string; sensitive = true }
variable "anthropic_api_key" { type = string; sensitive = true }
variable "tags" { type = map(string); default = {} }

output "key_vault_id" { value = azurerm_key_vault.main.id }
output "key_vault_uri" { value = azurerm_key_vault.main.vault_uri }
