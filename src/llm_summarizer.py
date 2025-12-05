from groq import Groq
import json

# Le client Groq utilise la variable d'environnement GROQ_API_KEY
client = Groq()

# Mots-clés pour filtrer le texte avant envoi au LLM
KEYWORDS = [

    # ---- GRAINS ----
    # Wheat
    "wheat", "blé", "ble", "trigo", "trigueros", "trigal", "trigo duro",
    "trigo de invierno", "trigo de primavera", "trigo argentino",
    "trigo brasileiro", "пшеница", "пшениця", "小麦",

    # Corn
    "corn", "maïs", "mais", "maiz", "maíz", "maicero",
    "milho", "safrinha", "milho safrinha", "пшено", "кукуруза", "кукурудза",
    "玉米",

    # Soy
    "soy", "soja", "soya", "soybean", "soybeans",
    "soja argentina", "soja brasileira",
    "соевые", "соја", "大豆",

    # Grains généraux
    "grain", "grains", "céréale", "cereale", "cereal", "cereais",
    "cultivos", "culturas", "зерно", "穀物", "粮食",

    # ---- AGRICULTURE ----
    "harvest", "récolte", "cosecha", "colheita",
    "yield", "rendement", "rinde",
    "planting", "seeding", "siembra", "sementes", "plantio",
    "acreage", "hectares", "superficie",

    # ---- WEATHER / METEO ----
    "drought", "sécheresse", "sequia", "seca",
    "rain", "pluie", "lluvia", "chuva",
    "floods", "inondations", "inundaciones", "enchentes",
    "frost", "gel", "helada", "geada",
    "heatwave", "canicule", "ola de calor", "onda de calor",
    "ENSO", "El Niño", "La Niña",

    # ---- LOGISTIQUE / SUPPLY CHAIN ----
    "export", "import", "exportación", "importación",
    "exportação", "importação",
    "ports", "puerto", "porto",
    "embarcaciones", "navios", "ships",
    "freight", "fret", "flete", "fretamento",
    "corridor", "corredor marítimo", "зерновий коридор",
    "судно", "港口", "航运",

    # ---- STOCKS / DEMANDE ----
    "stocks", "stock", "inventories", "inventario", "estoques",
    "demand", "demande", "demanda",
    "supply", "offre", "oferta",

    # ---- RISQUES AGRICOLES / MALADIES ----
    "locusts", "langosta", "gafanhoto",
    "plaga", "praga", "fungus", "roya", "ferrugem asiática",
    "spodoptera", "lagarta militar",
    "black rust", "stem rust", "roya negra",

    # ---- POLITIQUE AGRICOLE ----
    "tariff", "duty", "tax", "quota",
    "arancel", "impuesto", "tasa",
    "tarifa", "subsídio", "subsidio",
    "embargo", "ban", "prohibición",
    "санкции", "制裁",

    # ---- MACRO / ÉNERGIE / FX ----
    "fuel", "diesel", "ethanol",
    "gasoline", "biofuel", "biodiesel",
    "crude oil", "Brent", "WTI",
    "FX", "currency", "ARS", "BRL", "UAH", "RUB",
    "inflation", "interest rate", "policy rate",

]


def _filter_relevant_text(raw: str) -> str:
    """
    Garde seulement les paragraphes qui contiennent des mots-clés grains.
    Si rien n'est trouvé, on réduit simplement la longueur.
    """
    if not raw:
        return ""

    paragraphs = [p.strip() for p in raw.split("\n") if p.strip()]
    selected = []
    for p in paragraphs:
        if any(k.lower() in p.lower() for k in KEYWORDS):
            selected.append(p)

    if selected:
        text = " ".join(selected)
        return text[:6000]
    # fallback : on prend le début du texte brut
    return raw[:3000]


PROMPT = """
Tu es un analyste spécialisé en grains (blé, maïs, soja) sur un desk de trading.

Ta tâche :
- Lire le texte ci-dessous (news, rapport, analyse).
- Identifier la céréale principalement concernée.
- Identifier le type d'événement.
- Évaluer l'impact sur les PRIX (haussier, baissier, neutre).
- Produire une ANALYSE DE MARCHÉ STRUCTURÉE en FRANÇAIS :
    - analyse principale (4 à 7 phrases),
    - impact sur les prix (1 à 2 phrases),
    - principaux risques (liste),
    - perspective court terme (1 à 2 phrases).

RENVOIE UNIQUEMENT du JSON STRICT avec la structure suivante :

{
  "commodity": "wheat | corn | soy | other",
  "event_type": "weather | stocks | production | trade | politics | logistics | other",
  "sentiment": "bullish | bearish | neutral",
  "analysis": "Analyse détaillée en français, 4 à 7 phrases, orientée marché",
  "impact": "Impact sur les prix à court terme, 1 à 2 phrases",
  "risks": ["risque 1", "risque 2"],
  "outlook": "Perspectives court terme pour les prix, 1 à 2 phrases"
}

Règles :
- "commodity" :
    - blé -> "wheat"
    - maïs / maize -> "corn"
    - soja -> "soy"
    - sinon -> "other"
- "event_type" :
    - météo, sécheresse, pluies, gel -> "weather"
    - stocks, inventaires, stocks-to-use -> "stocks"
    - récolte, rendement, surfaces, production -> "production"
    - exportations, importations, commerce, flux -> "trade"
    - décisions gouvernementales, taxes, quotas, embargos -> "politics"
    - ports, logistique, transport, corridor, fret -> "logistics"
    - sinon -> "other"
- "sentiment" = impact sur les PRIX de la céréale principale :
    - haussier -> "bullish"
    - baissier -> "bearish"
    - neutre ou peu clair -> "neutral"

Réponds UNIQUEMENT avec le JSON, sans texte avant ou après.

Texte :
{TEXT}
"""


