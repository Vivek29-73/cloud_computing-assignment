"""Run the teacher on the first N validation commands and score the replies.
Usage: python3 scripts/test_teacher.py 20
"""
import json, os, subprocess, sys, time, urllib.request

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
PROMPT = open("prompts/teacher_prompt.txt", encoding="utf-8").read()
gold = [json.loads(l) for l in open("data/validation.jsonl", encoding="utf-8") if l.strip()][:N]

def ask(text):
    body = {
        "model": "phi3.5",
        "prompt": PROMPT + "Command: " + text + "\nJSON:",
        "stream": False,
        "options": {"temperature": 0, "seed": 42, "num_predict": 80, "stop": ["\n\n"]},
    }
    req = urllib.request.Request(URL + "/api/generate", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["response"]

os.makedirs("results", exist_ok=True)
preds = []
t0 = time.time()
for i, g in enumerate(gold, 1):
    t = time.time()
    out = ask(g["text"])
    preds.append({"id": g["id"], "prediction": out.strip()})
    print(f"{i}/{N}  {time.time()-t:.1f}s  {g['text']}  ->  {out.strip()}")
print(f"average {(time.time()-t0)/N:.1f}s per command")

with open("results/teacher_test_preds.jsonl", "w", encoding="utf-8") as f:
    for p in preds:
        f.write(json.dumps(p) + "\n")
with open("results/teacher_test_gold.jsonl", "w", encoding="utf-8") as f:
    for g in gold:
        f.write(json.dumps(g) + "\n")
subprocess.run([sys.executable, "tools/score.py",
                "results/teacher_test_preds.jsonl", "results/teacher_test_gold.jsonl"])
