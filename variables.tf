variable "cluster_name" {
  description = "EKS cluster name — used for subnet discovery tags"
  type        = string
  default     = "trijo-adijo"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}
