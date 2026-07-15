#!/bin/bash
# Simulates AZ-B outage for the ping app demo

# First print out where the pods are currently running 
kubectl get pods -n default -l app=ping -o wide
# where the pods are on AZ a it says 10.0.10.xx
# where the pods are on AZ b it says 10.0.11.xx

# Find AZ-B node
AZ_B_NODE=$(kubectl get nodes -L topology.kubernetes.io/zone --no-headers | grep "eu-west-1b" | awk '{print $1}')
echo "AZ-B node: $AZ_B_NODE"

# Cordon AZ-B node so ping pods can't reschedule there
kubectl cordon $AZ_B_NODE

# Delete only ping pods on AZ-B node — they reschedule on AZ-A
kubectl delete pods -n default -l app=ping --field-selector spec.nodeName=$AZ_B_NODE

echo "=== AZ-B ping pods killed. Watch Grafana for recovery on AZ-A ==="
echo "To restore: kubectl uncordon $AZ_B_NODE"

#Wait 5 seconds for pods to reschedule on AZ-A
echo ""
echo "Waiting 5 seconds for pods to reschedule on AZ-A..."
sleep 5
echo ""
# show pods switched to AZ-A
kubectl get pods -n default -l app=ping -o wide

# wait 10 seconds and then Restore AZ-B node so pods can schedule there again
sleep 10

# Find AZ-B node
AZ_B_NODE=$(kubectl get nodes -L topology.kubernetes.io/zone --no-headers | grep "eu-west-1b" | awk '{print $1}')
echo "AZ-B node: $AZ_B_NODE"

# Uncordon AZ-B node so pods can schedule there again
kubectl uncordon $AZ_B_NODE

# Restart ping deployment so pods spread back across AZ-A and AZ-B

kubectl rollout restart deployment/ping -n default

# Wait 5 seconds for pods to reschedule on AZ-B
echo ""
sleep 10
# show pods switched to AZ-B
kubectl get pods -n default -l app=ping -o wide
