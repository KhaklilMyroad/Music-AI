from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {},
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    # naive additive migration for pre-existing SQLite databases
    from sqlalchemy import text

    with engine.connect() as conn:
        for column, ddl in (("local_path", "VARCHAR"), ("stage", "VARCHAR")):
            try:
                conn.execute(text(f"ALTER TABLE track ADD COLUMN {column} {ddl}"))
                conn.commit()
            except Exception:  # noqa: BLE001 - column already exists
                conn.rollback()


def get_session():
    with Session(engine) as session:
        yield session
