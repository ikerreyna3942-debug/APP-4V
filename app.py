"""
app.py
======
FastAPI Server & Route Handlers for Furniture Prompt Generator Studio
(Generador de Prompts de Muebles).

Coordinates Gemini AI Vision Service and Dynamic Environment Injection.
Ready for containerized deployment on Render and local development.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    File,
    UploadFile,
    Form,
    Header,
    Request,
    status
)
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError

# Load environment variables (.env) if present
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("generador_prompts_muebles.app")

# Core Constants & Configuration
APP_VERSION = "1.0.0"
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Ensure static directory exists
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# The 5 Authoritative Generation Modes (strictly enforced per Requirement R2 & Acceptance Criteria 4)
ALLOWED_MODES: List[str] = [
    "solo mueble",
    "vistas",
    "entorno",
    "vistas + tela y madera",
    "vistas + tela"
]

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}
MAX_IMAGE_SIZE_MB = 50
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024

FALLBACK_INDEX_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generador de Prompts de Muebles</title>
</head>
<body>
    <header>
        <h1>Generador de Prompts de Muebles</h1>
    </header>
    <main>
        <section id="dropzone" class="dropzone">
            <p>Arrastra y suelta tu foto aquí (Drag and drop zone)</p>
            <button id="btn-borrar" type="button">Borrar imagen (Delete / Reset)</button>
        </section>
        <section class="mode-buttons">
            <button type="button" data-mode="solo mueble">solo mueble</button>
            <button type="button" data-mode="vistas">vistas</button>
            <button type="button" data-mode="entorno">entorno</button>
            <button type="button" data-mode="vistas + tela y madera">vistas + tela y madera</button>
            <button type="button" data-mode="vistas + tela">vistas + tela</button>
        </section>
        <section id="result-area">
            <button id="btn-copiar" type="button">Copiar al portapapeles (Copy)</button>
        </section>
    </main>
</body>
</html>"""

