# =============================================================================
# AKS Module — Hippogriff
# Two node pools: system (B2s on-demand) + app (B2s spot)
# Spot instances cut cost by ~70%. Evictions just reschedule pods — useful
# chaos demo in itself.
# =============================================================================

resource "azurerm_kubernetes_cluster" "main" {
  name                = var.cluster_name
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = var.cluster_name
  kubernetes_version  = var.kubernetes_version

  # System node pool — on-demand, always available
  default_node_pool {
    name                = "system"
    node_count          = 1
    vm_size             = "Standard_B2ps_v2"
    os_disk_size_gb     = 30
    type                = "VirtualMachineScaleSets"
    only_critical_addons_enabled = false
    temporary_name_for_rotation  = "tmpnodepool"

    node_labels = {
      "nodepool-type" = "system"
      "environment"   = "dev"
    }
  }

  identity {
    type = "SystemAssigned"
  }

  # Enable OIDC issuer for workload identity (future use)
  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
    outbound_type     = "loadBalancer"
  }

  # Enable monitoring addon (feeds Azure Monitor / Container Insights)
  oms_agent {
    log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  }

  tags = var.tags
}

# Application node pool — spot instances for cost savings
resource "azurerm_kubernetes_cluster_node_pool" "app" {
  name                  = "app"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.main.id
  vm_size               = "Standard_B2ps_v2"
  node_count            = 2
  os_disk_size_gb       = 30

  priority        = "Spot"
  eviction_policy = "Delete"
  spot_max_price  = -1 # Pay current spot price up to on-demand price

  node_labels = {
    "nodepool-type"                         = "app"
    "environment"                           = "dev"
    "kubernetes.azure.com/scalesetpriority" = "spot"
  }

  node_taints = [
    "kubernetes.azure.com/scalesetpriority=spot:NoSchedule"
  ]

  tags = var.tags
}

# Attach ACR to AKS (allows pulling images without explicit auth)
resource "azurerm_role_assignment" "aks_acr_pull" {
  principal_id                     = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
  role_definition_name             = "AcrPull"
  scope                            = var.acr_id
  skip_service_principal_aad_check = true
}

# Log Analytics Workspace for Azure Monitor / Container Insights
resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.cluster_name}-logs"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = var.tags
}
