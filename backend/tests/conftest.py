import os
os.environ["TESTING"] = "true"
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.session import Base, get_db
from app.database.seed import seed_database
from app.main import app
import os

TEST_DB_FILE = "./test_netguardian.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_database(db)
    db.close()
    yield
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

from fastapi.testclient import TestClient

@pytest.fixture
def client():
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
