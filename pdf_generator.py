"""
Génération du PDF du devis à partir du template HTML.
On utilise Jinja2 pour remplir le template, puis WeasyPrint pour convertir en PDF.
"""
from pathlib import Path
from datetime import date
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML


PDF_DIR = Path("pdfs")
PDF_DIR.mkdir(exist_ok=True)

TEMPLATE_DIR = Path("templates")
_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))


def generate_pdf(quote_id: int, quote, amount_ht: float, amount_ttc: float) -> str:
    """
    Génère un PDF pour le devis et le sauvegarde localement.

    Args:
        quote_id: Identifiant du devis en base.
        quote: Objet devis contenant les données.
        amount_ht: Montant hors taxe.
        amount_ttc: Montant toutes taxes comprises.

    Returns:
        Chemin absolu vers le fichier PDF généré.
    """
    template = _jinja_env.get_template("devis.html")

    html_rendered = template.render(
        quote_id=str(quote_id).zfill(5),
        date_emission=date.today().strftime("%d/%m/%Y"),
        validity_days=getattr(quote, "validity_days", 30),
        client_name=getattr(quote, "client_name", "") or "Client non renseigné",
        client_email=getattr(quote, "client_email", ""),
        work_description=getattr(quote, "work_description", ""),
        items=getattr(quote, "items", []),
        amount_excluding_tax=amount_ht,
        amount_including_tax=amount_ttc,
        vat_rate=getattr(quote, "vat_rate", 10),
    )

    pdf_path = PDF_DIR / f"quote_{quote_id}.pdf"
    HTML(string=html_rendered).write_pdf(str(pdf_path))

    return str(pdf_path.resolve())