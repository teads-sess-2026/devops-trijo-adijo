#!/bin/bash
# Restores AZ-B after the outage demo

# Find AZ-B node
AZ_B_NODE=$(kubectl get nodes -L topology.kubernetes.io/zone --no-headers | grep "eu-west-1b" | awk '{print $1}')
echo "AZ-B node: $AZ_B_NODE"

# Uncordon AZ-B node so pods can schedule there again
kubectl uncordon $AZ_B_NODE

echo "=== AZ-B restored ==="

# Restart ping deployment so pods spread back across AZ-A and AZ-B

#   kubectl rollout restart deployment/ping -n default
#   echo "=== Done. Watch Grafana for pods rebalancing across both AZs ==="
