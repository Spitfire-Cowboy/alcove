"""Signing helpers for Alcove provenance metadata.

This module provides local Ed25519 signing primitives for document and index
provenance. Signatures prove that bytes match a specific public key; callers
that need identity trust must pin or verify the public-key fingerprint out of
band.
"""

from __future__ import annotations

import base64
import contextlib
import datetime
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)


def document_hash(data: bytes) -> str:
    """Return the canonical SHA-256 digest string for *data*."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


class InstanceSigner:
    """Ed25519 signing context for one local Alcove instance."""

    def __init__(
        self,
        private_key: Ed25519PrivateKey | None,
        public_key: Ed25519PublicKey | None = None,
    ) -> None:
        self._private_key = private_key
        if public_key is not None:
            self._public_key = public_key
        elif private_key is not None:
            self._public_key = private_key.public_key()
        else:
            raise ValueError("private_key or public_key is required")

    @classmethod
    def generate(cls) -> "InstanceSigner":
        """Generate a fresh Ed25519 keypair."""
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def load_or_create(cls, key_path: str | Path) -> "InstanceSigner":
        """Load an Ed25519 private key, or create one with mode 0600."""
        path = Path(key_path)
        if path.is_file():
            private_key = load_pem_private_key(path.read_bytes(), password=None)
            if not isinstance(private_key, Ed25519PrivateKey):
                raise ValueError(f"{key_path}: expected Ed25519 private key")
            return cls(private_key)

        signer = cls.generate()
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(path, flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(signer.private_key_pem())
        except Exception:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
            raise
        return signer

    @classmethod
    def from_public_key_pem(cls, pem: bytes | str) -> "InstanceSigner":
        """Create a verification-only signer from an Ed25519 public key PEM."""
        if isinstance(pem, str):
            pem = pem.encode("utf-8")
        public_key = load_pem_public_key(pem)
        if not isinstance(public_key, Ed25519PublicKey):
            raise ValueError("expected Ed25519 public key")
        return cls(private_key=None, public_key=public_key)

    def private_key_pem(self) -> bytes:
        """Return the private key in PEM-encoded PKCS8 format."""
        if self._private_key is None:
            raise RuntimeError("no private key available")
        return self._private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )

    def public_key_pem(self) -> bytes:
        """Return the public key in PEM-encoded SubjectPublicKeyInfo format."""
        return self._public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        )

    def fingerprint(self) -> str:
        """Return the first 16 bytes of the raw public key as hex."""
        raw = self._public_key.public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )
        return raw[:16].hex()

    def sign(self, data: bytes) -> str:
        """Sign *data* and return a URL-safe base64 signature."""
        if self._private_key is None:
            raise RuntimeError("no private key available")
        signature = self._private_key.sign(data)
        return base64.urlsafe_b64encode(signature).decode("ascii")

    def verify(self, data: bytes, signature_b64: str) -> bool:
        """Return whether *signature_b64* is valid for *data*."""
        try:
            signature = base64.urlsafe_b64decode(signature_b64)
            self._public_key.verify(signature, data)
        except Exception:
            return False
        return True

    def sign_document(
        self,
        data: bytes,
        *,
        signed_at: str | None = None,
    ) -> dict[str, str]:
        """Return ChromaDB-ready signature metadata for document bytes."""
        digest = document_hash(data)
        timestamp = signed_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
        return {
            "doc_hash": digest,
            "doc_signature": self.sign(digest.encode("utf-8")),
            "signed_at": timestamp,
            "instance_key": self.fingerprint(),
        }

    def verify_document(self, data: bytes, signature_b64: str) -> bool:
        """Verify a document signature over the canonical document hash."""
        digest = document_hash(data)
        return self.verify(digest.encode("utf-8"), signature_b64)
