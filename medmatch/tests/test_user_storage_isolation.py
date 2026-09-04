from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from backend.scanner import storage


def _run_as(token: str, callback):
    context_token = storage.set_device_token(token)
    try:
        return callback()
    finally:
        storage.reset_device_token(context_token)


def test_device_storage_isolated_and_token_paths_are_safe(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "_DEVICES_DIR", tmp_path)
    storage._USER_DB_CACHE.clear()

    first_token = storage.new_device_token()
    second_token = storage.new_device_token()
    assert storage.is_valid_device_token(first_token)
    assert storage.is_valid_device_token(second_token)
    assert not storage.is_valid_device_token("../../shared")

    first = _run_as(
        first_token,
        lambda: storage.get_user_db(),
    )
    first.update_user_profile({"name": "Alice"})
    first.add_history({"productName": "Private item", "matchAssessment": {"status": "safe", "score": 100}})

    second = _run_as(second_token, lambda: storage.get_user_db())
    assert second is not first
    assert second.get_user_profile()["name"] != "Alice"
    assert second.get_history() == []
    assert first.storage_file == tmp_path / f"{first_token}.json"
    assert second.storage_file == tmp_path / f"{second_token}.json"


def test_concurrent_contexts_keep_cache_instances_separate(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "_DEVICES_DIR", tmp_path)
    storage._USER_DB_CACHE.clear()
    tokens = [storage.new_device_token() for _ in range(12)]

    def load_and_update(token: str):
        def update():
            db = storage.get_user_db()
            db.update_user_profile({"name": token})
            return id(db), db.get_user_profile()["name"]

        return _run_as(token, update)

    with ThreadPoolExecutor(max_workers=len(tokens)) as executor:
        results = list(executor.map(load_and_update, tokens))

    assert {name for _, name in results} == set(tokens)
    assert len({instance_id for instance_id, _ in results}) == len(tokens)
    assert len(list(tmp_path.glob("*.json"))) == len(tokens)


def test_missing_identity_uses_non_persistent_memory_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "_DEVICES_DIR", tmp_path)
    storage._NO_IDENTITY_DB.history = []
    storage._NO_IDENTITY_DB.update_user_profile({"name": "Transient"})
    storage._NO_IDENTITY_DB.add_history({"productName": "Transient", "matchAssessment": {"status": "safe", "score": 100}})

    assert not list(tmp_path.iterdir())
    assert storage.get_user_db() is storage._NO_IDENTITY_DB


def test_export_and_delete_cover_all_device_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "_DEVICES_DIR", tmp_path)
    storage._USER_DB_CACHE.clear()
    token = storage.new_device_token()

    def populate():
        db = storage.get_user_db()
        db.update_user_profile({
            "name": "Private",
            "pharmacogenomics": {
                "genotype": "CYP2C19 *2/*2",
                "phenotype": "poor metabolizer",
                "indication": "anticoagulation",
            },
        })
        db.set_routine([{"id": "routine-1", "name": "Private routine"}])
        db.add_history({"productName": "Private scan"})
        db.upsert_reminder({"label": "Morning medication", "medication": "Warfarin", "time": "08:00", "days": list(range(7)), "enabled": True})
        return db

    db = _run_as(token, populate)
    exported = db.export_data()
    assert exported["userProfile"]["name"] == "Private"
    assert exported["routine"][0]["name"] == "Private routine"
    assert exported["history"][0]["productName"] == "Private scan"
    assert exported["reminders"][0]["label"] == "Morning medication"
    assert exported["userProfile"]["pharmacogenomics"]["phenotype"] == "poor metabolizer"

    cleared = db.clear_all_data()
    assert cleared["history"] == []
    assert cleared["routine"] == []
    assert cleared["reminders"] == []
    assert cleared["userProfile"]["name"] == "You"


def test_reminders_persist_and_follow_active_profile(tmp_path) -> None:
    token = storage.new_device_token()
    path = tmp_path / f"{token}.json"
    db = storage.ScannerDB(token=token, storage_file=path)

    reminder = db.upsert_reminder({
        "label": "Evening medication",
        "medication": "Metformin",
        "time": "20:30",
        "days": [1, 3, 5],
        "enabled": True,
        "timezone": "Asia/Ho_Chi_Minh",
    })
    assert reminder["profileId"] == "profile_primary"
    assert db.get_reminders() == [reminder]

    reloaded = storage.ScannerDB(token=token, storage_file=path)
    assert reloaded.get_reminders()[0]["timezone"] == "Asia/Ho_Chi_Minh"
    reloaded.switch_family_profile("profile_child")
    assert reloaded.get_reminders() == []
    assert reloaded.delete_reminder(reminder["id"]) is False
    reloaded.switch_family_profile("profile_primary")
    assert reloaded.delete_reminder(reminder["id"]) is True
    assert reloaded.get_reminders() == []
