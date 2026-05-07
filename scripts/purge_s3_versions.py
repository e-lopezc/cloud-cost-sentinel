#!/usr/bin/env python3
"""Delete all object versions and delete markers from a versioned S3 bucket.

Handles pagination and batches deletions in chunks of 1000 (the API limit).
Exits with a non-zero status code on any failure so callers (e.g. make teardown)
can detect and stop early.
"""

import sys
import boto3
from botocore.exceptions import BotoCoreError, ClientError

BATCH_SIZE = 1000


def purge_bucket(bucket: str, region: str) -> None:
    s3 = boto3.client("s3", region_name=region)
    paginator = s3.get_paginator("list_object_versions")

    total_deleted = 0
    for page in paginator.paginate(Bucket=bucket):
        to_delete = [
            {"Key": obj["Key"], "VersionId": obj["VersionId"]}
            for key in ("Versions", "DeleteMarkers")
            for obj in page.get(key) or []
        ]

        for i in range(0, len(to_delete), BATCH_SIZE):
            batch = to_delete[i : i + BATCH_SIZE]
            response = s3.delete_objects(
                Bucket=bucket, Delete={"Objects": batch, "Quiet": True}
            )
            errors = response.get("Errors", [])
            if errors:
                for err in errors:
                    print(
                        f"ERROR deleting {err['Key']} (version {err['VersionId']}): "
                        f"{err['Code']} - {err['Message']}",
                        file=sys.stderr,
                    )
                sys.exit(1)
            total_deleted += len(batch)

    print(f"Deleted {total_deleted} object version(s)/marker(s) from '{bucket}'.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <bucket-name> <region>", file=sys.stderr)
        sys.exit(1)

    bucket_name, aws_region = sys.argv[1], sys.argv[2]
    try:
        purge_bucket(bucket_name, aws_region)
    except (BotoCoreError, ClientError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
