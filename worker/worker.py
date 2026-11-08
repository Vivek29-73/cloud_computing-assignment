"""Teacher labelling worker.
Env: SHARD_INDEX (from 0), SHARD_COUNT, OLLAMA_URL, INPUT, OUTPUT_DIR, PROMPT_FILE, LIMIT (optional, for tests).
Takes commands whose line number (from 0) % SHARD_COUNT == SHARD_INDEX and writes
{"id","text","teacher_raw"} lines to OUTPUT_DIR/shard-<SHARD_INDEX>.jsonl.
Resumable: ids already in the output file are skipped.
"""
import json, os, time, urllib.request

INDEX = int(os.environ["SHARD_INDEX"])
COUNT = int(os.environ["SHARD_COUNT"])
URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
INPUT = os.environ.get("INPUT", "data/commands_pool.jsonl")
OUTDIR = os.environ.get("OUTPUT_DIR", "output/teacher")
PROMPT = open(os.environ.get("PROMPT_FILE", "prompts/teacher_prompt.txt"), encoding="utf-8").read()
LIMIT = int(os.environ.get("LIMIT", "0"))


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


os.makedirs(OUTDIR, exist_ok=True)
out_path = os.path.join(OUTDIR, f"shard-{INDEX}.jsonl")
done = set()
if os.path.exists(out_path):
    done = {json.loads(l)["id"] for l in open(out_path, encoding="utf-8") if l.strip()}

rows = [json.loads(l) for l in open(INPUT, encoding="utf-8") if l.strip()]
mine = [r for n, r in enumerate(rows) if n % COUNT == INDEX]
todo = [r for r in mine if r["id"] not in done]
if LIMIT:
    todo = todo[:LIMIT]
print(f"shard {INDEX}/{COUNT}: {len(mine)} commands, {len(done)} done, {len(todo)} to do", flush=True)

t0 = time.time()
with open(out_path, "a", encoding="utf-8") as f:
    for i, r in enumerate(todo, 1):
        raw = ask(r["text"])
        f.write(json.dumps({"id": r["id"], "text": r["text"], "teacher_raw": raw}) + "\n")
        f.flush()
        if i % 25 == 0 or i == len(todo):
            print(f"shard {INDEX}: {i}/{len(todo)}  {(time.time() - t0) / i:.1f}s each", flush=True)
print(f"shard {INDEX} finished", flush=True)
