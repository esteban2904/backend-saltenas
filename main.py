from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # <--- ¡NUEVO IMPORT!
from supabase import create_client, Client
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Error config ENV")

supabase: Client = create_client(url, key)

app = FastAPI()

# --- AQUÍ ESTÁ EL CAMBIO IMPORTANTE ---
# Esto permite que tu App Web (y cualquiera) pueda hablar con este servidor
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # "*" significa "Todos son bienvenidos"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --------------------------------------

class MovimientoInventario(BaseModel):
    producto_nombre: str 
    cantidad: int
    tipo: str

@app.get("/")
def read_root():
    return {"mensaje": "API de Salteñas funcionando 🥟"}

# Endpoint para ver inventario (GET)
@app.get("/inventario")
def ver_inventario():
    response = supabase.table("productos").select("*").execute()
    return response.data

@app.post("/registrar-movimiento")
def registrar_movimiento(movimiento: MovimientoInventario):
    response = supabase.table("productos").select("*").eq("nombre", movimiento.producto_nombre).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail=f"Producto '{movimiento.producto_nombre}' no encontrado.")
    
    producto = response.data[0]
    nuevo_stock = producto['stock_actual'] + movimiento.cantidad

    data_historial = {
        "producto_id": producto['id'],
        "cantidad": movimiento.cantidad,
        "tipo": movimiento.tipo,
        "created_at": datetime.now().isoformat()
    }
    supabase.table("movimientos").insert(data_historial).execute()
    supabase.table("productos").update({"stock_actual": nuevo_stock}).eq("id", producto['id']).execute()

    return {"mensaje": "Ok", "nuevo_stock": nuevo_stock}