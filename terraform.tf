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
	}
	required_version = ">= 1.15" # Minimum required version is 1.15
}


## -- Provider config block -- ##

provider "aws" {
  region  = "eu-west-1"
  profile = "summer-school"
}

## -- -- ##