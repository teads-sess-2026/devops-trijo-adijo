# EKS file 
# holds all of the config for the eks cluster

# -- EKS -- #
# The trust policy: WHO is allowed to assume this role.
# Here: the EKS service itself.

data "aws_iam_policy_document" "eks_cluster_assume" {
    statement {
        actions = ["sts:AssumeRole"]

        principals {
            type        = "Service"
            identifiers = ["eks.amazonaws.com"]
        }
    }
}

resource "aws_iam_role" "eks_cluster" {
    name = "trijo-adijo-eks-cluster-role"
    assume_role_policy = data.aws_iam_policy_document.eks_cluster_assume.json
    permissions_boundary = "arn:aws:iam::937697200280:policy/summer-school-ljubljana-boundary"
}

# The permissions: WHAT the role can do.
# AWS provides a managed policy with exactly the cluster's needs.
resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
    role       = aws_iam_role.eks_cluster.name
    policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

# -- -- #

# -- EKS cluster (control plane) -- #

resource "aws_eks_cluster" "main" {
    name = "trijo-adijo"
    role_arn = aws_iam_role.eks_cluster.arn

    version = "1.36"

    vpc_config {
        subnet_ids = [
            aws_subnet.private_a.id,
            aws_subnet.private_b.id,
            aws_subnet.public_a.id,
            aws_subnet.public_b.id,
        ]
    }

    depends_on = [
        aws_iam_role_policy_attachment.eks_cluster_policy
    ]

    tags = { Name = "trijo-adijo" }
}

# -- -- #