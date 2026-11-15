"""Checkpointer selection: DynamoDB + S3 when configured, in-memory otherwise."""

import logging
import os

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

logger = logging.getLogger(__name__)

TABLE_ENV = "CHECKPOINT_TABLE"
BUCKET_ENV = "CHECKPOINT_BUCKET"
TTL_DAYS_ENV = "CHECKPOINT_TTL_DAYS"
S3_KEY_PREFIX = "checkpoints"


def _ttl_seconds() -> int | None:
    raw = os.environ.get(TTL_DAYS_ENV, "").strip()
    if not raw:
        return None
    days = int(raw)
    if days <= 0:
        raise ValueError(f"{TTL_DAYS_ENV} must be a positive integer, got {raw!r}")
    return days * 86400


def create_checkpointer() -> BaseCheckpointSaver:
    """DynamoDBSaver if CHECKPOINT_TABLE is set, else InMemorySaver (local dev / tests).

    No TTL unless CHECKPOINT_TTL_DAYS is set. Checkpoints larger than 350 KB go to
    CHECKPOINT_BUCKET when it is set.
    """
    table = os.environ.get(TABLE_ENV)
    if not table:
        logger.warning("%s not set; using InMemorySaver (history is lost on restart)", TABLE_ENV)
        return InMemorySaver()

    from langgraph_checkpoint_aws import DynamoDBSaver

    bucket = os.environ.get(BUCKET_ENV)
    return DynamoDBSaver(
        table_name=table,
        region_name=os.environ.get("AWS_REGION"),
        ttl_seconds=_ttl_seconds(),
        enable_checkpoint_compression=True,
        consistent_read=True,
        s3_offload_config={"bucket_name": bucket, "key_prefix": S3_KEY_PREFIX} if bucket else None,
    )
