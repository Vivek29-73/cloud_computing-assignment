"""Clean the teacher shard outputs.
Env: SHARD_DIR (default output/teacher), OUT_DIR (default output/v1).
Rejects (checked in this order, a record is counted once, under its first reason):
  (a) reply is not valid JSON
  (b) keys are not exactly intent, date, time, place
  (c) intent is not one of the eight
  (d) a slot is neither null nor text that appears in the command
Then (e) duplicate commands among the survivors: keep the smallest id.
Writes OUT_DIR/train.jsonl (id order), OUT_DIR/train.sha256, OUT_DIR/counts.json.
"""
import glob, hashlib, json, os

SHARD_DIR = os.environ.get("SHARD_DIR", "output/teacher")
OUT_DIR = os.environ.get("OUT_DIR", "output/v1")
INTENTS = {"alarm_set", "alarm_query", "calendar_set", "calendar_query",
           "calendar_remove", "weather_query", "datetime_query", "recommendation_events"}
KEYS = {"intent", "date", "time", "place"}

records = []
for path in sorted(glob.glob(os.path.join(SHARD_DIR, "shard-*.jsonl"))):
    with open(path, encoding="utf-8") as f:
        records += [json.loads(l) for l in f if l.strip()]
records.sort(key=lambda r: r["id"])

counts = {"input": len(records), "a_invalid_json": 0, "b_wrong_keys": 0,
          "c_bad_intent": 0, "d_bad_slot": 0, "duplicates": 0, "kept": 0}


def reason(r):
    try:
        obj = json.loads(r["teacher_raw"])
    except json.JSONDecodeError:
        return "a_invalid_json"
    if not isinstance(obj, dict) or set(obj) != KEYS:
        return "b_wrong_keys"
    if obj["intent"] not in INTENTS:
        return "c_bad_intent"
    for k in ("date", "time", "place"):
        v = obj[k]
        if v is not None and (not isinstance(v, str) or v not in r["text"]):
            return "d_bad_slot"
    return None


survivors = []
for r in records:
    why = reason(r)
    if why:
        counts[why] += 1
    else:
        survivors.append(r)

seen, kept = set(), []
for r in survivors:  # already in id order, so the first one seen has the smallest id
    key = r["text"].strip()
    if key in seen:
        counts["duplicates"] += 1
    else:
        seen.add(key)
        kept.append(r)
counts["kept"] = len(kept)

assert counts["input"] == sum(v for k, v in counts.items() if k != "input"), "counts do not add up"

os.makedirs(OUT_DIR, exist_ok=True)
train = os.path.join(OUT_DIR, "train.jsonl")
with open(train, "w", encoding="utf-8", newline="\n") as f:
    for r in kept:
        f.write(json.dumps(r) + "\n")
digest = hashlib.sha256(open(train, "rb").read()).hexdigest()
with open(os.path.join(OUT_DIR, "train.sha256"), "w") as f:
    f.write(f"{digest}  train.jsonl\n")
with open(os.path.join(OUT_DIR, "counts.json"), "w") as f:
    json.dump(counts, f, indent=2)
print(json.dumps(counts, indent=2))
print("sha256", digest)