def _normalize_commodity(raw: str) -> str:
    if not raw:
        return "other"
    t = raw.strip().lower()
    if t in ["wheat", "blé", "ble"]:
        return "wheat"
    if t in ["corn", "maïs", "mais", "maize"]:
        return "corn"
    if t in ["soy", "soja", "soybean", "soybeans"]:
        return "soy"
    return "other"


def _normalize_event_type(raw: str) -> str:
    if not raw:
        return "other"
    t = raw.strip().lower()
    mapping = {
        "weather": "weather",
        "stocks": "stocks",
        "stock": "stocks",
        "production": "production",
        "harvest": "production",
        "trade": "trade",
        "commerce": "trade",
        "politics": "politics",
        "policy": "politics",
        "logistics": "logistics",
        "transport": "logistics",
    }
    if t in mapping:
        return mapping[t]
    if any(w in t for w in ["drought", "rain", "pluie", "sécheresse", "gel"]):
        return "weather"
    if any(w in t for w in ["stock", "inventaire", "inventory"]):
        return "stocks"
    if any(w in t for w in ["récolte", "harvest", "yield", "production"]):
        return "production"
    if any(w in t for w in ["export", "import", "trade", "commerce"]):
        return "trade"
    if any(w in t for w in ["tax", "quota", "ban", "embargo", "policy", "gouvernement"]):
        return "politics"
    if any(w in t for w in ["port", "logistic", "logistique", "corridor", "freight"]):
        return "logistics"
    return "other"


def _normalize_sentiment(raw: str) -> str:
    if not raw:
        return "neutral"
    t = raw.strip().lower()
    if "bull" in t or "hauss" in t or "up" in t:
        return "bullish"
    if "bear" in t or "baiss" in t or "down" in t:
        return "bearish"
    return "neutral"


def summarize_and_extract(article: dict) -> dict:
    """
    Prend un article (dict avec au moins 'text') et renvoie le même dict
    enrichi avec :
      - commodity
      - event_type
      - sentiment
      - analysis (nouveau)
      - impact   (nouveau)
      - risks    (nouveau)
      - outlook  (nouveau)
      - summary  (pour compatibilité, recopie l'analyse)
    """
    raw_text = article.get("text") or ""
    text = _filter_relevant_text(raw_text)

    if not text.strip():
        data = {
            "commodity": "other",
            "event_type": "other",
            "sentiment": "neutral",
            "analysis": "Pas de contenu pertinent sur les grains dans cet article.",
            "impact": "",
            "risks": [],
            "outlook": "",
            "summary": "Pas de texte exploitable."
        }
        return {**article, **data}

    prompt = PROMPT.replace("{TEXT}", text)

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are an expert agricultural commodity analyst focused on grains (wheat, corn, soybeans)."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
    )

    output = completion.choices[0].message.content.strip()

    try:
        raw_data = json.loads(output)
    except Exception:
        raw_data = {
            "commodity": "other",
            "event_type": "other",
            "sentiment": "neutral",
            "analysis": output,
            "impact": "",
            "risks": [],
            "outlook": ""
        }

    commodity = _normalize_commodity(raw_data.get("commodity"))
    event_type = _normalize_event_type(raw_data.get("event_type"))
    sentiment = _normalize_sentiment(raw_data.get("sentiment"))

    analysis = (raw_data.get("analysis") or "").strip()
    impact = (raw_data.get("impact") or "").strip()
    risks = raw_data.get("risks") or []
    outlook = (raw_data.get("outlook") or "").strip()

    summary = analysis or "Résumé indisponible."

    data = {
        "commodity": commodity,
        "event_type": event_type,
        "sentiment": sentiment,
        "analysis": analysis,
        "impact": impact,
        "risks": risks if isinstance(risks, list) else [],
        "outlook": outlook,
        "summary": summary
    }

    return {**article, **data}