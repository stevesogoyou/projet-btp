"""
Configuration centralisée de l'application.
Toutes les variables d'environnement sont lues ici une seule fois.
Principe KISS : un seul endroit pour changer la config.
"""
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./devis_btp.db")

WHISPER_MODEL = "whisper-large-v3"
LLM_MODEL = "llama-3.3-70b-versatile"

TVA_DEFAULT = 10
DEVIS_VALIDITE_JOURS = 30
