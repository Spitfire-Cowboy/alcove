"""Sign and verify Alcove index export envelopes."""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from alcove.signer import InstanceSigner, document_hash  # noqa: E402


SIGNED_INDEX_VERSION = 1


def _canonical_index_bytes(index: dict[str, Any]) -> bytes:
    return json.dumps(index, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_index(
    index: dict[str, Any],
    key_path: Path,
    *,
    signed_at: str | None = None,
) -> dict[str, Any]:
    """Return a signed-index envelope for an Alcove index export."""
    if index.get("alcove_sync_version") != 1:
        raise ValueError("index export must use alcove_sync_version 1")

    signer = InstanceSigner.load_or_create(key_path)
    index_hash = document_hash(_canonical_index_bytes(index))
    timestamp = signed_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {
        "alcove_signed_index_version": SIGNED_INDEX_VERSION,
        "signed_at": timestamp,
        "signer_fingerprint": signer.fingerprint(),
        "signer_public_key_pem": signer.public_key_pem().decode("utf-8"),
        "index_hash": index_hash,
        "index_signature": signer.sign(index_hash.encode("utf-8")),
        "index": index,
    }


def verify_signed_index(envelope: dict[str, Any]) -> bool:
    """Verify envelope integrity and signature.

    This checks that the envelope version is supported, the index payload
    matches the stored hash, and the signature validates with the embedded
    public key. It does not establish identity trust; callers that care who
    signed the index must pin or verify the key fingerprint out of band.
    """
    if envelope.get("alcove_signed_index_version") != SIGNED_INDEX_VERSION:
        return False

    index = envelope.get("index")
    index_hash = envelope.get("index_hash")
    signature = envelope.get("index_signature")
    public_key_pem = envelope.get("signer_public_key_pem")
    fingerprint = envelope.get("signer_fingerprint")
    if not isinstance(index, dict):
        return False
    if not all(isinstance(value, str) for value in (index_hash, signature, public_key_pem, fingerprint)):
        return False

    expected_hash = document_hash(_canonical_index_bytes(index))
    if expected_hash != index_hash:
        return False

    try:
        verifier = InstanceSigner.from_public_key_pem(public_key_pem)
    except Exception:
        return False

    if verifier.fingerprint() != fingerprint:
        return False
    return verifier.verify(index_hash.encode("utf-8"), signature)


def _cmd_sign(args: argparse.Namespace) -> int:
    index_path = Path(args.index)
    if not index_path.is_file():
        print(f"error: index file not found: {index_path}", file=sys.stderr)
        return 1

    index = json.loads(index_path.read_text())
    envelope = sign_index(index, Path(args.key))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(envelope, indent=2) + "\n")
    print(f"signed: {out_path}")
    print(f"  fingerprint : {envelope['signer_fingerprint']}")
    print(f"  index_hash  : {envelope['index_hash']}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    signed_path = Path(args.signed)
    if not signed_path.is_file():
        print(f"error: signed index not found: {signed_path}", file=sys.stderr)
        return 1

    envelope = json.loads(signed_path.read_text())
    if verify_signed_index(envelope):
        print(f"OK  {signed_path}")
        print(f"    fingerprint : {envelope.get('signer_fingerprint', '?')}")
        print(f"    signed_at   : {envelope.get('signed_at', '?')}")
        return 0

    print(f"FAIL  {signed_path}  (signature invalid or index tampered)", file=sys.stderr)
    return 2


def _cmd_export_pubkey(args: argparse.Namespace) -> int:
    key_path = Path(args.key)
    if not key_path.is_file():
        print(f"error: key file not found: {key_path}", file=sys.stderr)
        return 1

    signer = InstanceSigner.load_or_create(key_path)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(signer.public_key_pem())
    print(f"public key written: {out_path}")
    print(f"  fingerprint: {signer.fingerprint()}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sign and verify Alcove index exports.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    sign_parser = subcommands.add_parser("sign", help="Sign an index dump.")
    sign_parser.add_argument("--index", required=True, help="Path to the index export JSON.")
    sign_parser.add_argument("--key", required=True, help="Path to the Ed25519 private key PEM.")
    sign_parser.add_argument("--out", required=True, help="Output path for the signed JSON envelope.")

    verify_parser = subcommands.add_parser("verify", help="Verify a signed index.")
    verify_parser.add_argument("--signed", required=True, help="Path to the signed index JSON.")

    export_parser = subcommands.add_parser("export-pubkey", help="Export the public key PEM.")
    export_parser.add_argument("--key", required=True, help="Path to the Ed25519 private key PEM.")
    export_parser.add_argument("--out", required=True, help="Output path for the public key PEM.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "sign":
        return _cmd_sign(args)
    if args.command == "verify":
        return _cmd_verify(args)
    if args.command == "export-pubkey":
        return _cmd_export_pubkey(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
