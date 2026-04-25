from fastapi import FastAPI, HTTPException
import pandas as pd
import os

app = FastAPI(title="Football Scouting API - U Cluj Project")

BASE_PATH = r'C:/Users/Cristina_PC/OneDrive - Technical University of Cluj-Napoca/Desktop/UHACK/Date'
DATA_FILE = os.path.join(BASE_PATH, 'data_finala_cu_nume.csv')

# Încărcăm datele
try:
    df = pd.read_csv(DATA_FILE)
    df['shortName'] = df['shortName'].fillna("Jucător Necunoscut")
except Exception as e:
    print(f"EROARE la încărcarea fișierului: {e}")

@app.get("/")
def home():
    return {"status": "Online", "message": "API-ul U Cluj funcționează."}

@app.get("/players")
def get_all_players():
    return df[['playerId', 'shortName', 'player_role', 'cluster_id', 'teamId']].head(100).to_dict(orient='records')

@app.get("/player/{player_id}")
def get_player(player_id: int):
    player_data = df[df['playerId'] == player_id]
    if player_data.empty:
        raise HTTPException(status_code=404, detail="Jucătorul nu a fost găsit")
    return player_data.to_dict(orient='records')[0]

# --- NOU: MOTORUL DE RECOMANDĂRI TACTICE ---

@app.get("/tactics/opponent/{team_id}")
def get_tactical_report(team_id: float):
    # 1. Extragem toți jucătorii echipei adverse (pe baza ID-ului)
    adversari = df[df['teamId'] == team_id]
    
    if adversari.empty:
        raise HTTPException(status_code=404, detail="Echipa nu a fost găsită în baza de date.")

    raport = {
        "echipa_id": team_id,
        "puncte_forte": [],
        "puncte_slabe": [],
        "sfaturi_tactice": []
    }

    # 2. Analizăm DEFENSIVA (Puncte slabe posibile)
    media_dueluri_aeriene = adversari['percent.aerialDuelsWon'].mean()
    if media_dueluri_aeriene < 50:
        raport["puncte_slabe"].append("Echipa pierde majoritatea duelurilor aeriene.")
        raport["sfaturi_tactice"].append("Folosiți centrări dese în careu și un Atacant Central (Target Man).")

    mingi_pierdute_propria_jumatate = adversari['average.ownHalfLosses'].mean()
    if mingi_pierdute_propria_jumatate > 8: # Prag arbitrar, poate fi ajustat
        raport["puncte_slabe"].append("Pierd multe mingi în propria jumătate de teren.")
        raport["sfaturi_tactice"].append("Aplicați un Pressing Avansat agresiv pentru a recupera mingi periculoase.")

    # 3. Analizăm OFENSIVA (Puncte forte la care trebuie să aveți grijă)
    extreme_ofensive = adversari[adversari['cluster_id'] == 1] # Presupunând