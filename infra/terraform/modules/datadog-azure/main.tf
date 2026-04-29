# =============================================================================
# Datadog Azure Integration Module
# Wires the Azure subscription into Datadog for:
#   - Azure Monitor metrics
#   - Resource inventory
#   - CSPM findings
#   - Container Insights
# =============================================================================

# Create the Azure AD app registration that Datadog uses to read your sub
resource "azuread_application" "datadog" {
  display_name = "datadog-hippogriff-${var.environment}"
}

resource "azuread_service_principal" "datadog" {
  client_id = azuread_application.datadog.client_id
}

resource "azuread_service_principal_password" "datadog" {
  service_principal_id = azuread_service_principal.datadog.id
  end_date_relative    = "8760h" # 1 year
}

# Grant Datadog read access to the subscription
resource "azurerm_role_assignment" "datadog_reader" {
  scope                = "/subscriptions/${var.subscription_id}"
  role_definition_name = "Reader"
  principal_id         = azuread_service_principal.datadog.object_id
}

# Also grant Monitoring Reader for deeper Azure Monitor metrics
resource "azurerm_role_assignment" "datadog_monitoring_reader" {
  scope                = "/subscriptions/${var.subscription_id}"
  role_definition_name = "Monitoring Reader"
  principal_id         = azuread_service_principal.datadog.object_id
}

# Register the integration in Datadog
resource "datadog_integration_azure" "main" {
  tenant_name   = azuread_service_principal.datadog.application_tenant_id
  client_id     = azuread_application.datadog.client_id
  client_secret = azuread_service_principal_password.datadog.value

  # Only pull metrics from resources tagged with environment=dev
  # Remove this filter to see all Azure resources
  host_filters = "environment:${var.environment}"
}

variable "subscription_id" { type = string }
variable "environment" { type = string }
variable "dd_api_key" { type = string; sensitive = true }
variable "dd_app_key" { type = string; sensitive = true }
variable "dd_site" { type = string; default = "datadoghq.com" }
variable "tags" { type = map(string); default = {} }

output "datadog_client_id" {
  value = azuread_application.datadog.client_id
}
