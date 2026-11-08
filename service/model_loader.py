"""Download and load a student model stored in SeaweedFS through its S3 API."""
import os
from pathlib import Path
from urllib.parse import urlparse

import boto3
import torch
from botocore.config import Config
from transformers import AutoModelForCausalLM, AutoTokenizer


def download_model(model_uri: str, destination: str) -> str:
    """Download every object under s3://<bucket>/<prefix>/ into destination."""
    parsed = urlparse(model_uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError("MODEL_URI must look like s3://bucket/prefix")

    bucket = parsed.netloc
    prefix = parsed.path.strip("/")
    if not prefix:
        raise ValueError("MODEL_URI must include a model prefix, e.g. s3://models/v2")

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    paginator = s3.get_paginator("list_objects_v2")
    downloaded = 0

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix + "/"):
        for item in page.get("Contents", []):
            key = item["Key"]
            relative = key[len(prefix) + 1:]
            if not relative:
                continue
            local_path = target / relative
            local_path.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, key, str(local_path))
            downloaded += 1

    if downloaded == 0:
        raise RuntimeError(f"No model files found at {model_uri}")
    return str(target)


def load_model(model_dir: str):
    """Load tokenizer and causal language model on CPU."""
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_dir,
        local_files_only=True,
        torch_dtype=torch.float32,
    )
    model.to("cpu")
    model.eval()
    return tokenizer, model
