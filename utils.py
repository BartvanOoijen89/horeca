from datetime import datetime
import requests

def get_weather(api_key: str, date: datetime):
    today = datetime.today().date()
    is_future = date.date() > today
    base_url = "https://api.openweathermap.org/data/2.5/"
    lat, lon = 51.8731, 5.5755  # Appeltern

    if is_future or (date.date() == today):
        url = f"{base_url}forecast?lat={lat}&lon={lon}&units=metric&appid={api_key}"
        resp = requests.get(url).json()
        forecasts = resp["list"]
        for f in forecasts:
            ts = datetime.fromtimestamp(f["dt"])
            if ts.date() == date.date() and ts.hour == 12:
                return f["main"]["temp"], f["rain"].get("3h", 0) if "rain" in f else 0
        return forecasts[0]["main"]["temp"], forecasts[0].get("rain", {}).get("3h", 0)
    else:
        url = f"{base_url}onecall/timemachine?lat={lat}&lon={lon}&dt={int(date.timestamp())}&units=metric&appid={api_key}"
        resp = requests.get(url).json()
        hourly = resp.get("hourly", [])
        temps = [h["temp"] for h in hourly]
        rains = [h.get("rain", {}).get("1h", 0) for h in hourly]
        return round(sum(temps)/len(temps), 1), round(sum(rains), 1)
