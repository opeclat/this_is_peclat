import pynput.mouse
import pynput.keyboard
import time
import json
import argparse
import threading
import sys
import os
import signal
import tkinter as tk

# --- Configurações Globais ---
RECORDER_PID_FILE = "recorder_v2.pid"
output_file_global = None
recorded_events_global = []
recording_start_time_global = None
stop_recording_event_global = threading.Event()
mouse_listener_global = None
keyboard_listener_global = None

# Globais do cronômetro
timer_window_global = None
timer_label_global = None
remaining_time_global = 0
timer_thread_global = None
timer_update_id_global = None

# Controle de limpeza
_cleanup_has_run = False
_cleanup_lock = threading.Lock()

# --- Funções do Cronômetro ---
def update_timer_display():
    """Atualiza o cronômetro na janela Tkinter."""
    global timer_label_global, remaining_time_global, timer_window_global, stop_recording_event_global, timer_update_id_global
    if timer_window_global and timer_label_global:
        mins, secs = divmod(remaining_time_global, 60)
        timer_label_global.config(text=f"Tempo: {mins:02d}:{secs:02d}")
        if remaining_time_global > 0 and not stop_recording_event_global.is_set():
            remaining_time_global -= 1
            timer_update_id_global = timer_window_global.after(1000, update_timer_display)
        elif not stop_recording_event_global.is_set():
            timer_label_global.config(text="Tempo esgotado!")
            print("DEBUG: Tempo esgotado.", file=sys.stderr, flush=True)
            stop_recording_event_global.set()

def create_timer_window():
    """Cria a janela do cronômetro de forma segura."""
    global timer_window_global, timer_label_global
    timer_window_global = tk.Tk()
    timer_window_global.title("Cronômetro do Gravador")
    timer_window_global.geometry("150x50+100+100")
    timer_window_global.attributes("-topmost", True)
    timer_window_global.protocol("WM_DELETE_WINDOW", lambda: None)
    timer_label_global = tk.Label(timer_window_global, text="Iniciando...", font=("Arial", 14))
    timer_label_global.pack(expand=True, fill=tk.BOTH)
    print("DEBUG: Janela Tkinter criada.", file=sys.stderr, flush=True)
    update_timer_display()
    while not stop_recording_event_global.is_set():
        try:
            timer_window_global.update()
            time.sleep(0.01)
        except tk.TclError:
            print("DEBUG: Janela Tkinter fechada ou erro.", file=sys.stderr, flush=True)
            break
    print("DEBUG: Loop Tkinter finalizado.", file=sys.stderr, flush=True)

# --- Callbacks do Mouse ---
def on_move(x, y):
    if recording_start_time_global and not stop_recording_event_global.is_set():
        elapsed = time.time() - recording_start_time_global
        recorded_events_global.append({'type': 'mouse', 'action': 'move', 'x': x, 'y': y, 'time_offset': elapsed})

def on_click(x, y, button, pressed):
    if recording_start_time_global and not stop_recording_event_global.is_set():
        elapsed = time.time() - recording_start_time_global
        recorded_events_global.append({
            'type': 'mouse', 'action': 'press' if pressed else 'release',
            'button': str(button), 'x': x, 'y': y, 'time_offset': elapsed
        })

def on_scroll(x, y, dx, dy):
    if recording_start_time_global and not stop_recording_event_global.is_set():
        elapsed = time.time() - recording_start_time_global
        recorded_events_global.append({
            'type': 'mouse', 'action': 'scroll', 'x': x, 'y': y, 'dx': dx, 'dy': dy, 'time_offset': elapsed
        })

# --- Callbacks do Teclado ---
def on_key_press(key):
    """Captura Ctrl+C globalmente para parar a gravação."""
    try:
        # Verifica se é a tecla 'c' ou 'C'
        if hasattr(key, 'char') and key.char and key.char.lower() == 'c':
            # Verifica se Ctrl está pressionado usando uma abordagem mais robusta
            # Vamos usar uma variável global para rastrear o estado do Ctrl
            if hasattr(on_key_press, 'ctrl_pressed') and on_key_press.ctrl_pressed:
                print("\nCtrl+C detectado! Parando gravação...", flush=True)
                stop_recording_event_global.set()
        # Verifica se é a tecla Ctrl
        elif key == pynput.keyboard.Key.ctrl or key == pynput.keyboard.Key.ctrl_l or key == pynput.keyboard.Key.ctrl_r:
            on_key_press.ctrl_pressed = True
    except AttributeError:
        pass

def on_key_release(key):
    """Callback para liberação de teclas."""
    try:
        # Reseta o estado do Ctrl quando liberado
        if key == pynput.keyboard.Key.ctrl or key == pynput.keyboard.Key.ctrl_l or key == pynput.keyboard.Key.ctrl_r:
            on_key_press.ctrl_pressed = False
    except AttributeError:
        pass

# Inicializa o estado do Ctrl
on_key_press.ctrl_pressed = False

