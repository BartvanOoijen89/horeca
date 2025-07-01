
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import pickle

# Data inladen
df = pd.read_excel("Horeca-data 2025 (Tot 19 mei 2025).xlsx")

# Voorbewerking
df['Datum'] = pd.to_datetime(df['Datum'])
df['Weekdag'] = df['Datum'].dt.dayofweek
df['Maand'] = df['Datum'].dt.month

# Filter eventueel op locatie
locatie = "Appeltern"
df = df[df['Locatie'] == locatie]

# Groeperen per productcategorie
features = ['Weekdag', 'Maand', 'Bezoekers']
target_col = 'Aantal'

productgroepen = df['Productgroep'].unique()

model_dict = {}

for productgroep in productgroepen:
    sub = df[df['Productgroep'] == productgroep]
    if sub[target_col].sum() == 0:
        continue
    X = sub[features]
    y = sub[target_col]

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    model_dict[productgroep] = model

# Opslaan
with open("model_per_product.pkl", "wb") as f:
    pickle.dump(model_dict, f)

print("✅ Model opgeslagen als model_per_product.pkl")
