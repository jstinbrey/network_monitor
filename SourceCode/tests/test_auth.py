"""Tests for core/auth.py and the account functions in services.py."""
import pytest

from netmonitor import config, models, services
from netmonitor.core import auth


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    """Each test gets an empty database, fast hashing, nobody signed in and no lock."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "AUTH_ITERATIONS", 1_000)
    monkeypatch.setattr(services, "_user", None)
    monkeypatch.setattr(services, "_failures", 0)
    monkeypatch.setattr(services, "_locked_until", 0.0)


def test_hash_round_trip():
    salt, digest = auth.hash_password("correct horse")
    assert auth.verify_password("correct horse", salt, digest)
    assert not auth.verify_password("wrong horse", salt, digest)


def test_same_password_twice_gives_different_hashes():
    assert auth.hash_password("same pass")[1] != auth.hash_password("same pass")[1]


@pytest.mark.parametrize("password, confirm", [
    ("short", "short"),                 # too short
    ("Alice123", "Alice123"),           # same as the username
    ("longenough", "longenougH"),       # confirm does not match
])
def test_bad_new_passwords_are_rejected(password, confirm):
    with pytest.raises(ValueError):
        auth.check_new_password("alice123", password, confirm)


def test_first_run_creates_the_admin_once():
    assert services.needs_setup()
    assert services.create_first_admin(" Admin ", "adminpass", "adminpass") == models.User("admin", models.ADMIN)
    assert not services.needs_setup()
    with pytest.raises(PermissionError):
        services.create_first_admin("other", "otherpass", "otherpass")


def test_a_user_cannot_do_admin_things():
    services.create_first_admin("admin", "adminpass", "adminpass")
    services.add_user("bob", "bobspass", "bobspass", models.USER)
    services.logout()
    assert not services.login("Bob", "bobspass").is_admin
    with pytest.raises(PermissionError):
        services.require_admin()
    with pytest.raises(PermissionError):
        services.add_user("eve", "evespass", "evespass", models.ADMIN)


def test_unknown_name_and_wrong_password_give_the_same_message():
    services.create_first_admin("admin", "adminpass", "adminpass")
    for name, password in [("nobody", "adminpass"), ("admin", "wrongpass")]:
        with pytest.raises(ValueError, match="^Wrong username or password.$"):
            services.login(name, password)


def test_the_signed_in_admin_cannot_remove_themselves():
    services.create_first_admin("admin", "adminpass", "adminpass")
    with pytest.raises(ValueError):
        services.delete_user("admin")
    with pytest.raises(ValueError):
        services.set_role("admin", models.USER)
    assert services.users() == [models.User("admin", models.ADMIN)]


def test_sixth_attempt_is_refused_even_with_the_right_password(monkeypatch):
    services.create_first_admin("admin", "adminpass", "adminpass")
    for _ in range(config.LOGIN_MAX_FAILURES):
        with pytest.raises(ValueError, match="Wrong"):
            services.login("admin", "wrongpass")
    with pytest.raises(ValueError, match="Too many attempts. Wait 30 s."):
        services.login("admin", "adminpass")
    monkeypatch.setattr(services, "_locked_until", 0.0)          # as if the 30 s had passed
    assert services.login("admin", "adminpass").is_admin