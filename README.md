# Command parser: knowledge distillation and deployment on local Kubernetes

GitHub: https://github.com/Vivek29-73/cloud_computing-assignment

A small voice-assistant command parser. Phi-3.5 (teacher, Ollama) labels 3,000 commands; EleutherAI/pythia-70m (student) is fine-tuned on the first 1,500 cleaned labels (sequence-level distillation) and served by a FastAPI service on a local k3d cluster, with model weights in SeaweedFS (S3-compatible, not AWS).

## Layout
`prompts/` teacher prompt | `worker/` labelling worker and cleaning | `training/` config and train.py | `scripts/` evaluation, S3 and secret helpers | `service/` FastAPI app and Dockerfile | `k8s/` manifests | `cluster/k3d.yaml` | `network/` NACL and subnets | `tools/` provided scoring, load test, NACL simulator | `tests/` unit tests | `results/` evidence | `.github/workflows/ci.yml`

## Prerequisites
Windows with WSL2 Ubuntu 24.04 (cgroup v2: `.wslconfig` with `kernelCommandLine = cgroup_no_v1=all`), Docker, Ollama (inside Ubuntu, `ollama pull phi3.5`), k3d, kubectl, Python 3.12.

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install torch==2.5.1+cpu --extra-index-url https://download.pytorch.org/whl/cpu
pip install transformers==4.46.3 PyYAML==6.0.2 numpy==1.26.4 boto3==1.35.99 locust ruff==0.8.4 pytest==8.3.4
```

## Teacher labelling and cleaning
```bash
SHARD_INDEX=0 SHARD_COUNT=2 python3 worker/worker.py   # and SHARD_INDEX=1 in a second terminal
python3 worker/clean.py                                 # writes output/v1/train.jsonl and train.sha256
```

## Train and evaluate
```bash
make train SUBSET=50                          # quick check
make train                                    # v1 -> models_local/v1, release/model-v1.tar
make train CONFIG=training/config_v2.yaml     # v2
python3 scripts/eval_teacher.py
python3 scripts/eval_student.py models_local/v1 student_v1
python3 scripts/eval_student.py EleutherAI/pythia-70m base_pythia
```
Model files are not in Git; `model-v1.tar` is a GitHub Release asset and its SHA-256 equals `models/v1/model.sha256`.

## Cluster, storage and deployment
```bash
k3d cluster create --config cluster/k3d.yaml
bash scripts/seaweed_secrets.sh                 # S3 credentials as Kubernetes Secrets (nothing written to disk)
kubectl apply -f k8s/seaweedfs.yaml
kubectl -n data port-forward svc/seaweedfs 8333:8333 &
export AWS_ACCESS_KEY_ID=$(kubectl -n data get secret s3-credentials -o jsonpath='{.data.AWS_ACCESS_KEY_ID}' | base64 -d)
export AWS_SECRET_ACCESS_KEY=$(kubectl -n data get secret s3-credentials -o jsonpath='{.data.AWS_SECRET_ACCESS_KEY}' | base64 -d)
python3 scripts/s3_tool.py make-buckets
python3 scripts/s3_tool.py put-dir models_local/v1 models v1
python3 scripts/s3_tool.py put-dir models_local/v2 models v2
docker build -f service/Dockerfile -t command-parser:v2 .       # image has no model weights
k3d image import command-parser:v2 -c cloudlab
kubectl apply -f k8s/app.yaml -f k8s/hpa.yaml
```
(The AWS_* names are only the standard S3 variable names; they hold random local SeaweedFS credentials, not Amazon credentials.)

## Test
```bash
curl -i -X POST http://localhost:8080/parse -H 'Content-Type: application/json' -d '{"text":"what is the weather in london"}'
locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 2m --host http://localhost:8080 --csv results/loadtest
python3 tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check
ruff check . && pytest -q tests
```
`FAULT_INJECT=1` makes the service return HTTP 500 `{"error":"invalid_model_output"}`.

## Tear down
```bash
k3d cluster delete cloudlab
```

## Results (100 validation commands)
| Model | JSON validity | Full frame |
|---|---|---|
| Teacher phi3.5 | 100% | 53% |
| Untrained Pythia-70M | 0% | 0% |
| Student v1 | 100% | 57% |
| Student v2 | 100% | 56% |

Load test (2 min, 4 users): 109 requests, 1.83% failures, median 4.5 s, p95 7.9 s, 0.94 req/s; cost about 2.33 INR per 1,000 requests (see `results/load_test_summary.md`).

## Limitations
Single-node k3d on one laptop (no multi-machine fault tolerance); 100 validation examples make accuracy numbers noisy; the load test did not meet the 1% error / 5 s p95 targets.
