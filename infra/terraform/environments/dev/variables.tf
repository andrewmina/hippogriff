variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "dd_api_key" {
  description = "Datadog API key"
  type        = string
  sensitive   = true
}

variable "dd_app_key" {
  description = "Datadog application key"
  type        = string
  sensitive   = true
}

variable "dd_site" {
  description = "Datadog site"
  type        = string
  default     = "datadoghq.com"
}

variable "anthropic_api_key" {
  description = "Anthropic API key for tip-assistant service"
  type        = string
  sensitive   = true
}

variable "project" {
  description = "Project name, used as resource prefix"
  type        = string
  default     = "hippogriff"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "region" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}
