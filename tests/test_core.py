"""
Tests unitaires des fonctions critiques.
On utilise des mocks pour ne pas appeler les vraies APIs pendant les tests.

Lancer avec : pytest tests/ -v
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from core.schemas import ExtractedQuote, QuoteItem
from extraction import extract_quote_info, calculate_amounts


# ============================================================
# Fixtures : données réutilisables dans plusieurs tests (DRY)
# ============================================================

@pytest.fixture
def complete_quote() -> ExtractedQuote:
    """Un devis complet avec tous les champs remplis."""
    return ExtractedQuote(
        client_name="Martin Dupont",
        client_email="martin@example.com",
        work_description="Rénovation salle de bain complète",
        items=[
            QuoteItem(label="Pose carrelage", quantity=12, unit="m²", unit_price=45.0),
            QuoteItem(label="Remplacement douche", quantity=1, unit="forfait", unit_price=800.0),
        ],
        vat_rate=10,
        validity_days=30,
        warnings=[],
    )


@pytest.fixture
def empty_quote() -> ExtractedQuote:
    """Un devis vide pour tester les cas limites."""
    return ExtractedQuote()


# ============================================================
# Tests : calcul des montants
# ============================================================

class TestCalculateAmounts:

    def test_correct_calculation_with_items(self, complete_quote):
        """Vérifie que HT et TTC sont calculés correctement."""
        ht, ttc = calculate_amounts(complete_quote)
        # 12 * 45 + 1 * 800 = 540 + 800 = 1340 HT
        assert ht == 1340.0
        # 1340 * 1.10 = 1474.0 TTC
        assert ttc == 1474.0

    def test_empty_quote_returns_zero(self, empty_quote):
        """Un devis sans postes doit retourner 0 pour les deux montants."""
        ht, ttc = calculate_amounts(empty_quote)
        assert ht == 0.0
        assert ttc == 0.0

    def test_rounded_to_two_decimals(self):
        """Vérifie que les montants sont bien arrondis à 2 décimales."""
        quote = ExtractedQuote(
            items=[QuoteItem(label="Test", quantity=3, unit="u", unit_price=1.005)],
            vat_rate=20,
        )
        ht, ttc = calculate_amounts(quote)
        assert ht == round(3 * 1.005, 2)

    def test_vat_20_percent(self):
        """Vérifie le calcul avec TVA à 20%."""
        quote = ExtractedQuote(
            items=[QuoteItem(label="Travaux neufs", quantity=1, unit="forfait", unit_price=1000.0)],
            vat_rate=20,
        )
        ht, ttc = calculate_amounts(quote)
        assert ht == 1000.0
        assert ttc == 1200.0


# ============================================================
# Tests : extraction LLM
# ============================================================

class TestExtractQuoteInfo:

    def test_valid_json_extraction(self):
        """Vérifie que la fonction parse correctement une réponse JSON du LLM."""
        expected_json = {
            "client_name": "Sophie Martin",
            "client_email": "sophie@example.com",
            "work_description": "Pose de parquet",
            "items": [
                {"label": "Parquet chêne", "quantity": 20, "unit": "m²", "unit_price": 60.0}
            ],
            "vat_rate": 10,
            "validity_days": 30,
            "warnings": ["Prix estimé, à confirmer"],
        }

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(expected_json)

        with patch("extraction._client.chat.completions.create", return_value=mock_response):
            result = extract_quote_info("Pose de parquet pour Sophie, 20m², 60€ le m²")

        assert result.client_name == "Sophie Martin"
        assert result.client_email == "sophie@example.com"
        assert len(result.items) == 1
        assert result.items[0].quantity == 20
        assert len(result.warnings) == 1

    def test_cleans_markdown_backticks(self):
        """Le LLM ajoute parfois ```json ... ```. Vérifie que le nettoyage fonctionne."""
        json_in_backticks = '```json\n{"client_name": "Test", "client_email": "", "work_description": "", "items": [], "vat_rate": 10, "validity_days": 30, "warnings": []}\n```'

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json_in_backticks

        with patch("extraction._client.chat.completions.create", return_value=mock_response):
            result = extract_quote_info("quelque chose")

        assert result.client_name == "Test"

    def test_invalid_json_raises_exception(self):
        """Si le LLM retourne du texte non-JSON, on doit obtenir une erreur claire."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Désolé, je ne comprends pas."

        with patch("extraction._client.chat.completions.create", return_value=mock_response):
            with pytest.raises(json.JSONDecodeError):
                extract_quote_info("texte ambigu")


# ============================================================
# Tests : transcription
# ============================================================

class TestTranscribeAudio:

    def test_transcription_returns_text(self, tmp_path):
        """Vérifie que la transcription retourne bien le texte du mock."""
        from transcription import transcribe_audio

        fake_audio = tmp_path / "test.mp3"
        fake_audio.write_bytes(b"faux contenu audio")

        with patch("transcription._client.audio.transcriptions.create", return_value="salle de bain 12m²"):
            result = transcribe_audio(str(fake_audio))

        assert result == "salle de bain 12m²"

    def test_missing_file_raises_error(self):
        """Doit lever FileNotFoundError si le fichier n'existe pas."""
        from transcription import transcribe_audio

        with pytest.raises(FileNotFoundError):
            transcribe_audio("/chemin/qui/nexiste/pas.mp3")