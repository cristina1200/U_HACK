import pandas as pd
import json
import os

BASE_PATH = r'C:/Users/Cristina_PC/OneDrive - Technical University of Cluj-Napoca/Desktop/UHACK/Date'

# 1. Încărcăm datele (care au playerId și matchId)
stats_file = os.path.join(BASE_PATH, 'data_clustered_advanced.csv')
df_stats = pd.read_csv(stats_file)

# 2. Încărcăm DOAR numele și currentTeamId din dicționar
json_file = os.path.join(BASE_PATH, 'players (1).json')
with open(json_file, 'r', encoding='utf-8') as f:
    players_raw = json.load(f)

df_info = pd.DataFrame(players_raw['players'])
df_info = df_info[['wyId', 'shortName', 'firstName', 'lastName', 'currentTeamId']]
df_info = df_info.rename(columns={'wyId': 'playerId'})

# 3. Unim tabelele 
df_final = pd.merge(df_stats, df_info, on='playerId', how='left')

# 4. REPARAREA CORECTĂ: Calculăm echipele PENTRU FIECARE MECI ÎN PARTE
df_final['teamId'] = None

print("Procesez echipele pentru fiecare meci...")

# Grupăm datele după matchId și aplicăm logica per meci
for match_id, group in df_final.groupby('matchId'):
    # Pentru acest meci specific, care sunt cele mai frecvente 2 echipe?
    echipa_counts = group['currentTeamId'].value_counts()
    cele_doua_echipe_reale = echipa_counts.head(2).index.tolist()
    
    # Setăm o echipă de bază (pentru a preveni erori dacă lista e goală)
    echipa_curenta = cele_doua_echipe_reale[0] if len(cele_doua_echipe_reale) > 0 else None
    
    # Parcurgem jucătorii DOAR din acest meci
    for idx in group.index:
        team_id_curent = df_final.at[idx, 'currentTeamId']
        
        # Dacă jucătorul aparține uneia dintre cele 2 echipe, o fixăm ca "activă"
        if team_id_curent in cele_doua_echipe_reale:
            echipa_curenta = team_id_curent
            
        # Atribuim echipa
        df_final.at[idx, 'teamId'] = echipa_curenta

# 5. Ștergem currentTeamId (ca să nu mai încurce pe viitor)
df_final = df_final.drop(columns=['currentTeamId'])

# 6. Reordonăm coloanele
cols = ['playerId', 'shortName', 'player_role', 'cluster_id', 'teamId', 'matchId']
cols += [c for c in df_final.columns if c not in cols]
df_final = df_final[cols]

# 7. Salvăm fișierul
final_output = os.path.join(BASE_PATH, 'data_finala_cu_nume.csv')
df_final.to_csv(final_output, index=False)

print("Gata! Fișierul a fost corectat. Fiecare meci are acum doar cele 2 echipe implicate.")