from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse  # IMPORTUL CORECTAT AICI
import pandas as pd
import os
import unicodedata
from google import genai
import json
from fastapi.staticfiles import StaticFiles



# ==========================================
# CONFIGURARE GOOGLE GEMINI
# ==========================================
GOOGLE_API_KEY = "AIzaSyAsdRZFEL12WFeJmGh83IXQVC1u75HHeHQ" # Asigură-te că e cheia corectă
client = genai.Client(api_key=GOOGLE_API_KEY)

# FOLOSIM VERSIUNEA STABILĂ
MODEL_ID = "gemini-2.5-flash"

app = FastAPI(title="U Cluj Tactical AI - Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_PATH = r'C:/Users/amzan/Desktop/Data'
app.mount("/static", StaticFiles(directory=os.path.join(BASE_PATH, "static")), name="static")
DATA_FILE = os.path.join(BASE_PATH, 'date_jucatori_complet.csv')
BIO_NOV = os.path.join(BASE_PATH, '2025 - NOIEMBRIE .xlsx')
BIO_DEC = os.path.join(BASE_PATH, '2025 - DECEMBRIE .xlsx')

def normalize_name(name):
    if pd.isna(name): return ""
    n = str(name).strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFD', n) if unicodedata.category(c) != 'Mn')

def load_tactical():
    try:
        df = pd.read_csv(DATA_FILE, encoding='utf-8-sig', sep=None, engine='python').dropna(how='all')
        df = df.fillna(0)
        
        df['MatchKey'] = df['lastName'].apply(normalize_name)
        df.loc[df['MatchKey'] == '', 'MatchKey'] = df['shortName'].apply(normalize_name)
        
        if 'position_name_ro' in df.columns:
            df['player_role'] = df['position_name_ro']
            
        return df
    except Exception as e:
        print(f"❌ Eroare la datele tactice: {e}")
        return pd.DataFrame()

def load_gps():
    try:
        d1 = pd.read_excel(BIO_NOV)
        d2 = pd.read_excel(BIO_DEC)
        df_bio = pd.concat([d1, d2], ignore_index=True)
        df_bio.columns = df_bio.columns.str.strip()

        def find_col(keywords, df):
            for col in df.columns:
                if any(k.lower() in col.lower() for k in keywords): return col
            return None

        p_col = find_col(['player', 'nume'], df_bio)
        dist_col = find_col(['Distance/time'], df_bio)
        acc_col = find_col(['Acc Abs'], df_bio)
        sprint_col = find_col(['Sprints Abs'], df_bio)

        if not all([p_col, dist_col, acc_col, sprint_col]):
            print(f"⚠️ GPS: Coloane lipsă. Găsite: player={p_col}, dist={dist_col}, acc={acc_col}, sprint={sprint_col}")
            print(f"   Coloane disponibile: {list(df_bio.columns)}")
            return pd.DataFrame()

        for c in [dist_col, acc_col, sprint_col]:
            df_bio[c] = pd.to_numeric(df_bio[c], errors='coerce').fillna(0)

        df_bio['MatchKey'] = df_bio[p_col].apply(normalize_name)

        bio_avg = df_bio.groupby('MatchKey').agg({
            dist_col: 'mean', acc_col: 'mean', sprint_col: 'mean'
        }).reset_index()
        
        bio_avg.columns = ['MatchKey', 'gps_dist', 'gps_accel', 'gps_sprints']
        print(f"✅ GPS încărcat: {len(bio_avg)} jucători cu date biometrice")
        return bio_avg
    except Exception as e:
        print(f"❌ Eroare GPS: {e}")
        return pd.DataFrame()

df_tactical = load_tactical()
df_gps = load_gps()

@app.get("/players")
def get_players():
    if df_tactical.empty: return []
    unique_players = df_tactical.drop_duplicates(subset=['playerId']).copy()
    unique_players['is_u_cluj'] = unique_players['teamId'].apply(lambda x: 1 if x == 60374.0 else 0)
    return unique_players.sort_values(by=['is_u_cluj', 'shortName'], ascending=[False, True]).to_dict(orient='records')

@app.get("/player/{player_id}")
def get_player(player_id: int):
    p_data = df_tactical[df_tactical['playerId'] == player_id]
    if p_data.empty: raise HTTPException(status_code=404)
    
    player_dict = p_data.iloc[0].to_dict()
    if not df_gps.empty:
        match_key = player_dict.get('MatchKey', '')
        gps_data = df_gps[df_gps['MatchKey'] == match_key]
        if not gps_data.empty:
            player_dict['gps_dist'] = gps_data.iloc[0]['gps_dist']
            player_dict['gps_accel'] = gps_data.iloc[0]['gps_accel']
            player_dict['gps_sprints'] = gps_data.iloc[0]['gps_sprints']
        else:
            player_dict['gps_dist'] = player_dict['gps_accel'] = player_dict['gps_sprints'] = 0

    return player_dict

@app.get("/player/{player_id}/chat")
async def chat_with_ai(player_id: int, message: str):
    p_data = df_tactical[df_tactical['playerId'] == player_id]
    if p_data.empty: return {"response": "Eroare date."}
    stats = p_data.iloc[0].to_dict()
    
    date_jucator = "\n".join([f"- {k}: {v:.2f}" if isinstance(v, float) else f"- {k}: {v}" for k, v in stats.items() if v != 0])
    
    # Prompt COMBINAT: Generare + Verificare directă pentru a evita eroarea 429 (Too Many Requests)
    prompt_check = f"""
    Ești antrenor secund și analist de date. Datele OFICIALE ale jucătorului {stats['shortName']} sunt:
    {date_jucator}
    
    Întrebarea antrenorului principal: "{message}"
    
    REGULI STRICTE:
    1. Bazează-te DOAR pe datele furnizate. Nu inventa nimic.
    2. Dacă antrenorul presupune o informație greșită în întrebare (ex: zice că jucătorul are 10 pase, dar în date are 5), trebuie să îl corectezi.
    3. Orice corecție sau cifră extrasă din date trebuie învelită în: <span style='color: #ff4444; font-weight: bold;'>cifra/textul corect</span>.
    4. Răspunsul trebuie să aibă MAXIM 100 DE CUVINTE. Fii scurt, tactic și la obiect.
    """
    
    try:
        final_answer = client.models.generate_content(model=MODEL_ID, contents=prompt_check).text
        return {"response": final_answer}
    except Exception as e:
        print(f"\n[EROARE GEMINI API - CHAT] -> {e}\n")
        return {"response": "A apărut o problemă de comunicare cu serverul AI. Verifică terminalul Python pentru detalii."}

@app.get("/tactics/victory-strategy/{opp_id}")
async def get_strategy(opp_id: float):
    opp = df_tactical[df_tactical['teamId'] == opp_id]
    if opp.empty: return {"strategy": "Adversar lipsă", "best_fit": []}
    
    avg_duel = opp['pct_duelsWon'].mean() if 'pct_duelsWon' in opp else 45.0
    league_duel = df_tactical['pct_duelsWon'].mean() if 'pct_duelsWon' in df_tactical else 45.0
    
    u_cluj = df_tactical[df_tactical['teamId'] == 60374.0].copy()
    
    if not df_gps.empty:
        merged = pd.merge(u_cluj, df_gps, on='MatchKey', how='left').fillna(0)
    else:
        merged = u_cluj.copy()
        merged['gps_accel'] = merged['gps_dist'] = merged['gps_sprints'] = 0

    if avg_duel < league_duel:
        mode = "JOC AGRESIV"
        merged['Fit_Score'] = (merged['pct_duelsWon'] * 0.7) + (merged['gps_accel'] * 0.3)
    else:
        mode = "POSESIE"
        merged['Fit_Score'] = (merged['pct_successfulPasses'] * 0.5) + (merged['gps_dist'] * 0.5)

    max_score = merged['Fit_Score'].max()
    merged['Fit_Score'] = (merged['Fit_Score'] / max_score * 100) if max_score > 0 else 0
    top_picks = merged.sort_values(by='Fit_Score', ascending=False).head(11)
    
    lista_jucatori = ", ".join(top_picks['shortName'].tolist())
    
    try:
        prompt_strat = f"""
        Ești Managerul lui U Cluj. Jucăm contra unei echipe care câștigă {avg_duel:.1f}% din dueluri (media ligii: {league_duel:.1f}%).
        Algoritmul ne propune primul 11: {lista_jucatori}. Stil principal recomandat: {mode}.
        Scrie o CONCLUZIE TACTICĂ scurtă (maxim 3-4 propoziții). Explică DE CE am ales acești jucători și CUM trebuie să jucăm.
        Răspunde direct, profesionist. Fără introduceri.
        """
        ai_summary = client.models.generate_content(model=MODEL_ID, contents=prompt_strat).text
    except Exception as e:
        print(f"\n[EROARE GEMINI API - STRATEGIE] -> {e}\n")
        ai_summary = f"Eroare de generare AI. Recomandăm {mode} pe baza statisticilor de dueluri. Pentru a vedea de ce a căzut conexiunea AI, te rugăm să verifici consola."

    return {
        "mode": mode,
        "strategy": ai_summary,
        "best_fit": top_picks[['shortName', 'Fit_Score', 'player_role']].to_dict(orient='records')
    }
#partea de simulare
import json

# Adaugă această rută la finalul fișierului main.py, înainte de rutele existente
@app.get("/tactics/simulation-data")
async def get_simulation_data():
    try:
        # Folosim fișierele StatsBomb din folderul tău Data
        with open(os.path.join(BASE_PATH, '3943043fisier1.json'), 'r', encoding='utf-8') as f1:
            events = json.load(f1)
        with open(os.path.join(BASE_PATH, '3943043fisier2.json'), 'r', encoding='utf-8') as f2:
            tracking = json.load(f2)
        return {"events": events, "tracking": tracking}
    except Exception as e:
        return {"error": str(e)}

@app.get("/tactics/simulator-page", response_class=HTMLResponse)
async def get_simulator_page():
    # Citim fișierul tău HTML original
    sim_path = os.path.join(BASE_PATH, 'football_tactical_simulator_euro2024_final.html')
    with open(sim_path, 'r', encoding='utf-8') as f:
        return f.read()