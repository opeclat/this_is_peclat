import pynput.mouse
import pynput.keyboard
import time
import json
import argparse
import threading
import sys
import os
import signal
import tkinter as tk # Added for timer display

# --- Globals ---
RECORDER_PID_FILE = "recorder_v2.pid" # Changed for v2 to avoid conflict
output_file_global = None
recorded_events_global = []
recording_start_time_global = None
stop_recording_event_global = threading.Event()
mouse_listener_global = None
keyboard_listener_global = None

# Timer display globals
timer_window_global = None
timer_label_global = None
remaining_time_global = 0 # Seconds
timer_thread_global = None
timer_update_id_global = None # To cancel after updates

# For Ctrl+Shift+Q detection (now for stop/save)
# Using a set to store currently pressed modifier keys for more robust hotkey detection
pressed_keys_global = set()

# For hotkey suppression (when Ctrl+Shift+Q is used to stop)
hotkey_was_triggered_flag = False


# Flag to ensure save_and_cleanup runs only once
_cleanup_has_run = False
_cleanup_lock = threading.Lock()


# --- Timer Display Functions ---
def update_timer_display():
    """Updates the timer label in the Tkinter window."""
    # Removed is_paused_global from globals here
    global timer_label_global, remaining_time_global, timer_window_global, stop_recording_event_global, timer_update_id_global

    if timer_window_global and timer_label_global:
        mins, secs = divmod(remaining_time_global, 60)
        time_str = f"Time: {mins:02d}:{secs:02d}"
        timer_label_global.config(text=time_str)

        # Decrement time if recording is active and time > 0
        if remaining_time_global > 0 and not stop_recording_event_global.is_set():
            remaining_time_global -= 1
            timer_update_id_global = timer_window_global.after(1000, update_timer_display)
        elif not stop_recording_event_global.is_set(): # Time ran out
            timer_label_global.config(text="Time's up!")
            print("DEBUG: Timer reached zero.", file=sys.stderr, flush=True)
            # The main recording loop handles setting stop_recording_event_global when remaining_time_global <= 0
        # If stop_recording_event_global is set (by main loop, signal, or hotkey), the timer will stop updating here.

def create_timer_window():
    """Creates and configures the Tkinter timer window."""
    global timer_window_global, timer_label_global, remaining_time_global

    timer_window_global = tk.Tk()
    timer_window_global.title("Recorder Timer")
    timer_window_global.geometry("150x50+100+100") # Position top-left
    timer_window_global.attributes("-topmost", True) # Keep window on top
    timer_window_global.protocol("WM_DELETE_WINDOW", lambda: None) # Disable closing via 'X' button

    timer_label_global = tk.Label(timer_window_global, text="Starting...", font=("Arial", 14))
    timer_label_global.pack(expand=True, fill=tk.BOTH)

    print("DEBUG: Tkinter window created.", file=sys.stderr, flush=True)
    update_timer_display() # Initial call to start the countdown
    timer_window_global.mainloop()
    print("DEBUG: Tkinter mainloop finished.", file=sys.stderr, flush=True)


# --- Listener Callbacks ---
def on_move(x, y):
    # Removed is_paused_global and total_paused_duration_global checks/usage
    if recording_start_time_global and not stop_recording_event_global.is_set():
        current_event_time = time.time()
        elapsed = current_event_time - recording_start_time_global
        recorded_events_global.append({
            'type': 'mouse', 'action': 'move',
            'x': x, 'y': y, 'time_offset': elapsed
        })

def on_click(x, y, button, pressed):
    # Removed is_paused_global and total_paused_duration_global checks/usage
    if recording_start_time_global and not stop_recording_event_global.is_set():
        current_event_time = time.time()
        elapsed = current_event_time - recording_start_time_global
        recorded_events_global.append({
            'type': 'mouse', 'action': 'press' if pressed else 'release',
            'button': str(button), 'x': x, 'y': y, 'time_offset': elapsed
        })

