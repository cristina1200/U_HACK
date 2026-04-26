"""
Turnover Risk Map - Backend
Analizează pierderi de minge per jucător/echipă și generează harta zonelor de risc.
"""

import json
import os
import glob
import math
from collections import defaultdict
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
# ─── Configurare căi ──────────────────────────────────────────────────────────
CSV_PATH = "date_jucatori_complet.csv"
MATCH_DIR = "Date - meciuri"

# ─── Zone pe teren bazate pe poziție ─────────────────────────────────────────
# Coordonate normalizate: x=0..100 (stânga→dreapta), y=0..100 (jos→sus)
# Terenul e împărțit în zone: proprie jumătate stânga/centru/dreapta, treime medie, treime ofensivă
POSITION_ZONES = {
    "gk":    {"x": 50, "y": 5,  "zone": "own_goal", "label": "Poartă"},
    "lcb":   {"x": 25, "y": 15, "zone": "own_def_left", "label": "Fundaș Central Stânga"},
    "cb":    {"x": 50, "y": 15, "zone": "own_def_center", "label": "Fundaș Central"},
    "rcb":   {"x": 75, "y": 15, "zone": "own_def_right", "label": "Fundaș Central Dreapta"},
    "lcb3":  {"x": 25, "y": 15, "zone": "own_def_left", "label": "Fundaș Central Stânga"},
    "rcb3":  {"x": 75, "y": 15, "zone": "own_def_right", "label": "Fundaș Central Dreapta"},
    "lb":    {"x": 10, "y": 25, "zone": "own_left_flank", "label": "Fundaș Stânga"},
    "rb":    {"x": 90, "y": 25, "zone": "own_right_flank", "label": "Fundaș Dreapta"},
    "lb5":   {"x": 10, "y": 25, "zone": "own_left_flank", "label": "Fundaș Stânga"},
    "rb5":   {"x": 90, "y": 25, "zone": "own_right_flank", "label": "Fundaș Dreapta"},
    "lwb":   {"x": 10, "y": 35, "zone": "mid_left_flank", "label": "Fundaș Stânga Ofensiv"},
    "rwb":   {"x": 90, "y": 35, "zone": "mid_right_flank", "label": "Fundaș Dreapta Ofensiv"},
    "ldmf":  {"x": 35, "y": 35, "zone": "own_mid_left", "label": "Mijlocaș Defensiv Stânga"},
    "dmf":   {"x": 50, "y": 35, "zone": "own_mid_center", "label": "Mijlocaș Defensiv"},
    "rdmf":  {"x": 65, "y": 35, "zone": "own_mid_right", "label": "Mijlocaș Defensiv Dreapta"},
    "lcmf":  {"x": 35, "y": 50, "zone": "mid_left", "label": "Mijlocaș Central Stânga"},
    "cmf":   {"x": 50, "y": 50, "zone": "mid_center", "label": "Mijlocaș Central"},
    "rcmf":  {"x": 65, "y": 50, "zone": "mid_right", "label": "Mijlocaș Central Dreapta"},
    "lcmf3": {"x": 35, "y": 50, "zone": "mid_left", "label": "Mijlocaș Central Stânga"},
    "rcmf3": {"x": 65, "y": 50, "zone": "mid_right", "label": "Mijlocaș Central Dreapta"},
    "lamf":  {"x": 25, "y": 62, "zone": "att_left", "label": "Mijlocaș Ofensiv Stânga"},
    "amf":   {"x": 50, "y": 65, "zone": "att_center", "label": "Mijlocaș Ofensiv"},
    "ramf":  {"x": 75, "y": 62, "zone": "att_right", "label": "Mijlocaș Ofensiv Dreapta"},
    "lw":    {"x": 15, "y": 72, "zone": "att_left_wing", "label": "Extremă Stânga"},
    "rw":    {"x": 85, "y": 72, "zone": "att_right_wing", "label": "Extremă Dreapta"},
    "lwf":   {"x": 20, "y": 78, "zone": "att_left_wing", "label": "Aripar Stânga"},
    "rwf":   {"x": 80, "y": 78, "zone": "att_right_wing", "label": "Aripar Dreapta"},
    "ss":    {"x": 50, "y": 78, "zone": "att_half_space", "label": "Secundă Vârf"},
    "cf":    {"x": 50, "y": 85, "zone": "att_striker", "label": "Atacant Central"},
}

