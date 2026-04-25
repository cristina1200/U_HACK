import json
import os

cale_meci = r'C:/Users/Cristina_PC/OneDrive - Technical University of Cluj-Napoca/Desktop/UHACK/Date/meci.json'

with open(cale_meci, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Extragem primul jucător din listă
primul_jucator = data['players'][0]

# Afișăm toate "cheile" (categoriile de date) pe care le are
print("Categoriile de date pentru un jucător din meci sunt:")
print(list(primul_jucator.keys()))