# --- Limpeza ---
def save_and_cleanup(signal_num=None, frame=None):
    global mouse_listener_global, keyboard_listener_global, _cleanup_has_run, timer_window_global, timer_thread_global, timer_update_id_global
    print("DEBUG: Iniciando save_and_cleanup.", file=sys.stderr, flush=True)
    
    with _cleanup_lock:
        if _cleanup_has_run:
            print("DEBUG: Limpeza já executada. Ignorando.", file=sys.stderr, flush=True)
            return
        _cleanup_has_run = True
        print("DEBUG: _cleanup_has_run definido como True.", file=sys.stderr, flush=True)

    if signal_num:
        print(f"Sinal {signal_num} recebido. Parando gravação...", flush=True)

    stop_recording_event_global.set()
    print("DEBUG: stop_recording_event_global definido.", file=sys.stderr, flush=True)

    # Para o listener do teclado primeiro
    if keyboard_listener_global and keyboard_listener_global.is_alive():
        print("DEBUG: Parando listener do teclado.", file=sys.stderr, flush=True)
        try:
            keyboard_listener_global.stop()
            print("DEBUG: Listener do teclado parado.", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"DEBUG: Erro ao parar listener do teclado: {e}", file=sys.stderr, flush=True)
        keyboard_listener_global.join(timeout=1.0)
        print("DEBUG: Thread do listener do teclado finalizado.", file=sys.stderr, flush=True)
        keyboard_listener_global = None

    # Para o listener do mouse
    if mouse_listener_global and mouse_listener_global.is_alive():
        print("DEBUG: Parando listener do mouse.", file=sys.stderr, flush=True)
        try:
            mouse_listener_global.stop()
            print("DEBUG: Listener do mouse parado.", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"DEBUG: Erro ao parar listener do mouse: {e}", file=sys.stderr, flush=True)
        mouse_listener_global.join(timeout=1.0)
        print("DEBUG: Thread do listener do mouse finalizado.", file=sys.stderr, flush=True)
        mouse_listener_global = None

    # Junta o thread do cronômetro (a janela Tkinter será destruída automaticamente)
    if timer_thread_global and timer_thread_global.is_alive():
        print("DEBUG: Juntando thread do cronômetro.", file=sys.stderr, flush=True)
        timer_thread_global.join(timeout=2.0)
        if timer_thread_global.is_alive():
            print("DEBUG: Thread do cronômetro não terminou a tempo.", file=sys.stderr, flush=True)
        else:
            print("DEBUG: Thread do cronômetro finalizado.", file=sys.stderr, flush=True)
        timer_thread_global = None

    # Limpa as variáveis globais do Tkinter
    timer_window_global = None
    timer_label_global = None
    timer_update_id_global = None

    # Salva os eventos, mesmo que a lista esteja vazia
    if output_file_global:
        # --- NOVO: Salvar na pasta mouse_app/mouse_files ---
        base_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(base_dir, 'mouse_files')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_filename = os.path.basename(output_file_global)
        output_path = os.path.join(output_dir, output_filename)
        print(f"DEBUG: Salvando gravação em {output_path}.", file=sys.stderr, flush=True)
        total_duration = (time.time() - recording_start_time_global) if recording_start_time_global else 0
        total_duration = max(0, total_duration)
        data = {'total_duration': total_duration, 'events': recorded_events_global}
        try:
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Gravação salva em {output_path}")
            print(f"Duração total: {total_duration // 60:.0f}m {total_duration % 60:.2f}s")
        except IOError as e:
            print(f"Erro ao salvar arquivo JSON: {e}", file=sys.stderr, flush=True)
    else:
        print("DEBUG: output_file_global não definido, não salvando arquivo.", file=sys.stderr, flush=True)

    # Remove o arquivo PID
    if os.path.exists(RECORDER_PID_FILE):
        try:
            with open(RECORDER_PID_FILE, 'r') as pf:
                pid_in_file = int(pf.read().strip())
            if pid_in_file == os.getpid():
                os.remove(RECORDER_PID_FILE)
                print(f"Arquivo PID {RECORDER_PID_FILE} removido.")
            else:
                print(f"DEBUG: Arquivo PID pertence a outro processo ({pid_in_file}), não removendo.", file=sys.stderr, flush=True)
        except (IOError, ValueError, OSError) as e:
            print(f"Erro ao remover arquivo PID: {e}", file=sys.stderr, flush=True)

    print("Limpeza concluída.", flush=True)

