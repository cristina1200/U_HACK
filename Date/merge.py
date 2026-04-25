import os
import glob
import pandas as pd
import json  # Lipsea importul de json

# Căile tale (verificate)
input_path = 'C:/Users/amzan/Desktop/Data/Date/*.json'
output_file = 'C:/Users/amzan/Desktop/Data/data_cleaned.csv'

all_players_data = []

# Buclă care trece prin fiecare fișier JSON găsit
for file in glob.glob(input_path):
    with open(file, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            # Pasul 1: Aplatizarea datelor 
            df_match = pd.json_normalize(data['players'])
            
            # Pasul 2: Eliminarea jucătorilor care nu au intrat pe teren 
            if 'total.minutesOnField' in df_match.columns:
                df_match = df_match[df_match['total.minutesOnField'] > 0]
            
            # Pasul 3: Păstrarea doar a coloanelor necesare (Average și Percent) [cite: 4, 5]
            # Ignorăm coloanele de tip "total" pentru a nu denatura AI-ul
            cols_to_keep = [col for col in df_match.columns if 
                            col.startswith('average.') or 
                            col.startswith('percent.') or 
                            col in ['playerId', 'matchId', 'teamId']] # Păstrăm ID-urile pentru legături în DB [cite: 3]
            
            df_match = df_match[cols_to_keep]
            
            all_players_data.append(df_match)
        except Exception as e:
            print(f"Eroare la fișierul {file}: {e}")

# Combinăm toate meciurile într-un singur tabel 
if all_players_data:
    final_df = pd.concat(all_players_data, ignore_index=True)
    
    # Pasul 4: Eliminarea valorilor lipsă (NaN) 
    final_df = final_df.fillna(0)
    
    # Salvarea rezultatului 
    final_df.to_csv(output_file, index=False)
    print(f"Succes! S-au procesat {len(all_players_data)} meciuri.")
else:
    print("Nu s-au găsit date de procesat.")