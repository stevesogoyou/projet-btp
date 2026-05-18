"""
Couche base de données.
On utilise SQLAlchemy async pour ne pas bloquer FastAPI pendant les requêtes DB.
L'idempotence est gérée via la colonne idempotency_key sur la table quotes.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker, mapped_column, Mapped
from sqlalchemy import String, Integer, Float, DateTime, Text, JSON
from datetime import datetime
from core.config import DATABASE_URL


engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


class Quote(Base):
    """
    Un devis généré par l'application.
    idempotency_key : clé unique pour éviter les doublons.
    warnings : points signalés par le LLM à vérifier par l'artisan.
    """
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_name: Mapped[str] = mapped_column(String(200), default="")
    client_email: Mapped[str] = mapped_column(String(200), default="")
    work_description: Mapped[str] = mapped_column(Text, default="")
    amount_excluding_tax: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[int] = mapped_column(Integer, default=10)
    amount_including_tax: Mapped[float] = mapped_column(Float, default=0.0)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default="pending_validation")
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def init_db():
    """Crée toutes les tables si elles n'existent pas encore."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    """Dépendance FastAPI : fournit une session DB par requête."""
    async with AsyncSessionLocal() as session:
        yield session