# ─── Cache date încărcate ─────────────────────────────────────────────────────
_players_df = None
_match_data = None
_teams_cache = None

def load_players_csv():
    global _players_df
    if _players_df is None:
        import csv
        players = []
        with open(CSV_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                players.append(row)
        _players_df = players
    return _players_df

def load_all_matches():
    global _match_data
    if _match_data is not None:
        return _match_data
    
    _match_data = []
    pattern = os.path.join(MATCH_DIR, "*_players_stats.json")
    files = glob.glob(pattern)
    
    for fpath in files:
        fname = os.path.basename(fpath)
        # Extrage echipele și scorul din numele fișierului
        name_part = fname.replace("_players_stats.json", "")
        # Elimină matchId dacă există (ex: "..._5715786_players_stats.json")
        parts = name_part.rsplit(",", 1)
        if len(parts) == 2:
            teams_part = parts[0].strip()
            score_part = parts[1].strip()
        else:
            teams_part = name_part
            score_part = "?"
        
        # Normalizează caracterele speciale
        teams_part = teams_part.replace("#U0326", "ș").replace("#U0327", "ș")
        teams_part = teams_part.replace("Ot\u015felul", "Oțelul").replace("Constant\u0327a", "Constanța")
        
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            match_info = {
                "file": fname,
                "teams_str": teams_part,
                "score": score_part,
                "players": data.get("players", [])
            }
            _match_data.append(match_info)
        except Exception as e:
            pass
    
    return _match_data

def get_teams():
    global _teams_cache
    if _teams_cache is not None:
        return _teams_cache
    
    players = load_players_csv()
    teams = defaultdict(list)
    for p in players:
        team = p.get("teamName", "").strip()
        if team:
            teams[team].append(p)
    
    _teams_cache = dict(teams)
    return _teams_cache

def get_position_zone(pos_code):
    """Returnează zona pe teren pentru un cod de poziție."""
    if not pos_code:
        return None
    pos_code = pos_code.lower().strip()
    return POSITION_ZONES.get(pos_code)

def compute_loss_rate(player):
    """Calculează rata de pierdere a mingii (pierderi per meci)."""
    try:
        total_losses = float(player.get("total_losses", 0) or 0)
        matches = float(player.get("matchesPlayed", 1) or 1)
        if matches == 0:
            matches = 1
        return total_losses / matches
    except:
        return 0.0

def compute_risk_score(player):
    """Scor compus de risc: pierderi totale + pierderi în propria jumătate (mai periculoase)."""
    try:
        total_losses = float(player.get("total_losses", 0) or 0)
        own_half = float(player.get("total_ownHalfLosses", 0) or 0)
        dangerous = float(player.get("total_dangerousOwnHalfLosses", 0) or 0)
        matches = float(player.get("matchesPlayed", 1) or 1)
        if matches == 0:
            matches = 1
        # Scor ponderat: pierderi normale + 1.5x propria jumătate + 2x periculoase
        score = (total_losses + 1.5 * own_half + 2.0 * dangerous) / matches
        return round(score, 3)
    except:
        return 0.0

# ─── Endpoint-uri API ─────────────────────────────────────────────────────────

@app.route("/api/teams", methods=["GET"])
def api_teams():
    """Returnează lista de echipe cu numărul de jucători."""
    teams = get_teams()
    result = []
    for name, players in teams.items():
        result.append({
            "name": name,
            "playerCount": len(players)
        })
    result.sort(key=lambda x: x["name"])
    return jsonify(result)


@app.route("/api/team/<team_name>/players", methods=["GET"])
def api_team_players(team_name):
    """Returnează jucătorii unei echipe cu statistici de pierdere."""
    teams = get_teams()
    
    # Caută echipa (case-insensitive)
    matched_team = None
    for t in teams:
        if t.lower() == team_name.lower() or t == team_name:
            matched_team = t
            break
    
    if not matched_team:
        return jsonify({"error": "Team not found"}), 404
    
    players = teams[matched_team]
    result = []
    
    for p in players:
        pos_code = p.get("position_code", "").lower()
        zone_info = get_position_zone(pos_code)
        
        total_losses = float(p.get("total_losses", 0) or 0)
        own_half_losses = float(p.get("total_ownHalfLosses", 0) or 0)
        dangerous_losses = float(p.get("total_dangerousOwnHalfLosses", 0) or 0)
        matches = float(p.get("matchesPlayed", 0) or 0)
        avg_losses = float(p.get("avg_losses", 0) or 0)
        
        risk_score = compute_risk_score(p)
        
        player_data = {
            "playerId": p.get("playerId"),
            "name": p.get("shortName", "?"),
            "firstName": p.get("firstName", ""),
            "lastName": p.get("lastName", ""),
            "position_code": pos_code,
            "position_name": p.get("position_name_en", p.get("position_name_ro", "")),
            "role": p.get("role_general", ""),
            "totalLosses": int(total_losses),
            "ownHalfLosses": int(own_half_losses),
            "dangerousLosses": int(dangerous_losses),
            "matchesPlayed": int(matches),
            "avgLosses": round(avg_losses, 2),
            "riskScore": risk_score,
            "zone": zone_info,
            "nationality": p.get("nationality", ""),
            "foot": p.get("foot", ""),
            "totalPasses": int(float(p.get("total_passes", 0) or 0)),
            "passAccuracy": round(float(p.get("pct_successfulPasses", 0) or 0), 1),
        }
        result.append(player_data)
    
    # Sortează după risk score descrescător
    result.sort(key=lambda x: x["riskScore"], reverse=True)
    return jsonify(result)


@app.route("/api/team/<team_name>/turnover_map", methods=["GET"])
def api_turnover_map(team_name):
    """
    Generează harta de risc pentru o echipă adversă.
    Returnează zone colorate cu intensitate bazată pe pierderi.
    """
    teams = get_teams()
    
    matched_team = None
    for t in teams:
        if t.lower() == team_name.lower() or t == team_name:
            matched_team = t
            break
    
    if not matched_team:
        return jsonify({"error": "Team not found"}), 404
    
    players = teams[matched_team]
    
    # Agregare pierderi pe zone
    zone_losses = defaultdict(lambda: {
        "totalLosses": 0, "ownHalfLosses": 0, "dangerousLosses": 0,
        "players": [], "riskScore": 0.0, "x": 0, "y": 0, "count": 0
    })
    
    for p in players:
        pos_code = p.get("position_code", "").lower()
        zone_info = get_position_zone(pos_code)
        if not zone_info:
            continue
        
        zone_key = zone_info["zone"]
        losses = float(p.get("total_losses", 0) or 0)
        own_half = float(p.get("total_ownHalfLosses", 0) or 0)
        dangerous = float(p.get("total_dangerousOwnHalfLosses", 0) or 0)
        matches = max(float(p.get("matchesPlayed", 1) or 1), 1)
        risk = compute_risk_score(p)
        
        z = zone_losses[zone_key]
        z["totalLosses"] += losses
        z["ownHalfLosses"] += own_half
        z["dangerousLosses"] += dangerous
        z["riskScore"] += risk
        z["x"] += zone_info["x"]
        z["y"] += zone_info["y"]
        z["count"] += 1
        z["players"].append({
            "name": p.get("shortName", ""),
            "position_code": pos_code,
            "position_name": p.get("position_name_en", ""),
            "role": p.get("role_general", ""),
            "totalLosses": int(losses),
            "avgLosses": round(float(p.get("avg_losses", 0) or 0), 2),
            "riskScore": risk,
            "passAccuracy": round(float(p.get("pct_successfulPasses", 0) or 0), 1),
        })
    
    # Normalizează coordonatele și calculează intensitate
    heatmap_zones = []
    max_risk = max((z["riskScore"] for z in zone_losses.values()), default=1)
    
    for zone_key, z in zone_losses.items():
        if z["count"] == 0:
            continue
        avg_x = z["x"] / z["count"]
        avg_y = z["y"] / z["count"]
        intensity = z["riskScore"] / max_risk if max_risk > 0 else 0
        
        heatmap_zones.append({
            "zone": zone_key,
            "x": round(avg_x, 1),
            "y": round(avg_y, 1),
            "intensity": round(intensity, 3),
            "riskScore": round(z["riskScore"], 2),
            "totalLosses": int(z["totalLosses"]),
            "ownHalfLosses": int(z["ownHalfLosses"]),
            "dangerousLosses": int(z["dangerousLosses"]),
            "players": sorted(z["players"], key=lambda x: x["riskScore"], reverse=True),
        })
    
    heatmap_zones.sort(key=lambda x: x["intensity"], reverse=True)
    return jsonify({
        "team": matched_team,
        "zones": heatmap_zones,
        "totalZones": len(heatmap_zones)
    })


@app.route("/api/team/<team_name>/analysis", methods=["GET"])
def api_team_analysis(team_name):
    """
    Analiză tactică completă a echipei adverse:
    - Top jucători care pierd mingea
    - Zone vulnerabile
    - Recomandări tactice (pe baza jucătorilor din echipa proprie dacă e furnizată)
    """
    my_team = request.args.get("my_team", None)
    teams = get_teams()
    
    # Găsește echipa adversă
    matched_opp = None
    for t in teams:
        if t.lower() == team_name.lower() or t == team_name:
            matched_opp = t
            break
    
    if not matched_opp:
        return jsonify({"error": "Team not found"}), 404
    
    opp_players = teams[matched_opp]
    
    # Top 5 jucători care pierd cel mai des mingea
    ranked = []
    for p in opp_players:
        pos_code = p.get("position_code", "").lower()
        zone_info = get_position_zone(pos_code)
        risk = compute_risk_score(p)
        if float(p.get("matchesPlayed", 0) or 0) < 3:
            continue
        ranked.append({
            "name": p.get("shortName", ""),
            "position_code": pos_code,
            "position_name": p.get("position_name_en", p.get("position_name_ro", "")),
            "role": p.get("role_general", ""),
            "totalLosses": int(float(p.get("total_losses", 0) or 0)),
            "avgLosses": round(float(p.get("avg_losses", 0) or 0), 2),
            "ownHalfLosses": int(float(p.get("total_ownHalfLosses", 0) or 0)),
            "dangerousLosses": int(float(p.get("total_dangerousOwnHalfLosses", 0) or 0)),
            "passAccuracy": round(float(p.get("pct_successfulPasses", 0) or 0), 1),
            "riskScore": risk,
            "zone": zone_info,
            "matchesPlayed": int(float(p.get("matchesPlayed", 0) or 0)),
        })
    
    ranked.sort(key=lambda x: x["riskScore"], reverse=True)
    top_losers = ranked[:8]
    
    # Identifică zonele vulnerabile pe flancuri
    left_risk = sum(p["riskScore"] for p in ranked 
                    if p["position_code"] in ["lb", "lb5", "lwb", "lcb", "lcb3", "lamf", "lw", "lwf"])
    right_risk = sum(p["riskScore"] for p in ranked 
                     if p["position_code"] in ["rb", "rb5", "rwb", "rcb", "rcb3", "ramf", "rw", "rwf"])
    center_risk = sum(p["riskScore"] for p in ranked 
                      if p["position_code"] in ["cb", "dmf", "cmf", "amf", "cf", "ss"])
    
    # Identifică cel mai slab jucător pe fiecare flanc
    left_players = [p for p in ranked if p["position_code"] in ["lb", "lb5", "lwb", "lcb", "lcb3", "lamf", "lw", "lwf"]]
    right_players = [p for p in ranked if p["position_code"] in ["rb", "rb5", "rwb", "rcb", "rcb3", "ramf", "rw", "rwf"]]
    
    weakest_left = left_players[0] if left_players else None
    weakest_right = right_players[0] if right_players else None
    
    # Jucătorii din echipa mea dacă e furnizată
    my_best_players = []
    if my_team:
        matched_my = None
        for t in teams:
            if t.lower() == my_team.lower() or t == my_team:
                matched_my = t
                break
        if matched_my:
            my_players = teams[matched_my]
            # Găsește jucătorii ofensivi cei mai buni
            for p in my_players:
                role = p.get("role_general", "")
                if role in ["Forward", "Midfielder"]:
                    goals = float(p.get("total_goals", 0) or 0)
                    assists = float(p.get("total_assists", 0) or 0)
                    xg = float(p.get("total_xgShot", 0) or 0)
                    matches = max(float(p.get("matchesPlayed", 1) or 1), 1)
                    attack_score = (goals + assists * 0.7 + xg * 0.5) / matches
                    my_best_players.append({
                        "name": p.get("shortName", ""),
                        "role": role,
                        "position_code": p.get("position_code", "").lower(),
                        "position_name": p.get("position_name_en", ""),
                        "goals": int(goals),
                        "assists": int(assists),
                        "attackScore": round(attack_score, 3),
                        "avgLosses": round(float(p.get("avg_losses", 0) or 0), 2),
                    })
            my_best_players.sort(key=lambda x: x["attackScore"], reverse=True)
            my_best_players = my_best_players[:5]
    
    # Generează interpretări tactice
    interpretations = []
    
    if weakest_left:
        tip = f"⚠️ FLANC STÂNGA VULNERABIL: {weakest_left['name']} ({weakest_left['position_name']}) pierde mingea în medie de {weakest_left['avgLosses']} ori/meci. Presează pe acest flanc!"
        if my_best_players:
            # Găsește jucătorul nostru potrivit pentru flanc stânga
            right_wingers = [p for p in my_best_players if p["position_code"] in ["rw", "rwf", "ramf"]]
            if right_wingers:
                tip += f" Trimite-l pe {right_wingers[0]['name']} să exploateze această zonă."
        interpretations.append({"type": "warning", "side": "left", "message": tip})
    
    if weakest_right:
        tip = f"⚠️ FLANC DREAPTA VULNERABIL: {weakest_right['name']} ({weakest_right['position_name']}) pierde mingea în medie de {weakest_right['avgLosses']} ori/meci. Exploatează spațiul!"
        if my_best_players:
            left_wingers = [p for p in my_best_players if p["position_code"] in ["lw", "lwf", "lamf"]]
            if left_wingers:
                tip += f" {left_wingers[0]['name']} poate crea probleme în această zonă."
        interpretations.append({"type": "warning", "side": "right", "message": tip})
    
    # Identifică dacă echipa adversă pierde frecvent în propria jumătate
    dangerous_losers = [p for p in ranked if p["dangerousLosses"] > 5]
    if dangerous_losers:
        names = ", ".join(p["name"] for p in dangerous_losers[:3])
        interpretations.append({
            "type": "danger",
            "side": "center",
            "message": f"🔴 PERICOL ÎN PROPRIA JUMĂTATE: {names} au pierderi periculoase frecvente. Presează sus (high press) pentru a provoca greșeli!"
        })
    
    # Analiză acuratețe pase
    low_pass_accuracy = [p for p in ranked if p["passAccuracy"] < 70 and p["passAccuracy"] > 0]
    if low_pass_accuracy:
        names = ", ".join(f"{p['name']} ({p['passAccuracy']}%)" for p in low_pass_accuracy[:3])
        interpretations.append({
            "type": "info",
            "side": "center",
            "message": f"📊 ACURATEȚE SCĂZUTĂ LA PASE: {names}. Presează acești jucători pentru a forța erori de pasă."
        })
    
    if center_risk > left_risk and center_risk > right_risk:
        interpretations.append({
            "type": "tactical",
            "side": "center",
            "message": "🎯 CENTRUL TERENULUI este zona cea mai vulnerabilă. Folosiți joc combinativ central cu schimbări rapide de ritm."
        })
    elif left_risk > right_risk:
        interpretations.append({
            "type": "tactical",
            "side": "left",
            "message": "🎯 FLANC STÂNGA - cel mai slab sector defensiv. Concentrați atacurile pe dreapta voastră (stânga lor)."
        })
    else:
        interpretations.append({
            "type": "tactical",
            "side": "right", 
            "message": "🎯 FLANC DREAPTA - cel mai slab sector defensiv. Concentrați atacurile pe stânga voastră (dreapta lor)."
        })
    
    return jsonify({
        "team": matched_opp,
        "topLosers": top_losers,
        "flankRisk": {
            "left": round(left_risk, 2),
            "right": round(right_risk, 2),
            "center": round(center_risk, 2),
            "weakestSide": "left" if left_risk >= right_risk else "right"
        },
        "weakestLeft": weakest_left,
        "weakestRight": weakest_right,
        "myBestPlayers": my_best_players,
        "interpretations": interpretations,
        "matchAnalysis": {
            "totalPlayersAnalyzed": len([p for p in ranked]),
            "avgTeamLossRate": round(sum(p["avgLosses"] for p in ranked) / max(len(ranked), 1), 2),
            "mostDangerousZone": top_losers[0]["zone"]["label"] if top_losers and top_losers[0].get("zone") else "N/A"
        }
    })


@app.route("/api/compare", methods=["GET"])
def api_compare():
    """Compară două echipe după rata de pierdere."""
    team1 = request.args.get("team1", "")
    team2 = request.args.get("team2", "")
    
    teams = get_teams()
    result = {}
    
    for label, tname in [("team1", team1), ("team2", team2)]:
        matched = None
        for t in teams:
            if t.lower() == tname.lower() or t == tname:
                matched = t
                break
        if not matched:
            continue
        
        players = teams[matched]
        total_loss_rate = sum(compute_risk_score(p) for p in players)
        avg = total_loss_rate / max(len(players), 1)
        result[label] = {
            "name": matched,
            "avgRiskScore": round(avg, 3),
            "playerCount": len(players)
        }
    
    return jsonify(result)


# ─── Servire fișiere statice ──────────────────────────────────────────────────
@app.route("/")
def dashboard():
    # Servește pagina de start cu butoanele mari
    return open("../index.html", encoding="utf-8").read()

@app.route("/analytics")
def analytics_page():
    # Servește interfața principală cu jucători (fostul frontend.html)
    return open("../frontend.html", encoding="utf-8").read()

@app.route("/turnover")
def turnover_page():
    # Servește noul modul de Turnover Risk Map
    return open("turnover.html", encoding="utf-8").read()

@app.route("/simulator")
def simulator_page():
    # Servește simulatorul 2D
    return open("../football_tactical_simulator_euro2024_final.html", encoding="utf-8").read()


if __name__ == "__main__":
    print("🚀 Pornire server Turnover Risk Map...")
    print(f"📁 CSV: {CSV_PATH}")
    print(f"📁 Meciuri: {MATCH_DIR}")
    
    # Pre-încarcă datele
    try:
        teams = get_teams()
        print(f"✅ Încărcate {len(teams)} echipe cu {sum(len(v) for v in teams.values())} jucători")
    except Exception as e:
        print(f"⚠️  Eroare la încărcare CSV: {e}")
    
    app.run(debug=True, host="0.0.0.0", port=5000)
