terraform {
  required_version = ">= 1.6"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.95"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.47"
    }
    datadog = {
      source  = "DataDog/datadog"
      version = "~> 3.37"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
  }

  # Uncomment after first apply to enable remote state in Azure Blob
  # backend "azurerm" {
  #   resource_group_name  = "hippogriff-tfstate-rg"
  #   storage_account_name = "hippogrifftfstate"
  #   container_name       = "tfstate"
  #   key                  = "dev/terraform.tfstate"
  # }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }
  subscription_id = var.subscription_id
}

provider "azuread" {}

provider "datadog" {
  api_key = var.dd_api_key
  app_key = var.dd_app_key
  api_url = "https://api.${var.dd_site}"
}

provider "kubernetes" {
  config_path    = "~/.kube/config"
  config_context = "hippogriff-dev"
}

provider "helm" {
  kubernetes {
    config_path    = "~/.kube/config"
    config_context = "hippogriff-dev"
  }
}

# =============================================================================
# Resource Group
# =============================================================================

resource "azurerm_resource_group" "main" {
  name     = "${var.project}-${var.environment}-rg"
  location = var.region

  tags = local.common_tags
}

# =============================================================================
# Modules
# =============================================================================

module "acr" {
  source              = "../../modules/acr"
  name                = "${var.project}acr${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.region
  tags                = local.common_tags
}

module "keyvault" {
  source              = "../../modules/keyvault"
  name                = "${var.project}-kv-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.region
  dd_api_key          = var.dd_api_key
  dd_app_key          = var.dd_app_key
  anthropic_api_key   = var.anthropic_api_key
  tags                = local.common_tags
}

module "aks" {
  source              = "../../modules/aks"
  cluster_name        = "${var.project}-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.region
  acr_id              = module.acr.registry_id
  tags                = local.common_tags
}

module "datadog_azure" {
  source          = "../../modules/datadog-azure"
  subscription_id = var.subscription_id
  environment     = var.environment
  dd_api_key      = var.dd_api_key
  dd_app_key      = var.dd_app_key
  dd_site         = var.dd_site
  tags            = local.common_tags
}

# =============================================================================
# Kubernetes namespaces
# =============================================================================

resource "kubernetes_namespace" "hippogriff" {
  metadata {
    name = "hippogriff"
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "environment"                  = var.environment
    }
  }
  depends_on = [module.aks]
}

resource "kubernetes_namespace" "datadog" {
  metadata {
    name = "datadog"
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }
  depends_on = [module.aks]
}

# =============================================================================
# Datadog Operator + Agent (via Helm)
# =============================================================================

resource "helm_release" "datadog_operator" {
  name             = "datadog-operator"
  repository       = "https://helm.datadoghq.com"
  chart            = "datadog-operator"
  version          = "1.4.0"
  namespace        = kubernetes_namespace.datadog.metadata[0].name
  create_namespace = false

  set {
    name  = "replicaCount"
    value = "1"
  }

  depends_on = [kubernetes_namespace.datadog]
}

# Datadog API/App keys as K8s secret (read from Key Vault via Terraform)
resource "kubernetes_secret" "datadog_keys" {
  metadata {
    name      = "datadog-secret"
    namespace = kubernetes_namespace.datadog.metadata[0].name
  }

  data = {
    api-key = var.dd_api_key
    app-key = var.dd_app_key
  }

  depends_on = [kubernetes_namespace.datadog]
}

# Anthropic key for tip-assistant
resource "kubernetes_secret" "anthropic_key" {
  metadata {
    name      = "anthropic-secret"
    namespace = kubernetes_namespace.hippogriff.metadata[0].name
  }

  data = {
    api-key = var.anthropic_api_key
  }

  depends_on = [kubernetes_namespace.hippogriff]
}

# DatadogAgent CRD — installs the agent DaemonSet + Cluster Agent
resource "helm_release" "datadog_agent" {
  name      = "datadog-agent"
  chart     = "${path.module}/../../../../infra/k8s/datadog-operator/datadog-agent"
  namespace = kubernetes_namespace.datadog.metadata[0].name

  set {
    name  = "ddApiKeySecretName"
    value = kubernetes_secret.datadog_keys.metadata[0].name
  }

  depends_on = [
    helm_release.datadog_operator,
    kubernetes_secret.datadog_keys,
  ]
}
