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

# public subnets get .0 and .1 
# private subnets get .10 and .11

resource "aws_subnet" "public_a" {
    vpc_id = aws_vpc.main.id # Reference that wires the subnet to the vpc
    
    cidr_block = "10.0.0.0/24" # public so it gets .0
    
    availability_zone = "eu-west-1a" # Which building it is on

    tags = { Name = "trijo-adijo-public-a" }
}

resource "aws_subnet" "private_a" {
    vpc_id = aws_vpc.main.id

    cidr_block = "10.0.10.0/24" # private so it gets .10

    availability_zone = "eu-west-1a"

    tags = { Name = "trijo-adijo-private-a" }
}

# -- -- #