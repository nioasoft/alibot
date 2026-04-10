import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from bot.models import Base


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Session:
    session_factory = sessionmaker(bind=db_engine)
    session = session_factory()
    yield session
    session.close()
