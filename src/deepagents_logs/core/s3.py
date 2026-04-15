from __future__ import annotations

import hashlib
import hmac
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import LoggingConfig


@dataclass(frozen=True)
class UploadItem:
    key: str
    body: str
    content_type: str


class S3Mirror:
    def __init__(self, config: LoggingConfig):
        self.config = config

    def enabled(self) -> bool:
        return (
            self.config.s3_enabled
            and bool(self.config.bucket)
            and bool(self.config.endpoint)
            and bool(self.config.access_key_id)
            and bool(self.config.secret_access_key)
        )

    def upload_text_async(self, key: str, body: str, content_type: str = "application/json") -> None:
        if not self.enabled():
            return
        thread = threading.Thread(
            target=self._upload_text,
            args=(UploadItem(key=key, body=body, content_type=content_type),),
            # Hook dispatchers are short-lived processes. Keep this non-daemon so
            # interpreter shutdown waits for the best-effort PUT instead of
            # dropping it immediately on process exit.
            daemon=False,
        )
        thread.start()

    def _upload_text(self, item: UploadItem) -> None:
        try:
            self._signed_put(item)
        except Exception:
            # Best-effort by design.
            return

    def _signed_put(self, item: UploadItem) -> None:
        endpoint = self.config.endpoint.rstrip("/")
        parsed = urlparse(endpoint)
        key = item.key.strip("/")
        if self.config.prefix:
            key = f"{self.config.prefix}/{key}"
        payload = item.body.encode("utf-8")
        payload_hash = hashlib.sha256(payload).hexdigest()
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        host = parsed.netloc
        path = f"/{self.config.bucket}/{'/'.join(quote(part, safe='') for part in key.split('/'))}"
        canonical_headers = (
            f"content-type:{item.content_type}\n"
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join([
            "PUT",
            path,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ])
        scope = f"{date_stamp}/{self.config.region}/s3/aws4_request"
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ])
        k_date = hmac.new(f"AWS4{self.config.secret_access_key}".encode("utf-8"), date_stamp.encode("utf-8"), hashlib.sha256).digest()
        k_region = hmac.new(k_date, self.config.region.encode("utf-8"), hashlib.sha256).digest()
        k_service = hmac.new(k_region, b"s3", hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            "AWS4-HMAC-SHA256 "
            f"Credential={self.config.access_key_id}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        request = Request(
            url=f"{endpoint}{path}",
            data=payload,
            method="PUT",
            headers={
                "Content-Type": item.content_type,
                "x-amz-content-sha256": payload_hash,
                "x-amz-date": amz_date,
                "Authorization": authorization,
            },
        )
        with urlopen(request, timeout=10):
            return
