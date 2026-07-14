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

# Chose the following rules :
# public subnets get .0 and .1 
# private subnets get .10 and .11
# (Same as pdf pg 5/6)

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

resource "aws_subnet" "public_b" {
    vpc_id = aws_vpc.main.id

    cidr_block = "10.0.1.0/24" 

    availability_zone = "eu-west-1b"

    tags = { Name = "trijo-adijo-public-b" }
}

resource "aws_subnet" "private_b" {
    vpc_id = aws_vpc.main.id

    cidr_block = "10.0.11.0/24" 

    availability_zone = "eu-west-1b"

    tags = { Name = "trijo-adijo-private-b" }
}

# -- -- #

# -- Internet gateway -- #

# wo-way internet access, plus 1:1 NAT

resource "aws_internet_gateway" "main" {
    vpc_id = aws_vpc.main.id

    tags = { Name = "trijo-adijo-gate" }
}

# -- -- #

# -- Route tables -- #

# the important part that tells us which subnet is private and which public
# routes traffic 

# - Public - #

resource "aws_route_table" "public" { # attached to the VPC, on its own only has automatic local route
    vpc_id = aws_vpc.main.id

    tags = { Name = "trijo-adijo-rtable-pub" }
}

resource "aws_route" "public_internet" {
    route_table_id         = aws_route_table.public.id
    destination_cidr_block = "0.0.0.0/0" # any address anywhere -> makes this subnet public 
    gateway_id             = aws_internet_gateway.main.id
}

resource "aws_route_table_association" "public_a" {
    subnet_id      = aws_subnet.public_a.id
    route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
    subnet_id      = aws_subnet.public_b.id
    route_table_id = aws_route_table.public.id
}

# --- NAT networking --- #
resource "aws_eip" "nat" {
    domain = "vpc"

    tags = { Name = "trijo-adijo-nat-eip" }
}

# Single NAT in public_a — both private subnets route through it
# Trade-off: cheaper but AZ-a failure takes down outbound for AZ-b too
resource "aws_nat_gateway" "main" {
    allocation_id = aws_eip.nat.id
    subnet_id     = aws_subnet.public_a.id

    tags = { Name = "trijo-adijo-nat" }

    depends_on = [aws_internet_gateway.main]
}

resource "aws_route_table" "private" {
    vpc_id = aws_vpc.main.id

    tags = { Name = "trijo-adijo-rtable-priv" }
}

resource "aws_route" "private_nat" {
    route_table_id         = aws_route_table.private.id
    destination_cidr_block = "0.0.0.0/0"
    nat_gateway_id         = aws_nat_gateway.main.id
}

resource "aws_route_table_association" "private_a" {
    subnet_id      = aws_subnet.private_a.id
    route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_b" {
    subnet_id      = aws_subnet.private_b.id
    route_table_id = aws_route_table.private.id
}
