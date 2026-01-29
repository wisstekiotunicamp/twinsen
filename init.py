# init.py (Versão Simplificada e Estável)

import subprocess
import sys
import os
import time

# --- Bloco de Compatibilidade de Cores para Windows ---
if sys.platform == "win32":
    os.system('')

# --- Configuração dos Scripts a Serem Executados ---
SCRIPTS = [
    {
        "name": "NIVEL 3 (Base)",
        "path": "base.py",
        "cwd": "nivel3",
        "color": "\033[94m" # Cor será usada apenas para mensagens de status do init.py
    },
    {
        "name": "NIVEL 5 (Análise)",
        "path": "analise.py",
        "cwd": "nivel5",
        "color": "\033[92m"
    },
    {
        "name": "NIVEL 6 (WebApp)",
        "path": "app.py",
        "cwd": "nivel6",
        "color": "\033[93m"
    }
]

RESET_COLOR = "\033[0m"

def main():
    processes = []
    print("=" * 50)
    print("INICIANDO TODOS OS SCRIPTS DO PROJETO...")
    print("Pressione Ctrl+C para encerrar todos os processos.")
    print("=" * 50)

    for script_info in SCRIPTS:
        script_path = script_info["path"]
        script_name = script_info["name"]
        script_color = script_info["color"]
        script_cwd = script_info["cwd"]
        
        full_script_path = os.path.join(script_cwd, script_path)
        if not os.path.exists(full_script_path):
            print(f"{script_color}[{script_name}]{RESET_COLOR} ERRO: Script não encontrado em '{full_script_path}'. Pulando.")
            continue
            
        print(f"{script_color}[{script_name}]{RESET_COLOR} Iniciando script em '{script_cwd}'...")

        try:
            # A flag "-u" (unbuffered) ainda é uma boa prática para garantir que a saída não fique presa.
            command = [sys.executable, "-u", script_path]

            # Esta é a parte crucial: sem stdout/stderr=PIPE, os scripts filhos
            # imprimirão diretamente no terminal, evitando o bloqueio do buffer.
            process = subprocess.Popen(
                command,
                cwd=script_cwd
            )
            processes.append((process, script_name, script_color))
            
        except Exception as e:
            print(f"{script_color}[{script_name}]{RESET_COLOR} ERRO ao iniciar o script: {e}")

    # Loop para monitorar e aguardar o encerramento
    try:
        while True:
            for p, name, color in processes:
                if p.poll() is not None:
                    print(f"\n{color}[{name}]{RESET_COLOR} ATENÇÃO: O processo encerrou com código {p.poll()}. Encerrando tudo.")
                    # Encerra tudo se um processo morrer para evitar estado inconsistente
                    raise KeyboardInterrupt
            time.sleep(2)

    except KeyboardInterrupt:
        print("\n" + "=" * 50)
        print("Recebido sinal de interrupção (Ctrl+C). Encerrando todos os scripts...")
        
        for process, name, color in reversed(processes): # Encerra na ordem inversa
            if process.poll() is None: # Se ainda estiver rodando
                print(f"{color}[{name}]{RESET_COLOR} Enviando sinal de encerramento...")
                process.terminate()
        
        # Aguarda um pouco para os processos terminarem
        time.sleep(2)
        
        for process, name, color in processes:
            if process.poll() is None:
                print(f"{color}[{name}]{RESET_COLOR} Processo não encerrou, forçando (kill)...")
                process.kill()
                
        print("Todos os scripts foram encerrados.")
        print("=" * 50)

if __name__ == "__main__":
    main()
