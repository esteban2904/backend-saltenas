from fastapi import FastAPI, HTTPException
from supabase import create_client, Client
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from datetime import datetime

# Cargar variables de entorno (tus claves secretas)
load_dotenv()

# Configuración de Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# Verificamos que las claves existan
if not url or not key:
    raise ValueError("¡Error! No encontré SUPABASE_URL o SUPABASE_KEY en el archivo .env")

# Conectamos con la base de datos
supabase: Client = create_client(url, key)

app = FastAPI()

# Modelo de datos (qué esperamos recibir)
class MovimientoInventario(BaseModel):
    producto_nombre: str 
    cantidad: int
    tipo: str

@app.get("/")
def read_root():
    return {"mensaje": "API de Salteñas funcionando 🥟"}

@app.post("/registrar-movimiento")
def registrar_movimiento(movimiento: MovimientoInventario):
    # 1. Buscar producto por nombre
    response = supabase.table("productos").select("*").eq("nombre", movimiento.producto_nombre).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail=f"Producto '{movimiento.producto_nombre}' no encontrado.")
    
    producto = response.data[0]
    nuevo_stock = producto['stock_actual'] + movimiento.cantidad

    # 2. Guardar en el historial
    data_historial = {
        "producto_id": producto['id'],
        "cantidad": movimiento.cantidad,
        "tipo": movimiento.tipo,
        "created_at": datetime.now().isoformat()
    }
    supabase.table("movimientos").insert(data_historial).execute()

    # 3. Actualizar el stock total
    supabase.table("productos").update({"stock_actual": nuevo_stock}).eq("id", producto['id']).execute()

    return {
        "mensaje": "Inventario actualizado", 
        "producto": movimiento.producto_nombre, 
        "nuevo_stock": nuevo_stock
    }