# Initialize FastAPI application
app = FastAPI(
    title="Generador de Prompts de Muebles",
    description="Aplicación web interactiva para análisis de imágenes de muebles y generación de prompts dinámicos con Google Gemini AI.",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Custom Exception Handlers for Strict API Contract Compliance
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Translates FastAPI 422 Unprocessable Entity into 400 Bad Request
    to strictly adhere to PROJECT.md interface contract for missing fields.
    """
    errors = exc.errors()
    missing_fields = []
    for err in errors:
        loc = err.get("loc", ())
        if loc:
            missing_fields.append(str(loc[-1]))
    fields_hint = f" (campos con error: {', '.join(missing_fields)})" if missing_fields else ""

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": f"El archivo de imagen es obligatorio y el modo debe ser uno de los 5 permitidos.{fields_hint}"
        }



@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catches any unhandled exceptions to return a structured JSON response
    instead of leaking raw server tracebacks.
    """
    logger.error(f"Excepción no capturada en {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": f"Error interno del servidor: {str(exc)}"
        }



# ---------------------------------------------------------------------------
# Static Assets Mount
# ---------------------------------------------------------------------------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# HTTP Route Handlers
# ---------------------------------------------------------------------------

@app.api_route("/", methods=["GET", "HEAD"], summary="Página principal de la aplicación")
async def root():
    """
    Serves the single-page application frontend.
    If static/index.html is created, serves it directly.
    Otherwise, returns fallback semantic HTML satisfying requirements.
    """
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse(content=FALLBACK_INDEX_HTML, status_code=status.HTTP_200_OK)


@app.get("/health", summary="Healthcheck para Render y monitoreo de estado")
async def healthcheck():
    """
    Healthcheck endpoint for Render zero-downtime deployments.
    Guarantees <5ms response time with zero external network dependencies.
    """
    return {
        "status": "ok",
        "version": APP_VERSION
    }


@app.get("/api/health", summary="Alias del endpoint de healthcheck")
async def api_healthcheck():
    """
    API namespace alias for healthcheck.
    """
    return {
        "status": "ok",
        "version": APP_VERSION
    }


@app.get("/api/modes", summary="Catálogo de los 5 modos de generación de prompts")
async def list_modes():
    """
    Returns the catalog of the 5 official prompt generation modes.
    Useful for UI dynamic population and client validations.
    """
    return {
        "success": True,
        "modes": [
            {
                "id": "solo mueble",
                "label": "solo mueble",
                "description": "Aislamiento digital de alta precisión sobre fondo blanco puro #FFFFFF sin sombras ni reflejos."
            },
            {
                "id": "vistas",
                "label": "vistas",
                "description": "5 perspectivas ortogonales de catálogo con inyección dinámica de escenarios arquitectónicos aleatorios (R3)."
            },
            {
                "id": "entorno",
                "label": "entorno",
                "description": "Ubicación contextual en interiores arquitectónicos de lujo con profundidad de campo óptica f/2.8."
            },
            {
                "id": "vistas + tela y madera",
                "label": "vistas + tela y madera",
                "description": "5 perspectivas con deconstrucción técnica de textura textil (weave mm) y vetas/acabados de madera."
            },
            {
                "id": "vistas + tela",
                "label": "vistas + tela",
                "description": "5 perspectivas centradas en tapicería textil con restricción estricta de preservación de patas y estructura de madera."
            }
        ]
    }


@app.post("/api/generate", summary="Analiza la imagen de mueble y genera prompts profesionales con Gemini AI")
async def generate_prompt(
    image: List[UploadFile] = File(..., description="Archivos de imagen del mueble cargado mediante Drag & Drop"),
    mode: str = Form(..., description="Modo exacto de generación (uno de los 5 permitidos)"),
    notes: Optional[str] = Form(None, description="Notas adicionales o requerimientos del usuario"),
    custom_api_key: Optional[str] = Form(None, description="Clave API opcional enviada en el formulario"),
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key", description="Clave API opcional en header")
):
    """
    Core generation endpoint:
    1. Validates generation mode strictly against the 5 allowed modes (case sensitive).
    2. Validates image presence, file size, image format, and Pillow decode integrity.
    3. Resolves Gemini API key hierarchy.
    4. For mode 'vistas', coordinates dynamic scenario sampling via services/random_scenarios.py.
    5. Calls services/gemini_service.py with fallback cascade across Gemini models.
    6. Returns structured JSON adhering to the PROJECT.md interface contract.
    """
    # 1. Validate Mode Strictly (Case-sensitive per AC 4 & tests)
    if mode not in ALLOWED_MODES:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": f"Modo '{mode}' no válido. El modo debe ser uno de los 5 permitidos: {', '.join(ALLOWED_MODES)}."
            }
        )

    # 2. Validate Image File
    if not image:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": "El archivo de imagen es obligatorio y el modo debe ser uno de los 5 permitidos."
            }
        )

    if len(image) > 10:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": "Se permite un máximo de 10 imágenes por generación."
            }
        )

    raw_bytes_list = []
    
    for img in image:
        if not img or not img.filename:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error": "El archivo de imagen es obligatorio y el modo debe ser uno de los 5 permitidos."
                }
            )

        filename_lower = (img.filename or "").lower()
        content_type_lower = (img.content_type or "").lower()

        has_valid_extension = any(filename_lower.endswith(ext) for ext in ALLOWED_IMAGE_EXTENSIONS)
        is_image_mime = content_type_lower.startswith("image/")

        if not (has_valid_extension or is_image_mime):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error": "El archivo proporcionado no es una imagen válida. Formatos permitidos: JPG, PNG, WEBP, GIF, BMP."
                }
            )

        try:
            image_bytes = await img.read()
        except Exception as read_err:
            logger.error(f"Error al leer el stream del archivo de imagen: {read_err}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error": "No se pudo leer el archivo de imagen subido."
                }
            )

        if not image_bytes or len(image_bytes) == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error": "El archivo de imagen está vacío."
                }
            )

        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error": f"El archivo de imagen supera el tamaño máximo permitido ({MAX_IMAGE_SIZE_MB}MB)."
                }
            )

        raw_bytes_list.append(image_bytes)

    # 3. Dynamic Environment Coordination for 'vistas' (R3 & AC 5)
    environment_data = None
    if mode == "vistas":
        try:
            from services.random_scenarios import sample_random_scene
            scene_result = sample_random_scene()
            environment_data = scene_result.get("environment", {
                "style": scene_result.get("style", ""),
                "location": scene_result.get("location", ""),
                "lighting": scene_result.get("lighting", ""),
                "palette": scene_result.get("palette", "")
            })
        except Exception as rand_err:
            logger.error(f"Error al muestrear escenario dinámico: {rand_err}", exc_info=True)
            environment_data = {
                "style": "Contemporary Minimalist luxury architecture",
                "location": "Curated residential art salon with expansive views",
                "lighting": "Diffused northern daylight with soft contact shadows",
                "palette": "Warm neutral earthy harmony"
            }

    # 4. Resolve API Key
    effective_api_key = (
        (custom_api_key.strip() if custom_api_key else None) or
        (x_gemini_key.strip() if x_gemini_key else None) or
        os.getenv("GEMINI_API_KEY", "").strip() or
        os.getenv("GOOGLE_API_KEY", "").strip() or
        None


    if not effective_api_key:
        logger.error("GEMINI_API_KEY no encontrada en la solicitud ni en variables de entorno")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Error al comunicarse con Gemini AI: Falta configurar la variable de entorno GEMINI_API_KEY. Configure la variable en su archivo .env o en el panel de Render."
            }
        )

    # 5. Call Gemini AI Vision Service
    try:
        from services.gemini_service import GeminiService
        service = GeminiService(api_key=effective_api_key)

        ai_result = service.generate_prompt(
            images_bytes=raw_bytes_list,
            mode=mode,
            user_notes=notes,
            environment=environment_data
        )

    except ImportError as imp_err:
        logger.error(f"Error de importación de gemini_service: {imp_err}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Error al comunicarse con Gemini AI: El módulo de servicio services.gemini_service no está disponible."
            }
        )
    except Exception as srv_err:
        logger.error(f"Excepción al ejecutar gemini_service: {srv_err}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": f"Error al comunicarse con Gemini AI: {str(srv_err)}"
            }
        )

    # 6. Evaluate AI Service Response
    if isinstance(ai_result, dict):
        if not ai_result.get("success", True) and "error" in ai_result:
            error_msg = ai_result['error']
            # Map image processing errors to 400
            if "procesar la imagen" in error_msg.lower():
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "success": False,
                        "error": error_msg
                    }
                )
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "error": f"Error al comunicarse con Gemini AI: {error_msg}"
                }
            )

        master_prompt = (
            ai_result.get("prompt") or
            ai_result.get("master_prompt") or
            (ai_result.get("data", {}).get("master_prompt") if isinstance(ai_result.get("data"), dict) else "") or
            ""
        )
        negative_prompt = (
            ai_result.get("negative_prompt") or
            (ai_result.get("data", {}).get("negative_prompt") if isinstance(ai_result.get("data"), dict) else "") or
            ""
        )
        view_prompts = (
            ai_result.get("view_prompts") or
            (ai_result.get("data", {}).get("view_prompts") if isinstance(ai_result.get("data"), dict) else None)
        )
        model_used = ai_result.get("model_used", "gemini-2.5-pro")
        analysis_data = (
            ai_result.get("analysis") or
            ai_result.get("furniture_analysis") or
            (ai_result.get("data", {}).get("analysis") if isinstance(ai_result.get("data"), dict) else None)
        )
        final_environment = (
            environment_data or
            ai_result.get("environment") or
            ai_result.get("random_environment")
        )
    else:
        master_prompt = str(ai_result)
        negative_prompt = ""
        view_prompts = None
        analysis_data = None
        model_used = "gemini-2.5-pro"
        final_environment = environment_data

    # 7. Build Standardized JSON Payload per PROJECT.md
    response_payload = {
        "success": True,
        "mode": mode,
        "model_used": model_used,
        "prompt": master_prompt,
        "negative_prompt": negative_prompt,
        "view_prompts": view_prompts,
        "environment": final_environment,
        "analysis": analysis_data
    }

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response_payload



# ---------------------------------------------------------------------------
# Direct Execution Support (Dynamic Port Binding & Host 0.0.0.0)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    logger.info(f"Iniciando servidor Uvicorn en http://{host}:{port} (Render dynamic port ready)")
    uvicorn.run("app:app", host=host, port=port)
