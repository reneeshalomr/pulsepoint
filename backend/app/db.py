from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


def make_engine(database_url: str = settings.database_url):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


engine = make_engine()


def init_db(db_engine=engine) -> None:
    # Import registers all table models with SQLModel metadata.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(db_engine)
    # Phase 3 adds corpus identity to existing EvidenceSource databases.
    if "evidencesource" in inspect(db_engine).get_table_names():
        columns = {column["name"] for column in inspect(db_engine).get_columns("evidencesource")}
        if "external_id" not in columns:
            with db_engine.begin() as connection:
                connection.execute(text("ALTER TABLE evidencesource ADD COLUMN external_id VARCHAR"))


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
