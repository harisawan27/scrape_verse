import os
import sys
import subprocess
import atexit
import signal
import threading
import spaces
import gradio as gr

# 0. Unconditional module-level ZeroGPU compatibility function
@spaces.GPU(duration=1)
def zerogpu_startup_compatibility():
    return "ok"

# 1. Run Neon PostgreSQL database migrations on startup
try:
    print("Executing database migrations against Neon PostgreSQL...")
    subprocess.run([sys.executable, "database/migrate.py"], check=False)
except Exception as exc:
    print(f"Migration note: {exc}")

# 2. Add backend package directory to Python path and disable embedded lifespan scheduler
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ["SCHEDULER_ENABLED"] = "false"

from app.main import app as fastapi_app

# 3. Create Gradio interface
with gr.Blocks(title="Web Radar API & Monitoring Hub") as demo:
    gr.Markdown("""
    # 📡 Web Radar — Backend API & Monitoring Engine

    Web Radar is an autonomous, persistent web monitoring platform backed by **Bright Data Scraper Studio** and **Neon PostgreSQL**.

    ### 🚀 API Endpoints
    - **Interactive API Documentation (Swagger UI)**: [Open `/docs`](/docs)
    - **Alternative API Docs (ReDoc)**: [Open `/redoc`](/redoc)
    - **Liveness Probe**: [Check `/health`](/health)
    - **Database Health**: [Check `/health/database`](/health/database)

    ### 🌐 Connected Frontend
    The Next.js 15 frontend communicates with this backend via REST API (`/v1/watch-plans`, `/v1/watches`, `/v1/activity`, `/v1/auth/me`).
    """)

# 4. Launch Gradio using only standard public arguments (NO _app, NO manual Uvicorn)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))

    # Launch Gradio server
    gradio_app, local_url, share_url = demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        prevent_thread_lock=True,
    )

    # Attach existing Web Radar FastAPI routes directly to Gradio's FastAPI application
    gradio_app.include_router(fastapi_app.router)
    print(f"Web Radar REST API and Gradio UI running on {local_url}")

    # Start exactly ONE standalone background worker process for scheduler and Bright Data polling
    worker_env = os.environ.copy()
    worker_env["PYTHONPATH"] = backend_dir
    worker_env["SCHEDULER_ENABLED"] = "true"

    worker_proc = subprocess.Popen(
        [sys.executable, "-m", "app.worker"],
        cwd=backend_dir,
        env=worker_env,
    )
    print(f"Autonomous background worker started (PID {worker_proc.pid})")

    def cleanup_worker():
        if worker_proc and worker_proc.poll() is None:
            print("Stopping background worker...")
            worker_proc.terminate()
            try:
                worker_proc.wait(timeout=5)
            except Exception:
                worker_proc.kill()

    atexit.register(cleanup_worker)

    stop_event = threading.Event()

    def signal_handler(signum, frame):
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while not stop_event.is_set():
            stop_event.wait(timeout=1.0)
    finally:
        cleanup_worker()
        demo.close()
