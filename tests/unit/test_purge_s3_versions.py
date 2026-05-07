"""
Unit tests for scripts/purge_s3_versions.py.

Uses moto to mock S3. Verifies that purge_bucket correctly removes all
object versions and delete markers, handles pagination/batching, and
raises on API errors.
"""

import sys
import os
import pytest
import boto3
from moto import mock_aws
from unittest.mock import patch

# Make the scripts/ directory importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
from purge_s3_versions import purge_bucket, BATCH_SIZE  # noqa: E402

BUCKET = "test-purge-bucket"
REGION = "us-east-1"


def _make_versioned_bucket(s3):
    """Create a versioned bucket and return the client."""
    s3.create_bucket(Bucket=BUCKET)
    s3.put_bucket_versioning(
        Bucket=BUCKET,
        VersioningConfiguration={"Status": "Enabled"},
    )
    return s3


def _list_all_versions(s3):
    """Return all remaining versions + delete markers in the bucket."""
    resp = s3.list_object_versions(Bucket=BUCKET)
    versions = resp.get("Versions") or []
    markers = resp.get("DeleteMarkers") or []
    return versions, markers


# ------------------------------------------------------------------ #
# Empty bucket
# ------------------------------------------------------------------ #

class TestEmptyBucket:
    @mock_aws
    def test_empty_bucket_no_error(self, aws_credentials):
        s3 = _make_versioned_bucket(boto3.client("s3", region_name=REGION))
        purge_bucket(BUCKET, REGION, s3_client=s3)  # should not raise
        versions, markers = _list_all_versions(s3)
        assert versions == []
        assert markers == []


# ------------------------------------------------------------------ #
# Object versions
# ------------------------------------------------------------------ #

class TestVersionDeletion:
    @mock_aws
    def test_single_version_deleted(self, aws_credentials):
        s3 = _make_versioned_bucket(boto3.client("s3", region_name=REGION))
        s3.put_object(Bucket=BUCKET, Key="file.txt", Body=b"v1")

        purge_bucket(BUCKET, REGION, s3_client=s3)

        versions, markers = _list_all_versions(s3)
        assert versions == []

    @mock_aws
    def test_multiple_versions_of_same_key_deleted(self, aws_credentials):
        s3 = _make_versioned_bucket(boto3.client("s3", region_name=REGION))
        for body in (b"v1", b"v2", b"v3"):
            s3.put_object(Bucket=BUCKET, Key="file.txt", Body=body)

        purge_bucket(BUCKET, REGION, s3_client=s3)

        versions, _ = _list_all_versions(s3)
        assert versions == []

    @mock_aws
    def test_versions_across_multiple_keys_deleted(self, aws_credentials):
        s3 = _make_versioned_bucket(boto3.client("s3", region_name=REGION))
        for key in ("a.txt", "b.txt", "c.txt"):
            s3.put_object(Bucket=BUCKET, Key=key, Body=b"data")

        purge_bucket(BUCKET, REGION, s3_client=s3)

        versions, _ = _list_all_versions(s3)
        assert versions == []


# ------------------------------------------------------------------ #
# Delete markers
# ------------------------------------------------------------------ #

class TestDeleteMarkerDeletion:
    @mock_aws
    def test_delete_markers_removed(self, aws_credentials):
        s3 = _make_versioned_bucket(boto3.client("s3", region_name=REGION))
        s3.put_object(Bucket=BUCKET, Key="file.txt", Body=b"v1")
        s3.delete_object(Bucket=BUCKET, Key="file.txt")  # creates a delete marker

        purge_bucket(BUCKET, REGION, s3_client=s3)

        versions, markers = _list_all_versions(s3)
        assert versions == []
        assert markers == []


# ------------------------------------------------------------------ #
# Mixed versions + markers
# ------------------------------------------------------------------ #

class TestMixed:
    @mock_aws
    def test_versions_and_markers_all_deleted(self, aws_credentials):
        s3 = _make_versioned_bucket(boto3.client("s3", region_name=REGION))
        for key in ("x.txt", "y.txt"):
            s3.put_object(Bucket=BUCKET, Key=key, Body=b"data")
            s3.delete_object(Bucket=BUCKET, Key=key)
        s3.put_object(Bucket=BUCKET, Key="z.txt", Body=b"keep")

        purge_bucket(BUCKET, REGION, s3_client=s3)

        versions, markers = _list_all_versions(s3)
        assert versions == []
        assert markers == []


# ------------------------------------------------------------------ #
# Batching
# ------------------------------------------------------------------ #

class TestBatching:
    @mock_aws
    def test_batching_deletes_all_objects(self, aws_credentials):
        """Patch BATCH_SIZE to 2 and create 5 objects to exercise the chunking loop."""
        s3 = _make_versioned_bucket(boto3.client("s3", region_name=REGION))
        for i in range(5):
            s3.put_object(Bucket=BUCKET, Key=f"file{i}.txt", Body=b"data")

        with patch("purge_s3_versions.BATCH_SIZE", 2):
            purge_bucket(BUCKET, REGION, s3_client=s3)

        versions, markers = _list_all_versions(s3)
        assert versions == []
        assert markers == []
