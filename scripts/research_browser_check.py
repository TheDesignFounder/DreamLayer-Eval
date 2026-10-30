"""Start isolated local servers, run Playwright, and always stop owned processes."""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def main():
    root = Path(__file__).resolve().parents[1]
    work = root / ".research" / "ci-browser-servers"
    work.mkdir(parents=True, exist_ok=False)
    for port in (5057, 8082):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Port {port} is occupied; no existing process will be stopped")
    env = {
        **os.environ,
        "RESEARCH_API_URL": "http://127.0.0.1:5057",
        "PLAYWRIGHT_BASE_URL": "http://127.0.0.1:8082",
    }
    processes, logs = [], []
    try:
        commands = [
            (
                [
                    sys.executable,
                    "-m",
                    "research",
                    "--db",
                    str(work / "study.sqlite3"),
                    "serve",
                    "--port",
                    "5057",
                ],
                root,
            ),
            (
                [
                    "npm",
                    "run",
                    "dev",
                    "--",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8082",
                    "--strictPort",
                ],
                root / "dream_layer_frontend",
            ),
        ]
        for index, (command, directory) in enumerate(commands):
            log = (work / f"server-{index}.log").open("w")
            logs.append(log)
            processes.append(
                subprocess.Popen(
                    command,
                    cwd=directory,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
        for url in ("http://127.0.0.1:5057/api/research/health", "http://127.0.0.1:8082/research"):
            deadline = time.monotonic() + 40
            while True:
                try:
                    with urlopen(url, timeout=1) as response:
                        assert response.status == 200
                    break
                except (URLError, TimeoutError):
                    if time.monotonic() > deadline or any(p.poll() is not None for p in processes):
                        raise RuntimeError(f"Server did not become ready: {url}") from None
                    time.sleep(0.2)
        result = subprocess.run(["npm", "test"], cwd=root / "dream_layer_frontend", env=env)
        raise SystemExit(result.returncode)
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
