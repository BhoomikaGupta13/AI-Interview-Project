import subprocess
import sys
import time

COMMANDS = [
    [sys.executable, "server.py"],
    [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "portal.py",
        "--server.port",
        "8501",
    ],
]


def main():
    processes = []
    try:
        for command in COMMANDS:
            processes.append(subprocess.Popen(command))
            time.sleep(1)

        print("\nAI Interview Portal is starting.")
        print("Open: http://localhost:8501")
        print("Press Ctrl+C here to stop both services.\n")

        while all(process.poll() is None for process in processes):
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()


#  python run_portal.py
