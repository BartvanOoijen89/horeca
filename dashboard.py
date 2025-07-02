def get_weather(api_key, lat=51.8421, lon=5.5820, date=None):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,alerts&units=metric&appid={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()

        # Zet 'date' om naar een datetime.date object (als dat nog niet is)
        if date:
            try:
                date = pd.to_datetime(date).date()
            except:
                date = None

        today = datetime.now().date()

        if date and today != date:
            forecast = data['daily']
            for day in forecast:
                if datetime.fromtimestamp(day['dt']).date() == date:
                    temp = day['temp']['day']
                    rain = day.get('rain', 0)
                    return temp, rain
            return None, None
        else:
            temp = data['current']['temp']
            rain = data['daily'][0].get('rain', 0)
            return temp, rain
    return None, None
