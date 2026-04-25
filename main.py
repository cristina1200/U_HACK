from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
from google import genai

# 1. CONFIGURARE GOOGLE GEMINI
GOOGLE_API_KEY = "AIzaSyAQpuSyFPzt0j6yfsmOGRdwsRQXA8wgicY"
client = genai.Client(api_key=GOOGLE_API_KEY)
MODEL_ID = "gemini-2.5-flash"

app = FastAPI(title="U Cluj Tactical AI - Backend")

# 2. CONFIGURARE CORS (Permite comunicarea cu Frontend-ul)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. ÎNCĂRCARE DATE
# Asigură-te că drumul către fișier este corect pe PC-ul tău
BASE_PATH = r'C:/Users/amzan/Desktop/Data'
DATA_FILE = os.path.join(BASE_PATH, 'data_finala_cu_nume.csv')

try:
    df = pd.read_csv(DATA_FILE)
    df['shortName'] = df['shortName'].fillna("Jucător Necunoscut")
    df['teamId'] = df['teamId'].astype(float)
    print("✅ Datele au fost încărcate cu succes!")
except Exception as e:
    print(f"❌ EROARE la încărcare: {e}")

# --- FUNCTIE HELPER: Calcul Media Jucator (Filtrare Rezerve) ---
def get_active_player_stats(player_id: int):
    player_matches = df[df['playerId'] == player_id]
    if player_matches.empty:
        return None
    
    # Luăm doar meciurile în care a fost activ (pentru a evita mediile stricate de statul pe bancă)
    active_matches = player_matches[(player_matches['average.passes'] > 0) | (player_matches['average.duels'] > 0)]
    
    # Dacă n-a jucat deloc, revenim la datele brute să nu dăm eroare
    target_df = active_matches if not active_matches.empty else player_matches

    # Calculăm media
    numeric_cols = target_df.select_dtypes(include=['number']).columns
    avg_stats = target_df[numeric_cols].mean().to_dict()
    
    # Reatașăm datele de profil
    avg_stats['shortName'] = player_matches.iloc[0]['shortName']
    avg_stats['player_role'] = player_matches.iloc[0]['player_role']
    avg_stats['cluster_id'] = int(player_matches.iloc[0]['cluster_id'])
    avg_stats['teamId'] = float(player_matches.iloc[0]['teamId'])
    
    return avg_stats

# --- RUTE API ---

@app.get("/")
def read_root():
    return {"message": "API-ul U Cluj Tactic este online."}

@app.get("/players")
def get_players():
    # 1. Luăm jucătorii unici
    unique_players = df.drop_duplicates(subset=['playerId']).copy()
    
    # 2. Curățăm valorile NaN (aceasta este rezolvarea pentru eroarea ta)
    # Înlocuim orice celulă goală cu 0 sau text gol pentru a fi compatibil cu JSON
    unique_players = unique_players.fillna({
        'teamId': 0,
        'player_role': 'Fără rol',
        'cluster_id': 0,
        'shortName': 'Jucător Necunoscut'
    })

    # 3. Sortăm: U Cluj (60374) să fie mereu primii
    unique_players['is_u_cluj'] = unique_players['teamId'].apply(lambda x: 1 if x == 60374.0 else 0)
    unique_players = unique_players.sort_values(by=['is_u_cluj', 'shortName'], ascending=[False, True])
    
    # 4. Limităm la 300 pentru performanță (browser-ul se va bloca la 2000+ jucători)
    data_to_send = unique_players[['playerId', 'shortName', 'player_role', 'teamId']].head(300).to_dict(orient='records')
    
    return data_to_send

