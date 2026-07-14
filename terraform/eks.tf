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
    name = "${var.cluster_name}-role"
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
    name = var.cluster_name
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

    tags = { Name = var.cluster_name }
}

# -- -- #

# =============================================================================
# WORKER NODES
# =============================================================================
# The control plane (above) is the Kubernetes brain — it runs the API server,
# scheduler, and etcd. Worker nodes are the EC2 instances that actually run
# your pods. They are separate from the control plane and need their own IAM
# role, because they authenticate to AWS as EC2 instances, not as EKS.

# -- Node IAM role -- #

# Same pattern as the cluster role above: define WHO can assume it first.
# Here the principal is ec2.amazonaws.com because worker nodes ARE EC2 instances.
data "aws_iam_policy_document" "eks_node_assume" {
    statement {
        actions = ["sts:AssumeRole"]

        principals {
            type        = "Service"
            identifiers = ["ec2.amazonaws.com"]
        }
    }
}

resource "aws_iam_role" "eks_node" {
    name = "${var.team_name}-eks-node-role"
    assume_role_policy = data.aws_iam_policy_document.eks_node_assume.json

    # Same boundary as the cluster role — required by the account's permission policy.
    permissions_boundary = "arn:aws:iam::937697200280:policy/summer-school-ljubljana-boundary"
}

# --- Policy 1: lets the node register itself with the EKS control plane ---
# Without this the node can't join the cluster at all.
resource "aws_iam_role_policy_attachment" "eks_node_policy" {
    role       = aws_iam_role.eks_node.name
    policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

# --- Policy 2: VPC CNI (pod networking) ---
# The aws-node DaemonSet (VPC CNI plugin) runs on every worker.
# It needs to create/attach Elastic Network Interfaces so each pod gets a real
# VPC IP address. Without this policy, pod networking never comes up.
resource "aws_iam_role_policy_attachment" "eks_cni_policy" {
    role       = aws_iam_role.eks_node.name
    policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

# --- Policy 3: pull images from ECR ---
# Nodes need to authenticate to ECR to pull the core EKS system images
# (coredns, kube-proxy, VPC CNI). Read-only is enough — nodes never push.
resource "aws_iam_role_policy_attachment" "eks_ecr_read" {
    role       = aws_iam_role.eks_node.name
    policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# -- -- #

# -- Managed Node Group -- #

# A "managed" node group means AWS handles the EC2 launch template, the
# Auto Scaling Group, and node lifecycle (draining before termination).
# The alternative is a "self-managed" group where you wire all of that yourself.

resource "aws_eks_node_group" "main" {
    cluster_name    = aws_eks_cluster.main.name
    node_group_name = "${var.team_name}-nodes"
    node_role_arn   = aws_iam_role.eks_node.arn

    # Private subnets only — worker nodes have no business being directly
    # internet-reachable. They reach the internet outbound via the NAT gateway.
    subnet_ids = [
        aws_subnet.private_a.id,
        aws_subnet.private_b.id,
    ]

    # t3.medium = 2 vCPU / 4 GB RAM.
    # Each node can hold ~29 pods with the VPC CNI (limited by ENI slots).
    # Fine for a learning cluster; bump to t3.large if you run memory-hungry workloads.
    instance_types = ["t3.medium"]

    scaling_config {
        desired_size = 2  # Start with one node per AZ
        min_size     = 1  # Floor: never scale below 1 (keeps cluster usable)
        max_size     = 3  # Ceiling: allow one extra for rolling updates
    }

    # CRITICAL: Terraform must attach all three policies before any node boots.
    # If you skip this, a node can come up before it has ECR or CNI permissions,
    # fail to pull system images, and get stuck in a NotReady loop.
    depends_on = [
        aws_iam_role_policy_attachment.eks_node_policy,
        aws_iam_role_policy_attachment.eks_cni_policy,
        aws_iam_role_policy_attachment.eks_ecr_read,
    ]

    tags = { Name = "${var.team_name}-nodes" }
}

# -- -- #