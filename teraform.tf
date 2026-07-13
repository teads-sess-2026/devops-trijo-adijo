terraform {
  required_providers {
		aws {
			source = "hashicorp/aws"
			version = "~> 6.54"	
		}
		kubernetes {
			source = "hashicorp/kubernetes"
			version = "~> 3.2"
		}
	}
	required_version = ">= 0.12"
}
