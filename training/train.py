"""Sequence-level distillation: fine-tune Pythia-70M on the teacher's replies (CPU).
Usage: python3 training/train.py training/config.yaml     (SUBSET=50 env var: first 50 records only)
Everything is read from the config file.
"""
import csv, hashlib, json, math, os, random, sys, tarfile, time

import numpy as np
import torch
import transformers
import yaml
from transformers import AutoModelForCausalLM, AutoTokenizer, get_linear_schedule_with_warmup

cfg_path = sys.argv[1] if len(sys.argv) > 1 else "training/config.yaml"
cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
subset = int(os.environ.get("SUBSET") or 0)
tag = "subset-test" if subset else cfg["version"]
loss_file = "training/loss_subset.csv" if subset else cfg["loss_file"]

seed = cfg["seed"]
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)

for name, mod in (("torch", torch), ("transformers", transformers), ("pyyaml", yaml)):
    want = str(cfg["library_versions"][name])
    if not mod.__version__.startswith(want):
        print(f"WARNING: {name} {mod.__version__} installed, config says {want}")

rows = [json.loads(l) for l in open(cfg["train_file"], encoding="utf-8") if l.strip()]
n = subset if subset else cfg["num_train_examples"]
rows = rows[:n]
print(f"training on {len(rows)} records, config {cfg_path}, tag {tag}", flush=True)

tok = AutoTokenizer.from_pretrained(cfg["base_model"])
tok.pad_token = tok.eos_token
maxlen = cfg["max_seq_length"]


def encode(r):
    # "Command: <command>\nJSON: <teacher reply>"; loss only on the reply (prompt tokens masked)
    prompt_ids = tok("Command: " + r["text"] + "\nJSON:")["input_ids"]
    reply_ids = tok(" " + r["teacher_raw"].strip())["input_ids"] + [tok.eos_token_id]
    ids = (prompt_ids + reply_ids)[:maxlen]
    labels = ([-100] * len(prompt_ids) + reply_ids)[:maxlen]
    return ids, labels


def collate(batch):
    longest = max(len(i) for i, _ in batch)
    ids = torch.full((len(batch), longest), tok.pad_token_id, dtype=torch.long)
    lab = torch.full((len(batch), longest), -100, dtype=torch.long)
    att = torch.zeros((len(batch), longest), dtype=torch.long)
    for k, (i, l) in enumerate(batch):
        ids[k, :len(i)] = torch.tensor(i)
        lab[k, :len(l)] = torch.tensor(l)
        att[k, :len(i)] = 1
    return ids, att, lab


data = [encode(r) for r in rows]
model = AutoModelForCausalLM.from_pretrained(cfg["base_model"])
model.train()
bs = cfg["batch_size"]
epochs = cfg["num_epochs"]
opt = torch.optim.AdamW(model.parameters(), lr=cfg["learning_rate"], weight_decay=cfg.get("weight_decay", 0.0))
sched = get_linear_schedule_with_warmup(opt, 0, epochs * math.ceil(len(data) / bs))
gen = torch.Generator().manual_seed(seed)

losses = []
t0 = time.time()
for epoch in range(1, epochs + 1):
    perm = torch.randperm(len(data), generator=gen).tolist()
    total, steps = 0.0, 0
    for s in range(0, len(perm), bs):
        ids, att, lab = collate([data[j] for j in perm[s:s + bs]])
        loss = model(input_ids=ids, attention_mask=att, labels=lab).loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        opt.zero_grad()
        total += loss.item()
        steps += 1
    losses.append(total / steps)
    print(f"epoch {epoch}/{epochs}  loss {losses[-1]:.4f}  elapsed {time.time() - t0:.0f}s", flush=True)

os.makedirs(os.path.dirname(loss_file), exist_ok=True)
with open(loss_file, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["epoch", "train_loss"])
    for e, l in enumerate(losses, 1):
        w.writerow([e, f"{l:.6f}"])

outdir = os.path.join(cfg["output_dir"], tag)
os.makedirs(outdir, exist_ok=True)
model.save_pretrained(outdir)
tok.save_pretrained(outdir)
info = {
    "version": tag, "base_model": cfg["base_model"], "seed": seed,
    "learning_rate": cfg["learning_rate"], "batch_size": bs, "num_epochs": epochs,
    "max_seq_length": maxlen, "num_train_examples": len(rows),
    "final_train_loss": losses[-1],
    "train_file_sha256": hashlib.sha256(open(cfg["train_file"], "rb").read()).hexdigest(),
    "torch": torch.__version__, "transformers": transformers.__version__,
}
with open(os.path.join(outdir, "version.json"), "w") as f:
    json.dump(info, f, indent=2)

# Deterministic tar of the model files = the GitHub Release asset; model.sha256 is its checksum.
os.makedirs(cfg["release_dir"], exist_ok=True)
tar_path = os.path.join(cfg["release_dir"], f"model-{tag}.tar")
with tarfile.open(tar_path, "w", format=tarfile.GNU_FORMAT) as tf:
    for name in sorted(os.listdir(outdir)):
        p = os.path.join(outdir, name)
        if name == "model.sha256" or not os.path.isfile(p):
            continue
        ti = tarfile.TarInfo(name)
        ti.size, ti.mtime, ti.mode, ti.uid, ti.gid, ti.uname, ti.gname = os.path.getsize(p), 0, 0o644, 0, 0, "", ""
        with open(p, "rb") as fh:
            tf.addfile(ti, fh)
digest = hashlib.sha256(open(tar_path, "rb").read()).hexdigest()
with open(os.path.join(outdir, "model.sha256"), "w") as f:
    f.write(f"{digest}  model-{tag}.tar\n")
print(f"saved model to {outdir}, release asset {tar_path}\nsha256 {digest}")
