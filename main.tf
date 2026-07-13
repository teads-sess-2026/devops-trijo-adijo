# This file holds the actual infra

# -- AWS vpc -- #

resource "aws_vpc" "main" { # named main for now change later if needed
    cidr_block = "10.0.0.0/16"

    # The following are there to make the VPC's internal DNS work
    # Without theese instances don't get internal DNS names
    # Makes EKS sad !!
    enable_dns_support = true # defaults to true
    enable_dns_hostnames = true # defaults to false 

    tags = { Name = "trijo-adijo"}
}

# -- -- #

# -- AWS subnets -> 2 x public, 2 x private -- #

resource "aws_subnet" "public_a" {
    vpc_id = aws_vpc.main.id
    cidr_block = "10.0.0.0/24"
    availability_zone = "eu-west-1a"
}

# -- -- #