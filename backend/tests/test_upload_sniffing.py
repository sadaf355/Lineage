"""Upload content sniffing (docs/THREAT_MODEL.md T-UPLOAD-1..3)."""
import io
import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.automation import AuditEvent
from app.models.media import MediaItem
from app.services import file_storage, upload_sniff as us


def _img(fmt):
    buf = io.BytesIO(); Image.new("RGB", (8, 8), (200, 10, 10)).save(buf, fmt); return buf.getvalue()


PNG, JPG, GIF, WEBP = _img("PNG"), _img("JPEG"), _img("GIF"), _img("WEBP")
EXE = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 200
ELF = b"\x7fELF\x02\x01\x01" + b"\x00" * 200
MOV_FTYP = struct.pack(">I", 20) + b"ftypqt  " + b"\x00" * 12
MOV_MOOV_FIRST = struct.pack(">I", 24) + b"moov" + b"\x00" * 20     # old QuickTime: no ftyp box
MOV_WIDE = struct.pack(">I", 8) + b"wide" + struct.pack(">I", 16) + b"mdat" + b"\x00" * 8
MP4 = struct.pack(">I", 24) + b"ftypisom" + b"\x00" * 16
WAV = b"RIFF" + struct.pack("<I", 36) + b"WAVEfmt " + b"\x00" * 24
RF64 = b"RF64" + b"\xff\xff\xff\xff" + b"WAVEds64" + b"\x00" * 24
RIFX = b"RIFX" + struct.pack(">I", 36) + b"WAVEfmt " + b"\x00" * 24
AVI = b"RIFF" + struct.pack("<I", 36) + b"AVI LIST" + b"\x00" * 24
MP3_ID3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 50
MP3_SYNC = b"\xff\xfb\x90\x00" + b"\x00" * 50
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 50
OGG = b"OggS\x00\x02" + b"\x00" * 50
UNKNOWN = b"\x01\x02\x03\x04strange-but-maybe-valid-header" + b"\x00" * 30


@pytest.mark.parametrize("data,kind,name", [
    (PNG, "image", "a.png"), (JPG, "image", "a.jpg"), (GIF, "image", "a.gif"), (WEBP, "image", "a.webp"),
    (MOV_FTYP, "video", "clip.mov"), (MOV_MOOV_FIRST, "video", "old.mov"), (MOV_WIDE, "video", "wide.mov"),
    (MP4, "video", "clip.mp4"), (AVI, "video", "clip.avi"), (WEBM, "video", "clip.webm"),
    (WAV, "audio", "v.wav"), (RF64, "audio", "big.wav"), (RIFX, "audio", "be.wav"),
    (MP3_ID3, "audio", "v.mp3"), (MP3_SYNC, "audio", "v2.mp3"), (OGG, "audio", "v.ogg"),
    (MP4, "audio", "voice.m4a"),          # audio in an MP4 container
    (WEBM, "audio", "voice.webm"),        # browser recorder output
])
def test_valid_media_is_accepted_and_verified(data, kind, name):
    res = us.sniff_media(data, kind, name)
    assert res.ok and res.verified, res


@pytest.mark.parametrize("data,kind,name", [
    (EXE, "image", "holiday.png"),        # the headline case: renamed .exe sent as an image
    (ELF, "image", "pic.jpg"),
    (EXE, "video", "clip.mp4"),
    (b"#!/bin/sh\nrm -rf /\n", "audio", "voice.mp3"),
    (b"PK\x03\x04" + b"\x00" * 30, "video", "clip.mov"),   # zip/jar/docx
    (b"%PDF-1.7\n", "image", "scan.png"),
    (b"<html><script>alert(1)</script>", "image", "x.png"),
    (b"<?xml version='1.0'?><svg onload='x'/>", "image", "x.png"),
    (b"\xef\xbb\xbf  <?php system($_GET[1]); ?>", "image", "x.jpg"),
    (UNKNOWN, "image", "x.png"),           # an image claim with no image signature
    (MP4, "image", "x.png"),               # a video sent as an image
    (PNG, "video", "x.mp4"),               # an image sent as a video
    (PNG, "audio", "x.mp3"),
    (PNG, "image", "payload.exe"),         # real PNG bytes but an executable extension
    (PNG, "image", "run.ps1"),
])
def test_disguised_files_are_refused(data, kind, name):
    res = us.sniff_media(data, kind, name)
    assert not res.ok and not res.verified, res


def test_unrecognised_av_container_is_accepted_unverified_unless_strict():
    lenient = us.sniff_media(UNKNOWN, "video", "odd.mov")
    assert lenient.ok and not lenient.verified
    strict = us.sniff_media(UNKNOWN, "video", "odd.mov", strict_av=True)
    assert not strict.ok


def test_log_mode_records_but_does_not_refuse_and_off_disables():
    res = us.sniff_media(EXE, "image", "a.png", mode="log")
    assert res.ok and res.would_reject and not res.verified
    assert us.sniff_media(EXE, "image", "a.png", mode="off").ok


