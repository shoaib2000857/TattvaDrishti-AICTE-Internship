"""Authenticated encrypted transfer for routine partner-node sharing.

AES-256-GCM protects the payload itself. HTTPS connections are restricted to
TLS 1.3 when enabled, while local HTTP remains available for the multi-node
demo because the application-layer envelope is still encrypted.
"""

import base64
import hashlib
import json
import os
import ssl
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import get_settings
from ..schemas import SecureTransferEnvelope, SecureTransferReceipt
from .crypto import get_public_key_hex, sign_payload, verify_signature


def _canonical(value: Dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


class SecureTransferError(ValueError):
    pass


class SecureTransferService:
    def __init__(self) -> None:
        self.settings = get_settings()
        try:
            self.key = _b64decode(self.settings.secure_transfer_key)
        except Exception as error:
            raise SecureTransferError("SECURE_TRANSFER_KEY must be URL-safe base64.") from error
        if len(self.key) != 32:
            raise SecureTransferError(
                "SECURE_TRANSFER_KEY must decode to exactly 32 bytes for AES-256."
            )

    def destination_url(self, destination: str) -> Optional[str]:
        mappings: Dict[str, str] = {}
        for entry in self.settings.secure_transfer_nodes.split(","):
            region, separator, url = entry.partition("=")
            if separator and region.strip() and url.strip():
                mappings[region.strip().upper()] = url.strip().rstrip("/")
        return mappings.get(destination.upper())

    def create_envelope(
        self,
        *,
        package_id: str,
        destination: str,
        payload: Dict[str, Any],
    ) -> SecureTransferEnvelope:
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(
            seconds=max(30, self.settings.secure_transfer_ttl_seconds)
        )
        envelope_id = f"env-{uuid4()}"
        aad_payload = {
            "version": "1.0",
            "envelope_id": envelope_id,
            "package_id": package_id,
            "source_node": self.settings.secure_transfer_node_id,
            "destination": destination,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "algorithm": "AES-256-GCM",
            "key_id": self.settings.secure_transfer_key_id,
        }
        aad_bytes = _canonical(aad_payload).encode("utf-8")
        nonce = os.urandom(12)
        ciphertext = AESGCM(self.key).encrypt(
            nonce,
            _canonical(payload).encode("utf-8"),
            aad_bytes,
        )
        unsigned = {
            **aad_payload,
            "nonce": _b64encode(nonce),
            "aad": _b64encode(aad_bytes),
            "ciphertext": _b64encode(ciphertext),
            "ciphertext_sha256": hashlib.sha256(ciphertext).hexdigest(),
            "signing_public_key": get_public_key_hex(),
        }
        envelope = SecureTransferEnvelope(**unsigned, signature="")
        normalized_unsigned = envelope.model_dump(mode="json", exclude={"signature"})
        envelope.signature = sign_payload(_canonical(normalized_unsigned))
        return envelope

    def decrypt_envelope(
        self, envelope: SecureTransferEnvelope
    ) -> Dict[str, Any]:
        unsigned = envelope.model_dump(mode="json", exclude={"signature"})
        if not verify_signature(
            envelope.signing_public_key,
            _canonical(unsigned),
            envelope.signature,
        ):
            raise SecureTransferError("Envelope signature verification failed.")
        if envelope.key_id != self.settings.secure_transfer_key_id:
            raise SecureTransferError("Unknown encryption key identifier.")
        now = datetime.now(envelope.expires_at.tzinfo or timezone.utc)
        if envelope.expires_at < now:
            raise SecureTransferError("Envelope has expired.")

        try:
            ciphertext = _b64decode(envelope.ciphertext)
            if hashlib.sha256(ciphertext).hexdigest() != envelope.ciphertext_sha256:
                raise SecureTransferError("Ciphertext digest mismatch.")
            plaintext = AESGCM(self.key).decrypt(
                _b64decode(envelope.nonce),
                ciphertext,
                _b64decode(envelope.aad),
            )
            return json.loads(plaintext.decode("utf-8"))
        except SecureTransferError:
            raise
        except Exception as error:
            raise SecureTransferError(
                "Envelope authentication or decryption failed."
            ) from error

    async def deliver(
        self, envelope: SecureTransferEnvelope
    ) -> Tuple[str, Optional[SecureTransferReceipt], Optional[str]]:
        destination_url = self.destination_url(envelope.destination)
        if not destination_url:
            return "prepared_offline", None, "No endpoint is configured for this destination."

        parsed = urlparse(destination_url)
        is_local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if self.settings.secure_transfer_require_tls and parsed.scheme != "https" and not is_local:
            return "blocked", None, "The destination does not use the required HTTPS transport."

        verify: Any = self.settings.secure_transfer_verify_tls
        transport_label = "AES-256-GCM over local development HTTP"
        if parsed.scheme == "https":
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            if not self.settings.secure_transfer_verify_tls:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            verify = context
            transport_label = "AES-256-GCM over TLS 1.3"

        try:
            async with httpx.AsyncClient(
                timeout=float(self.settings.secure_transfer_timeout),
                verify=verify,
            ) as client:
                response = await client.post(
                    f"{destination_url}/api/v1/secure-transfer/receive",
                    json=envelope.model_dump(mode="json"),
                )
                response.raise_for_status()
                return (
                    "delivered",
                    SecureTransferReceipt.model_validate(response.json()),
                    transport_label,
                )
        except Exception as error:
            return "prepared_offline", None, f"Delivery deferred: {type(error).__name__}"
