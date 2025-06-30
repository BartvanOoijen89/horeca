import streamlit as st
import pandas as pd

st.set_page_config(page_title="Horeca Voorspelling", layout="wide")

st.title("📊 Horeca Verkoopvoorspelling")
st.markdown("Welkom bij het dashboard voor **Appeltern**. Hier zie je straks voorspellingen voor horecaproducten op basis van bezoekersaantallen en het weer.")

st.info("✅ Het dashboard staat live — de koppeling met GitHub en Streamlit werkt!")

# Voorbeeld: toon eerste rijen uit CSV
try:
    df = pd.read_csv("data.csv")
    st.subheader("Voorbeeld dataset")
    st.dataframe(df.head())
except Exception as e:
    st.error(f"⚠️ Fout bij het laden van data.csv: {e}")
# Streamlit dashboard komt hier – voorbeeldbestand
