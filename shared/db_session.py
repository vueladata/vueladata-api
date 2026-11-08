import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Falta DATABASE_URL. En AWS se inyecta desde SSM "
        "(/vueladata/dev/database/url); en local, desde .env."
    )

# Engine con pool_pre_ping=True para reconectar si la BD se reinicia
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"options": "-csearch_path=vueladata,public"}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

@contextmanager
def get_db():
    """Generador de contexto para uso seguro de sesiones DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
