import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import get_db
from app.main import app
from app.models import Base


@pytest.fixture()
def client():
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionForTest = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        db = SessionForTest()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        test_client.session_factory = SessionForTest
        yield test_client
    app.dependency_overrides.clear()

    engine.dispose()
    os.unlink(path)