def test_evidence_only_blocks_executable_content():
    assert us.sniff_evidence(b"%PDF-1.7", "report.pdf").ok
    assert us.sniff_evidence(b"<html>saved page</html>", "page.html").ok
    assert us.sniff_evidence(b"PK\x03\x04", "export.zip").ok
    assert not us.sniff_evidence(EXE, "shot.png").ok
    assert not us.sniff_evidence(b"#!/bin/bash\n", "notes.txt").ok
    assert not us.sniff_evidence(b"anything", "setup.exe").ok


def test_safe_ext_only_keeps_simple_extensions():
    assert us.safe_ext("a.PNG") == ".png"
    assert us.safe_ext("a.tar.gz") == ".gz"
    assert us.safe_ext("noext") == ""
    assert us.safe_ext("weird.p!ng") == ""
    assert us.safe_ext("long." + "a" * 20) == ""


def test_repo_demo_assets_pass_sniffing():
    assets = Path(__file__).parents[1] / "demo_assets"
    files = [p for p in assets.iterdir() if p.suffix.lower() in {".jpg", ".png", ".mp4", ".mov", ".wav", ".mp3"}]
    assert files, "expected demo media in backend/demo_assets"
    for p in files:
        kind = "image" if p.suffix.lower() in {".jpg", ".png"} else ("audio" if p.suffix.lower() in {".wav", ".mp3"} else "video")
        res = us.sniff_media(p.read_bytes()[:us.HEAD_BYTES], kind, p.name)
        assert res.ok and res.verified, (p.name, res)


# ---- through the API: nothing is stored when a file is refused ----------------------------------------
@pytest.fixture()
def api(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)

    def override():
        db = Session()
        try: yield db
        finally: db.close()
    app.dependency_overrides[get_db] = override
    from cryptography.fernet import Fernet
    monkeypatch.setattr(file_storage.settings, "UPLOADS_DIR", str(tmp_path))
    monkeypatch.setattr(file_storage.settings, "FILE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(file_storage.settings, "FILE_ENCRYPTION_KEY_PREVIOUS", "")
    monkeypatch.setattr(file_storage.settings, "DATA_DIR", str(tmp_path))
    c = TestClient(app)
    assert c.post("/auth/register", json={"email": "s@example.com", "password": "StrongPass123!", "display_name": "s"}).status_code == 201
    tok = c.post("/auth/login", data={"username": "s@example.com", "password": "StrongPass123!"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    iid = c.post("/incidents", json={"title": "t"}, headers=h).json()["id"]
    yield c, Session, h, iid, tmp_path
    app.dependency_overrides.clear()


def test_api_refuses_exe_renamed_to_png_and_stores_nothing(api):
    c, Session, h, iid, tmp = api
    r = c.post(f"/incidents/{iid}/media", files={"file": ("holiday.png", io.BytesIO(EXE), "image/png")}, headers=h)
    assert r.status_code == 415 and "looks like windows-executable" in r.json()["detail"]
    with Session() as db:
        assert db.query(MediaItem).count() == 0
        ev = db.query(AuditEvent).filter(AuditEvent.action == "upload_rejected").one()
        assert "windows-executable" in ev.details_json
    assert not list(Path(tmp).glob("*.enc"))


def test_api_accepts_real_png_and_unverified_mov_is_audited(api):
    c, Session, h, iid, _ = api
    assert c.post(f"/incidents/{iid}/media", files={"file": ("ok.png", io.BytesIO(PNG), "image/png")}, headers=h).status_code == 201
    r = c.post(f"/incidents/{iid}/media", files={"file": ("odd.mov", io.BytesIO(UNKNOWN), "video/quicktime")}, headers=h)
    assert r.status_code == 201
    with Session() as db:
        assert db.query(AuditEvent).filter(AuditEvent.action == "upload_unverified").count() == 1


def test_api_strict_av_setting_refuses_unrecognised_container(api, monkeypatch):
    c, _, h, iid, _ = api
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "UPLOAD_SNIFF_STRICT_AV", True)
    r = c.post(f"/incidents/{iid}/media", files={"file": ("odd.mov", io.BytesIO(UNKNOWN), "video/quicktime")}, headers=h)
    assert r.status_code == 415


def test_api_evidence_refuses_executables_but_accepts_saved_pages(api):
    c, _, h, iid, _ = api
    bad = c.post(f"/incidents/{iid}/evidence", data={"item_type": "screenshot"}, files={"file": ("shot.png", io.BytesIO(EXE), "image/png")}, headers=h)
    assert bad.status_code == 415
    ok = c.post(f"/incidents/{iid}/evidence", data={"item_type": "page"}, files={"file": ("page.html", io.BytesIO(b"<html>x</html>"), "text/html")}, headers=h)
    assert ok.status_code == 201


def test_stored_filename_extension_is_sanitised(api):
    c, _, h, iid, tmp = api
    c.post(f"/incidents/{iid}/media", files={"file": ("a.p!ng", io.BytesIO(PNG), "image/png")}, headers=h)
    assert all(p.name.endswith(".enc") and "!" not in p.name for p in Path(tmp).glob("*.enc"))
