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

# -- kube-prometheus-stack -- #
# The fancy thing that combines Prometheus, Grafana.
# HelmRepository tells Flux where to find the chart.
# It also pushes a bunch of manifests - YAMLs of what we are running on cluster.
resource "kubectl_manifest" "prometheus_helmrepository" {
  yaml_body = <<-YAML
    apiVersion: source.toolkit.fluxcd.io/v1
    kind: HelmRepository
    metadata:
      name: prometheus-community
      namespace: flux-system
    spec:
      interval: 1h
      url: https://prometheus-community.github.io/helm-charts
  YAML

  depends_on = [flux_bootstrap_git.main]
}

# HelmRelease tells Flux which chart version to install and with what values.
resource "kubectl_manifest" "prometheus_helmrelease" {
  yaml_body = <<-YAML
    apiVersion: helm.toolkit.fluxcd.io/v2
    kind: HelmRelease
    metadata:
      name: kube-prometheus-stack
      namespace: monitoring
    spec:
      interval: 1h
      chart:
        spec:
          chart: kube-prometheus-stack
          version: ">=60.0.0 <70.0.0"
          sourceRef:
            kind: HelmRepository
            name: prometheus-community
            namespace: flux-system
          interval: 1h
      install:
        createNamespace: true
      values:
        grafana:
          enabled: true
        prometheus:
          enabled: true
        alertmanager:
          enabled: true
  YAML

  depends_on = [kubectl_manifest.prometheus_helmrepository]
}

# -- -- #
