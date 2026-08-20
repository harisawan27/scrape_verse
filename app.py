import os
import sys
import subprocess
import contextlib
import spaces
import gradio as gr
from gradio.routes import App

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

# 2. Add backend package directory to Python path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

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

# 4. Integrate FastAPI routers and lifespan into Gradio's underlying FastAPI application
app = App.create_app(demo)
app.include_router(fastapi_app.router)

# Merge FastAPI lifespan context so autonomous scheduler/worker loop runs within Gradio
fastapi_lifespan = fastapi_app.router.lifespan_context
gradio_lifespan = app.router.lifespan_context

@contextlib.asynccontextmanager
async def unified_lifespan(asgi_app):
    async with fastapi_lifespan(asgi_app) as s1:
        async with gradio_lifespan(asgi_app) as s2:
            yield s1 or s2

app.router.lifespan_context = unified_lifespan

# 5. Launch via demo.launch using the Gradio-managed server on port 7860
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        _app=app,
    )
