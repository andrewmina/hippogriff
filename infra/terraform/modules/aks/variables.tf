variable "cluster_name" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "location" {
  type = string
}
variable "acr_id" {
  type = string
}
variable "kubernetes_version" {
  type    = string
  default = "1.33.6"
}
variable "tags" {
  type    = map(string)
  default = {}
}
