import pandas as pd
import plotly.express as px
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# -----------------------------
# 1. Configuración de archivos
# -----------------------------
CSV_FILE = Path('metrics_log.csv')
OUTPUT_HTML = Path('metrics_seg_report.html')

# -----------------------------
# 2. Funciones auxiliares
# -----------------------------
def load_data(csv_path: Path) -> pd.DataFrame:
    """Carga el CSV y agrega columna request_int para mostrar enteros en la tabla."""
    df = pd.read_csv(csv_path, parse_dates=['timestamp'])
    df['request_int'] = pd.factorize(df['request_id'])[0] + 1
    return df

def compute_metrics(df: pd.DataFrame) -> dict:
    """Calcula métricas principales usando IDs únicos para total, exitosos y fallidos."""
    metrics = {
        'total_requests': df['request_id'].nunique(),
        'successful_requests': df[df['status'] == 'success']['request_id'].nunique(),
        'failed_requests': df[df['status'] == 'failed']['request_id'].nunique(),
        'events_count': df['event_type'].value_counts(),
        'users_count': df['user'].value_counts()
    }
    return metrics

def create_bar_chart(series: pd.Series, title: str, x_label: str, y_label: str, include_js: bool = True) -> str:
    """Crea un gráfico de barras interactivo y devuelve HTML."""
    fig = px.bar(
        series,
        x=series.index,
        y=series.values,
        labels={'x': x_label, 'y': y_label},
        title=title
    )
    return fig.to_html(full_html=False, include_plotlyjs='cdn' if include_js else False)

def render_html(metrics: dict, events_html: str, users_html: str, table_html: str) -> str:
    """Renderiza el informe HTML usando Jinja2."""
    env = Environment(loader=FileSystemLoader('.'))
    template_html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Informe Enriquecido de Metrics Log</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { margin: 20px; font-family: Arial, sans-serif; }
            h1, h2 { margin-top: 20px; }
            .metrics { display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }
            .metric { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; flex: 1; min-width: 150px; }
            .metric h3 { margin-bottom: 10px; }
            table { font-size: 0.9rem; }
        </style>
    </head>
    <body>
        <h1>Informe tacticas de seguridad</h1>

        <div class="metrics">
            <div class="metric">
                <h3>Total Requests</h3>
                <p>{{ total_requests }}</p>
            </div>
            <div class="metric">
                <h3>Successful Requests</h3>
                <p>{{ successful_requests }}</p>
            </div>
            <div class="metric">
                <h3>Failed Requests</h3>
                <p>{{ failed_requests }}</p>
            </div>
        </div>

        <h2>Eventos por Tipo</h2>
        {{ events_html | safe }}

        <h2>Requests por Usuario</h2>
        {{ users_html | safe }}

        <h2>Tabla Detallada de Logs</h2>
        {{ table_html | safe }}
    </body>
    </html>
    """
    template = env.from_string(template_html)
    return template.render(
        total_requests=metrics['total_requests'],
        successful_requests=metrics['successful_requests'],
        failed_requests=metrics['failed_requests'],
        events_html=events_html,
        users_html=users_html,
        table_html=table_html
    )

# -----------------------------
# 3. Pipeline principal
# -----------------------------
def main():
    # Cargar datos
    df = load_data(CSV_FILE)

    # Calcular métricas
    metrics = compute_metrics(df)

    # Crear gráficos
    events_html = create_bar_chart(metrics['events_count'], "Eventos por Tipo", "Tipo de Evento", "Cantidad", include_js=True)
    users_html = create_bar_chart(metrics['users_count'], "Requests por Usuario", "Usuario", "Cantidad", include_js=False)

    # Tabla detallada
    df_display = df.copy()
    df_display = df_display.drop(columns=['request_id'])  # eliminar UUID original
    df_display = df_display.rename(columns={'request_int': 'request_id'})  # renombrar a request_id
    cols = ['request_id'] + [c for c in df_display.columns if c != 'request_id']
    df_display = df_display[cols]

    # Generar tabla HTML
    table_html = df_display.to_html(
        index=False,
        classes='table table-striped table-hover table-bordered',
        border=0
    )

    # Renderizar HTML
    html_content = render_html(metrics, events_html, users_html, table_html)

    # Guardar archivo
    OUTPUT_HTML.write_text(html_content, encoding='utf-8')
    print(f"Informe generado correctamente: {OUTPUT_HTML}")

if __name__ == "__main__":
    main()
