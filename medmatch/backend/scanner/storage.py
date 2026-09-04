"""Scanner user-data storage — ported from personalized-product-scanner/server/db.ts — do not diverge.

JSON-file persistence with atomic tmp+rename saves. HTTP requests use one
server-side `<SCANNER_DATA_DIR>/<opaque-device-token>.json` namespace per
device; non-request callers use an in-memory database.
"""
from __future__ import annotations
import json
import os
import random
import re
import secrets
import time
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock


_DEVICE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def is_valid_device_token(token: str | None) -> bool:
    return bool(token and _DEVICE_TOKEN_RE.fullmatch(token))


def new_device_token() -> str:
    return secrets.token_urlsafe(32)


def _iso_now() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _rand_token(n: int) -> str:
    return "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(n))


def _now_ms() -> int:
    return int(time.time() * 1000)


DEFAULT_ROUTINE: list[dict] = [
    {
        "id": "routine_1",
        "name": "CeraVe Hydrating Cleanser",
        "brand": "CeraVe",
        "step": "cleanser",
        "timeOfDay": "both",
        "activeIngredients": ["Ceramides", "Hyaluronic Acid"],
    },
    {
        "id": "routine_2",
        "name": "The Ordinary Niacinamide 10% + Zinc 1% Serum",
        "brand": "The Ordinary",
        "step": "serum",
        "timeOfDay": "am",
        "activeIngredients": ["Niacinamide (Vitamin B3)", "Zinc PCA"],
    },
    {
        "id": "routine_3",
        "name": "Paula’s Choice 1% Retinol Treatment",
        "brand": "Paula’s Choice",
        "step": "treatment",
        "timeOfDay": "pm",
        "activeIngredients": ["Retinol", "Peptides"],
    },
    {
        "id": "routine_4",
        "name": "La Roche-Posay Anthelios UVMune 400 Sunscreen",
        "brand": "La Roche-Posay",
        "step": "sunscreen",
        "timeOfDay": "am",
        "activeIngredients": ["Mexoryl 400", "Chemical UV Filters"],
    },
]

DEFAULT_PROFILE: dict = {
    "id": "profile_primary",
    "name": "Alex Rivera",
    "role": "Primary Account",
    "avatarColor": "blue",
    "allergies": ["peanut", "milk"],
    "customAllergens": [],
    "dietType": "omnivore",
    "specialConditions": [],
    "medications": [],
    "pharmacogenomics": {},
    "updatedAt": None,  # filled with real ISO at instantiation
}

DEFAULT_FAMILY_PROFILES: list[dict] = [
    {
        "id": "profile_primary",
        "name": "Alex Rivera",
        "role": "Self (Primary)",
        "avatarColor": "blue",
        "allergies": ["peanut", "milk"],
        "customAllergens": [],
        "dietType": "omnivore",
        "specialConditions": [],
        "pharmacogenomics": {},
        "medications": [],
    },
    {
        "id": "profile_child",
        "name": "Liam (6 y/o)",
        "role": "Child",
        "avatarColor": "amber",
        "age": 6,
        "allergies": ["peanut", "tree_nut", "egg", "sesame"],
        "customAllergens": ["red 40", "titanium dioxide"],
        "dietType": "omnivore",
        "specialConditions": ["eczema"],
        "medications": [],
    },
    {
        "id": "profile_partner",
        "name": "Elena",
        "role": "Partner",
        "avatarColor": "purple",
        "age": 34,
        "allergies": ["fragrance", "salicylic_acid", "parabens"],
        "customAllergens": [],
        "dietType": "vegan",
        "specialConditions": ["pregnant", "sensitive_skin"],
        "medications": [],
    },
    {
        "id": "profile_parent",
        "name": "Arthur (Senior)",
        "role": "Parent",
        "avatarColor": "emerald",
        "age": 68,
        "allergies": ["gluten"],
        "customAllergens": ["high fructose corn syrup"],
        "dietType": "low_sodium",
        "specialConditions": ["hypertension"],
        "medications": ["Amlodipine", "Metformin"],
    },
]

