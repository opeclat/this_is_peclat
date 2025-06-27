import argparse
import json
import os
import signal
import sys
import time
from multiprocessing import Process, Value
from pynput.mouse import Controller, Button

EXECUTOR_PID_FILE = "executor.pid"
is_executing_shared = Value('b', False) # Shared flag to signal execution stop

class MouseExecutor:
    def __init__(self, recording_file):
        self.recording_file = recording_file
        self.events = []
        self.mouse = Controller()
        self.execution_process = None

    def _load_events(self):
        try:
            with open(self.recording_file, 'r') as f:
                data = json.load(f)
                self.events = data.get('events', [])
                # Events should be sorted by time_offset if not already
                self.events.sort(key=lambda e: e['time_offset'])
            if not self.events:
                print(f"No events found in {self.recording_file}")
                return False
            return True
        except FileNotFoundError:
            print(f"Error: Recording file {self.recording_file} not found.")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {self.recording_file}.")
            sys.exit(1)

    def _execute_events(self):
        if not self._load_events():
            is_executing_shared.value = False
            return

        is_executing_shared.value = True
        print(f"Starting execution of {self.recording_file}...")
        start_playback_time = time.time()

        # Get the timestamp of the first event to calculate initial delay
        # This assumes the first event's time_offset is the "wait time" before the first action
        first_event_offset = self.events[0]['time_offset'] if self.events else 0

        # Correctly handle the time relative to the start of playback
        # The time_offset in the file is relative to the original recording start.
        # We need to make sure playback respects these relative timings.

        last_event_time_offset = 0.0

        for event in self.events:
            if not is_executing_shared.value:
                print("Execution stopped by user.")
                break

            current_event_time_offset = event['time_offset']

            # Wait for the time difference between this event and the last event
            delay = current_event_time_offset - last_event_time_offset
            if delay > 0:
                time.sleep(delay)

            if not is_executing_shared.value: # Check again after sleep
                print("Execution stopped by user during sleep.")
                break

            # Update mouse position for click/scroll events to ensure they happen at correct location
            if event['type'] != 'move': # For click and scroll, ensure position is set first
                 self.mouse.position = (event['x'], event['y'])
                 time.sleep(0.01) # Small delay to ensure position is set before action

            if event['type'] == 'move':
                self.mouse.position = (event['x'], event['y'])
            elif event['type'] == 'click':
                button_map = {
                    'Button.left': Button.left,
                    'Button.right': Button.right,
                    'Button.middle': Button.middle,
                }
                # Handle potential new button types from pynput if any, or stick to known ones
                pynput_button = button_map.get(event['button'])
                if pynput_button:
                    if event['pressed']:
                        self.mouse.press(pynput_button)
                    else:
                        self.mouse.release(pynput_button)
                else:
                    print(f"Warning: Unknown button type {event['button']} in recording. Skipping.")
            elif event['type'] == 'scroll':
                self.mouse.scroll(event['dx'], event['dy'])

            last_event_time_offset = current_event_time_offset

        if is_executing_shared.value: # If not stopped by user
            print("Execution finished.")
        is_executing_shared.value = False # Ensure it's set to false at the end

        # Clean up PID file if this process was the one that created it
        # This check is important if stop_execution might be called by another process
        # For simplicity, the stop_execution will handle PID removal.
        # if os.path.exists(EXECUTOR_PID_FILE):
        #    with open(EXECUTOR_PID_FILE, 'r') as f:
        #        if int(f.read().strip()) == os.getpid():
        #            os.remove(EXECUTOR_PID_FILE)


    def start_execution_daemon(self):
        if os.path.exists(EXECUTOR_PID_FILE):
            try:
                with open(EXECUTOR_PID_FILE, 'r') as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                print(f"Error: Execution is already in progress (PID: {pid}).")
                sys.exit(1)
            except (OSError, ValueError):
                os.remove(EXECUTOR_PID_FILE)

        self.execution_process = Process(target=self._execute_events)
        self.execution_process.daemon = True
        self.execution_process.start()

        with open(EXECUTOR_PID_FILE, 'w') as f:
            f.write(str(self.execution_process.pid))

        print(f"Execution started in background (PID: {self.execution_process.pid}). File: {self.recording_file}")
        sys.exit(0)

    @staticmethod
    def stop_execution_daemon():
        if not os.path.exists(EXECUTOR_PID_FILE):
            print("Error: No active execution found (PID file missing).")
            sys.exit(1)

        try:
            with open(EXECUTOR_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
        except ValueError:
            print("Error: Invalid PID file.")
            if os.path.exists(EXECUTOR_PID_FILE):
                os.remove(EXECUTOR_PID_FILE)
            sys.exit(1)

        print(f"Attempting to stop execution process PID: {pid}...")
        is_executing_shared.value = False # Signal the execution process to stop

        # Give it a moment to stop gracefully
        time.sleep(1) # Adjust as necessary

        try:
            os.kill(pid, 0) # Check if process still exists
            # If still running, it might be stuck or didn't check the flag in time.
            # For critical stops, a SIGTERM or SIGKILL could be used, but that's riskier.
            print(f"Process {pid} is still running. It should stop shortly.")
            # Consider a timeout and then os.kill(pid, signal.SIGTERM) if it doesn't stop
        except OSError:
            print(f"Execution process (PID: {pid}) successfully stopped or was not found.")
        finally:
            if os.path.exists(EXECUTOR_PID_FILE):
                os.remove(EXECUTOR_PID_FILE)
            # print("Execution stop command processed.") # Avoid double "stopped" messages

def main():
    parser = argparse.ArgumentParser(description="Mouse Executor CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    play_parser = subparsers.add_parser("play", help="Play a recorded mouse event file.")
    play_parser.add_argument("--file", "-f", type=str, required=True, help="Recording file name to play (e.g., recording.mrec).")

    stop_parser = subparsers.add_parser("stop", help="Stop the active mouse execution.")

    args = parser.parse_args()

    # Pass the recording file path only if the command is 'play'
    executor = MouseExecutor(args.file if args.command == "play" else None)

    if args.command == "play":
        executor.start_execution_daemon()
    elif args.command == "stop":
        MouseExecutor.stop_execution_daemon()

if __name__ == "__main__":
    main()
