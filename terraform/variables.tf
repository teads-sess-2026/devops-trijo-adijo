variable "team_name" {
  description = "team name - always tag resources with this"
  type        = string
  default     = "trijo-adijo"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "trijo-adijo-eks-cluster"
}