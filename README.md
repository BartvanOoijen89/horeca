
# 📊 Horeca Verkooppredictie – Appeltern

Een Streamlit-dashboard dat de verwachte horeca-omzet en verkochte aantallen per productcategorie voorspelt voor Bloemenpark Appeltern op basis van:
- Weersverwachting (OpenWeather API)
- Bezoekersaantallen (ingeschat of gepland)
- Historische verkoopdata

## 🧩 Bestandsoverzicht
- `dashboard.py` – hoofdapp
- `model.pkl` – getraind voorspellingsmodel
- `data.csv` – historische verkoop + bezoekers
- `productsByTurnoverGroupReport.csv` – detaildata per product
- `requirements.txt` – Python afhankelijkheden
- `.streamlit/secrets.toml` – OpenWeather API-config

## ▶️ Installatie & Gebruik
1. Zorg dat Python 3.9+ is geïnstalleerd
2. Installeer vereisten:
```bash
pip install -r requirements.txt
```

3. Start het dashboard lokaal:
```bash
streamlit run dashboard.py
```

## 🔐 API-sleutel instellen
Maak een `.streamlit/secrets.toml` aan met daarin:

```toml
[openweather]
api_key = "JOUW_API_KEY_HIER"
```
