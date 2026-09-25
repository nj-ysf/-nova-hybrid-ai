"""Finish first-run local model downloads and verify the running app.

Uses only loopback services and synthetic demo data. Credentials are read from
the ignored .env file and never printed. Safe to rerun: Ollama reuses its cache.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
OLLAMA = "http://localhost:11434"
APP = "http://localhost:8000"
MODELS = ("qwen2.5:0.5b",)


def wait_for_ollama():
    print("Waiting for the local Ollama container to finish its first download.", flush=True)
    deadline = time.monotonic() + 7200
    with httpx.Client(timeout=5, trust_env=False) as client:
        while time.monotonic() < deadline:
            try:
                if client.get(OLLAMA + "/api/tags").status_code == 200:
                    print("Ollama is available. Preparing the CPU test model.", flush=True)
                    return
            except httpx.HTTPError:
                pass
            time.sleep(5)
    raise RuntimeError("Ollama did not become available. Check Docker Compose status.")


def pull_model(name):
    print(f"Downloading {name} (cached data will be reused).", flush=True)
    last_report = 0.0
    with httpx.Client(timeout=httpx.Timeout(120, connect=10), trust_env=False) as client:
        with client.stream("POST", OLLAMA + "/api/pull", json={"model": name, "stream": True}) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if "error" in data:
                    raise RuntimeError(f"Model download failed for {name}; rerun this script to resume.")
                if data.get("status") == "success":
                    print(f"Ready: {name}", flush=True)
                    return
                if time.monotonic() - last_report >= 30 and data.get("total"):
                    completed = data.get("completed", 0) / 1024**2
                    total = data["total"] / 1024**2
                    print(f"{name}: {completed:.0f}/{total:.0f} MiB", flush=True)
                    last_report = time.monotonic()
    raise RuntimeError(f"Download interrupted for {name}; rerun this script to resume.")


def verify_app():
    config = dotenv_values(ROOT / ".env")
    # Warm up weights before the app's bounded generation request.
    with httpx.Client(timeout=300, trust_env=False) as client:
        response = client.post(
            OLLAMA + "/api/chat",
            json={
                "model": MODELS[0],
                "messages": [{"role": "user", "content": "Say ready."}],
                "stream": False,
                "options": {"num_predict": 8},
            },
        )
        response.raise_for_status()
    with httpx.Client(base_url=APP, timeout=180, follow_redirects=True, trust_env=False) as client:
        client.get("/login/").raise_for_status()
        client.post(
            "/login/",
            data={
                "username": config["DJANGO_DEMO_USERNAME"],
                "password": config["DJANGO_DEMO_PASSWORD"],
                "csrfmiddlewaretoken": client.cookies.get("csrftoken"),
            },
            headers={"Referer": APP + "/login/"},
        ).raise_for_status()
        projects = client.get("/api/projects/")
        projects.raise_for_status()
        project = next(item for item in projects.json()["results"] if item["slug"] == "demo")
        response = client.post(
            "/api/chat/",
            json={
                "project_id": project["id"],
                "message": "Say hello in one short sentence.",
                "mode": "local",
            },
            headers={"X-CSRFToken": client.cookies.get("csrftoken"), "Referer": APP + "/"},
        )
        response.raise_for_status()
        if not response.json().get("reply"):
            raise RuntimeError("The chat response was empty.")
        print("READY: CPU-only local chat verified at http://localhost:8000.", flush=True)


def main():
    wait_for_ollama()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(pull_model, MODELS))
    verify_app()


if __name__ == "__main__":
    main()