_EMPTY_ANALYTICS = {
    "averageCompatibilityScore": 100,
    "totalProductsScanned": 0,
    "safeCount": 0,
    "warningCount": 0,
    "dangerCount": 0,
    "ultraProcessedCount": 0,
    "ultraProcessedPercentage": 0,
    "topAllergensAvoided": [],
    "flaggedAdditivesEncountered": [],
    "cleanProductRatio": 100,
}

class ScannerDB:
    def __init__(
        self,
        token: str | None = None,
        *,
        storage_file: Path | None = None,
        persist: bool = True,
    ) -> None:
        default_path = (
            Path(__file__).resolve().parent.parent / "data" / "devices" / f"{token}.json"
            if token
            else Path(__file__).resolve().parent.parent / "data" / "scanner_storage.json"
        )
        # A device token always selects its own file. The legacy override is
        # retained only for the singleton/explicit non-device database used by
        # maintenance scripts and tests.
        configured_path = os.environ.get("SCANNER_STORAGE_PATH")
        self.storage_file: Path | None = (
            storage_file or default_path
            if token
            else Path(configured_path or storage_file or default_path)
        ) if persist else None
        self.token = token
        self._cache: dict[str, dict] = {}
        self._lock = RLock()
        self.user_profile: dict = {**DEFAULT_PROFILE, "updatedAt": _iso_now()}
        self.family_profiles: list[dict] = json.loads(json.dumps(DEFAULT_FAMILY_PROFILES))
        self.routine: list[dict] = json.loads(json.dumps(DEFAULT_ROUTINE))
        self.reminders: list[dict] = []
        self.history: list[dict] = []
        self._load_from_disk()

    # --- persistence -------------------------------------------------------
    def _load_from_disk(self) -> None:
        if self.storage_file is None:
            return
        try:
            if self.storage_file.exists():
                data = json.loads(self.storage_file.read_text(encoding="utf-8"))
                if data.get("userProfile"):
                    self.user_profile = data["userProfile"]
                if isinstance(data.get("familyProfiles"), list) and len(data["familyProfiles"]) > 0:
                    self.family_profiles = data["familyProfiles"]
                if isinstance(data.get("routine"), list) and len(data["routine"]) > 0:
                    self.routine = data["routine"]
                if isinstance(data.get("reminders"), list):
                    self.reminders = data["reminders"]
                if isinstance(data.get("history"), list):
                    self.history = data["history"]
                if isinstance(data.get("cache"), dict):
                    self._cache.update(data["cache"])
        except Exception as e:  # noqa: BLE001 - mirror TS console.warn behavior
            print(f"Could not load storage from disk, using in-memory default: {e}")

    def _save_to_disk(self) -> None:
        if self.storage_file is None:
            return
        with self._lock:
            try:
                # Save top 200 cache items to prevent file bloat
                cache_obj = dict(list(self._cache.items())[:200])
                data = {
                    "userProfile": self.user_profile,
                    "familyProfiles": self.family_profiles,
                    "routine": self.routine,
                    "history": self.history[:100],
                    "reminders": self.reminders[:32],
                    "cache": cache_obj,
                }
                tmp = self.storage_file.with_suffix(".json.tmp")
                tmp.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(tmp, self.storage_file)
            except Exception as e:  # noqa: BLE001
                print(f"Could not persist storage to disk: {e}")

    # --- cache methods (parity with TS; unused by routes) --------------------
    def get_cache(self, key: str, max_age_ms: int = 1000 * 60 * 60 * 24 * 7) -> dict | None:
        entry = self._cache.get(key)
        if not entry:
            return None
        if _now_ms() - entry["cachedAt"] > max_age_ms:
            del self._cache[key]
            return None
        return entry["data"]

    def set_cache(self, key: str, data) -> None:
        self._cache[key] = {"key": key, "data": data, "cachedAt": _now_ms()}
        self._save_to_disk()

    # --- user profile --------------------------------------------------------
    def get_user_profile(self) -> dict:
        return self.user_profile


    def export_data(self) -> dict:
        """Return the current device namespace without exposing another token."""
        with self._lock:
            return json.loads(json.dumps({
                "userProfile": self.user_profile,
                "familyProfiles": self.family_profiles,
                "routine": self.routine,
                "reminders": self.get_reminders(),
                "history": self.history,
            }))

    def clear_all_data(self) -> dict:
        """Erase profile, family profiles, routine, reminders, history, and cache."""
        with self._lock:
            self.user_profile = {
                "id": "profile_primary",
                "name": "You",
                "role": "Primary Account",
                "avatarColor": "blue",
                "allergies": [],
                "customAllergens": [],
                "dietType": "omnivore",
                "specialConditions": [],
                "medications": [],
                "age": None,
                "gender": None,
                "pregnancyStatus": None,
                "lactationStatus": None,
                "kidneyFunction": None,
                "scheduleTimes": {},
                "pharmacogenomics": {},
                "updatedAt": _iso_now(),
            }
            self.family_profiles = [dict(self.user_profile)]
            self.routine = []
            self.reminders = []
            self.history = []
            self._cache = {}
            self._save_to_disk()
            return self.export_data()

    # --- medication reminders -------------------------------------------------
    def get_reminders(self) -> list[dict]:
        profile_id = self.user_profile.get("id") or "profile_primary"
        return [
            reminder
            for reminder in self.reminders
            if reminder.get("profileId", profile_id) == profile_id
        ]

    def upsert_reminder(self, reminder: dict) -> dict:
        profile_id = self.user_profile.get("id") or "profile_primary"
        reminder_id = str(reminder.get("id") or f"reminder_{_now_ms()}_{_rand_token(5)}")
        existing = next(
            (
                item
                for item in self.reminders
                if item.get("id") == reminder_id and item.get("profileId", profile_id) == profile_id
            ),
            None,
        )
        item = {
            **(existing or {}),
            **reminder,
            "id": reminder_id,
            "profileId": profile_id,
            "updatedAt": _iso_now(),
        }
        if existing is None:
            item["createdAt"] = item["updatedAt"]
            self.reminders = [*self.reminders, item]
        else:
            self.reminders = [
                item if row.get("id") == reminder_id and row.get("profileId", profile_id) == profile_id else row
                for row in self.reminders
            ]
        self.reminders = self.reminders[-32:]
        self._save_to_disk()
        return item

    def delete_reminder(self, reminder_id: str) -> bool:
        profile_id = self.user_profile.get("id") or "profile_primary"
        before = len(self.reminders)
        self.reminders = [
            item
            for item in self.reminders
            if not (item.get("id") == reminder_id and item.get("profileId", profile_id) == profile_id)
        ]
        if len(self.reminders) == before:
            return False
        self._save_to_disk()
        return True

    def update_user_profile(self, profile: dict) -> dict:
        self.user_profile = {
            **self.user_profile,
            **profile,
            "updatedAt": _iso_now(),
        }
        # Keep the full active profile synced in familyProfiles.
        for p in self.family_profiles:
            if p["id"] == self.user_profile["id"]:
                p.update(
                    {
                        "name": self.user_profile.get("name") or p.get("name"),
                        "role": self.user_profile.get("role") or p.get("role"),
                        "avatarColor": self.user_profile.get("avatarColor") or p.get("avatarColor"),
                        "allergies": self.user_profile.get("allergies") or [],
                        "customAllergens": self.user_profile.get("customAllergens") or [],
                        "dietType": self.user_profile.get("dietType"),
                        "specialConditions": self.user_profile.get("specialConditions") or [],
                        "medications": self.user_profile.get("medications") or [],
                        "age": self.user_profile.get("age"),
                        "gender": self.user_profile.get("gender"),
                        "pregnancyStatus": self.user_profile.get("pregnancyStatus"),
                        "lactationStatus": self.user_profile.get("lactationStatus"),
                        "kidneyFunction": self.user_profile.get("kidneyFunction"),
                        "scheduleTimes": self.user_profile.get("scheduleTimes") or {},
                        "pharmacogenomics": dict(self.user_profile.get("pharmacogenomics") or {}),
                    }
                )
                break
        self._save_to_disk()
        return self.user_profile

    def get_family_profiles(self) -> list[dict]:
        return self.family_profiles

    def switch_family_profile(self, profile_id: str) -> dict:
        found = next((p for p in self.family_profiles if p["id"] == profile_id), None)
        if found:
            self.user_profile = {
                "id": found["id"],
                "name": found["name"],
                "role": found["role"],
                "avatarColor": found["avatarColor"],
                "allergies": list(found.get("allergies") or []),
                "customAllergens": list(found.get("customAllergens") or []),
                "dietType": found.get("dietType") or "omnivore",
                "specialConditions": list(found.get("specialConditions") or []),
                "medications": list(found.get("medications") or []),
                "age": found.get("age"),
                "gender": found.get("gender"),
                "pregnancyStatus": found.get("pregnancyStatus"),
                "lactationStatus": found.get("lactationStatus"),
                "kidneyFunction": found.get("kidneyFunction"),
                "scheduleTimes": dict(found.get("scheduleTimes") or {}),
                "pharmacogenomics": dict(found.get("pharmacogenomics") or {}),
                "updatedAt": _iso_now(),
            }
            self._save_to_disk()
        return self.user_profile

    def add_or_update_family_profile(self, profile: dict) -> list[dict]:
        idx = next((i for i, p in enumerate(self.family_profiles) if p["id"] == profile["id"]), -1)
        if idx >= 0:
            self.family_profiles[idx] = profile
        else:
            self.family_profiles.append(profile)
        if self.user_profile["id"] == profile["id"]:
            self.user_profile.update(
                {
                    "name": profile.get("name"),
                    "role": profile.get("role"),
                    "avatarColor": profile.get("avatarColor"),
                    "allergies": list(profile.get("allergies") or []),
                    "customAllergens": list(profile.get("customAllergens") or []),
                    "dietType": profile.get("dietType") or "omnivore",
                    "specialConditions": list(profile.get("specialConditions") or []),
                    "medications": list(profile.get("medications") or []),
                    "age": profile.get("age"),
                    "gender": profile.get("gender"),
                    "pregnancyStatus": profile.get("pregnancyStatus"),
                    "lactationStatus": profile.get("lactationStatus"),
                    "kidneyFunction": profile.get("kidneyFunction"),
                    "scheduleTimes": dict(profile.get("scheduleTimes") or {}),
                    "pharmacogenomics": dict(profile.get("pharmacogenomics") or {}),
                }
            )
        self._save_to_disk()
        return self.family_profiles

    def delete_family_profile(self, id: str) -> list[dict]:
        if len(self.family_profiles) <= 1:
            return self.family_profiles
        self.family_profiles = [p for p in self.family_profiles if p["id"] != id]
        if self.user_profile["id"] == id and len(self.family_profiles) > 0:
            self.switch_family_profile(self.family_profiles[0]["id"])
        self._save_to_disk()
        return self.family_profiles

    # --- skincare routine shelf ----------------------------------------------
    def get_routine(self) -> list[dict]:
        return self.routine

    def set_routine(self, routine: list[dict]) -> list[dict]:
        self.routine = routine
        self._save_to_disk()
        return self.routine

    def add_or_update_routine_item(self, item: dict) -> list[dict]:
        idx = next((i for i, r in enumerate(self.routine) if r["id"] == item.get("id")), -1)
        if idx >= 0:
            self.routine[idx] = item
        else:
            item = {**item}
            item.setdefault("id", f"routine_{_now_ms()}_{_rand_token(4)}")
            self.routine.append(item)
        self._save_to_disk()
        return self.routine

    def delete_routine_item(self, id: str) -> list[dict]:
        self.routine = [r for r in self.routine if r["id"] != id]
        self._save_to_disk()
        return self.routine

    # --- analytics --------------------------------------------------------------
    def get_health_analytics(self) -> dict:
        history = self.history
        total = len(history)
        if total == 0:
            return dict(_EMPTY_ANALYTICS)

        safe_count = sum(1 for h in history if h.get("status") == "safe")
        warning_count = sum(1 for h in history if h.get("status") in ("warning", "caution"))
        danger_count = sum(1 for h in history if h.get("status") == "danger")
        total_score = sum(h.get("score") or 0 for h in history)
        avg_score = round(total_score / total)

        ultra_processed = sum(
            1 for h in history
            if ((h.get("fullResult") or {}).get("nutrition") or {}).get("novaGroup") == 4
        )
        nova_percentage = round((ultra_processed / total) * 100)
        allergen_map: dict[str, int] = {}
        additive_map: dict[str, dict] = {}

        for h in history:
            full = h.get("fullResult") or {}
            warnings = ((full.get("matchAssessment") or {}).get("warnings")) or []
            for w in warnings:
                if w.get("category") == "allergy":
                    allergen_map[w["matchedItem"]] = allergen_map.get(w["matchedItem"], 0) + 1
                else:
                    key = w.get("matchedItem") or w.get("title")
                    additive_map[key] = {
                        "count": (additive_map.get(key) or {}).get("count", 0) + 1,
                        "risk": w.get("message"),
                    }

        top_allergens = sorted(
            [{"name": n, "count": c} for n, c in allergen_map.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]
        flagged_additives = sorted(
            [{"name": n, "count": v["count"], "risk": v["risk"]} for n, v in additive_map.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        clean_ratio = round((safe_count / total) * 100)

        return {
            "averageCompatibilityScore": avg_score,
            "totalProductsScanned": total,
            "safeCount": safe_count,
            "warningCount": warning_count,
            "dangerCount": danger_count,
            "ultraProcessedCount": ultra_processed,
            "ultraProcessedPercentage": nova_percentage,
            "topAllergensAvoided": top_allergens,
            "flaggedAdditivesEncountered": flagged_additives,
            "cleanProductRatio": clean_ratio,
        }

    # --- history ------------------------------------------------------------------
    def get_history(self) -> list[dict]:
        return self.history

    def add_history(self, result: dict) -> dict:
        ma = result.get("matchAssessment") or {}
        item = {
            "id": f"scan_{_now_ms()}_{_rand_token(5)}",
            "barcode": result.get("barcode"),
            "productName": result.get("productName"),
            "brand": result.get("brand"),
            "productType": result.get("productType"),
            "imageUrl": result.get("imageUrl"),
            "status": ma.get("status"),
            "score": ma.get("score"),
            "warningCount": len(ma.get("warnings") or []),
            "scannedAt": result.get("scannedAt"),
            "fullResult": result,
            "favorite": False,
        }
        # Remove older scan of same barcode if duplicate to keep history clean
        self.history = [item] + [h for h in self.history if h["barcode"] != result.get("barcode")]
        self.history = self.history[:100]
        self._save_to_disk()
        return item

    def toggle_favorite(self, history_id: str) -> bool:
        for item in self.history:
            if item["id"] == history_id:
                item["favorite"] = not item["favorite"]
                self._save_to_disk()
                return bool(item["favorite"])
        return False

    def clear_history(self) -> None:
        self.history = []
        self._save_to_disk()

_DEVICES_DIR = Path(
    os.environ.get("SCANNER_DATA_DIR")
    or Path(__file__).resolve().parent.parent / "data" / "devices"
)
_CURRENT_TOKEN: ContextVar[str | None] = ContextVar("mt_device", default=None)
_USER_DB_CACHE: dict[str, "ScannerDB"] = {}
_USER_DB_CACHE_LOCK = RLock()
_NO_IDENTITY_DB = ScannerDB(persist=False)


def set_device_token(token: str) -> Token[str | None]:
    return _CURRENT_TOKEN.set(token)


def reset_device_token(token: Token[str | None]) -> None:
    _CURRENT_TOKEN.reset(token)


def get_device_token() -> str | None:
    return _CURRENT_TOKEN.get()


def get_user_db() -> "ScannerDB":
    # Internal, non-request callers (for example a standalone skincare rule
    # evaluation) get an in-memory database. Public HTTP requests always pass
    # through app middleware, which assigns a validated device token first.
    token = _CURRENT_TOKEN.get()
    if not token:
        return _NO_IDENTITY_DB
    with _USER_DB_CACHE_LOCK:
        inst = _USER_DB_CACHE.get(token)
        if inst is None:
            _DEVICES_DIR.mkdir(parents=True, exist_ok=True)
            inst = ScannerDB(token=token, storage_file=_DEVICES_DIR / f"{token}.json")
            _USER_DB_CACHE[token] = inst
        return inst


db = ScannerDB()
