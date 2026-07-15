# flux.tf
# 1. Bootstraps Flux - basically a GitOps thingamajig that watches a GitHub repo and applies manifests to the cluster.
# 2. For us we need it to install the kube-prometheus-stack Helm thingamajig
# 3. Needs repo url and token, which we provide via variable that reads enviroment variable when terraform init

# Also doing all of this this way so that if someone deletes the kube-prometheus-stack FLUX installs it automatically

resource "flux_bootstrap_git" "main" {
  path = "kubernetes/clusters/trijo-adijo"
  depends_on = [aws_eks_node_group.main]
}

# -- -- #
