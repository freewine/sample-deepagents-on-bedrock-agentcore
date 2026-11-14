"""AgentCore Gateway MCP client (IAM / SigV4 authorized)."""

import asyncio
import os
import re
from collections.abc import Generator

import httpx
from botocore.auth import SigV4Auth as _BotoSigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import get_session
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

GATEWAY_URL_ENV = "AGENTCORE_GATEWAY_WEBSEARCHGW_URL"
GATEWAY_LIST_TIMEOUT_S = 30
_REGION_RE = re.compile(r"\.gateway\.bedrock-agentcore\.([a-z0-9-]+)\.amazonaws\.com$")


def region_from_url(url: str) -> str:
    host = httpx.URL(url).host
    m = _REGION_RE.search(host)
    if not m:
        raise ValueError(f"Cannot parse region from gateway URL host: {host}")
    return m.group(1)


class SigV4Auth(httpx.Auth):
    """Sign each httpx request with SigV4.

    Credentials are resolved once at construction (may hit IMDS, so not per
    request). get_frozen_credentials() is called per request; refreshable
    credentials renew themselves before expiry, so rotating role creds work.
    """

    requires_request_body = True

    def __init__(self, region: str, service: str = "bedrock-agentcore"):
        self.region = region
        self.service = service
        self._credentials = get_session().get_credentials()
        if self._credentials is None:
            raise RuntimeError("No AWS credentials available to sign gateway request")

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        creds = self._credentials.get_frozen_credentials()
        headers = {"host": request.url.netloc.decode()}
        if request.content:
            if not request.headers.get("content-type"):
                request.headers["content-type"] = "application/json"
            headers["content-type"] = request.headers["content-type"]
        aws_req = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers=headers,
        )
        _BotoSigV4Auth(creds, self.service, self.region).add_auth(aws_req)
        for name in ("Authorization", "X-Amz-Date", "X-Amz-Security-Token"):
            if name in aws_req.headers:
                request.headers[name] = aws_req.headers[name]
        yield request


async def load_gateway_tools() -> list[BaseTool]:
    url = os.environ.get(GATEWAY_URL_ENV)
    if not url:
        raise RuntimeError(f"{GATEWAY_URL_ENV} is not set; cannot load gateway tools")
    client = MultiServerMCPClient(
        {
            "gateway": {
                "transport": "streamable_http",
                "url": url,
                "auth": SigV4Auth(region_from_url(url)),
            }
        }
    )
    return await asyncio.wait_for(client.get_tools(), timeout=GATEWAY_LIST_TIMEOUT_S)
