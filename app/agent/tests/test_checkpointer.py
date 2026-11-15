import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph_checkpoint_aws import DynamoDBSaver

import harness.checkpointer as cp


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (cp.TABLE_ENV, cp.BUCKET_ENV, cp.TTL_DAYS_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_REGION", "ap-northeast-1")


@pytest.fixture
def captured(monkeypatch):
    calls = []

    class FakeSaver:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    import langgraph_checkpoint_aws

    monkeypatch.setattr(langgraph_checkpoint_aws, "DynamoDBSaver", FakeSaver)
    return calls


def test_in_memory_when_table_unset():
    assert isinstance(cp.create_checkpointer(), InMemorySaver)


def test_dynamodb_without_ttl_or_bucket(monkeypatch, captured):
    monkeypatch.setenv(cp.TABLE_ENV, "tbl")
    cp.create_checkpointer()
    (kw,) = captured
    assert kw["table_name"] == "tbl"
    assert kw["region_name"] == "ap-northeast-1"
    assert kw["ttl_seconds"] is None
    assert kw["s3_offload_config"] is None
    assert kw["enable_checkpoint_compression"] is True
    assert kw["consistent_read"] is True


def test_dynamodb_with_bucket_and_ttl(monkeypatch, captured):
    monkeypatch.setenv(cp.TABLE_ENV, "tbl")
    monkeypatch.setenv(cp.BUCKET_ENV, "bkt")
    monkeypatch.setenv(cp.TTL_DAYS_ENV, "30")
    cp.create_checkpointer()
    (kw,) = captured
    assert kw["s3_offload_config"] == {"bucket_name": "bkt", "key_prefix": "checkpoints"}
    assert kw["ttl_seconds"] == 30 * 86400


@pytest.mark.parametrize("bad", ["0", "-1", "abc"])
def test_invalid_ttl_raises(monkeypatch, captured, bad):
    monkeypatch.setenv(cp.TABLE_ENV, "tbl")
    monkeypatch.setenv(cp.TTL_DAYS_ENV, bad)
    with pytest.raises(ValueError):
        cp.create_checkpointer()


def test_real_saver_constructs_without_aws_calls(monkeypatch):
    monkeypatch.setenv(cp.TABLE_ENV, "tbl")
    monkeypatch.setenv(cp.BUCKET_ENV, "bkt")
    assert isinstance(cp.create_checkpointer(), DynamoDBSaver)
