from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict
from pathlib import Path 

# --- CONFIGURACIÓN DE CARGA DE .ENV ---
# Esto busca el archivo .env explícitamente en la carpeta actual
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

print("--- DEBUG DIAGNÓSTICO ---")
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
print(f"URL detectada: {url}")
print(f"KEY detectada: {'SÍ (Oculta)' if key else 'NO ENCONTRADA ❌'}")
print("-------------------------")

if not url or not key:
    raise ValueError("¡Error CRÍTICO! No se encontraron SUPABASE_URL o SUPABASE_KEY en el archivo .env")

supabase: Client = create_client(url, key)

app = FastAPI()

# Configuración de CORS (Permitir que React hable con Python)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS ACTUALIZADOS ---
class MovimientoInventario(BaseModel):
    producto_nombre: str 
    cantidad: int     # Ahora esto representa UNIDADES sueltas
    tipo: str 

class NuevoProducto(BaseModel):
    nombre: str
    stock_minimo: int
    stock_inicial: int = 0
    # NUEVOS CAMPOS:
    unidades_por_bandeja: int 
    unidades_por_bolsa: int

class EditarProducto(BaseModel):
    stock_minimo: int
    unidades_por_bandeja: int
    unidades_por_bolsa: int

# --- ENDPOINTS ---

@app.get("/")
def read_root():
    return {"mensaje": "ERP v3.0 (Unidades Reales)"}

@app.get("/inventario")
def ver_inventario():
    response = supabase.table("productos").select("*").order('id').execute()
    return response.data

@app.post("/registrar-movimiento")
def registrar_movimiento(movimiento: MovimientoInventario):
    response = supabase.table("productos").select("*").eq("nombre", movimiento.producto_nombre).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail=f"Producto '{movimiento.producto_nombre}' no encontrado.")
    
    producto = response.data[0]
    
    # La cantidad ya viene calculada desde el frontend (ej: +30 o -10)
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

# --- GESTIÓN DE PRODUCTOS ---

@app.post("/admin/productos")
def crear_producto(nuevo: NuevoProducto):
    existe = supabase.table("productos").select("*").eq("nombre", nuevo.nombre).execute()
    if existe.data:
        raise HTTPException(status_code=400, detail="Este producto ya existe")

    datos = {
        "nombre": nuevo.nombre,
        "stock_minimo": nuevo.stock_minimo,
        "stock_actual": nuevo.stock_inicial,
        "unidades_por_bandeja": nuevo.unidades_por_bandeja,
        "unidades_por_bolsa": nuevo.unidades_por_bolsa
    }
    supabase.table("productos").insert(datos).execute()
    return {"mensaje": "Producto creado"}

@app.delete("/admin/productos/{id}")
def borrar_producto(id: int):
    supabase.table("movimientos").delete().eq("producto_id", id).execute()
    supabase.table("productos").delete().eq("id", id).execute()
    return {"mensaje": "Eliminado"}

@app.put("/admin/productos/{id}")
def editar_producto(id: int, edicion: EditarProducto):
    supabase.table("productos").update({
        "stock_minimo": edicion.stock_minimo,
        "unidades_por_bandeja": edicion.unidades_por_bandeja,
        "unidades_por_bolsa": edicion.unidades_por_bolsa
    }).eq("id", id).execute()
    return {"mensaje": "Actualizado"}

@app.get("/admin/reportes/mensual")
def reporte_mensual():
    response = supabase.table("movimientos").select("*, productos(nombre)").execute()
    movimientos = response.data
    reporte = defaultdict(lambda: defaultdict(int))

    for mov in movimientos:
        fecha = mov['created_at'][:7]
        if not mov['productos']: continue
        
        nombre = mov['productos']['nombre']
        cantidad = mov['cantidad']
        
        if cantidad > 0:
            reporte[fecha][f"Entrada: {nombre}"] += cantidad
        else:
            reporte[fecha][f"Salida: {nombre}"] += abs(cantidad)

    return reporte