from app.core.local_auth import hash_password, verify_password


def test_hash_password_is_salted_and_verifiable() -> None:
    first = hash_password("INP@2026")
    second = hash_password("INP@2026")
    assert first != second
    assert first.startswith("scrypt$")
    assert "INP@2026" not in first
    assert verify_password("INP@2026", first)
    assert verify_password("INP@2026", second)


def test_verify_password_rejects_wrong_or_malformed_hash() -> None:
    stored = hash_password("INP@2026")
    assert not verify_password("inp@2026", stored)
    assert not verify_password("INP@2026", "texto-puro")
    assert not verify_password("INP@2026", "bcrypt$1$2$3$aa$bb")
