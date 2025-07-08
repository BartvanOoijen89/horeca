import requests
from datetime import datetime

def get_weather(api_key, date, lat=51.8421, lon=5.5820):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,alerts&units=metric&appid={api_key}"
    r = requests.get(url)
    if r.status_code != 200:
        return None, None

    data = r.json()
    today = datetime.now().date()
    
    if date > today:
        # Voor toekomst: gebruik voorspelde data
        for dag in data.get("daily", []):
            datum = datetime.fromtimestamp(dag["dt"]).date()
            if datum == date:
                temperatuur = dag["temp"]["day"]
                neerslag = dag.get("rain", 0)
                return temperatuur, neerslag
        return None, None
    else:
        # Voor vandaag of verleden: gebruik actuele data
        temperatuur = data.get("current", {}).get("temp")
        neerslag = data.get("daily", [{}])[0].get("rain", 0)
        return temperatuur, neerslag
