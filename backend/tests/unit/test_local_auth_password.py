from app.core.local_auth import hash_password, verify_password


def test_hash_password_is_salted_and_verifiable() -> None:
    first = hash_password("TestOnly-Passw0rd!")
    second = hash_password("TestOnly-Passw0rd!")
    assert first != second
    assert first.startswith("scrypt$")
    assert "TestOnly-Passw0rd!" not in first
    assert verify_password("TestOnly-Passw0rd!", first)
    assert verify_password("TestOnly-Passw0rd!", second)


def test_verify_password_rejects_wrong_or_malformed_hash() -> None:
    stored = hash_password("TestOnly-Passw0rd!")
    assert not verify_password("testonly-passw0rd!", stored)
    assert not verify_password("TestOnly-Passw0rd!", "texto-puro")
    assert not verify_password("TestOnly-Passw0rd!", "bcrypt$1$2$3$aa$bb")
