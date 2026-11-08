"""Score a causal LM (trained student or untrained base) on validation.jsonl.
Usage: python3 scripts/eval_student.py <model dir or HF name> <label>
  python3 scripts/eval_student.py models_local/v1 student_v1
  python3 scripts/eval_student.py EleutherAI/pythia-70m base_pythia
Writes results/<label>_raw.jsonl (full generated text), results/<label>_predictions.jsonl
(text up to the first newline, which is what is scored) and results/<label>_validation.json
"""
import json, os, subprocess, sys, time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_path, label = sys.argv[1], sys.argv[2]
max_new = int(os.environ.get("MAX_NEW_TOKENS", "80"))
gold = [json.loads(l) for l in open("data/validation.jsonl", encoding="utf-8") if l.strip()]

tok = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(model_path)
model.eval()

os.makedirs("results", exist_ok=True)
t0 = time.time()
with open(f"results/{label}_raw.jsonl", "w", encoding="utf-8") as raw_f, \
     open(f"results/{label}_predictions.jsonl", "w", encoding="utf-8") as pred_f:
    for i, g in enumerate(gold, 1):
        enc = tok("Command: " + g["text"] + "\nJSON:", return_tensors="pt")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_new, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        text = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        raw_f.write(json.dumps({"id": g["id"], "raw": text}) + "\n")
        pred_f.write(json.dumps({"id": g["id"], "prediction": text.split("\n")[0].strip()}) + "\n")
        if i % 25 == 0:
            print(f"{i}/{len(gold)}  {(time.time() - t0) / i:.1f}s each", flush=True)
subprocess.run([sys.executable, "tools/score.py", f"results/{label}_predictions.jsonl",
                "data/validation.jsonl", "--out", f"results/{label}_validation.json"])
