"""Small S3 helper for SeaweedFS.
Env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_ENDPOINT (default http://localhost:8333)
  python3 scripts/s3_tool.py make-buckets
  python3 scripts/s3_tool.py put <file> <bucket> <key>
  python3 scripts/s3_tool.py put-dir <local dir> <bucket> <prefix>
  python3 scripts/s3_tool.py ls <bucket> [prefix]
"""
import os, sys

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT", "http://localhost:8333"),
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def main(argv):
    s3 = client()
    cmd = argv[1]
    if cmd == "make-buckets":
        for b in ("datasets", "models"):
            try:
                s3.create_bucket(Bucket=b)
                print("created", b)
            except ClientError as e:
                if e.response["Error"]["Code"] in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                    print("exists", b)
                else:
                    raise
    elif cmd == "put":
        s3.upload_file(argv[2], argv[3], argv[4])
        print("uploaded", argv[2], "->", f"{argv[3]}/{argv[4]}")
    elif cmd == "put-dir":
        folder, bucket, prefix = argv[2], argv[3], argv[4].strip("/")
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                s3.upload_file(path, bucket, f"{prefix}/{name}")
                print("uploaded", path, "->", f"{bucket}/{prefix}/{name}")
    elif cmd == "ls":
        prefix = argv[3] if len(argv) > 3 else ""
        resp = s3.list_objects_v2(Bucket=argv[2], Prefix=prefix)
        for o in resp.get("Contents", []):
            print(f"{o['Size']:>12}  {o['Key']}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
