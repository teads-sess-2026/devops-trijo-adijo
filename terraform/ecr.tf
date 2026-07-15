resource "aws_ecr_repository" "ping" {
    name                 = "${var.team_name}/ping"
    image_tag_mutability = "IMMUTABLE"

    image_scanning_configuration {
        scan_on_push = true
    }

    tags = { Name = "${var.team_name}-ping" }
}

output "ecr_repository_url" {
    value = aws_ecr_repository.ping.repository_url
}