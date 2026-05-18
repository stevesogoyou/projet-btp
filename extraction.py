"""
Extraction structurée des infos d'un devis à partir du texte transcrit.
Le LLM reçoit le texte brut et retourne un JSON propre qu'on valide avec Pydantic.
"""
import json
from groq import Groq
from core.config import GROQ_API_KEY, LLM_MODEL
from core.schemas import ExtractedQuote


_client = Groq(api_key=GROQ_API_KEY)

# Prompt système séparé du code pour faciliter les ajustements futurs
_SYSTEM_PROMPT = """
Tu es un assistant expert en devis BTP français.
À partir de la description orale d'un artisan, extrais les informations et retourne
UNIQUEMENT un objet JSON valide avec cette structure exacte, sans texte autour :

{
  "client_name": "string",
  "client_email": "string",
  "work_description": "string",
  "items": [
    {
      "label": "string",
      "quantity": number,
      "unit": "string",
      "unit_price": number
    }
  ],
  "vat_rate": 10,
  "validity_days": 30,
  "warnings": ["string"]
}

Règles :
- TVA à 10% pour rénovation résidentielle, 20% sinon. Si incertain, mets 10.
- Si le prix n'est pas mentionné, estime un prix marché parisien réaliste.
- Si une info est absente, mets une chaîne vide ou 0.
- Dans "warnings", liste TOUTES les informations manquantes ou incertaines.
  Exemples de warnings : "Email client non détecté", "Prix du carrelage estimé à 45€/m², à confirmer", "TVA appliquée à 10% par défaut, à vérifier"
- Ne retourne RIEN d'autre que le JSON.
"""


def extract_quote_info(transcribed_text: str) -> ExtractedQuote:
    """
    Analyse le texte transcrit et retourne les données structurées du devis.

    Args:
        transcribed_text: Texte brut issu de la transcription Whisper.

    Returns:
        ExtractedQuote validé par Pydantic.

    Raises:
        json.JSONDecodeError: Si le LLM ne retourne pas du JSON valide.
        pydantic.ValidationError: Si la structure JSON ne correspond pas au schéma.
    """
    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": transcribed_text},
        ],
        temperature=0.1,
        max_tokens=1000,
    )

    raw_content = response.choices[0].message.content

    # Nettoyage défensif au cas où le LLM ajoute des backticks markdown
    clean_content = raw_content.strip().removeprefix("```json").removesuffix("```").strip()

    data = json.loads(clean_content)
    return ExtractedQuote(**data)


def calculate_amounts(quote: ExtractedQuote) -> tuple[float, float]:
    """
    Calcule le montant HT et TTC à partir des postes du devis.

    Returns:
        Tuple (amount_excluding_tax, amount_including_tax) arrondis à 2 décimales.
    """
    excluding_tax = sum(item.quantity * item.unit_price for item in quote.items)
    including_tax = excluding_tax * (1 + quote.vat_rate / 100)
    return round(excluding_tax, 2), round(including_tax, 2)