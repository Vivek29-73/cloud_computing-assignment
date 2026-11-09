CONFIG ?= training/config.yaml
SUBSET ?=

.PHONY: train up down

train:
	SUBSET=$(SUBSET) python3 training/train.py $(CONFIG)

up:
	k3d cluster create --config cluster/k3d.yaml || true
	bash scripts/seaweed_secrets.sh
	kubectl apply -f k8s/seaweedfs.yaml
	kubectl -n data rollout status deployment/seaweedfs --timeout=180s
	kubectl apply -f k8s/app.yaml -f k8s/hpa.yaml

down:
	k3d cluster delete cloudlab