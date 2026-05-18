"""
Envoi d'emails via Resend (gratuit jusqu'à 3000 emails/mois).
"""
import resend
from core.config import RESEND_API_KEY

resend.api_key = RESEND_API_KEY


def send_quote_to_client(
    client_email: str,
    client_name: str,
    pdf_path: str,
    quote_id: int,
) -> str:
    """
    Envoie le devis PDF par email au client.

    Args:
        client_email: Adresse email du destinataire.
        client_name: Nom du client pour personnaliser l'email.
        pdf_path: Chemin local du fichier PDF à attacher.
        quote_id: Numéro du devis pour la ligne d'objet.

    Returns:
        ID de l'email retourné par Resend.
    """
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    response = resend.Emails.send({
        "from": "devis@tondomaine.fr",
        "to": [client_email],
        "subject": f"Votre devis N°{str(quote_id).zfill(5)}",
        "html": f"""
            <p>Bonjour {client_name},</p>
            <p>Veuillez trouver ci-joint votre devis.</p>
            <p>Pour l'accepter, retournez-le signé avec la mention <strong>« Bon pour accord »</strong>.</p>
            <p>N'hésitez pas à nous contacter pour toute question.</p>
            <p>Cordialement</p>
        """,
        "attachments": [
            {
                "filename": f"quote_{str(quote_id).zfill(5)}.pdf",
                "content": list(pdf_bytes),
            }
        ],
    })

    return response["id"]