@app.get("/player/{player_id}")
def get_player(player_id: int):
    stats = get_active_player_stats(player_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Jucător negăsit")
    return stats

@app.get("/player/{player_id}/chat")
async def chat_with_ai(player_id: int, message: str):
    stats = get_active_player_stats(player_id)
    if not stats:
        return {"response": "Nu am date despre acest jucător."}

    # Contextul pe care îl dăm AI-ului despre jucător
    context = f"""
    Ești asistentul tactic al lui Neluțu Sabău la U Cluj. 
    Date jucător: {stats['shortName']}, Rol: {stats['player_role']}, 
    Pase: {stats.get('percent.successfulPasses', 0)}%, 
    Dueluri: {stats.get('percent.duelsWon', 0)}%.
    """
    
    full_prompt = f"{context}\n\nAntrenorul întreabă: {message}\nRăspunde scurt și tactic în română."

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=full_prompt
        )
        return {"response": response.text}
    except Exception as e:
        print(f"DEBUG AI: {e}")
        return {"response": "Gemini este ocupat. Sfat rapid: Analizează forcing-ul pe flancuri."}

# Pentru Modulul 4: Scaner de Slăbiciuni pe Echipă
@app.get("/tactics/opponent/{team_id}")
def get_team_vulnerabilities(team_id: float):
    adversari = df[df['teamId'] == team_id]
    if adversari.empty:
        raise HTTPException(status_code=404, detail="Echipa nu a fost găsită.")

    # Analiză matematică simplă bazată pe slăbiciuni (Modulul 4 din Word)
    slăbiciuni = []
    if adversari['percent.aerialDuelsWon'].mean() < 45:
        slăbiciuni.append("Deficit major la duelurile aeriene în careu.")
    
    if adversari['average.ballLosses'].mean() > 12:
        slăbiciuni.append("Pierderi de posesie critice sub presiune (Turnover Map High).")

    return {
        "echipa_id": team_id,
        "vulnerabilitati": slăbiciuni,
        "advice": "Aplicați pressing înalt în fereastra de oboseală (min 75-90)."
    }

@app.get("/tactics/victory-strategy/{opponent_team_id}")
async def get_victory_strategy(opponent_team_id: float):
    # 1. Datele U Cluj (ID: 60374)
    u_cluj_data = df[df['teamId'] == 60374.0]
    # 2. Datele Adversarului
    opponent_data = df[df['teamId'] == opponent_team_id]

    if opponent_data.empty:
        raise HTTPException(status_code=404, detail="Echipa adversă nu a fost găsită.")

    # 3. Calculăm medii cheie pentru ambele echipe
    u_cluj_metrics = {
        "pas": u_cluj_data['percent.successfulPasses'].mean(),
        "duel": u_cluj_data['percent.duelsWon'].mean(),
        "rec": u_cluj_data['average.ballRecoveries'].mean()
    }
    
    opp_metrics = {
        "pas": opponent_data['percent.successfulPasses'].mean(),
        "duel": opponent_data['percent.duelsWon'].mean(),
        "aerian": opponent_data['percent.aerialDuelsWon'].mean()
    }

    # 4. Prompt-ul "Strategia de Victorie"
    prompt = f"""
    Ești strategul șef al Universității Cluj. Trebuie să batem echipa cu ID {opponent_team_id}.
    
    COMPARAȚIE DATE:
    - U Cluj: Pase {u_cluj_metrics['pas']:.1f}%, Dueluri {u_cluj_metrics['duel']:.1f}%.
    - Adversar: Pase {opp_metrics['pas']:.1f}%, Dueluri {opp_metrics['duel']:.1f}%, Dueluri Aeriene {opp_metrics['aerian']:.1f}%.
    
    Cerință: Scrie un plan de bătaie în 3 puncte (Stil, Atac, Apărare). 
    Fii agresiv, tactic și scurt (max 80 cuvinte).
    """

    try:
        response = client.models.generate_content(model=MODEL_ID, contents=prompt)
        return {
            "strategy": response.text,
            "comparison": {"u_cluj": u_cluj_metrics, "opponent": opp_metrics}
        }
    except Exception as e:
        return {"strategy": "Eroare AI. Sfat general: Jucați pe contraatac și forțați flancurile."}