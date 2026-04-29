locals {
  common_tags = {
    project     = var.project
    environment = var.environment
    managed-by  = "terraform"
    team        = "platform"
  }
}
