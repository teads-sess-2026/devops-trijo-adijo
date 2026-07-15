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

variable "github_token" {
  #read from environment variable GITHUB_TOKEN or if that doesnt work 
  description = "GitHub personal access token with repo scope (used by Flux bootstrap)"
  type        = string
  default     = "trijo-adijo"
  sensitive   = true
}

