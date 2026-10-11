import pytest
from sqlalchemy import func, select, update

from app.db.engine import Database, normalize_url
from app.db.models import Crop, CropAlias, CropProblem, SafetyTerm
from app.knowledge import crop_entry, load_aliases, load_safety, reload_knowledge
from app.knowledge.safety import audit_text
from app.services.crop_names import normalize_crop


@pytest.fixture
async def db(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'k.db'}")
    await database.ensure_ready()
    yield database
    await database.dispose()


@pytest.mark.parametrize("url,expected", [
    ("sqlite:///./a.db", "sqlite+aiosqlite:///./a.db"),
    ("sqlite+aiosqlite:///./a.db", "sqlite+aiosqlite:///./a.db"),
    ("postgres://u:p@h:5432/d", "postgresql+asyncpg://u:p@h:5432/d"),
    ("postgresql://u:p@h/d", "postgresql+asyncpg://u:p@h/d"),
    ("postgresql://u:p@h/d?sslmode=require", "postgresql+asyncpg://u:p@h/d?ssl=require"),
    ("postgresql://u:p@h/d?sslmode=require&channel_binding=require", "postgresql+asyncpg://u:p@h/d?ssl=require"),
    ("postgresql://u:p@h/d?sslmode=disable", "postgresql+asyncpg://u:p@h/d"),
    ("postgresql+asyncpg://u:p@h/d?ssl=require", "postgresql+asyncpg://u:p@h/d?ssl=require"),
])
def test_database_url_normalised_for_async_drivers(url, expected):
    assert normalize_url(url) == expected


async def test_tables_are_created_and_seeded(db):
    async with db.session() as s:
        assert await s.scalar(select(func.count()).select_from(Crop)) == 6
        assert await s.scalar(select(func.count()).select_from(CropProblem)) >= 18
        assert await s.scalar(select(func.count()).select_from(SafetyTerm)) > 40
    assert db.dialect == "sqlite"


async def test_seeding_is_idempotent_and_never_overwrites_edits(db):
    async with db.session() as s:
        await s.execute(update(Crop).where(Crop.key == "cassava").values(planting_calendar="EDITED IN DB"))
        await s.commit()
    db._ready = False
    await db.ensure_ready()  # second start: tables already hold data
    async with db.session() as s:
        assert (await s.get(Crop, "cassava")).planting_calendar == "EDITED IN DB"
        assert await s.scalar(select(func.count()).select_from(Crop)) == 6


async def test_snapshot_comes_from_the_database_not_files(db):
    async with db.session() as s:
        s.add(Crop(key="tomato", local_names=["tomato"], growth_stages=[], planting_calendar="dry season, irrigated"))
        s.add(CropProblem(crop_key="tomato", name="Early blight", type="fungus", serious=False, signs="rings", low_cost_actions="rotate"))
        s.add(CropAlias(alias="tomatoes", crop_key="tomato"))
        await s.commit()
    assert crop_entry("tomato") is None  # not visible until reload
    await reload_knowledge(db)
    assert crop_entry("tomato")["common_problems"][0]["name"] == "Early blight"
    assert normalize_crop("Tomatoes") == "tomato"
    # restore the shared snapshot for the other tests
    async with db.session() as s:
        await s.delete(await s.get(Crop, "tomato"))
        await s.commit()
    await reload_knowledge(db)


async def test_safety_edits_in_the_database_change_the_audit(db):
    assert audit_text("Try quinalphos on the farm") == []
    async with db.session() as s:
        s.add(SafetyTerm(kind="banned", value="quinalphos", position=99))
        await s.commit()
    await reload_knowledge(db)
    try:
        assert any("banned" in p for p in audit_text("Try quinalphos on the farm"))
    finally:
        async with db.session() as s:
            await s.execute(SafetyTerm.__table__.delete().where(SafetyTerm.value == "quinalphos"))
            await s.commit()
        await reload_knowledge(db)
    assert audit_text("Try quinalphos on the farm") == []


async def test_snapshot_shapes(db):
    s = load_safety()
    assert {"banned", "allowed", "dosage_patterns", "chemical_trigger_terms", "required_label_terms",
            "required_protection_terms", "out_of_scope"} <= set(s)
    assert "paraquat" in s["banned"] and s["allowed"]["classes"]
    assert load_aliases()["akpu"] == "cassava" and load_aliases()["corn"] == "maize"
    problems = crop_entry("maize")["common_problems"]
    assert [p["name"] for p in problems][0] == "Fall armyworm" and problems[0]["serious"] is True


def test_health_reports_the_database(client):
    body = client.get("/v1/health").json()
    assert body["database"] == "sqlite" and body["status"] == "ok"


def test_app_creates_database_file_on_first_request(settings, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from tests.fakes.mock_provider import MockProvider
    from tests.fakes.mock_weather import MockWeatherProvider

    url = f"sqlite+aiosqlite:///{tmp_path / 'fresh.db'}"
    s = settings.model_copy(update={"database_url": url})
    assert not (tmp_path / "fresh.db").exists()
    c = TestClient(create_app(s, vision=MockProvider(), weather_provider=MockWeatherProvider()))  # no lifespan
    assert c.get("/v1/health").status_code == 200
    assert (tmp_path / "fresh.db").exists()
