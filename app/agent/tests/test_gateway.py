import asyncio

import httpx
import pytest

from harness.gateway import GATEWAY_URL_ENV, SigV4Auth, load_gateway_tools, region_from_url

URL = "https://x.gateway.bedrock-agentcore.ap-northeast-1.amazonaws.com/mcp"


def test_region_from_url():
    assert region_from_url(URL) == "ap-northeast-1"


def test_region_from_url_rejects_other_hosts():
    with pytest.raises(ValueError):
        region_from_url("https://example.com/mcp")


def test_sigv4_signs_request(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIDEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "tok")
    req = httpx.Request("POST", URL, content=b"{}")
    signed = next(SigV4Auth("ap-northeast-1").auth_flow(req))
    auth = signed.headers["Authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256")
    assert "/ap-northeast-1/bedrock-agentcore/aws4_request" in auth
    assert signed.headers["X-Amz-Security-Token"] == "tok"
    assert "X-Amz-Date" in signed.headers


def test_missing_url_raises(monkeypatch):
    monkeypatch.delenv(GATEWAY_URL_ENV, raising=False)
    with pytest.raises(RuntimeError, match="AGENTCORE_GATEWAY_WEBSEARCHGW_URL"):
        asyncio.run(load_gateway_tools())


def test_sigv4_no_credentials_raises_at_construction(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "nope-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "nope-creds"))
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    with pytest.raises(RuntimeError, match="credentials"):
        SigV4Auth("ap-northeast-1")


def test_sigv4_bodyless_get_does_not_sign_content_type(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIDEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    req = httpx.Request("GET", URL)
    signed = next(SigV4Auth("ap-northeast-1").auth_flow(req))
    auth = signed.headers["Authorization"]
    assert "SignedHeaders=" in auth
    signed_headers = auth.split("SignedHeaders=")[1].split(",")[0]
    assert "content-type" not in signed_headers.split(";")
    assert "content-type" not in signed.headers
