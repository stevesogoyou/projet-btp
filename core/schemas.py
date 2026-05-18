"""
Schémas Pydantic : définissent la forme des données qui entrent et sortent de l'API.
Pydantic valide automatiquement les types et lève des erreurs claires si ça ne correspond pas.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class QuoteItem(BaseModel):
    """Une ligne dans un devis (ex: tile installation, 12m², 45€/m²)."""
    label: str
    quantity: float
    unit: str = "forfait"
    unit_price: float


class ExtractedQuote(BaseModel):
    """
    Résultat brut retourné par le LLM après analyse du vocal.
    Tous les champs sont optionnels car le LLM peut manquer d'infos.
    warnings : liste des infos manquantes ou incertaines détectées par le LLM.
    """
    client_name: str = ""
    client_email: str = ""
    work_description: str = ""
    items: list[QuoteItem] = []
    vat_rate: int = 10
    validity_days: int = 30
    warnings: list[str] = []  # Ex: ["Email client non détecté", "Prix estimé à 45€/m²"]


class QuoteCreationRequest(BaseModel):
    """
    Corps de la requête POST /quotes/vocal.
    idempotency_key : le frontend génère un UUID unique par tentative d'envoi.
    """
    idempotency_key: str = Field(..., min_length=8, max_length=64)
    artisan_email: Optional[str] = None


class QuoteResponse(BaseModel):
    """Réponse retournée après création ou récupération d'un devis."""
    id: int
    idempotency_key: str
    client_name: str
    client_email: str
    amount_excluding_tax: float
    amount_including_tax: float
    status: str
    warnings: list[str] = []
    created_at: datetime
    already_existed: bool = False