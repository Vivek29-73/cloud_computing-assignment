"""Unit tests for the data pipeline, the scoring/quality gate and the NACL file."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOOD = '{"intent": "alarm_set", "date": null, "time": "six am", "place": null}'


def run(args, env=None):
    full_env = dict(os.environ, **(env or {}))
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=full_env, capture_output=True, text=True)


def write_shard(folder, rows):
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "shard-0.jsonl", "w", encoding="utf-8") as f:
        for rid, text, raw in rows:
            f.write(json.dumps({"id": rid, "text": text, "teacher_raw": raw}) + "\n")


def test_clean_applies_every_rejection_rule(tmp_path):
    rows = [
        ("C0001", "set alarm for six am", GOOD),
        ("C0002", "set alarm for six am", GOOD),  # duplicate of C0001
        ("C0003", "hello", "not json"),  # (a) invalid JSON
        ("C0004", "weather in rome", '{"intent": "weather_query", "place": "rome"}'),  # (b) wrong keys
        ("C0005", "play music", '{"intent": "music", "date": null, "time": null, "place": null}'),  # (c) bad intent
        ("C0006", "weather in rome",
         '{"intent": "weather_query", "date": "tomorrow", "time": null, "place": "rome"}'),  # (d) slot not in command
    ]
    write_shard(tmp_path / "shards", rows)
    result = run(["worker/clean.py"], {"SHARD_DIR": str(tmp_path / "shards"), "OUT_DIR": str(tmp_path / "out")})
    assert result.returncode == 0, result.stderr
    counts = json.loads((tmp_path / "out" / "counts.json").read_text())
    assert counts == {"input": 6, "a_invalid_json": 1, "b_wrong_keys": 1, "c_bad_intent": 1,
                      "d_bad_slot": 1, "duplicates": 1, "kept": 1}
    kept = [json.loads(line) for line in open(tmp_path / "out" / "train.jsonl", encoding="utf-8")]
    assert [r["id"] for r in kept] == ["C0001"]  # the duplicate with the smallest id survives


def test_clean_is_reproducible_and_checksum_matches(tmp_path):
    write_shard(tmp_path / "shards", [("C0002", "set alarm for six am", GOOD), ("C0001", "set alarm for six am", GOOD)])
    env = {"SHARD_DIR": str(tmp_path / "shards")}
    run(["worker/clean.py"], dict(env, OUT_DIR=str(tmp_path / "a")))
    run(["worker/clean.py"], dict(env, OUT_DIR=str(tmp_path / "b")))
    first = (tmp_path / "a" / "train.jsonl").read_bytes()
    assert first == (tmp_path / "b" / "train.jsonl").read_bytes()
    recorded = (tmp_path / "a" / "train.sha256").read_text().split()[0]
    assert recorded == hashlib.sha256(first).hexdigest()


def make_gold(tmp_path, n=5):
    lines = (ROOT / "data" / "validation.jsonl").read_text(encoding="utf-8").splitlines()[:n]
    gold = [json.loads(line) for line in lines]
    path = tmp_path / "gold.jsonl"
    path.write_text("\n".join(json.dumps(g) for g in gold) + "\n", encoding="utf-8")
    return gold, path


def write_predictions(path, predictions):
    with open(path, "w", encoding="utf-8") as f:
        for rid, pred in predictions:
            f.write(json.dumps({"id": rid, "prediction": pred}) + "\n")


def test_score_gate_passes_for_valid_json(tmp_path):
    gold, gold_file = make_gold(tmp_path)
    preds = [(g["id"], json.dumps({k: g[k] for k in ("intent", "date", "time", "place")})) for g in gold]
    write_predictions(tmp_path / "p.jsonl", preds)
    result = run(["tools/score.py", str(tmp_path / "p.jsonl"), str(gold_file), "--min-validity", "95"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"full_frame": 100.0' in result.stdout


def test_score_gate_fails_for_untrained_style_output(tmp_path):
    gold, gold_file = make_gold(tmp_path)
    write_predictions(tmp_path / "p.jsonl", [(g["id"], "the quick brown fox") for g in gold])
    result = run(["tools/score.py", str(tmp_path / "p.jsonl"), str(gold_file), "--min-validity", "95"])
    assert result.returncode != 0


def test_nacl_matches_all_sample_packets():
    assert (ROOT / "network" / "nacl.json").exists()
    result = run(["tools/nacl_sim.py", "network/nacl.json", "network/packets_sample.jsonl", "--check"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "100.0%" in result.stdout