def on_scroll(x, y, dx, dy):
    # Removed is_paused_global and total_paused_duration_global checks/usage
    if recording_start_time_global and not stop_recording_event_global.is_set():
        current_event_time = time.time()
        elapsed = current_event_time - recording_start_time_global
        recorded_events_global.append({
            'type': 'mouse', 'action': 'scroll',
            'x': x, 'y': y, 'dx': dx, 'dy': dy, 'time_offset': elapsed
        })

def get_key_repr(key):
    if isinstance(key, pynput.keyboard.KeyCode): return key.char
    elif isinstance(key, pynput.keyboard.Key): return key.name
    return None

# Hotkey logic (Ctrl+Shift+Q to stop) will be in on_key_press.
# Pause/resume functionality is removed.

def on_key_press(key):
    global pressed_keys_global, recording_start_time_global, stop_recording_event_global, hotkey_was_triggered_flag

    key_name = get_key_repr(key)
    # is_modifier variable was here, but not used. Removed.

    if key_name:
        pressed_keys_global.add(key_name)
    elif isinstance(key, pynput.keyboard.Key):
        pressed_keys_global.add(key.name)

    # --- Hotkey Detection (Ctrl+Shift+Q) ---
    # Add current key to the set of currently pressed keys
    # Note: key_name comes from get_key_repr(key) at the start of the function.
    # pressed_keys_global is updated at the start of on_key_press.

    ctrl_pressed = any('ctrl' in k for k in pressed_keys_global)
    shift_pressed = any('shift' in k for k in pressed_keys_global)
    is_q_for_hotkey = (key_name == 'q' or key_name == 'Q') # Current key press is 'q' or 'Q'

    if ctrl_pressed and shift_pressed and is_q_for_hotkey:
        # This is the hotkey combination to STOP recording.
        print("DEBUG: Ctrl+Shift+Q hotkey pressed. Stopping recording.", file=sys.stderr, flush=True)
        hotkey_was_triggered_flag = True # To help suppress component key releases
        stop_recording_event_global.set() # Signal the main loop to stop
        return # IMPORTANT: Do not record the 'q' press that triggered the hotkey.

    # --- Normal Key Press Recording ---
    # Record key press if:
    # 1. Recording is not paused.
    # 2. Recording is active (start_time set, stop_event not set).
    # 3. The key press was not the 'q' that triggered the hotkey (handled by the return above).
    # Removed is_paused_global check
    if recording_start_time_global and not stop_recording_event_global.is_set():
        # Presses of Ctrl and Shift *leading up to* the hotkey 'q' press will be recorded here.
        # This is generally acceptable behavior.
        current_event_time = time.time()
        elapsed = current_event_time - recording_start_time_global # Removed total_paused_duration_global
        if key_name:
            recorded_events_global.append({
                'type': 'keyboard', 'action': 'press',
                'key': key_name, 'time_offset': elapsed
            })

