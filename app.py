import os
import io
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Form, status, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.v4")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Generador Prompts V4")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>V4 Ready</h1>")

@app.get("/health")
async def healthcheck():
    return {"status": "ok"}

@app.post("/api/generate")
async def generate_prompt(
    image: UploadFile = File(...),
    vista: str = Form(...),
    tela: str = Form(""),
    madera: str = Form(""),
    ambiente: str = Form("")
):
    try:
        image_bytes = await image.read()
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Optimize image for Gemini
        max_size = 1600
        if max(pil_image.size) > max_size:
            pil_image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        opt_bytes_io = io.BytesIO()
        pil_image.save(opt_bytes_io, format="JPEG", quality=85)
        opt_bytes = opt_bytes_io.getvalue()
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return JSONResponse(status_code=500, content={"error": "Falta GEMINI_API_KEY en las variables de entorno"})
            
        client = genai.Client(api_key=api_key)
        
        # Sistema de instrucciones estrictas de V4
        sys_instructions = (
            "Actúa como un experto en diseño industrial, catalogación e-commerce y director de fotografía de producto. "
            "Tu tarea es analizar detalladamente la imagen de referencia del mueble y redactar un prompt visual ultra-técnico "
            "para recrear exactamente la misma pieza.\n\n"
            "Reglas estrictas para estructurar el prompt de salida:\n"
            "1. Configuraciones Base: Siempre debes iniciar el prompt con: 'Tamaño de lienzo: 2080x2080 px', 'Fondo: Blanco sólido (#FFFFFF)' y 'Posición: Perfectamente centrado'.\n"
            "2. Fidelidad Estructural: Describe la geometría, proporciones y detalles de ensamble del mueble de la foto con precisión técnica.\n"
            "3. Vistas y Estilos: Aplica estrictamente la vista solicitada. Si es dibujo técnico, especifica ilustraciones isométricas puramente lineales sin sombras/color. Si es toma superior, especifica inclinación del 25%.\n"
            "4. Materiales: Integra las texturas indicadas con precisión fotorrealista.\n"
            "5. Exclusiones: Indica claramente qué NO generar.\n"
            "Salida requerida: Devuelve ÚNICAMENTE el prompt final estructurado, optimizado y listo para ser procesado por un modelo generador de imágenes. No incluyas saludos, confirmaciones ni análisis."
        )
        
        user_prompt = f"MODIFICADORES APLICADOS:\nVista requerida: {vista}\n"
        if tela: user_prompt += f"Tela/Material: {tela}\n"
        if madera: user_prompt += f"Madera/Acabado: {madera}\n"
        if ambiente: user_prompt += f"Ambiente: {ambiente}\n"
        
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=[
                types.Part.from_bytes(data=opt_bytes, mime_type='image/jpeg'),
                user_prompt
            ],
            config=types.GenerateContentConfig(
                system_instruction=sys_instructions,
                temperature=0.2
            )
        )
        
        return {"success": True, "prompt": response.text}
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
