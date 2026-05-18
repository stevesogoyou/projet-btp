"""
Point d'entrée de l'API.
Principe d'idempotence : si une requête arrive avec une idempotency_key déjà connue,
on retourne le résultat existant sans rien recréer.
Ça protège contre les double-clics, retries réseau et timeouts.
"""
import os
import shutil
import tempfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import init_db, get_session, Quote
from core.schemas import QuoteResponse
from transcription import transcribe_audio
from extraction import extract_quote_info, calculate_amounts
from pdf_generator import generate_pdf, _jinja_env
from email_sender import send_quote_to_client


# --- Démarrage / arrêt de l'app ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise la base de données au démarrage."""
    await init_db()
    yield

app = FastAPI(
    title="Devis BTP API",
    description="Génère des devis professionnels depuis un message vocal.",
    version="1.0.0",
    lifespan=lifespan,
)

# On réutilise l'environnement Jinja2 déjà initialisé dans pdf_generator (DRY)


# --- Route principale : traitement du vocal ---

@app.post("/quotes/vocal", response_model=QuoteResponse)
async def create_quote_from_audio(
    audio_file: UploadFile = File(..., description="Fichier audio (mp3, m4a, ogg, wav)"),
    idempotency_key: str = Form(..., description="UUID unique généré côté client"),
    artisan_email: str = Form(default=""),
    session: AsyncSession = Depends(get_session),
):
    """
    Crée un devis depuis un message vocal :
    1. Vérifie l'idempotence (retourne l'existant si déjà traité)
    2. Transcrit l'audio avec Whisper
    3. Extrait les infos avec le LLM
    4. Sauvegarde en base avec statut "pending_validation"
    5. Redirige l'artisan vers la page de validation
    """

    # --- Étape 1 : Vérification idempotence ---
    existing = await session.scalar(
        select(Quote).where(Quote.idempotency_key == idempotency_key)
    )
    if existing:
        return QuoteResponse(
            id=existing.id,
            idempotency_key=existing.idempotency_key,
            client_name=existing.client_name,
            client_email=existing.client_email,
            amount_excluding_tax=existing.amount_excluding_tax,
            amount_including_tax=existing.amount_including_tax,
            status=existing.status,
            warnings=existing.warnings or [],
            created_at=existing.created_at,
            already_existed=True,
        )

    # --- Étape 2 : Sauvegarde temporaire du fichier audio ---
    extension = os.path.splitext(audio_file.filename)[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
        shutil.copyfileobj(audio_file.file, tmp)
        tmp_path = tmp.name

    try:
        # --- Étape 3 : Transcription ---
        transcribed_text = transcribe_audio(tmp_path)

        # --- Étape 4 : Extraction structurée ---
        extracted = extract_quote_info(transcribed_text)
        amount_ht, amount_ttc = calculate_amounts(extracted)

        # --- Étape 5 : Sauvegarde en base ---
        # Statut "pending_validation" : l'artisan doit valider avant l'envoi
        new_quote = Quote(
            idempotency_key=idempotency_key,
            client_name=extracted.client_name,
            client_email=extracted.client_email,
            work_description=extracted.work_description,
            amount_excluding_tax=amount_ht,
            vat_rate=extracted.vat_rate,
            amount_including_tax=amount_ttc,
            warnings=extracted.warnings,
            status="pending_validation",
        )
        session.add(new_quote)
        await session.commit()
        await session.refresh(new_quote)

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement : {str(e)}")

    finally:
        os.unlink(tmp_path)

    return QuoteResponse(
        id=new_quote.id,
        idempotency_key=new_quote.idempotency_key,
        client_name=new_quote.client_name,
        client_email=new_quote.client_email,
        amount_excluding_tax=new_quote.amount_excluding_tax,
        amount_including_tax=new_quote.amount_including_tax,
        status=new_quote.status,
        warnings=new_quote.warnings or [],
        created_at=new_quote.created_at,
        already_existed=False,
    )


# --- Route de validation : page que l'artisan voit sur son téléphone ---

@app.get("/quotes/{quote_id}/validate", response_class=HTMLResponse)
async def validation_page(
    request: Request,
    quote_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Affiche la page de validation du devis pour l'artisan."""
    quote = await session.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Devis introuvable")

    # Rendu direct avec notre environnement Jinja2 (évite le conflit avec Starlette)
    template = _jinja_env.get_template("validation.html")
    html = template.render(
        quote_id=quote.id,
        idempotency_key=quote.idempotency_key,
        client_name=quote.client_name,
        client_email=quote.client_email,
        work_description=quote.work_description,
        items=[],
        amount_excluding_tax=quote.amount_excluding_tax,
        amount_including_tax=quote.amount_including_tax,
        vat_rate=quote.vat_rate,
        warnings=quote.warnings or [],
    )
    return HTMLResponse(content=html)


# --- Route de confirmation : l'artisan valide et envoie au client ---

@app.post("/quotes/confirm")
async def confirm_and_send_quote(
    payload: dict,
    session: AsyncSession = Depends(get_session),
):
    """
    Reçoit le devis validé par l'artisan, génère le PDF et envoie au client.
    Idempotent : si le devis est déjà envoyé, on retourne le résultat existant.
    """
    quote_id = payload.get("quote_id")
    quote = await session.get(Quote, int(quote_id))

    if not quote:
        raise HTTPException(status_code=404, detail="Devis introuvable")

    # Idempotence : ne pas renvoyer un devis déjà envoyé
    if quote.status == "sent":
        return {"status": "already_sent", "quote_id": quote.id}

    # Mise à jour avec les corrections de l'artisan
    quote.client_name = payload.get("client_name", quote.client_name)
    quote.client_email = payload.get("client_email", quote.client_email)
    quote.work_description = payload.get("work_description", quote.work_description)

    try:
        # Génération du PDF avec les données validées
        pdf_path = generate_pdf(quote.id, quote, quote.amount_excluding_tax, quote.amount_including_tax)
        quote.pdf_path = pdf_path

        # Envoi email si l'email client est renseigné
        if quote.client_email:
            send_quote_to_client(
                client_email=quote.client_email,
                client_name=quote.client_name,
                pdf_path=pdf_path,
                quote_id=quote.id,
            )
            quote.status = "sent"
        else:
            quote.status = "pdf_generated"

        await session.commit()

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'envoi : {str(e)}")

    return {"status": "sent", "quote_id": quote.id}


# --- Route de téléchargement du PDF ---

@app.get("/quotes/{quote_id}/pdf")
async def download_pdf(quote_id: int, session: AsyncSession = Depends(get_session)):
    """Retourne le PDF d'un devis existant."""
    quote = await session.get(Quote, quote_id)
    if not quote or not quote.pdf_path:
        raise HTTPException(status_code=404, detail="Devis ou PDF introuvable")

    return FileResponse(
        path=quote.pdf_path,
        media_type="application/pdf",
        filename=f"quote_{str(quote_id).zfill(5)}.pdf",
    )


# --- Health check ---

@app.get("/health")
async def health():
    """Endpoint de vérification que le serveur tourne."""
    return {"status": "ok"}