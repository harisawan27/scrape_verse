import os
import sys
import subprocess
import gradio as gr
import uvicorn

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

# 3. Create a lightweight Gradio interface for the Hugging Face Space UI
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
    The Next.js 15 frontend communicates with this backend via REST API (`/v1/watch-plans`, `/v1/watches`, `/v1/activity`).
    """)

# 4. Mount Gradio alongside the FastAPI REST API
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"Starting Web Radar API on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
