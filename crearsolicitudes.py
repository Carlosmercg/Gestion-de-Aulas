import random
import json

# Definir las facultades y los programas
facultades = [
    "Facultad de Ciencias Sociales",
    "Facultad de Ciencias Naturales",
    "Facultad de Ingeniería",
    "Facultad de Medicina",
    "Facultad de Derecho",
    "Facultad de Artes",
    "Facultad de Educación",
    "Facultad de Ciencias Económicas",
    "Facultad de Arquitectura",
    "Facultad de Tecnología"
]

programas_por_facultad = {
    "Facultad de Ciencias Sociales": ["Psicología", "Sociología", "Trabajo Social", "Antropología", "Comunicación"],
    "Facultad de Ciencias Naturales": ["Biología", "Química", "Física", "Geología", "Ciencias Ambientales"],
    "Facultad de Ingeniería": ["Ingeniería Civil", "Ingeniería Electrónica", "Ingeniería de Sistemas", "Ingeniería Mecánica", "Ingeniería Industrial"],
    "Facultad de Medicina": ["Medicina General", "Enfermería", "Odontología", "Farmacia", "Terapia Física"],
    "Facultad de Derecho": ["Derecho Penal", "Derecho Civil", "Derecho Internacional", "Derecho Laboral", "Derecho Constitucional"],
    "Facultad de Artes": ["Bellas Artes", "Música", "Teatro", "Danza", "Diseño Gráfico"],
    "Facultad de Educación": ["Educación Primaria", "Educación Secundaria", "Educación Especial", "Psicopedagogía", "Administración Educativa"],
    "Facultad de Ciencias Económicas": ["Administración de Empresas", "Contabilidad", "Economía", "Mercadotecnia", "Finanzas"],
    "Facultad de Arquitectura": ["Arquitectura", "Urbanismo", "Diseño de Interiores", "Paisajismo", "Restauración de Patrimonio"],
    "Facultad de Tecnología": ["Desarrollo de Software", "Redes y Telecomunicaciones", "Ciberseguridad", "Inteligencia Artificial", "Big Data"]
}

# Función para generar valores aleatorios de salones y laboratorios
def generar_salones_y_laboratorios():
    # Generar una cantidad aleatoria de laboratorios entre 2 y 4
    laboratorios = random.randint(2, 4)
    # Generar la cantidad de salones para que la suma sea entre 7 y 10
    salones = random.randint(7 - laboratorios, 10 - laboratorios)
    return salones, laboratorios

# Generar el JSON
semestre = "2025-1"
facultades_info = []

for facultad in facultades:
    facultad_info = {"nombre": facultad, "programas": []}
    for programa in programas_por_facultad[facultad]:
        salones, laboratorios = generar_salones_y_laboratorios()
        programa_info = {
            "nombre": programa,
            "salones": salones,
            "laboratorios": laboratorios
        }
        facultad_info["programas"].append(programa_info)
    facultades_info.append(facultad_info)

# Crear el objeto final con el semestre y las facultades
resultado = {
    "semestre": semestre,
    "facultades": facultades_info
}

# Guardar el JSON en un archivo llamado solicitudes.json sin codificación Unicode
with open("solicitudes.json", "w", encoding="utf-8") as archivo:
    json.dump(resultado, archivo, indent=2, ensure_ascii=False)

print("El archivo solicitudes.json ha sido generado.")
