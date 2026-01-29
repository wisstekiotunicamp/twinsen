# base.py - Versão Híbrida (Lógica Síncrona + Execução Não-Bloqueante)

import socket
import time
import os
import yaml
import csv
import tempfile
from datetime import datetime
import select  # Importamos o select

# --- As funções auxiliares (carregar_configuracoes, etc.) são as mesmas da sua versão funcional ---
def carregar_configuracoes(caminho_config):
    try:
        with open(caminho_config, "r") as f: return yaml.safe_load(f)
    except: return None

def registrar_log_rede(caminho_log, timestamp, rssi, status):
    file_exists = os.path.isfile(caminho_log)
    try:
        with open(caminho_log, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists: writer.writerow(["Timestamp", "RSSI_Downlink", "Status"])
            writer.writerow([timestamp, rssi, status])
    except IOError: pass

def registrar_log_aplicacao(caminho_log, timestamp, luminosidade):
    file_exists = os.path.isfile(caminho_log)
    try:
        with open(caminho_log, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists: writer.writerow(["Timestamp", "Luminosidade"])
            writer.writerow([timestamp, luminosidade])
    except IOError: pass

def salvar_yaml_seguro(caminho, dados):
    dir_name = os.path.dirname(caminho)
    try:
        with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, encoding="utf-8") as tmp:
            yaml.dump(dados, tmp, default_flow_style=False, sort_keys=False)
            temp_name = tmp.name
        os.replace(temp_name, caminho)
    except: pass

def atualizar_status_yaml(caminho_yaml, novos_estados):
    try:
        with open(caminho_yaml, 'r') as f:
            config_data = yaml.safe_load(f) or {}
        if 'nivel6' not in config_data: config_data['nivel6'] = {}
        config_data['nivel6']['led_verde'] = novos_estados.get('led_verde', config_data['nivel6'].get('led_verde'))
        config_data['nivel6']['led_amarelo'] = novos_estados.get('led_amarelo', config_data['nivel6'].get('led_amarelo'))
        config_data['nivel6']['led_vermelho'] = novos_estados.get('led_vermelho', config_data['nivel6'].get('led_vermelho'))
        config_data['nivel6']['buzzer'] = novos_estados.get('buzzer', config_data['nivel6'].get('buzzer'))
        if 'luminosidade' in novos_estados: config_data['nivel6']['luminosidade_atual'] = novos_estados['luminosidade']
        config_data['nivel6']['ultima_atualizacao'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        salvar_yaml_seguro(caminho_yaml, config_data)
    except: pass

# --- Configuração de Caminhos ---
dir_atual = os.path.dirname(__file__) if '__file__' in locals() else os.getcwd()
caminho_nivel4 = os.path.abspath(os.path.join(dir_atual, '..', 'nivel4')) 
caminho_config_yaml = os.path.join(caminho_nivel4, 'configuracoes.yaml')
caminho_log_rede_csv = os.path.join(caminho_nivel4, 'dados_brutos_rede.csv')
caminho_log_aplicacao_csv = os.path.join(caminho_nivel4, 'dados_brutos_aplicacao.csv')

def main():
    config_inicial = carregar_configuracoes(caminho_config_yaml)
    if not config_inicial: return

    current_ip = config_inicial['nivel1']['ip']
    current_port = config_inicial['nivel1']['porta']
    HOST_LOCAL = ''
    
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Importante: Não definimos mais um timeout global no socket
    # udp_socket.settimeout(2.0) 
    try:
        udp_socket.bind((HOST_LOCAL, current_port))
    except OSError as e:
        print(f"Erro ao fazer bind na porta {current_port}: {e}.")
        return

    print(f"Servidor UDP escutando na porta {current_port}")
    print(f"Monitorando e configurando o Nó Sensor em {current_ip}")
    print("Pressione Ctrl+C para encerrar.")

    pkt_down_counter = 0
    last_comm_time = 0

    try:
        while True:
            current_time = time.time()
            config = carregar_configuracoes(caminho_config_yaml)
            if not config or not config.get('nivel3', {}).get('ligado', False):
                time.sleep(5)
                continue
            
            intervalo = config['nivel3']['intervalo_medicoes']

            # Mantém a lógica de reconfiguração dinâmica que já funcionava
            new_ip = config['nivel1']['ip']
            new_port = config['nivel1']['porta']
            if new_port != current_port:
                try:
                    udp_socket.close()
                    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    udp_socket.bind((HOST_LOCAL, new_port))
                    current_port = new_port
                except OSError as e:
                    time.sleep(intervalo)
                    continue
            current_ip = new_ip
            ENDERECO_SENSOR = (current_ip, current_port)
            
            # Controla o envio de pacotes para não inundar a rede
            if current_time - last_comm_time > intervalo:
                last_comm_time = current_time
                
                # --- Preparação e Envio do Pacote (igual à sua versão) ---
                PacoteTX = [0] * 52
                pkt_down_counter = (pkt_down_counter + 1) % 256
                PacoteTX[12] = pkt_down_counter
                PacoteTX[8] = 1; PacoteTX[10] = 0 
                try:
                    limiar_atencao = int(config['nivel6']['limiar_atencao'])
                    limiar_critico = int(config['nivel6']['limiar_critico'])
                    PacoteTX[16] = limiar_atencao // 256; PacoteTX[17] = limiar_atencao % 256
                    PacoteTX[18] = limiar_critico // 256; PacoteTX[19] = limiar_critico % 256
                except: pass
                
                udp_socket.sendto(bytes(PacoteTX), ENDERECO_SENSOR)

            # ======================= A MUDANÇA ESTÁ AQUI =======================
            # Usamos 'select' para verificar se há dados para ler, sem bloquear o script.
            # O timeout de 1 segundo define o tempo máximo que o select espera.
            ready_to_read, _, _ = select.select([udp_socket], [], [], 1.0)
            
            if ready_to_read:
                # Se houver dados, nós os lemos e processamos
                Pacote_RX, cliente = udp_socket.recvfrom(1024)
                if len(Pacote_RX) == 52:
                    timestamp_recebido = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    luminosidade = Pacote_RX[17] * 256 + Pacote_RX[18]
                    print(f"[{timestamp_recebido}] Sincronizado! Luminosidade: {luminosidade}")
                    
                    # Salva logs e atualiza YAML
                    rssi_dl = ((Pacote_RX[2] - 256) / 2.0) - 74 if Pacote_RX[2] > 128 else (Pacote_RX[2] / 2.0) - 74
                    registrar_log_rede(caminho_log_rede_csv, timestamp_recebido, f"{rssi_dl:.2f}", "Sucesso")
                    registrar_log_aplicacao(caminho_log_aplicacao_csv, timestamp_recebido, luminosidade)
                    novos_estados = {
                        'led_verde': bool(Pacote_RX[34]), 'led_amarelo': bool(Pacote_RX[37]),
                        'led_vermelho': bool(Pacote_RX[40]), 'buzzer': bool(Pacote_RX[43]),
                        'luminosidade': luminosidade
                    }
                    atualizar_status_yaml(caminho_config_yaml, novos_estados)
            # Se 'ready_to_read' for falso, o loop simplesmente continua, sem travar.
            # ====================================================================

            # Pequeno sleep para evitar uso de 100% da CPU
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nExecução interrompida.")
    finally:
        udp_socket.close()
        print("Socket fechado.")

if __name__ == "__main__":
    main()
