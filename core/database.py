"""
Couche base de données.
On utilise SQLAlchemy async pour ne pas bloquer FastAPI pendant les requêtes DB.
L'idempotence est gérée via la colonne idempotency_key sur la table Devis.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker, mapped_column, Mapped
from sqlalchemy import String, Integer, Float, DateTime, Text
from datetime import datetime
from core.config import DATABASE_URL


# --- Moteur et session ---

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# --- Modèles ---

class Base(DeclarativeBase):
    pass


class Quote(Base):
    """
    Un devis généré par l'application.
    idempotency_key : clé unique envoyée par le client pour éviter les doublons.
    Si le même key arrive deux fois, on retourne le devis existant.
    """
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_name: Mapped[str] = mapped_column(String(200))
    client_email: Mapped[str] = mapped_column(String(200))
    description_travaux: Mapped[str] = mapped_column(Text)
    amount_excluding_tax: Mapped[float] = mapped_column(Float)
    tva_taux: Mapped[int] = mapped_column(Integer, default=10)
    montant_ttc: Mapped[float] = mapped_column(Float)
    statut: Mapped[str] = mapped_column(String(50), default="brouillon")
    # Chemin local du PDF généré
    pdf_chemin: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Helpers ---

async def init_db():
    """Crée toutes les tables si elles n'existent pas encore."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    """Dépendance FastAPI : fournit une session DB par requête."""
    async with AsyncSessionLocal() as session:
        yield session
