import sqlite3
from filelock import FileLock

DB_FILE  = "recursos.db"
DB_LOCK  = "recursos.db.lock"

# ------------------------------------------------------------------ #
def _conn():
    conn = sqlite3.connect(DB_FILE, timeout=30, isolation_level=None)  # autocommit
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def inicializar_bd():
    # Adquirir candado solo el tiempo mínimo
    with FileLock(DB_LOCK):
        with _conn() as conn:
            conn.execute("""
              CREATE TABLE IF NOT EXISTS recursos (
                semestre TEXT PRIMARY KEY,
                salones_disponibles     INTEGER,
                laboratorios_disponibles INTEGER
              )
            """)

# ------------------------------------------------------------------ #
def obtener_y_bloquear(semestre: str, sal_orig: int, lab_orig: int):
    """
    Devuelve (lock, conn, dict_disponibles) con el candado YA tomado.
    El llamador debe liberar con guardar_y_desbloquear() o lock.release().
    """
    lock = FileLock(DB_LOCK)
    lock.acquire()                  # bloqueo inter-proceso (bloqueante)

    conn = _conn()                  # ya en modo autocommit
    cur  = conn.execute(
        "SELECT salones_disponibles, laboratorios_disponibles "
        "FROM recursos WHERE semestre=?",
        (semestre,)
    )
    row = cur.fetchone()

    if row is None:
        # Semestre nuevo: insertar y tomar valores originales
        conn.execute(
            "INSERT INTO recursos VALUES (?, ?, ?)",
            (semestre, sal_orig, lab_orig)
        )
        sal, lab = sal_orig, lab_orig
    else:
        sal, lab = row

    return lock, conn, {"salones": sal, "laboratorios": lab}

def guardar_y_desbloquear(lock, conn, semestre: str, nuevos: dict):
    """
    Actualiza los contadores y libera el candado.
    ¡Llamar siempre dentro de un bloque try/finally en el caller!
    """
    try:
        conn.execute(
            "UPDATE recursos "
            "SET salones_disponibles=?, laboratorios_disponibles=? "
            "WHERE semestre=?",
            (nuevos["salones"], nuevos["laboratorios"], semestre)
        )
        conn.commit()               # explícito: asegura flush en WAL
    finally:
        conn.close()
        if lock:                    # evita dejar el candado tomado
            lock.release()
