terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
    azuread = {
      source = "hashicorp/azuread"
    }
    datadog = {
      source = "DataDog/datadog"
    }
  }
}

# =============================================================================
# Datadog Azure Integration Module
# Wires the Azure subscription into Datadog for:
#   - Azure Monitor metrics
#   - Resource inventory
#   - CSPM findings
#   - Container Insights
# =============================================================================

resource "azuread_application" "datadog" {
  display_name = "datadog-hippogriff-${var.environment}"
}

resource "azuread_service_principal" "datadog" {
  client_id = azuread_application.datadog.client_id
}

resource "azuread_service_principal_password" "datadog" {
  service_principal_id = azuread_service_principal.datadog.id
  end_date_relative    = "8760h"
}

resource "azurerm_role_assignment" "datadog_reader" {
  scope                = "/subscriptions/${var.subscription_id}"
  role_definition_name = "Reader"
  principal_id         = azuread_service_principal.datadog.object_id
}

resource "azurerm_role_assignment" "datadog_monitoring_reader" {
  scope                = "/subscriptions/${var.subscription_id}"
  role_definition_name = "Monitoring Reader"
  principal_id         = azuread_service_principal.datadog.object_id
}

resource "datadog_integration_azure" "main" {
  tenant_name   = azuread_service_principal.datadog.application_tenant_id
  client_id     = azuread_application.datadog.client_id
  client_secret = azuread_service_principal_password.datadog.value
  host_filters  = "environment:${var.environment}"
}

variable "subscription_id" {
  type = string
}
variable "environment" {
  type = string
}
variable "dd_api_key" {
  type      = string
  sensitive = true
}
variable "dd_app_key" {
  type      = string
  sensitive = true
}
variable "dd_site" {
  type    = string
  default = "datadoghq.com"
}
variable "tags" {
  type    = map(string)
  default = {}
}

output "datadog_client_id" {
  value = azuread_application.datadog.client_id
}
