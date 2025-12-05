from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict

load_dotenv()

url: str = os.environ.get("https://kplnksqjolmbkuxdvtxh.supabase.co")
key: str = os.environ.get("sb_secret_zxZEBWpu6PBnoKcFBXOFLQ_SvjMw36y")

if not url or not key:
    raise ValueError("Error config ENV")

supabase: Client = create_client(url, key)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DATOS ---
class MovimientoInventario(BaseModel):
    producto_nombre: str 
    cantidad: int
    tipo: str # "PRODUCCION", "VENTA", "AJUSTE_MANUAL"

class NuevoProducto(BaseModel):
    nombre: str
    stock_minimo: int
    stock_inicial: int = 0

class EditarProducto(BaseModel):
    stock_minimo: int

# --- ENDPOINTS BÁSICOS ---

@app.get("/")
def read_root():
    return {"mensaje": "Sistema ERP Salteñas v2.0 Activo 🚀"}

@app.get("/inventario")
def ver_inventario():
    # Ordenamos por id para que no salten al editar
    response = supabase.table("productos").select("*").order('id').execute()
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

# --- NUEVOS PODERES DE SUPERVISOR ---

# 1. Crear un nuevo sabor (Producto)
@app.post("/admin/productos")
def crear_producto(nuevo: NuevoProducto):
    # Verificamos si ya existe
    existe = supabase.table("productos").select("*").eq("nombre", nuevo.nombre).execute()
    if existe.data:
        raise HTTPException(status_code=400, detail="Este producto ya existe")

    datos = {
        "nombre": nuevo.nombre,
        "stock_minimo": nuevo.stock_minimo,
        "stock_actual": nuevo.stock_inicial
    }
    supabase.table("productos").insert(datos).execute()
    return {"mensaje": "Producto creado exitosamente"}

# 2. Eliminar un sabor (Cuidado: Esto es destructivo)
@app.delete("/admin/productos/{id}")
def borrar_producto(id: int):
    # Primero borramos movimientos para no romper la base de datos (Integridad referencial)
    supabase.table("movimientos").delete().eq("producto_id", id).execute()
    # Luego borramos el producto
    supabase.table("productos").delete().eq("id", id).execute()
    return {"mensaje": "Producto eliminado"}

# 3. Editar el mínimo de alerta
@app.put("/admin/productos/{id}")
def editar_producto(id: int, edicion: EditarProducto):
    supabase.table("productos").update({"stock_minimo": edicion.stock_minimo}).eq("id", id).execute()
    return {"mensaje": "Configuración actualizada"}

# 4. DASHBOARD: Reporte Mensual
@app.get("/admin/reportes/mensual")
def reporte_mensual():
    # Traemos todos los movimientos (En un sistema real filtraríamos por fechas aquí mismo)
    response = supabase.table("movimientos").select("*, productos(nombre)").execute()
    movimientos = response.data

    # Procesamos los datos con Python
    reporte = defaultdict(lambda: {"entradas": 0, "salidas": 0, "neto": 0})

    for mov in movimientos:
        # Extraemos el mes (ej: "2023-12")
        fecha = mov['created_at'][:7] 
        cantidad = mov['cantidad']
        
        if cantidad > 0:
            reporte[fecha]["entradas"] += cantidad
        else:
            reporte[fecha]["salidas"] += abs(cantidad) # Ponemos positivo para contar volumen
        
        reporte[fecha]["neto"] += cantidad

    return reporte