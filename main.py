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

# --- MODELOS DE DATOS ---
class MovimientoInventario(BaseModel):
    producto_nombre: str 
    cantidad: int
    tipo: str # "PRODUCCION", "VENTA"

class NuevoProducto(BaseModel):
    nombre: str
    stock_minimo: int
    stock_inicial: int = 0

class EditarProducto(BaseModel):
    stock_minimo: int

# --- ENDPOINTS PÚBLICOS (Para el Escáner y App) ---

@app.get("/")
def read_root():
    return {"mensaje": "Sistema ERP Salteñas v2.0 Activo 🚀"}

@app.get("/inventario")
def ver_inventario():
    # Ordenamos por ID para que la lista no salte visualmente
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

# --- ENDPOINTS DE SUPERVISOR (Gestión) ---

@app.post("/admin/productos")
def crear_producto(nuevo: NuevoProducto):
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

@app.delete("/admin/productos/{id}")
def borrar_producto(id: int):
    # Primero borramos movimientos para mantener integridad de base de datos
    supabase.table("movimientos").delete().eq("producto_id", id).execute()
    supabase.table("productos").delete().eq("id", id).execute()
    return {"mensaje": "Producto eliminado"}

@app.put("/admin/productos/{id}")
def editar_producto(id: int, edicion: EditarProducto):
    supabase.table("productos").update({"stock_minimo": edicion.stock_minimo}).eq("id", id).execute()
    return {"mensaje": "Configuración actualizada"}

# --- REPORTE AVANZADO (Para Gráfica Apilada Doble) ---
@app.get("/admin/reportes/mensual")
def reporte_mensual():
    # 1. Traemos movimientos y el nombre del producto asociado
    response = supabase.table("movimientos").select("*, productos(nombre)").execute()
    movimientos = response.data

    # 2. Estructura: {'2023-11': {'Entrada: Carne': 50, 'Salida: Carne': 20}}
    reporte = defaultdict(lambda: defaultdict(int))

    for mov in movimientos:
        fecha = mov['created_at'][:7] # "YYYY-MM"
        if not mov['productos']: continue # Por si se borró el producto
        
        nombre_producto = mov['productos']['nombre']
        cantidad = mov['cantidad']
        
        if cantidad > 0:
            # Es PRODUCCIÓN
            clave = f"Entrada: {nombre_producto}"
            reporte[fecha][clave] += cantidad
        else:
            # Es VENTA (Guardamos positivo para la gráfica)
            clave = f"Salida: {nombre_producto}"
            reporte[fecha][clave] += abs(cantidad)

    return reporte