def on_key_release(key):
    global pressed_keys_global, recording_start_time_global, stop_recording_event_global, hotkey_was_triggered_flag
    # Removed is_paused_global, total_paused_duration_global

    key_name = get_key_repr(key)
    # Check if the released key is 'q' or 'Q'
    is_q_key_release = (key_name == 'q' or key_name == 'Q')
    is_ctrl = key_name and 'ctrl' in key_name
    is_shift = key_name and 'shift' in key_name

    # --- Hotkey Release Suppression ---
    # If hotkey_was_triggered_flag is true, it means a pause/resume was just actioned via Ctrl+Shift+Q.
    # We need to suppress the recording of the release of 'q', 'ctrl', and 'shift' keys
    # that were part of this hotkey combination.
    if hotkey_was_triggered_flag:
        # Check if the currently released key is one of the hotkey components
        if is_q_key_release or is_ctrl or is_shift:
            # First, ensure this key is removed from the set of currently pressed keys
            if key_name and key_name in pressed_keys_global:
                pressed_keys_global.remove(key_name)
            elif isinstance(key, pynput.keyboard.Key) and key.name in pressed_keys_global:
                try: pressed_keys_global.remove(key.name)
                except KeyError: pass # Should not happen if logic is correct

            # Reset hotkey_was_triggered_flag under certain conditions:
            # 1. If 'q' (the main action key of the hotkey) is released.
            # 2. If 'ctrl' or 'shift' is released AND no other non-modifier keys are currently pressed
            #    (suggesting the user has finished the hotkey gesture).
            if is_q_key_release:
                hotkey_was_triggered_flag = False
                # DEBUG message clarifies flag reset due to Q release (after stop hotkey)
                print(f"DEBUG: Suppressing release of STOP hotkey component '{key_name}' and resetting hotkey_was_triggered_flag (Q release).", file=sys.stderr, flush=True)
            elif (is_ctrl or is_shift) and not any(k not in ['ctrl_l', 'ctrl_r', 'shift_l', 'shift_r', 'alt_l', 'alt_r', 'cmd', 'cmd_r'] for k in pressed_keys_global):
                # If only modifiers are left pressed (or no keys at all), reset the flag.
                # This handles cases like: Ctrl+Shift+Q (stop), release Q, release Shift, release Ctrl.
                hotkey_was_triggered_flag = False
                print(f"DEBUG: Suppressing release of STOP hotkey component '{key_name}' and resetting hotkey_was_triggered_flag (modifier release, only modifiers left).", file=sys.stderr, flush=True)
            else:
                # A modifier (ctrl/shift) was released, but other keys might still be pressed.
                # Keep the flag true, expecting more hotkey component releases (e.g., Q or the other modifier).
                print(f"DEBUG: Suppressing release of STOP hotkey component '{key_name}'. Flag remains true. Pressed keys: {pressed_keys_global}", file=sys.stderr, flush=True)

            return # Suppress recording of this key release (Q, Ctrl, or Shift from the hotkey)

    # --- Standard Key Release Processing ---
    # If the release was not suppressed as part of a hotkey:
    # Remove the key from the set of pressed keys.
    if key_name and key_name in pressed_keys_global:
        pressed_keys_global.remove(key_name)
    elif isinstance(key, pynput.keyboard.Key) and key.name in pressed_keys_global:
        try: pressed_keys_global.remove(key.name)
        except KeyError:
            print(f"DEBUG: Tried to remove {key.name} from pressed_keys_global (on release) but not found.", file=sys.stderr)

    # Removed is_paused_global check
    if recording_start_time_global and not stop_recording_event_global.is_set():
        current_event_time = time.time()
        elapsed = current_event_time - recording_start_time_global # Removed total_paused_duration_global
        if key_name:
            recorded_events_global.append({
                'type': 'keyboard', 'action': 'release',
                'key': key_name, 'time_offset': elapsed
            })

