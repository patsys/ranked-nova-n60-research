"""Check whether a firmware blob matches the Nova AES master-key profile.

Offline only. This prints metadata/checksum results; it never saves plaintext.
"""
from __future__ import annotations
import argparse, hashlib, json, struct, functools
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

def aes(key: bytes, data: bytes) -> bytes:
    if len(key) != 16 or len(data) % 16:
        raise ValueError("AES-128 key and block-aligned data required")
    ctx = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return ctx.update(data) + ctx.finalize()

def xor_words(data: bytes) -> int:
    if len(data) % 4:
        raise ValueError("checksum input must be word aligned")
    return functools.reduce(int.__xor__, struct.unpack("<" + "I" * (len(data) // 4), data), 0)

def check(blob: bytes, master: bytes) -> dict:
    if len(blob) < 32 or (len(blob) - 32) % 16:
        raise ValueError("blob is not 32-byte header plus AES block-aligned body")
    meta = aes(master, blob[:16])
    file_key = aes(master, blob[16:32])
    body = blob[32:]
    plain = aes(file_key, aes(master, body))
    size, whole_xor, packed, code_xor = struct.unpack("<4I", meta)
    code_bytes = (packed >> 16) * 4
    valid_range = 0 < code_bytes <= len(plain) and code_bytes % 4 == 0
    whole_ok = size == len(body) and xor_words(plain) == whole_xor
    code_ok = valid_range and xor_words(plain[:code_bytes]) == code_xor
    sp, reset = struct.unpack_from("<II", plain)
    return {
        "blob_bytes": len(blob), "declared_body_bytes": size, "actual_body_bytes": len(body),
        "hardware_id": f"0x{packed & 0xffff:04x}", "code_bytes": code_bytes,
        "whole_checksum_matches": whole_ok, "code_checksum_matches": code_ok,
        "arm_vector_words": [f"0x{sp:08x}", f"0x{reset:08x}"],
        "profile_matches": size == len(body) and whole_ok and code_ok and valid_range,
    }

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--master-key", required=True, type=Path, help="16-byte local key file")
    p.add_argument("firmware_blob", type=Path, help="one extracted .enc firmware blob")
    a = p.parse_args()
    key = a.master_key.read_bytes(); blob = a.firmware_blob.read_bytes()
    result = check(blob, key)
    result["blob_sha256"] = hashlib.sha256(blob).hexdigest()
    print(json.dumps(result, indent=2))
    if not result["profile_matches"]: raise SystemExit(1)

if __name__ == "__main__": main()
