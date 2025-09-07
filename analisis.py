import pandas as pd 
import json
from collections import Counter

df = pd.read_csv("metrics.csv")

summary = []

def try_parse_json(value):
    """Intenta parsear un string a JSON, devuelve None si falla."""
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return None

# Alias para microservicios
alias_map = {
    1: "MS1",
    2: "MS2",
    3: "MS3",
    "1": "MS1",
    "2": "MS2",
    "3": "MS3"
}

for request_id, group in df.groupby("request_id"):
    if request_id == "-":  # ignorar eventos sin request
        continue

    tiempo_inicio = group["timestamp"].min()
    tiempo_fin = group["timestamp"].max()
    latencia_total = tiempo_fin - tiempo_inicio

    # Microservicios que respondieron
    respondieron = group[group["event"] == "response_received"]["microservice_id"].tolist()
    respondieron_alias = [alias_map.get(ms, str(ms)) for ms in respondieron]

    # Info de votación
    fila_voto = group[group["event"] == "vote_result"]
    consenso_alcanzado = not fila_voto.empty and fila_voto["status"].iloc[0] == "consensus_reached"

    # Extraer respuestas
    respuestas = group[group["event"] == "microservice_response"][["microservice_id", "extra_info"]]

    valores_relevantes = []
    for _, row in respuestas.iterrows():
        parsed = try_parse_json(row["extra_info"])
        if isinstance(parsed, dict):
            data = parsed.get("data", {})
            valores_relevantes.append({
                "microservice_id": alias_map.get(row["microservice_id"], str(row["microservice_id"])),
                "clave": (data.get("product_id"), data.get("in_stock"), data.get("quantity"))
            })

    # Determinar consenso y discrepantes
    id_producto = en_stock = cantidad_producto = None
    microservicios_discrepantes = []

    if valores_relevantes:
        conteos = Counter([v["clave"] for v in valores_relevantes])
        valor_mas_comun, frecuencia = conteos.most_common(1)[0]

        if frecuencia == 1:
            # Todos difieren → no hay consenso
            microservicios_discrepantes = respondieron_alias
            id_producto = en_stock = cantidad_producto = "Sin consenso"
            consenso_alcanzado = False
        else:
            # Tomar valor consensuado
            id_producto, en_stock, cantidad_producto = valor_mas_comun
            # Detectar discrepantes (los que no coinciden con el consenso)
            microservicios_discrepantes = [
                v["microservice_id"] for v in valores_relevantes if v["clave"] != valor_mas_comun
            ]
    else:
        if not consenso_alcanzado:
            microservicios_discrepantes = respondieron_alias

    summary.append({
        "id_peticion": request_id,
        "tiempo_inicio": tiempo_inicio,
        "tiempo_fin": tiempo_fin,
        "latencia_total": latencia_total,
        "microservicios_respondieron": ", ".join(respondieron_alias),
        "microservicios_discrepantes": ", ".join(microservicios_discrepantes),
        "consenso_alcanzado": "Sí" if consenso_alcanzado else "No",
        "id_producto": id_producto,
        "en_stock": en_stock,
        "cantidad_producto": cantidad_producto
    })

# --- Crear DataFrame resumen ---
summary_df = pd.DataFrame(summary)

# Ordenar por id_peticion
summary_df["id_peticion"] = pd.to_numeric(summary_df["id_peticion"], errors="ignore")
summary_df = summary_df.sort_values(by="id_peticion").reset_index(drop=True)

# Guardar CSV
summary_df.to_csv("metrics_summary.csv", index=False)

# Generar HTML con estilo
html_table = summary_df.to_html(index=False, escape=False)

# Pintar en rojo solo los "No"
rows = html_table.split("<tr>")
for i, row in enumerate(rows):
    if "<td>No</td>" in row:
        rows[i] = f"<tr style='background-color:#ffcccc'>{row}"
    elif row.strip() != "":
        rows[i] = "<tr>" + row

html = "<tr>".join(rows)

with open("metrics_summary.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Generados: metrics_summary.csv y metrics_summary.html (con MS1, MS2, MS3 en columnas)")  
