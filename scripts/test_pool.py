"""Spot-check the teacher on unlabelled pool commands (no gold labels needed).
Usage: python3 scripts/test_pool.py 10
Checks each reply against the cleaning rules: valid JSON, exact four keys,
known intent, slot values that appear in the command.
"""
import json, os, sys, time, urllib.request

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
PROMPT = open("prompts/teacher_prompt.txt", encoding="utf-8").read()
INTENTS = {"alarm_set", "alarm_query", "calendar_set", "calendar_query",
           "calendar_remove", "weather_query", "datetime_query", "recommendation_events"}
pool = [json.loads(l) for l in open("data/commands_pool.jsonl", encoding="utf-8") if l.strip()]
step = max(1, len(pool) // N)
sample = pool[::step][:N]


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


def problem(text, raw):
    try:
        obj = json.loads(raw.strip())
    except json.JSONDecodeError:
        return "not valid JSON"
    if not isinstance(obj, dict) or set(obj) != {"intent", "date", "time", "place"}:
        return "wrong keys"
    if obj["intent"] not in INTENTS:
        return "unknown intent"
    for k in ("date", "time", "place"):
        v = obj[k]
        if v is not None and (not isinstance(v, str) or v not in text):
            return f"{k} not in command"
    return None


bad = 0
t0 = time.time()
for i, rec in enumerate(sample, 1):
    out = ask(rec["text"]).strip()
    p = problem(rec["text"], out)
    bad += p is not None
    print(f"{i}/{len(sample)} [{'OK' if p is None else 'BAD: ' + p}]  {rec['text']}  ->  {out}", flush=True)
print(f"{bad} of {len(sample)} would be rejected by the cleaning rules; "
      f"average {(time.time() - t0) / len(sample):.1f}s per command")
