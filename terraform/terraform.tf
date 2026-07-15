# This file holds the setup
# It is what terraform itself needs to run :
# - provider versions
# - backend
# - provider config


terraform {
  required_providers {
		aws = {
			source = "hashicorp/aws"
			version = "~> 6.0"	# Allow versions 6 -> 7
		}
		flux = {
			source  = "fluxcd/flux"
			version = "~> 1.4"
		}
		github = {
			source  = "integrations/github"
			version = "~> 6.0"
		}
		kubectl = {
			source  = "gavinbunney/kubectl"
			version = "~> 1.14"
		}
	}
	backend "s3" {
		bucket = "trijo-adijo-tfstate"
		key = "vpc-eks/terraform.tfstate"
		region = "eu-west-1"
		encrypt = true
		use_lockfile = true   # native S3 locking (Terraform 1.11+, DynamoDB ni potreben)
  	}
	required_version = ">= 1.15" # Minimum required version is 1.15
}


## -- Provider config block -- ##

provider "aws" {
  region = "eu-west-1"
  profile = "summer-school"
}



## -- Added this Alja -- ##

provider "github" {
  owner = "teads-sess-2026"
  token = var.github_token
}

provider "flux" {
  kubernetes = {
    config_path = "~/.kube/config"
  }
  git = {
    url = "https://github.com/teads-sess-2026/devops-trijo-adijo.git"
    http = {
      username = "git"
      password = var.github_token
    }
  }
}

provider "kubectl" {
  config_path = "~/.kube/config"
}