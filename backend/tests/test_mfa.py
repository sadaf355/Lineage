import base64
import json

import pytest
from cryptography.fernet import Fernet

from app.core.config import get_settings
from app.services import mfa, totp

SECRET = base64.b32encode(b"12345678901234567890").decode()


def test_secret_is_encrypted_at_rest_and_round_trips():
    stored = mfa.encrypt_secret(SECRET)
    assert stored.startswith("enc1:") and SECRET not in stored
    assert mfa.decrypt_secret(stored) == SECRET
    assert mfa.decrypt_secret(SECRET) == SECRET                  # legacy plaintext still readable
    assert mfa.decrypt_secret(None) is None
    assert mfa.decrypt_secret("enc1:not-a-token") is None         # damaged value never raises


def test_explicit_key_is_used_and_a_different_key_cannot_read_it(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    stored = mfa.encrypt_secret(SECRET)
    monkeypatch.setattr(s, "MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert mfa.decrypt_secret(stored) is None


def test_production_without_a_key_refuses_instead_of_deriving_one(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "ENV", "production")
    monkeypatch.setattr(s, "MFA_ENCRYPTION_KEY", "")
    with pytest.raises(mfa.MfaConfigError):
        mfa.encrypt_secret(SECRET)


def test_a_totp_code_cannot_be_reused_or_replaced_by_an_older_one():
    t = 1_111_111_109                                              # RFC vector: code 081804
    first = mfa.check(SECRET, None, None, "081804", at=t)
    assert first.ok and first.via == "totp" and first.last_step == t // 30
    again = mfa.check(SECRET, first.last_step, None, "081804", at=t + 5)         # same code, still inside the window
    assert again.ok is False
    earlier = totp.totp(SECRET, at=t - 30)
    assert mfa.check(SECRET, first.last_step, None, earlier, at=t + 5).ok is False   # an older step is refused too
    nxt = totp.totp(SECRET, at=t + 30)
    assert mfa.check(SECRET, first.last_step, None, nxt, at=t + 31).ok is True       # the next step is fine


def test_recovery_codes_work_once_and_only_the_right_ones():
    codes = mfa.new_recovery_codes(10)
    assert len(set(codes)) == 10 and all(len(c) == 11 and c[5] == "-" for c in codes)
    stored = mfa.hash_codes(codes)
    assert codes[0] not in stored and mfa.remaining(stored) == 10
    r = mfa.check(SECRET, None, stored, codes[3].upper().replace("-", " "))                # case, dash and spacing do not matter
    assert r.ok and r.via == "recovery" and mfa.remaining(r.recovery_json) == 9
    assert mfa.check(SECRET, None, r.recovery_json, codes[3]).ok is False                  # already used
    assert mfa.check(SECRET, None, r.recovery_json, codes[4]).ok is True                   # the others still work
    assert mfa.check(SECRET, None, stored, "aaaaa-aaaaa").ok is False
    assert mfa.check(SECRET, None, "not json", codes[0]).ok is False
    assert mfa.check(None, None, stored, "123456").ok is False


def test_recovery_codes_are_tied_to_the_server_key(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    codes = mfa.new_recovery_codes(2)
    stored = mfa.hash_codes(codes)
    monkeypatch.setattr(s, "MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert mfa.check(None, None, stored, codes[0]).ok is False                              # a copied hash list is useless elsewhere
    assert json.loads(stored) and all(len(h) == 64 for h in json.loads(stored))
