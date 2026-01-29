# nivel6/app.py - VERSÃO CORRIGIDA E ROBUSTA

import os
import yaml
import csv
import io
import tempfile
from flask import Flask, render_template, request, jsonify
from markupsafe import Markup
from collections import deque
from datetime import datetime
import random
import time # <<< IMPORTANTE: Adicionado para a lógica de espera

app = Flask(__name__)

# --- CONFIGURAÇÃO DE CAMINHOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NIVEL4_PATH = os.path.join(BASE_DIR, '..', 'nivel4')

YAML_PATH = os.path.join(NIVEL4_PATH, 'configuracoes.yaml')
CSV_RAW_PATH = os.path.join(NIVEL4_PATH, 'dados_brutos_aplicacao.csv')
CSV_STATS_PATH = os.path.join(NIVEL4_PATH, 'estatisticas_aplicacao.csv')

# --- LÓGICA DO JOGO DA PLANTA ---
limiar_atencao_secreto, limiar_critico_secreto = (0, 0)
def gerar_limiares_secretos():
    global limiar_atencao_secreto, limiar_critico_secreto
    valores_possiveis = list(range(100, 801, 100))
    limiares = random.sample(valores_possiveis, 2)
    limiar_atencao_secreto = max(limiares)
    limiar_critico_secreto = min(limiares)
    print(f"--- Jogo da Planta Recarregado ---")
    print(f"Limiar de Atenção Secreto: {limiar_atencao_secreto}")
    print(f"Limiar Crítico Secreto: {limiar_critico_secreto}")
    print("--------------------")
gerar_limiares_secretos()

# --- FUNÇÕES AUXILIARES ---
def salvar_yaml_seguro(caminho, dados):
    dir_name = os.path.dirname(caminho)
    try:
        with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, encoding="utf-8") as tmp:
            yaml.dump(dados, tmp, default_flow_style=False, sort_keys=False)
            temp_name = tmp.name
        os.replace(temp_name, caminho)
    except Exception as e:
        print(f"Erro ao salvar o YAML de forma segura: {e}")

# <<< NOVO: Adiciona cabeçalhos para prevenir cache do navegador ---
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# --- ROTAS PRINCIPAIS E DO JOGO ---
@app.route('/')
def home():
    try:
        with open(YAML_PATH, 'r') as f:
            config_data = yaml.safe_load(f) or {}
        initial_data = config_data.get('nivel6', {})
    except FileNotFoundError:
        return "Erro: O arquivo 'configuracoes.yaml' não foi encontrado!", 404
    try:
        svg_path = os.path.join(BASE_DIR, 'static', 'pk2.svg')
        with open(svg_path, 'r') as f:
            svg_content = f.read()
    except FileNotFoundError:
        svg_content = "<p>Erro: Arquivo 'pk2.svg' não encontrado.</p>"
    return render_template('index.html', svg_data=Markup(svg_content), initial_data=initial_data)

@app.route('/planta')
def planta():
    return render_template('planta.html')

@app.route('/monitor')
def monitor():
    return render_template('monitor.html', limiar_atencao_secreto=limiar_atencao_secreto, limiar_critico_secreto=limiar_critico_secreto)

# --- APIS ---
@app.route('/api/luminosidade')
def get_luminosidade_data():
    try:
        with open(CSV_RAW_PATH, 'r', encoding='utf-8') as f:
            last_lines = deque(f, 30)
        labels, values, latest_value = [], [], "N/A"
        for row in csv.reader(last_lines):
            if len(row) >= 2 and "Timestamp" not in row[0]:
                try:
                    dt_object = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S.%f')
                    labels.append(dt_object.strftime('%H:%M:%S'))
                    values.append(float(row[1]))
                except (ValueError, IndexError): continue
        if values: latest_value = values[-1]
        return jsonify({'labels': labels, 'values': values, 'latest_value': latest_value})
    except FileNotFoundError: return jsonify(labels=[], values=[], latest_value="N/A", error="Arquivo não encontrado"), 200
    except Exception as e: return jsonify(labels=[], values=[], latest_value="N/A", error=str(e)), 200

@app.route('/update_thresholds', methods=['POST'])
def update_thresholds():
    data = request.get_json()
    try:
        with open(YAML_PATH, 'r') as f:
            config_data = yaml.safe_load(f) or {}
        if 'nivel6' not in config_data: config_data['nivel6'] = {}
        config_data['nivel6']['limiar_atencao'] = int(data['limiar_atencao'])
        config_data['nivel6']['limiar_critico'] = int(data['limiar_critico'])
        salvar_yaml_seguro(YAML_PATH, config_data)
        return jsonify(success=True)
    except Exception as e: return jsonify(success=False, error=str(e)), 500

# <<< CORRIGIDO: Função de estatísticas com lógica de retentativa
@app.route('/api/estatisticas')
def get_estatisticas_data():
    response_data, yaml_sucesso = {}, False
    for _ in range(3):
        try:
            with open(YAML_PATH, 'r') as f:
                config = yaml.safe_load(f) or {}
            # ESTA PARTE ATUALIZA O STATUS DA FIGURA (LEDS)
            response_data.update(config.get('nivel6', {}))
            response_data.update(config.get('nivel5', {}))
            yaml_sucesso = True
            break
        except FileNotFoundError: time.sleep(0.05)
        except Exception as e:
            response_data['error_yaml'] = str(e)
            break
    if not yaml_sucesso: response_data['error_yaml'] = "Não foi possível ler config.yaml"

    try:
        with open(CSV_STATS_PATH, 'r', encoding='utf-8') as f:
            header_str, last_line_str = f.readline(), deque(f, 1)[0]
        header, last_line_data = next(csv.reader(io.StringIO(header_str))), next(csv.reader(io.StringIO(last_line_str)))
        latest_stats_raw = dict(zip(header, last_line_data))
        for key, value in latest_stats_raw.items():
            try: response_data[key] = float(value)
            except (ValueError, TypeError): response_data[key] = value
    except (FileNotFoundError, IndexError): pass
    except Exception as e: response_data['error_csv'] = str(e)

    return jsonify(response_data)

@app.route('/api/estado_planta')
def get_estado_planta():
    try:
        luminosidade_atual = float(request.args.get('luminosidade', "0"))
        if luminosidade_atual >= limiar_atencao_secreto: estado = 'feliz'
        elif luminosidade_atual >= limiar_critico_secreto: estado = 'neutra'
        else: estado = 'triste'
        return jsonify({'estado_planta': estado})
    except (ValueError, TypeError): return jsonify({'estado_planta': 'neutra'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
