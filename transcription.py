"""
Transcription audio → texte via Whisper (hébergé sur Groq, donc gratuit et rapide).
Ce module fait UNE seule chose : prendre un fichier audio, retourner du texte.
"""
from groq import Groq
from core.config import GROQ_API_KEY, WHISPER_MODEL


# Client initialisé une seule fois au chargement du module (DRY)
_client = Groq(api_key=GROQ_API_KEY)


def transcribe_audio(file_path: str) -> str:
    """
    Transcrit un fichier audio en texte français.

    Args:
        file_path: Chemin local vers le fichier audio (mp3, m4a, ogg, wav).

    Returns:
        Texte transcrit sous forme de chaîne.

    Raises:
        FileNotFoundError: Si le fichier n'existe pas.
        groq.APIError: Si l'API Groq échoue.
    """
    with open(file_path, "rb") as fichier:
        transcription = _client.audio.transcriptions.create(
            file=(file_path, fichier.read()),
            model=WHISPER_MODEL,
            language="fr",
            response_format="text",
        )
    return transcription