# --- Gravação ---
def start_recording_foreground(output_f, duration_seconds):
    global output_file_global, recording_start_time_global, recorded_events_global, mouse_listener_global, keyboard_listener_global, remaining_time_global, timer_thread_global
    print("DEBUG: Iniciando start_recording_foreground.", file=sys.stderr, flush=True)
    
    # Valida o arquivo de saída
    if not output_f:
        print("Erro: Nome do arquivo de saída não fornecido.", file=sys.stderr, flush=True)
        sys.exit(1)
    output_file_global = output_f
    remaining_time_global = duration_seconds
    recorded_events_global = []
    recording_start_time_global = time.time()
    stop_recording_event_global.clear()
    global _cleanup_has_run
    _cleanup_has_run = False

    # Configura sinais
    signal.signal(signal.SIGINT, save_and_cleanup)
    signal.signal(signal.SIGTERM, save_and_cleanup)
    print("DEBUG: Manipuladores de sinais configurados.", file=sys.stderr, flush=True)

    # Cria arquivo PID
    try:
        with open(RECORDER_PID_FILE, 'w') as pf:
            pf.write(str(os.getpid()))
        print(f"Gravação iniciada (PID: {os.getpid()}). Arquivo PID: {RECORDER_PID_FILE}")
        print(f"Saída em: {output_file_global}")
        print("Pressione Ctrl+C (em qualquer janela) ou execute 'python3 mouse_recorder_v2.py stop' para parar.")
    except IOError as e:
        print(f"Erro ao criar arquivo PID: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

    # Inicia cronômetro
    timer_thread_global = threading.Thread(target=create_timer_window, daemon=True)
    timer_thread_global.start()
    print("DEBUG: Thread do cronômetro iniciado.", file=sys.stderr, flush=True)
    time.sleep(0.5)

    # Inicia listener do teclado para capturar Ctrl+C globalmente
    try:
        keyboard_listener_global = pynput.keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
        keyboard_listener_global.start()
        print("DEBUG: Listener do teclado iniciado.", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Erro ao iniciar listener do teclado: {e}", file=sys.stderr, flush=True)
        save_and_cleanup()
        sys.exit(1)

    # Inicia listener do mouse
    try:
        mouse_listener_global = pynput.mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
        mouse_listener_global.start()
        print("DEBUG: Listener do mouse iniciado.", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Erro ao iniciar listener do mouse: {e}", file=sys.stderr, flush=True)
        save_and_cleanup()
        sys.exit(1)

    try:
        print("DEBUG: Entrando no loop principal de gravação.", file=sys.stderr, flush=True)
        while not stop_recording_event_global.is_set():
            if remaining_time_global <= 0:
                print("DEBUG: Duração atingida. Parando gravação.", file=sys.stderr, flush=True)
                stop_recording_event_global.set()
                break
            stop_recording_event_global.wait(timeout=0.25)
    except Exception as e:
        print(f"Erro inesperado no loop de gravação: {e}", file=sys.stderr, flush=True)
    finally:
        print("DEBUG: Entrando no bloco finally de start_recording_foreground.", file=sys.stderr, flush=True)
        if not _cleanup_has_run:
            save_and_cleanup()

# --- Comando Stop ---
def stop_recording_command():
    print("DEBUG: Iniciando stop_recording_command.", file=sys.stderr, flush=True)
    if not os.path.exists(RECORDER_PID_FILE):
        print(f"Gravador não ativo (PID {RECORDER_PID_FILE} ausente).", file=sys.stderr, flush=True)
        sys.exit(1)
    try:
        with open(RECORDER_PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        print(f"Enviando SIGTERM para o processo {pid}...", flush=True)
        os.kill(pid, signal.SIGTERM)
        time.sleep(1.5)
        if not os.path.exists(RECORDER_PID_FILE):
            print(f"Processo {pid} parado.")
        else:
            print(f"Aviso: Arquivo PID {RECORDER_PID_FILE} ainda existe após SIGTERM.", file=sys.stderr, flush=True)
    except ProcessLookupError:
        print("Processo não encontrado. Removendo PID obsoleto.", file=sys.stderr, flush=True)
        if os.path.exists(RECORDER_PID_FILE):
            try:
                os.remove(RECORDER_PID_FILE)
                print(f"Arquivo PID {RECORDER_PID_FILE} removido.", flush=True)
            except OSError as e:
                print(f"Erro ao remover arquivo PID: {e}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Erro ao enviar SIGTERM: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

# --- Principal ---
def main():
    parser = argparse.ArgumentParser(description="Gravador de Mouse")
    subparsers = parser.add_subparsers(dest="command", required=True)
    start_parser = subparsers.add_parser("start", help="Inicia gravação.")
    start_parser.add_argument("--output", "-o", type=str, required=True, help="Arquivo de saída JSON.")
    start_parser.add_argument("--duration", "-d", type=int, default=600, help="Duração em segundos (padrão: 600).")
    subparsers.add_parser("stop", help="Para gravação ativa.")
    args = parser.parse_args()

    if args.command == "start":
        if os.path.exists(RECORDER_PID_FILE):
            try:
                with open(RECORDER_PID_FILE, 'r') as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                print(f"Erro: Gravador já ativo com PID {pid} ({RECORDER_PID_FILE}).", file=sys.stderr, flush=True)
                sys.exit(1)
            except (OSError, ValueError):
                print(f"Arquivo PID obsoleto encontrado. Removendo {RECORDER_PID_FILE}.", file=sys.stderr, flush=True)
                try:
                    os.remove(RECORDER_PID_FILE)
                except OSError as e:
                    print(f"Erro ao remover arquivo PID: {e}", file=sys.stderr, flush=True)
        start_recording_foreground(args.output, args.duration)
    elif args.command == "stop":
        stop_recording_command()

if __name__ == "__main__":
    main() 