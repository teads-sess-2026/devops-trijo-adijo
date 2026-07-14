terraform {
  backend "s3" {
    bucket       = "trijo-adijo-tfstate"
    key          = "vpc-eks/terraform.tfstate"
    region       = "eu-west-1"
    encrypt      = true
    use_lockfile = true   # native S3 locking (Terraform 1.11+, DynamoDB ni potreben)
  }
}