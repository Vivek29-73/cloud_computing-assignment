#!/usr/bin/env bash
# Creates the S3 credentials as Kubernetes Secrets. Nothing is written to disk or to Git.
# Re-running keeps the existing keys.
set -euo pipefail

for ns in data pipeline app; do
  kubectl get namespace "$ns" >/dev/null 2>&1 || kubectl create namespace "$ns"
done

if kubectl -n data get secret s3-credentials >/dev/null 2>&1; then
  ACCESS=$(kubectl -n data get secret s3-credentials -o jsonpath='{.data.AWS_ACCESS_KEY_ID}' | base64 -d)
  SECRET=$(kubectl -n data get secret s3-credentials -o jsonpath='{.data.AWS_SECRET_ACCESS_KEY}' | base64 -d)
  echo "reusing existing S3 keys"
else
  ACCESS=$(openssl rand -hex 8)
  SECRET=$(openssl rand -hex 20)
  echo "generated new S3 keys"
fi

JSON=$(printf '{"identities":[{"name":"platform","credentials":[{"accessKey":"%s","secretKey":"%s"}],"actions":["Admin","Read","Write","List","Tagging"]}]}' "$ACCESS" "$SECRET")

kubectl -n data create secret generic seaweedfs-s3-config --from-literal=s3.json="$JSON" \
  --dry-run=client -o yaml | kubectl apply -f -
for ns in data pipeline app; do
  kubectl -n "$ns" create secret generic s3-credentials \
    --from-literal=AWS_ACCESS_KEY_ID="$ACCESS" --from-literal=AWS_SECRET_ACCESS_KEY="$SECRET" \
    --dry-run=client -o yaml | kubectl apply -f -
done
