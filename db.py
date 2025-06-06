# db.py  – módulo de acceso centralizado a SQLite
import sqlite3
from threading import Lock

DB_FILE = "recursos.db"
db_lock = Lock()          # evita carreras entre hilos del mismo worker

def inicializar_bd() -> None:
    """Crea la tabla si no existe."""
    with db_lock, sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS recursos (
                semestre TEXT PRIMARY KEY,
                salones_disponibles INTEGER,
                laboratorios_disponibles INTEGER
            )
        """)
        conn.commit()

def obtener_disponibilidad(semestre: str,
                           salones_orig: int,
                           labs_orig: int) -> dict:
    """Devuelve {'salones': int, 'laboratorios': int} para el semestre."""
    with db_lock, sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT salones_disponibles, laboratorios_disponibles "
                  "FROM recursos WHERE semestre = ?", (semestre,))
        row = c.fetchone()
        if row:
            return {"salones": row[0], "laboratorios": row[1]}
        # semestre nuevo → insertar valores originales
        c.execute("INSERT INTO recursos VALUES (?, ?, ?)",
                  (semestre, salones_orig, labs_orig))
        conn.commit()
        return {"salones": salones_orig, "laboratorios": labs_orig}

def actualizar_disponibilidad(semestre: str, nuevos: dict) -> None:
    """Guarda los nuevos contadores en la base."""
    with db_lock, sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE recursos
               SET salones_disponibles = ?, laboratorios_disponibles = ?
             WHERE semestre = ?
        """, (nuevos["salones"], nuevos["laboratorios"], semestre))
        conn.commit()