def save_and_cleanup(signal_num=None, frame=None):
    # Removed is_paused_global, pause_start_time_global, total_paused_duration_global from globals here
    global mouse_listener_global, keyboard_listener_global, _cleanup_has_run

    print("DEBUG: Entered save_and_cleanup.", file=sys.stderr, flush=True)

    with _cleanup_lock:
        if _cleanup_has_run:
            print("DEBUG: Cleanup has already run. Exiting save_and_cleanup.", file=sys.stderr, flush=True)
            return
        _cleanup_has_run = True
        print("DEBUG: _cleanup_has_run set to True.", file=sys.stderr, flush=True)

    if signal_num is not None:
        print(f"Signal {signal_num} received. Stopping recording...") # Corrected f-string

    stop_recording_event_global.set()
    print("DEBUG: stop_recording_event_global has been set.", file=sys.stderr, flush=True)

    global timer_window_global, timer_thread_global, timer_update_id_global
    if timer_window_global:
        print("DEBUG: Attempting to stop timer display.", file=sys.stderr, flush=True)
        if timer_update_id_global:
            timer_window_global.after_cancel(timer_update_id_global)
            timer_update_id_global = None
        timer_window_global.quit() # Quit Tkinter mainloop
        timer_window_global.destroy() # Destroy window
        timer_window_global = None
        print("DEBUG: Timer window should be closed.", file=sys.stderr, flush=True)

    if timer_thread_global and timer_thread_global.is_alive():
        print("DEBUG: Joining timer thread.", file=sys.stderr, flush=True)
        timer_thread_global.join(timeout=1.0)
        if timer_thread_global.is_alive():
            print("DEBUG: Timer thread did not join in time.", file=sys.stderr, flush=True)
        else:
            print("DEBUG: Timer thread joined.", file=sys.stderr, flush=True)
        timer_thread_global = None

    print("Stopping listeners...")
    if mouse_listener_global and mouse_listener_global.is_alive():
        try:
            print("DEBUG: Attempting to stop mouse_listener.", file=sys.stderr, flush=True)
            mouse_listener_global.stop()
            print("DEBUG: mouse_listener.stop() called.", file=sys.stderr, flush=True)
        except Exception as e: print(f"Error stopping mouse listener: {e}", file=sys.stderr)
    if keyboard_listener_global and keyboard_listener_global.is_alive():
        try:
            print("DEBUG: Attempting to stop keyboard_listener.", file=sys.stderr, flush=True)
            keyboard_listener_global.stop()
            print("DEBUG: keyboard_listener.stop() called.", file=sys.stderr, flush=True)
        except Exception as e: print(f"Error stopping keyboard listener: {e}", file=sys.stderr)

    if mouse_listener_global:
        print("DEBUG: Attempting to join mouse_listener thread.", file=sys.stderr, flush=True)
        mouse_listener_global.join(timeout=1.0)
        print("DEBUG: mouse_listener thread joined or timed out.", file=sys.stderr, flush=True)
    if keyboard_listener_global:
        print("DEBUG: Attempting to join keyboard_listener thread.", file=sys.stderr, flush=True)
        keyboard_listener_global.join(timeout=1.0)
        print("DEBUG: keyboard_listener thread joined or timed out.", file=sys.stderr, flush=True)
    print("Listeners stopped.")

    # Save the recorded data to JSON file
    # Save the recorded data to JSON file
    if recording_start_time_global is not None and output_file_global:
        print(f"DEBUG: Attempting to save recording to {output_file_global}.", file=sys.stderr, flush=True)

        current_cleanup_time = time.time()
        # total_duration is simply the time from start of recording to now, as pauses are removed.
        total_duration = current_cleanup_time - recording_start_time_global
        total_duration = max(0, total_duration) # Ensure non-negative

        print(f"DEBUG: Cleanup Time: {current_cleanup_time}, Recording Start Time: {recording_start_time_global}", file=sys.stderr, flush=True)
        print(f"DEBUG: Calculated total_duration for JSON: {total_duration:.2f}s", file=sys.stderr, flush=True)

        data_to_save = {
            'total_duration': total_duration,
            'events': recorded_events_global
        }
        try:
            with open(output_file_global, 'w') as f:
                json.dump(data_to_save, f, indent=4)
            print(f"Recording saved to {output_file_global}")
            duration_str = "Total duration: {:.0f}m {:.2f}s".format(total_duration // 60, total_duration % 60)
            print(duration_str)
        except IOError as e: print(f"Error saving recording: {e}", file=sys.stderr)
    else: print("No recording data to save or output file not specified.", file=sys.stderr)

    if os.path.exists(RECORDER_PID_FILE):
        try:
            with open(RECORDER_PID_FILE, 'r') as pf: pid_in_file = int(pf.read().strip())
            if pid_in_file == os.getpid():
                os.remove(RECORDER_PID_FILE)
                print(f"PID file {RECORDER_PID_FILE} removed.")
            else: print(f"PID file {RECORDER_PID_FILE} belongs to PID {pid_in_file}, not removing.", file=sys.stderr)
        except (IOError, ValueError, OSError) as e: print(f"Error removing PID file: {e}", file=sys.stderr)

    print("mouse_recorder.py cleanup complete. Exiting.")
    print("DEBUG: Exiting save_and_cleanup.", file=sys.stderr, flush=True)


def start_recording_foreground(output_f, duration_seconds): # Added duration
    global output_file_global, recording_start_time_global, recorded_events_global
    global mouse_listener_global, keyboard_listener_global, stop_recording_event_global, _cleanup_has_run
    global remaining_time_global, timer_thread_global # Timer globals
    global pressed_keys_global, hotkey_was_triggered_flag # Hotkey globals (pause globals removed)

    print("DEBUG: Entered start_recording_foreground.", file=sys.stderr, flush=True)
    output_file_global = output_f
    remaining_time_global = duration_seconds
    recorded_events_global = []
    recording_start_time_global = time.time()
    stop_recording_event_global.clear()
    _cleanup_has_run = False

    # Initialize/Reset hotkey state for a new recording
    pressed_keys_global.clear()
    hotkey_was_triggered_flag = False


    print("DEBUG: Globals initialized in start_recording_foreground.", file=sys.stderr, flush=True)

    signal.signal(signal.SIGINT, save_and_cleanup)
    signal.signal(signal.SIGTERM, save_and_cleanup)
    print("DEBUG: Signal handlers set.", file=sys.stderr, flush=True)

    try:
        with open(RECORDER_PID_FILE, 'w') as pf: pf.write(str(os.getpid()))
        print(f"Recording started in foreground (PID: {os.getpid()}). PID file: {RECORDER_PID_FILE}")
        print(f"Output will be saved to: {output_file_global}")
        print("Press Ctrl+C or Ctrl+Shift+Q to stop recording, or run 'python3 mouse_recorder_v2.py stop' from another terminal.")
    except IOError as e:
        print(f"Error creating PID file {RECORDER_PID_FILE}: {e}", file=sys.stderr); sys.exit(1)

    # Start timer display in a separate thread
    print("DEBUG: Starting timer display thread.", file=sys.stderr, flush=True)
    timer_thread_global = threading.Thread(target=create_timer_window, daemon=True)
    timer_thread_global.start()
    # Give a moment for the window to potentially initialize
    # This is a bit of a hack; a more robust solution might use a queue or event
    # for communication between threads if startup order is critical.
    time.sleep(0.5)
    print("DEBUG: Timer display thread should be running.", file=sys.stderr, flush=True)


    print("DEBUG: Initializing pynput listeners.", file=sys.stderr, flush=True)
    try:
        mouse_listener_global = pynput.mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
        keyboard_listener_global = pynput.keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
        print("DEBUG: pynput listeners objects created.", file=sys.stderr, flush=True)
    except Exception as e_listener_init:
        print(f"DEBUG: ERROR INITIALIZING PYNPUT LISTENERS: {e_listener_init}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        if not _cleanup_has_run: save_and_cleanup()
        sys.exit(1)

    try:
        mouse_listener_global.start()
        print("DEBUG: Mouse listener started.", file=sys.stderr, flush=True)
        keyboard_listener_global.start()
        print("DEBUG: Keyboard listener started.", file=sys.stderr, flush=True)
    except Exception as e_listener_start:
        print(f"DEBUG: ERROR STARTING PYNPUT LISTENERS: {e_listener_start}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        if mouse_listener_global and mouse_listener_global.is_alive(): mouse_listener_global.stop()
        if keyboard_listener_global and keyboard_listener_global.is_alive(): keyboard_listener_global.stop()
        if not _cleanup_has_run: save_and_cleanup()
        sys.exit(1)

    try:
        print("DEBUG: Entering main recording loop (waiting on stop_event or timeout).", file=sys.stderr, flush=True)
        # The timer display thread decrements remaining_time_global.
        # This loop checks if time is up or if an external stop signal (Ctrl+C, 'stop' command) is received.
        while not stop_recording_event_global.is_set():
            if remaining_time_global <= 0:
                print("DEBUG: Recording duration reached. Stopping recording.", file=sys.stderr, flush=True)
                stop_recording_event_global.set() # Signal stop
                break
            # Wait for a short period or until stop_event is set
            # This allows the loop to be responsive to stop_recording_event_global
            # and also periodically check remaining_time_global
            stop_recording_event_global.wait(timeout=0.25) # Check every 250ms

        print("DEBUG: stop_event detected or time ran out in main loop.", file=sys.stderr, flush=True)
        # Ensure cleanup is called if it hasn't been initiated by a signal
        if not _cleanup_has_run:
            print("DEBUG: Main loop initiating cleanup as _cleanup_has_run is False.", file=sys.stderr, flush=True)
            save_and_cleanup() # This will also handle stopping listeners and timer
    except Exception as e:
        print(f"Unexpected error during recording loop: {e}", file=sys.stderr, flush=True)
        if not _cleanup_has_run: save_and_cleanup()
    finally:
        print("DEBUG: Reached finally block of start_recording_foreground's main try.", file=sys.stderr, flush=True)
        # Ensure cleanup one last time, though it should have been called by now.
        if not _cleanup_has_run:
            print("DEBUG: Ensuring cleanup in finally block of start_recording_foreground as _cleanup_has_run is False.", file=sys.stderr, flush=True)
            save_and_cleanup()

        # Listeners and timer thread joining is now primarily handled within save_and_cleanup
        # However, a final check here can be a safeguard.
        if mouse_listener_global and mouse_listener_global.is_alive():
            print("DEBUG: Mouse listener still alive in finally (after cleanup attempt), joining.", file=sys.stderr, flush=True)
            mouse_listener_global.join(timeout=0.5)
        if keyboard_listener_global and keyboard_listener_global.is_alive():
            print("DEBUG: Keyboard listener still alive in finally, joining.", file=sys.stderr, flush=True)
            keyboard_listener_global.join(timeout=0.5)
        print("DEBUG: Exiting start_recording_foreground.", file=sys.stderr, flush=True)

def stop_recording_command():
    if not os.path.exists(RECORDER_PID_FILE):
        print(f"Recorder not running (PID file {RECORDER_PID_FILE} missing).", file=sys.stderr); sys.exit(1)
    try:
        with open(RECORDER_PID_FILE, 'r') as f: pid = int(f.read().strip())
    except (IOError, ValueError) as e:
        print(f"Error reading PID file: {e}", file=sys.stderr); sys.exit(1)

    print(f"Sending SIGTERM to recorder process (PID: {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(1.5)
        if os.path.exists(RECORDER_PID_FILE):
            print(f"Warning: PID file {RECORDER_PID_FILE} still exists after sending SIGTERM to PID {pid}. Manual check may be needed.", file=sys.stderr)
        else:
            print(f"Stop signal sent. Recorder process {pid} should have terminated and cleaned up its PID file.")
    except ProcessLookupError:
        print(f"Process {pid} not found. Already stopped or PID file is stale.", file=sys.stderr)
        if os.path.exists(RECORDER_PID_FILE):
            try:
                os.remove(RECORDER_PID_FILE)
                print(f"Removed stale PID file {RECORDER_PID_FILE}.", file=sys.stderr)
            except OSError as e_rm:
                print(f"Error removing stale PID file {RECORDER_PID_FILE}: {e_rm}", file=sys.stderr)
    except Exception as e:
        print(f"Error sending SIGTERM to process {pid}: {e}", file=sys.stderr); sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Mouse and Keyboard Recorder (Foreground)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    start_parser = subparsers.add_parser("start", help="Start recording (blocks terminal).")
    start_parser.add_argument("--output", "-o", type=str, required=True, help="Output file name.")
    start_parser.add_argument("--duration", "-d", type=int, default=600, help="Maximum recording duration in seconds (default: 600 for 10 minutes).")
    subparsers.add_parser("stop", help="Stop active recording by signaling PID.")
    args = parser.parse_args()

    if args.command == "start":
        if os.path.exists(RECORDER_PID_FILE):
            try:
                with open(RECORDER_PID_FILE, 'r') as f: pid = int(f.read().strip())
                os.kill(pid, 0)
                print(f"Error: Recorder seems to be already running with PID {pid} (found {RECORDER_PID_FILE}).", file=sys.stderr)
                print("If it's not, delete the PID file and try again.", file=sys.stderr)
                sys.exit(1)
            except (OSError, ValueError):
                print(f"Stale or corrupt PID file {RECORDER_PID_FILE} found. Removing.", file=sys.stderr)
                try: os.remove(RECORDER_PID_FILE)
                except OSError as e: print(f"Could not remove stale PID file: {e}", file=sys.stderr)

        start_recording_foreground(args.output, args.duration)
    elif args.command == "stop":
        stop_recording_command()

if __name__ == "__main__":
    main()
