from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, repr=False)
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    public_base_url: str | None = None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> R2Config:
        values = os.environ if environ is None else environ
        account_id = values.get("R2_ACCOUNT_ID", "").strip()
        access_key_id = (
            values.get("R2_ACCESS_KEY_ID", "").strip()
            or values.get("ACCESS_KEY_ID", "").strip()
        )
        secret_access_key = (
            values.get("R2_SECRET_ACCESS_KEY", "").strip()
            or values.get("SECRET_ACCESS_KEY", "").strip()
        )
        bucket_name = values.get("R2_BUCKET_NAME", "").strip()
        resolved = {
            "R2_ACCOUNT_ID": account_id,
            "R2_ACCESS_KEY_ID": access_key_id,
            "R2_SECRET_ACCESS_KEY": secret_access_key,
            "R2_BUCKET_NAME": bucket_name,
        }
        missing = [name for name, value in resolved.items() if not value]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        public_base_url = values.get("R2_PUBLIC_BASE_URL", "").strip().rstrip("/") or None
        return cls(
            account_id=account_id,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            bucket_name=bucket_name,
            public_base_url=public_base_url,
        )

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"

    def __repr__(self) -> str:
        return (
            "R2Config("
            f"account_id={self.account_id!r}, "
            "access_key_id='***', secret_access_key='***', "
            f"bucket_name={self.bucket_name!r}, public_base_url={self.public_base_url!r})"
        )
