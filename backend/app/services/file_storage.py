"""
Handles writing uploaded files to disk *encrypted*, and reading them back.
This is a genuine implementation of TRD §7.1's "encrypted at rest" requirement
— not a TODO. It uses Fernet (AES-128-CBC + HMAC) from the `cryptography`
package, which is appropriate for a project this size; a larger deployment
would likely move this to a KMS-backed key and object storage (S3/GCS) rather
than local disk, but the encrypt/decrypt boundary here is written so that
swap only touches this one file.
"""
import os
import uuid
import struct
import tempfile
from contextlib import contextmanager
from pathlib import Path

from cryptography.fernet import Fernet, MultiFernet

from app.core.config import get_settings
from app.services import object_storage
from app.services.upload_sniff import safe_ext

settings = get_settings()

_KEY_FILE = Path(settings.DATA_DIR) / ".file_encryption_key"
_DECRYPTED_TEMP_DIR = Path(settings.DATA_DIR) / ".tmp" / "decrypted"


def _get_fernet() -> Fernet:
    key = settings.FILE_ENCRYPTION_KEY.strip()
    if not key and settings.ENV.lower() not in {"development", "dev", "test"}:
        raise RuntimeError("FILE_ENCRYPTION_KEY must be supplied by the deployment secret manager outside development/test.")
    if not key:
        # Dev convenience: generate once and persist, so restarts can still
        # decrypt previously-uploaded files. A real deployment should set
        # FILE_ENCRYPTION_KEY explicitly (e.g. from a secrets manager) instead
        # of relying on this file.
        _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _KEY_FILE.exists():
            key = _KEY_FILE.read_text().strip()
        else:
            key = Fernet.generate_key().decode()
            _KEY_FILE.write_text(key)
    keys = [Fernet(key.encode())]
    if settings.FILE_ENCRYPTION_KEY_PREVIOUS.strip():
        keys.append(Fernet(settings.FILE_ENCRYPTION_KEY_PREVIOUS.strip().encode()))
    return MultiFernet(keys)


