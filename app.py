import os
import sys
import subprocess
import gradio as gr
import uvicorn

# 0. ZeroGPU startup compatibility shim (for Hugging Face ZeroGPU runtime)
try:
    import spaces

    @spaces.GPU(duration=1)
    def zerogpu_startup_compatibility():
        return "ok"
except Exception:
    def zerogpu_startup_compatibility():
        return "ok"

# 1. Run Neon PostgreSQL database migrations on startup
try:
    print("Executing database migrations against Neon PostgreSQL...")
    subprocess.run([sys.executable, "database/migrate.py"], check=False)
except Exception as exc:
    print(f"Migration note: {exc}")

# 2. Add backend package directory to Python path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app as fastapi_app

# 3. Create a lightweight Gradio interface for the Hub
def build_gradio_ui() -> gr.Blocks:
    with gr.Blocks(title="Web Radar API & Monitoring Hub") as ui:
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
    return ui

# 4. Mount Gradio alongside the FastAPI REST API at /hub
# Single-process architecture: FastAPI owns the application; Gradio is mounted at /hub.
app = gr.mount_gradio_app(fastapi_app, build_gradio_ui(), path="/hub")

if __name__ == "__main__":
    # In Hugging Face Spaces (sdk: gradio), the reverse proxy strictly routes to port 7860
    port = 7860 if os.environ.get("SPACE_ID") else int(os.environ.get("PORT", 7860))
    print(f"Starting Web Radar API on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
