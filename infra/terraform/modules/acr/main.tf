resource "azurerm_container_registry" "main" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Basic"
  admin_enabled       = false

  tags = var.tags
}

variable "name" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "location" {
  type = string
}
variable "tags" {
  type    = map(string)
  default = {}
}

output "registry_id" {
  value = azurerm_container_registry.main.id
}
output "login_server" {
  value = azurerm_container_registry.main.login_server
}
output "name" {
  value = azurerm_container_registry.main.name
}