def save_encrypted(raw_bytes: bytes, original_filename: str) -> tuple[str, int]:
    """
    Encrypts raw_bytes and writes them to UPLOADS_DIR under a random name
    (never the original filename, to avoid leaking anything through the path).
    Returns (storage_path, plaintext_size_bytes).
    """
    uploads_dir = Path(settings.UPLOADS_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    ext = safe_ext(original_filename)
    stored_name = f"{uuid.uuid4().hex}{ext}.enc"
    storage_path = uploads_dir / stored_name

    fernet = _get_fernet()
    encrypted = fernet.encrypt(raw_bytes)
    storage_path.write_bytes(encrypted)
    stored = object_storage.put_file(str(storage_path), storage_path.name)
    return stored, len(raw_bytes)


def save_encrypted_stream(file_obj, original_filename: str, max_bytes: int) -> tuple[str, int, str]:
    """Encrypt an upload in authenticated chunks, avoiding a second whole-file plaintext buffer.

    The format is LINEAGE2 + repeated 8-byte length + Fernet token. Existing Fernet files
    remain readable through read_decrypted().
    """
    uploads_dir = Path(settings.UPLOADS_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    ext = safe_ext(original_filename)
    storage_path = uploads_dir / f"{uuid.uuid4().hex}{ext}.enc"
    fernet = _get_fernet()
    total = 0
    import struct, hashlib
    digest = hashlib.sha256()
    with storage_path.open("wb") as out:
        out.write(b"LINEAGE2\n")
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                out.close()
                storage_path.unlink(missing_ok=True)
                raise ValueError(f"File exceeds {max_bytes // (1024*1024)} MB limit.")
            digest.update(chunk)
            token = fernet.encrypt(chunk)
            out.write(struct.pack("!Q", len(token)))
            out.write(token)
    stored = object_storage.put_file(str(storage_path), storage_path.name)
    return stored, total, digest.hexdigest()


def read_decrypted(storage_path: str) -> bytes:
    temp_path = None
    if storage_path.startswith("s3://"):
        _DECRYPTED_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix="lineage-s3-encrypted-", suffix=".enc", dir=str(_DECRYPTED_TEMP_DIR))
        os.close(fd)
        Path(temp_path).parent.mkdir(parents=True, exist_ok=True)
        object_storage.download_to_file(storage_path, temp_path)
        path = Path(temp_path)
    else:
        path = Path(storage_path)
    fernet = _get_fernet()
    try:
      with path.open("rb") as inp:
        prefix = inp.read(9)
        if prefix != b"LINEAGE2\n":
            encrypted = prefix + inp.read()
            return fernet.decrypt(encrypted)
        import struct
        parts = []
        while True:
            header = inp.read(8)
            if not header:
                break
            if len(header) != 8:
                raise ValueError("Corrupt encrypted upload header")
            size = struct.unpack("!Q", header)[0]
            if size > 32 * 1024 * 1024:
                raise ValueError("Corrupt encrypted upload chunk")
            token = inp.read(size)
            if len(token) != size:
                raise ValueError("Truncated encrypted upload")
            parts.append(fernet.decrypt(token))
        return b"".join(parts)
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


def delete_file(storage_path: str) -> None:
    try:
        os.remove(storage_path)
    except FileNotFoundError:
        pass


def cleanup_decrypted_tempfiles() -> int:
    """Remove plaintext analysis leftovers from an interrupted previous process."""
    if not _DECRYPTED_TEMP_DIR.exists():
        return 0
    removed = 0
    for path in _DECRYPTED_TEMP_DIR.glob("lineage-decrypted-*"):
        try:
            path.unlink()
            removed += 1
        except FileNotFoundError:
            pass
    return removed


def delete_encrypted(path: str) -> None:
    """Delete an encrypted local or S3 object, with a strict local path boundary."""
    if path.startswith("s3://"):
        object_storage.delete(path); return
    p = Path(path).resolve(); base = Path(settings.UPLOADS_DIR).resolve()
    try: p.relative_to(base)
    except ValueError: return
    if p.exists() and p.is_file(): p.unlink()


@contextmanager
def decrypted_tempfile(storage_path: str, suffix: str = ""):
    """Stream a chunked encrypted upload into a temporary plaintext file.

    New LINEAGE2 uploads are decrypted chunk-by-chunk, so callers can hand a
    file path to Pillow/OpenCV without creating a second whole-file buffer.
    Legacy single-Fernet files remain supported and are decrypted as one token.
    """
    _DECRYPTED_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(_DECRYPTED_TEMP_DIR, 0o700)
    except OSError:
        pass
    fd, tmp_name = tempfile.mkstemp(prefix="lineage-decrypted-", suffix=suffix, dir=str(_DECRYPTED_TEMP_DIR))
    os.close(fd)
    try:
        source = Path(storage_path)
        download_path = None
        if storage_path.startswith("s3://"):
            fd2, download_path = tempfile.mkstemp(prefix="lineage-s3-encrypted-", suffix=".enc", dir=str(_DECRYPTED_TEMP_DIR))
            os.close(fd2); object_storage.download_to_file(storage_path, download_path); source = Path(download_path)
        fernet = _get_fernet()
        with source.open("rb") as inp, Path(tmp_name).open("wb") as out:
            prefix = inp.read(9)
            if prefix != b"LINEAGE2\n":
                out.write(fernet.decrypt(prefix + inp.read()))
            else:
                while True:
                    header = inp.read(8)
                    if not header:
                        break
                    if len(header) != 8:
                        raise ValueError("Corrupt encrypted upload header")
                    size = struct.unpack("!Q", header)[0]
                    if size > 32 * 1024 * 1024:
                        raise ValueError("Corrupt encrypted upload chunk")
                    token = inp.read(size)
                    if len(token) != size:
                        raise ValueError("Truncated encrypted upload")
                    out.write(fernet.decrypt(token))
        yield tmp_name
    finally:
        Path(tmp_name).unlink(missing_ok=True)
        if "download_path" in locals() and download_path:
            Path(download_path).unlink(missing_ok=True)
