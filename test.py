import pandas as pd

# Încarcă datele
df = pd.read_csv('data_finala_cu_nume.csv')

# SCHIMBĂ NUMELE AICI cu cel la care îți dă 0 pe ecran
NUME_JUCATOR = "T. Seto" 

jucator_date = df[df['shortName'] == NUME_JUCATOR]

print(f"Meciuri totale în baza de date: {len(jucator_date)}")
print("\nStatistici Brute (pe meci):")
print(jucator_date[['matchId', 'average.shots', 'average.dribbles', 'average.interceptions']])