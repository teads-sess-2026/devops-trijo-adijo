#!/bin/bash
# Simulates AZ-B outage for the ping app demo

# Find AZ-B node
AZ_B_NODE=$(kubectl get nodes -L topology.kubernetes.io/zone --no-headers | grep "eu-west-1b" | awk '{print $1}')
echo "AZ-B node: $AZ_B_NODE"

# Cordon AZ-B node so ping pods can't reschedule there
kubectl cordon $AZ_B_NODE

# Delete only ping pods on AZ-B node — they reschedule on AZ-A
kubectl delete pods -n default -l app=ping --field-selector spec.nodeName=$AZ_B_NODE

echo "=== AZ-B ping pods killed. Watch Grafana for recovery on AZ-A ==="
echo "To restore: kubectl uncordon $AZ_B_NODE"
