"""Score the teacher (same prompt and settings as the labelling) on validation.jsonl.
Usage: python3 scripts/eval_teacher.py     (needs Ollama running; takes several minutes)
Writes results/teacher_predictions.jsonl and results/teacher_validation.json
"""
import json, os, subprocess, sys, time, urllib.request

URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
PROMPT = open("prompts/teacher_prompt.txt", encoding="utf-8").read()
gold = [json.loads(l) for l in open("data/validation.jsonl", encoding="utf-8") if l.strip()]


def ask(text):
    body = {"model": "phi3.5", "prompt": PROMPT + "Command: " + text + "\nJSON:", "stream": False,
            "options": {"temperature": 0, "seed": 42, "num_predict": 80, "stop": ["\n\n"]}}
    req = urllib.request.Request(URL + "/api/generate", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["response"]


os.makedirs("results", exist_ok=True)
t0 = time.time()
with open("results/teacher_predictions.jsonl", "w", encoding="utf-8") as f:
    for i, g in enumerate(gold, 1):
        f.write(json.dumps({"id": g["id"], "prediction": ask(g["text"])}) + "\n")
        f.flush()
        if i % 10 == 0:
            print(f"{i}/{len(gold)}  {(time.time() - t0) / i:.1f}s each", flush=True)
subprocess.run([sys.executable, "tools/score.py", "results/teacher_predictions.jsonl",
                "data/validation.jsonl", "--out", "results/teacher_validation.json"])
