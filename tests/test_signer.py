from __future__ import annotations

import base64
import hashlib
import stat

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from alcove.signer import InstanceSigner, document_hash


def test_document_hash_is_canonical_sha256() -> None:
    assert document_hash(b"") == "sha256:" + hashlib.sha256(b"").hexdigest()
    assert document_hash(b"data").startswith("sha256:")
    assert document_hash(b"a") != document_hash(b"b")


def test_generated_signers_have_different_keys() -> None:
    assert InstanceSigner.generate().public_key_pem() != InstanceSigner.generate().public_key_pem()


def test_signer_requires_private_or_public_key() -> None:
    with pytest.raises(ValueError, match="private_key or public_key"):
        InstanceSigner(None)


def test_key_serialization_and_fingerprint() -> None:
    signer = InstanceSigner.generate()
    assert b"PRIVATE KEY" in signer.private_key_pem()
    assert b"PUBLIC KEY" in signer.public_key_pem()
    fingerprint = signer.fingerprint()
    assert len(fingerprint) == 32
    int(fingerprint, 16)


def test_load_or_create_persists_generated_key_with_0600_mode(tmp_path) -> None:
    key_path = tmp_path / "keys" / "alcove.key"
    signer = InstanceSigner.load_or_create(key_path)
    loaded = InstanceSigner.load_or_create(key_path)

    assert key_path.is_file()
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    assert signer.public_key_pem() == loaded.public_key_pem()


def test_load_or_create_rejects_non_ed25519_private_key(tmp_path) -> None:
    key_path = tmp_path / "rsa.key"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path.write_bytes(
        key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )
    )

    with pytest.raises(ValueError, match="expected Ed25519 private key"):
        InstanceSigner.load_or_create(key_path)


def test_load_or_create_removes_partial_key_on_write_failure(tmp_path, monkeypatch) -> None:
    key_path = tmp_path / "alcove.key"

    def fail_private_key_pem(self):
        raise RuntimeError("write failed")

    monkeypatch.setattr(InstanceSigner, "private_key_pem", fail_private_key_pem)

    with pytest.raises(RuntimeError, match="write failed"):
        InstanceSigner.load_or_create(key_path)
    assert not key_path.exists()


def test_load_or_create_ignores_missing_partial_key_on_cleanup(tmp_path, monkeypatch) -> None:
    key_path = tmp_path / "alcove.key"

    def fail_private_key_pem(self):
        raise RuntimeError("write failed")

    def missing_unlink(self):
        raise FileNotFoundError

    monkeypatch.setattr(InstanceSigner, "private_key_pem", fail_private_key_pem)
    monkeypatch.setattr(type(key_path), "unlink", missing_unlink)

    with pytest.raises(RuntimeError, match="write failed"):
        InstanceSigner.load_or_create(key_path)


def test_public_key_pem_creates_verify_only_signer() -> None:
    signer = InstanceSigner.generate()
    verifier = InstanceSigner.from_public_key_pem(signer.public_key_pem().decode("utf-8"))

    with pytest.raises(RuntimeError):
        verifier.private_key_pem()
    with pytest.raises(RuntimeError):
        verifier.sign(b"data")


def test_rejects_invalid_public_key_pem() -> None:
    with pytest.raises(Exception):
        InstanceSigner.from_public_key_pem(b"not-valid-pem")


def test_rejects_non_ed25519_public_key_pem() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    )

    with pytest.raises(ValueError, match="expected Ed25519 public key"):
        InstanceSigner.from_public_key_pem(public_pem)


def test_sign_and_verify_bytes() -> None:
    signer = InstanceSigner.generate()
    signature = signer.sign(b"hello")

    base64.urlsafe_b64decode(signature)
    assert signer.verify(b"hello", signature)
    assert not signer.verify(b"tampered", signature)
    assert not InstanceSigner.generate().verify(b"hello", signature)
    assert not signer.verify(b"hello", "not-a-real-signature==")


def test_sign_document_metadata_and_verification() -> None:
    signer = InstanceSigner.generate()
    data = b"document bytes"
    metadata = signer.sign_document(data, signed_at="2026-01-01T00:00:00+00:00")

    assert metadata == {
        "doc_hash": document_hash(data),
        "doc_signature": metadata["doc_signature"],
        "signed_at": "2026-01-01T00:00:00+00:00",
        "instance_key": signer.fingerprint(),
    }
    assert signer.verify_document(data, metadata["doc_signature"])
    assert not signer.verify_document(b"tampered", metadata["doc_signature"])


def test_verify_document_with_public_key_only() -> None:
    signer = InstanceSigner.generate()
    metadata = signer.sign_document(b"document")
    verifier = InstanceSigner.from_public_key_pem(signer.public_key_pem())

    assert verifier.verify_document(b"document", metadata["doc_signature"])
