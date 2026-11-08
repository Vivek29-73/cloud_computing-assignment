"""FastAPI inference service for the distilled command parser."""
import json
import os
import socket
from pathlib import Path
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from jsonschema import validate, ValidationError
from pydantic import BaseModel, Field

from service.model_loader import download_model, load_model

MODEL_DIR = "/tmp/student-model"
MODEL_VERSION = os.environ.get("MODEL_VERSION", "unknown")
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "80"))
SERVED_BY = os.environ.get("HOSTNAME", socket.gethostname())
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "data" / "schema.json"

tokenizer = None
model = None
output_schema = None
model_ready = False


class ParseRequest(BaseModel):
    text: str = Field(min_length=1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global tokenizer, model, output_schema, model_ready

    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        schema_document = json.load(f)
    output_schema = schema_document["json_schema"]

    model_uri = os.environ["MODEL_URI"]
    download_model(model_uri, MODEL_DIR)
    tokenizer, model = load_model(MODEL_DIR)
    model_ready = True
    yield
    model_ready = False


app = FastAPI(title="Distilled Command Parser", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    if not model_ready:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready"}


@app.post("/parse")
def parse_command(request: ParseRequest):
    if not model_ready or tokenizer is None or model is None:
        return JSONResponse(status_code=503, content={"error": "model_not_ready"})

    # This prefix exactly matches the prompt format used in training/train.py.
    prompt = "Command: " + request.text + "\nJSON:"
    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=128,
    )

    with torch.inference_mode():
        generated = model.generate(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    continuation = generated[0, inputs["input_ids"].shape[1]:]
    raw_output = tokenizer.decode(continuation, skip_special_tokens=True).strip()

    if os.environ.get("FAULT_INJECT", "0") == "1":
        raw_output = "not json"

    try:
        result = json.loads(raw_output)
        validate(instance=result, schema=output_schema)
        if set(result.keys()) != {"intent", "date", "time", "place"}:
            raise ValidationError("Output must contain exactly four required keys.")
    except (json.JSONDecodeError, ValidationError, TypeError, AttributeError):
        return JSONResponse(
            status_code=500,
            content={"error": "invalid_model_output"},
        )

    return JSONResponse(
        content=result,
        headers={
            "X-Model-Version": MODEL_VERSION,
            "X-Served-By": SERVED_BY,
        },
    )
