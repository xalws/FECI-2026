"""Siembra un grupo ficticio de 30 alumnos con actividad variada en una clase del maestro José Miguel (Circuitos Eléctricos).

Sirve para ver cómo se ven las gráficas, el boletín y las estadísticas del maestro con un grupo de tamaño real.

Uso, desde la carpeta del proyecto y con el entorno virtual activo:
    python scripts/sembrar_grupo_circuitos.py            # crea (o rehace) el grupo
    python scripts/sembrar_grupo_circuitos.py --borrar   # lo elimina por completo

Todas las cuentas usan el dominio `@alumnos.example.com`, así que --borrar solo toca lo que este script creó: no toca
otras cuentas, otras clases ni la clase «Robotica 1». Las credenciales se guardan en `cuentas_alumnos_circuitos.txt`
(archivo ignorado por git). Los datos son inventados.
"""
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, insert, select  # noqa: E402

from core import clases  # noqa: E402
from core.db import get_session, init_db  # noqa: E402
from core.passwords import hash_password  # noqa: E402
from models.schema import (Actividad, Asignacion, Aviso, Clase, Conversacion, Inscripcion, IntentoEjercicio, Materia,  # noqa: E402
                           Mensaje, PreguntaSinRespuesta, Quiz, RespuestaQuiz, Tarea, Tarjeta, Tema, Unidad, Usuario)

DOMINIO = "@alumnos.example.com"
MAESTRO_EMAIL = "jose@gmail.com"
MATERIA = "Circuitos Eléctricos"
NOMBRE_CLASE = "Circuitos Eléctricos · Grupo 3B"
PASSWORD = "Circuitos-2026"
SALIDA = Path(__file__).resolve().parent.parent / "cuentas_alumnos_circuitos.txt"
ahora = datetime.now(timezone.utc)

NOMBRES = ["Valeria", "Santiago", "Camila", "Mateo", "Ximena", "Diego", "Renata", "Emiliano", "Regina", "Sebastián",
           "Fernanda", "Leonardo", "Daniela", "Alejandro", "Paola", "Iván", "Mariana", "Ángel", "Andrea", "Jesús",
           "Karla", "Luis Fernando", "Natalia", "Rodrigo", "Itzel", "Erick", "Dulce", "Brayan", "Montserrat", "Adrián"]
APELLIDOS = ["Hernández", "García", "Martínez", "López", "González", "Rodríguez", "Pérez", "Sánchez", "Ramírez", "Flores",
             "Gómez", "Díaz", "Reyes", "Morales", "Cruz", "Ortiz", "Gutiérrez", "Chávez", "Ramos", "Mendoza", "Aguilar",
             "Vargas", "Castillo", "Jiménez", "Moreno", "Romero", "Herrera", "Medina", "Luna", "Fuentes"]

# (tema, pregunta, opciones con la correcta primero, explicación, dificultad 1-4)
BANCO = [
    ("Aislantes y conductores", "¿Cuál de estos materiales es un buen conductor eléctrico?",
     ["Cobre", "Vidrio", "Hule", "Madera seca"], "Los metales como el cobre tienen electrones libres que se mueven con facilidad.", 1),
    ("Aislantes y conductores", "¿Qué material se usa normalmente como aislante en el recubrimiento de los cables?",
     ["PVC (plástico)", "Aluminio", "Cobre", "Plata"], "El plástico no conduce la corriente y protege al usuario.", 1),
    ("Aislantes y conductores", "¿Qué le pasa a la resistividad de un conductor metálico cuando aumenta su temperatura?",
     ["Aumenta", "Disminuye", "Se vuelve cero", "No cambia"], "En los metales, más temperatura significa más choques de electrones y más resistividad.", 3),
    ("Sistemas de unidades en circuitos eléctricos", "¿En qué unidad se mide la resistencia eléctrica en el SI?",
     ["Ohm (Ω)", "Volt (V)", "Ampere (A)", "Watt (W)"], "La resistencia se mide en ohms.", 1),
    ("Sistemas de unidades en circuitos eléctricos", "¿Cuántos miliamperes son 0.25 A?",
     ["250 mA", "25 mA", "2.5 mA", "2 500 mA"], "1 A = 1 000 mA, así que 0.25 A = 250 mA.", 2),
    ("Sistemas de unidades en circuitos eléctricos", "Un resistor de 4.7 kΩ equivale a:",
     ["4 700 Ω", "47 Ω", "470 Ω", "47 000 Ω"], "El prefijo k (kilo) multiplica por 1 000.", 2),
    ("Circuitos Resistivos (serie, paralelo y mixtos)", "Dos resistores de 100 Ω en serie tienen una resistencia equivalente de:",
     ["200 Ω", "50 Ω", "100 Ω", "10 000 Ω"], "En serie las resistencias se suman.", 1),
    ("Circuitos Resistivos (serie, paralelo y mixtos)", "Dos resistores de 100 Ω en paralelo tienen una resistencia equivalente de:",
     ["50 Ω", "200 Ω", "100 Ω", "25 Ω"], "Con dos resistores iguales en paralelo, la equivalente es la mitad.", 2),
    ("Circuitos Resistivos (serie, paralelo y mixtos)", "Tres resistores de 30 Ω en paralelo equivalen a:",
     ["10 Ω", "90 Ω", "30 Ω", "3 Ω"], "Con n resistores iguales en paralelo, R/n = 30/3 = 10 Ω.", 3),
    ("Circuitos Resistivos (serie, paralelo y mixtos)",
     "Un resistor de 10 Ω está en serie con dos resistores de 20 Ω en paralelo. La resistencia total es:",
     ["20 Ω", "50 Ω", "40 Ω", "30 Ω"], "Los dos de 20 Ω en paralelo dan 10 Ω; en serie con 10 Ω suman 20 Ω.", 3),
    ("Leyes básicas de circuitos eléctricos", "Según la ley de Ohm, ¿qué corriente circula por un resistor de 10 Ω con 20 V?",
     ["2 A", "0.5 A", "200 A", "10 A"], "I = V / R = 20 / 10 = 2 A.", 2),
    ("Leyes básicas de circuitos eléctricos", "¿Qué potencia disipa un resistor con 12 V entre sus terminales y 2 A?",
     ["24 W", "6 W", "14 W", "0.17 W"], "P = V · I = 12 · 2 = 24 W.", 2),
    ("Leyes básicas de circuitos eléctricos", "La ley de voltajes de Kirchhoff establece que:",
     ["La suma algebraica de los voltajes en una malla cerrada es cero", "La suma de las corrientes en un nodo es 100",
      "El voltaje es igual a la resistencia entre la corriente", "La potencia de cada resistor es siempre cero"],
     "En una trayectoria cerrada, las subidas y caídas de voltaje se compensan.", 3),
    ("Leyes básicas de circuitos eléctricos", "La ley de corrientes de Kirchhoff dice que en un nodo:",
     ["La suma de las corrientes que entran es igual a la de las que salen", "Todas las corrientes son iguales",
      "El voltaje se divide entre las ramas", "La corriente se pierde en el nodo"], "La carga no se acumula en un nodo.", 2),
    ("Divisor de voltaje y divisor de corriente", "En un divisor de voltaje con R1 = 1 kΩ y R2 = 3 kΩ alimentado con 12 V, ¿cuánto cae en R2?",
     ["9 V", "3 V", "4 V", "6 V"], "V2 = 12 · 3 / (1 + 3) = 9 V.", 3),
    ("Divisor de voltaje y divisor de corriente", "En un divisor de corriente con dos resistores iguales, la corriente de entrada se reparte:",
     ["En partes iguales", "Toda por uno", "El doble por uno", "Nada por ninguno"], "Con resistencias iguales, cada rama recibe la mitad.", 2),
    ("Inductancia y capacitancia", "¿En qué unidad se mide la capacitancia?",
     ["Farad (F)", "Henry (H)", "Ohm (Ω)", "Weber (Wb)"], "La capacitancia se mide en farads.", 1),
    ("Inductancia y capacitancia", "Un capacitor ya cargado, en corriente directa y estado estable, se comporta como:",
     ["Circuito abierto", "Cortocircuito", "Resistor de 1 Ω", "Fuente de voltaje"], "Deja de circular corriente por él.", 3),
    ("Inductancia y capacitancia", "Un inductor ideal en corriente directa y estado estable se comporta como:",
     ["Cortocircuito", "Circuito abierto", "Resistor de 1 MΩ", "Capacitor"], "Sin variación de corriente no hay voltaje inducido.", 3),
    ("Mallas y nodos", "El análisis de mallas se basa principalmente en la ley de:",
     ["Voltajes de Kirchhoff", "Corrientes de Kirchhoff", "Coulomb", "Faraday"], "Se escribe una ecuación de voltajes por malla.", 3),
    ("Mallas y nodos", "El análisis nodal se basa principalmente en la ley de:",
     ["Corrientes de Kirchhoff", "Voltajes de Kirchhoff", "Lenz", "Joule"], "Se escribe una ecuación de corrientes por nodo.", 3),
    ("Teoremas para análisis de circuitos", "El equivalente de Thévenin de un circuito consiste en:",
     ["Una fuente de voltaje en serie con una resistencia", "Una fuente de corriente en paralelo con un capacitor",
      "Un solo capacitor", "Dos fuentes de corriente"], "Reduce la red vista desde dos terminales a Vth y Rth.", 4),
    ("Teoremas para análisis de circuitos", "El teorema de superposición se aplica a circuitos:",
     ["Lineales", "Solo no lineales", "Solo con diodos", "Sin fuentes"], "Solo vale cuando las ecuaciones son lineales.", 4),
    ("Teoremas para análisis de circuitos", "Para la máxima transferencia de potencia, la resistencia de carga debe ser igual a:",
     ["La resistencia de Thévenin", "Cero", "Infinito", "El doble de la de Thévenin"], "RL = Rth maximiza la potencia en la carga.", 4),
]
TEMAS_PESO = {"Aislantes y conductores": 3, "Sistemas de unidades en circuitos eléctricos": 3,
              "Circuitos Resistivos (serie, paralelo y mixtos)": 5, "Leyes básicas de circuitos eléctricos": 5,
              "Divisor de voltaje y divisor de corriente": 3, "Inductancia y capacitancia": 2, "Mallas y nodos": 1.5,
              "Teoremas para análisis de circuitos": 1}
ENUNCIADOS = ["Calcula la resistencia equivalente de un circuito con tres resistores de 120 Ω, 220 Ω y 330 Ω en serie.",
              "Una fuente de 9 V alimenta dos resistores en serie de 1 kΩ y 2 kΩ. Calcula la corriente y la caída en cada uno.",
              "Obtén la corriente total y la potencia entregada por una fuente de 24 V a dos resistores de 48 Ω en paralelo."]
DUDAS = [("¿Cuál es la diferencia entre serie y paralelo?", "En serie hay un solo camino y la corriente es la misma; en paralelo hay varios y el voltaje es el mismo."),
         ("¿Cómo aplico la ley de Ohm?", "Despeja la incógnita de V = I · R: I = V / R o R = V / I."),
         ("¿Cómo sé si un resistor está en serie?", "Si la misma corriente pasa por los dos sin dividirse en ningún nodo."),
         ("¿Qué es una malla?", "Una trayectoria cerrada del circuito que no contiene otras trayectorias dentro.")]
SIN_RESPUESTA = ["¿Qué es un transformador trifásico?", "¿Cómo funciona un diodo Zener?", "¿Qué es el factor de potencia en motores?"]


def borrar() -> None:
    with get_session() as s:
        uids = list(s.scalars(select(Usuario.id).where(Usuario.email.like(f"%{DOMINIO}"))))
        cids = list(s.scalars(select(Clase.id).where(Clase.nombre == NOMBRE_CLASE)))
        if cids:
            s.execute(delete(Tarea).where(Tarea.clase_id.in_(cids)))
            s.execute(delete(Aviso).where(Aviso.clase_id.in_(cids)))
            s.execute(delete(Inscripcion).where(Inscripcion.clase_id.in_(cids)))
            s.execute(delete(Clase).where(Clase.id.in_(cids)))
        if uids:
            convs = list(s.scalars(select(Conversacion.id).where(Conversacion.alumno_id.in_(uids))))
            quizzes = list(s.scalars(select(Quiz.id).where(Quiz.conversacion_id.in_(convs)))) if convs else []
            if quizzes:
                s.execute(delete(Tarjeta).where(Tarjeta.quiz_id.in_(quizzes)))
                s.execute(delete(RespuestaQuiz).where(RespuestaQuiz.quiz_id.in_(quizzes)))
                s.execute(delete(Quiz).where(Quiz.id.in_(quizzes)))
            if convs:
                s.execute(delete(Mensaje).where(Mensaje.conversacion_id.in_(convs)))
                s.execute(delete(Conversacion).where(Conversacion.id.in_(convs)))
            for modelo, col in ((Actividad, Actividad.usuario_id), (IntentoEjercicio, IntentoEjercicio.alumno_id),
                                (PreguntaSinRespuesta, PreguntaSinRespuesta.alumno_id)):
                s.execute(delete(modelo).where(col.in_(uids)))
            s.execute(delete(Inscripcion).where(Inscripcion.alumno_id.in_(uids)))
            s.execute(delete(Usuario).where(Usuario.id.in_(uids)))
    print("Grupo de Circuitos eliminado.")


def _hora(rng: random.Random, dia: int) -> datetime:
    return (ahora - timedelta(days=dia)).replace(hour=rng.randint(14, 23), minute=rng.randint(0, 59), second=rng.randint(0, 59))


def perfiles(rng: random.Random) -> list[dict]:
    """30 perfiles: unos destacan, otros van regular, otros batallan, dos dejaron de entrar y uno nunca ha entrado."""
    p = []
    p += [{"nivel": "alto", "habilidad": rng.uniform(0.82, 0.95), "n": rng.randint(28, 44), "activo": True} for _ in range(8)]
    p += [{"nivel": "medio", "habilidad": rng.uniform(0.58, 0.78), "n": rng.randint(14, 28), "activo": True} for _ in range(14)]
    p += [{"nivel": "bajo", "habilidad": rng.uniform(0.28, 0.48), "n": rng.randint(8, 18), "activo": True} for _ in range(5)]
    p += [{"nivel": "medio", "habilidad": rng.uniform(0.5, 0.7), "n": rng.randint(6, 10), "activo": False} for _ in range(2)]
    p += [{"nivel": "nunca", "habilidad": 0.5, "n": 0, "activo": False}]
    rng.shuffle(p)
    return p


def crear() -> None:
    init_db()
    borrar()
    rng = random.Random(2026)
    with get_session() as s:
        maestro = s.scalar(select(Usuario).where(Usuario.email == MAESTRO_EMAIL, Usuario.rol == "maestro"))
        if maestro is None:
            raise SystemExit(f"No existe el maestro {MAESTRO_EMAIL}.")
        materia = s.scalar(select(Materia).where(Materia.nombre == MATERIA))
        if materia is None or not s.scalar(select(Asignacion.id).where(Asignacion.maestro_id == maestro.id,
                                                                     Asignacion.materia_id == materia.id)):
            raise SystemExit(f"{maestro.nombre} no tiene asignada la materia {MATERIA}.")
        temas = {t.nombre: t.id for t in s.scalars(select(Tema).join(Unidad, Unidad.id == Tema.unidad_id)
                                                   .where(Unidad.materia_id == materia.id))}
        faltan = {b[0] for b in BANCO} - set(temas)
        if faltan:
            raise SystemExit(f"Faltan temas en la base: {sorted(faltan)}")
        maestro_id, materia_id, cuatrimestre_id = maestro.id, materia.id, materia.cuatrimestre_id

        clase = Clase(nombre=NOMBRE_CLASE, materia_id=materia_id, maestro_id=maestro_id, codigo=clases._codigo_nuevo(s),
                      aprobacion=False, creada=ahora - timedelta(days=16))
        s.add(clase)
        s.flush()
        clase_id, codigo = clase.id, clase.codigo

        # --- alumnos
        nombres = list(zip(NOMBRES, APELLIDOS))
        rng.shuffle(nombres)
        clave = hash_password(PASSWORD)
        specs, alumnos = perfiles(rng), []
        for (nombre, apellido), perfil in zip(nombres, specs):
            ap2 = rng.choice(APELLIDOS)
            base = f"{nombre.lower().split()[0]}.{apellido.lower()}".replace("á", "a").replace("é", "e").replace("í", "i") \
                .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
            u = Usuario(nombre=f"{nombre} {apellido} {ap2}", email=base + DOMINIO, rol="alumno", password_hash=clave,
                        cuatrimestre_id=cuatrimestre_id, fecha=ahora - timedelta(days=rng.randint(18, 60)))
            s.add(u)
            alumnos.append((u, perfil))
        s.flush()
        for u, _ in alumnos:
            s.add(Inscripcion(clase_id=clase_id, alumno_id=u.id, estado="activo", fecha=ahora - timedelta(days=rng.randint(9, 15))))

        # --- tareas (con fecha de creación pasada, para que lo que ya hicieron cuente)
        def tarea(tipo, tema, meta, creada_dias, limite_dias, nota):
            t = Tarea(clase_id=clase_id, tema_id=temas[tema], autor_id=maestro_id, tipo=tipo, meta=meta,
                      instrucciones=nota, fecha_limite=ahora + timedelta(days=limite_dias),
                      creada=ahora - timedelta(days=creada_dias))
            s.add(t)
            s.flush()
            desc = {"preguntas": f"responder {meta} preguntas de examen", "ejercicios": f"resolver {meta} ejercicios prácticos",
                    "nivel": "llegar al nivel intermedio"}[tipo]
            s.add(Aviso(clase_id=clase_id, autor_id=maestro_id, tarea_id=t.id, fecha=ahora - timedelta(days=creada_dias),
                        texto=f"Nueva tarea: {desc} en «{tema}». Fecha límite: "
                              f"{(ahora + timedelta(days=limite_dias)).astimezone():%d/%m/%Y}. {nota}"))
        TA, TB, TC = "Circuitos Resistivos (serie, paralelo y mixtos)", "Leyes básicas de circuitos eléctricos", "Sistemas de unidades en circuitos eléctricos"
        tarea("preguntas", TA, 10, 5, 2, "Repasen serie y paralelo antes de empezar.")
        tarea("ejercicios", TB, 2, 4, 5, "Muestren el procedimiento completo.")
        tarea("nivel", TC, 2, 9, -1, "Entrega cerrada.")
        s.add(Aviso(clase_id=clase_id, autor_id=maestro_id, fecha=ahora - timedelta(days=2),
                    texto="El examen parcial de la unidad 1 será la próxima semana. Repasen leyes de Kirchhoff y circuitos resistivos."))

        # --- actividad de cada alumno
        quizzes, respuestas_hechas = [], 0
        for u, perfil in alumnos:
            if perfil["nivel"] == "nunca":
                continue
            hab, n, activo = perfil["habilidad"], perfil["n"], perfil["activo"]
            lista = []  # (días atrás, nombre del tema)
            if activo:  # lo que pide cada tarea, según qué tan bien le va al alumno
                a = {"alto": rng.randint(10, 14), "medio": rng.randint(3, 12), "bajo": rng.randint(0, 6)}[perfil["nivel"]]
                c = {"alto": rng.randint(5, 8), "medio": rng.randint(2, 6), "bajo": rng.randint(0, 3)}[perfil["nivel"]]
                lista += [(rng.randint(0, 4), TA) for _ in range(a)] + [(rng.randint(0, 8), TC) for _ in range(c)]
            nombres_t, pesos = list(TEMAS_PESO), list(TEMAS_PESO.values())
            objetivo = len(lista) + n  # lo de las tareas va además del estudio normal
            while len(lista) < objetivo:
                dia = rng.randint(0, 6) if activo and rng.random() < 0.5 else rng.randint(8, 13) if not activo or rng.random() < 0.9 else rng.randint(0, 6)
                lista.append((dia, rng.choices(nombres_t, pesos)[0]))
            if not activo:
                lista = [(max(d, 8), t) for d, t in lista]
            dias_uso = sorted({d for d, _ in lista})
            # conversaciones (una por tema) con sus preguntas y respuestas
            por_tema: dict[str, list] = {}
            for dia, tema in lista:
                por_tema.setdefault(tema, []).append(dia)
            for tema, dias in por_tema.items():
                conv = Conversacion(alumno_id=u.id, tema_id=temas[tema], titulo="Examen", tipo="examen", fecha=_hora(rng, max(dias)))
                s.add(conv)
                s.flush()
                banco_tema = [b for b in BANCO if b[0] == tema]
                for dia in dias:
                    _, pregunta, opciones, explicacion, dif = rng.choice(banco_tema)
                    giro = rng.randrange(4)
                    mostradas = opciones[giro:] + opciones[:giro]
                    correcta = mostradas.index(opciones[0])
                    acierta = rng.random() < min(0.98, max(0.05, hab - 0.07 * (dif - 2) + rng.gauss(0, 0.05)))
                    elegido = correcta if acierta else rng.choice([i for i in range(4) if i != correcta])
                    fecha = _hora(rng, dia)
                    q = Quiz(conversacion_id=conv.id, tema_id=temas[tema], pregunta=pregunta, opciones=mostradas,
                             indice_correcto=correcta, explicacion=explicacion, dificultad=dif, fecha=fecha)
                    s.add(q)
                    quizzes.append((q, u.id, elegido, acierta, fecha))
            # ejercicios prácticos
            if activo or perfil["nivel"] != "nunca":
                k = {"alto": rng.randint(2, 4), "medio": rng.randint(0, 3), "bajo": rng.randint(0, 1)}.get(perfil["nivel"], 0)
                if not activo:
                    k = 0
                for j in range(k):
                    tema = rng.choice([TB, TB, TA, TC])
                    dia = rng.randint(0, 3) if tema == TB else rng.randint(0, 11)
                    puntaje = max(0, min(10, round(10 * hab + rng.gauss(0, 1.4))))
                    s.add(IntentoEjercicio(alumno_id=u.id, tema_id=temas[tema], enunciado=rng.choice(ENUNCIADOS),
                                           respuesta="Apliqué la ley de Ohm y sumé las resistencias según su conexión.",
                                           puntaje=puntaje, retroalimentacion="Buen planteamiento; revisa las unidades del resultado."
                                           if puntaje >= 7 else "Revisa el procedimiento: hay un paso que no está justificado.",
                                           fecha=_hora(rng, dia)))
            # tiempo en la app: 2 sesiones de unos 10 a 30 minutos los días en que estudió
            marcas = []
            for dia in dias_uso:
                for sesion in range(rng.choice([1, 2, 2])):
                    inicio = _hora(rng, dia) - timedelta(hours=sesion * 3)
                    marcas += [{"usuario_id": u.id, "fecha": inicio + timedelta(minutes=m)}
                               for m in range(0, rng.randint(10, 30), 2)]
            if marcas:
                s.execute(insert(Actividad), marcas)
            # conversaciones con el tutor
            if activo and rng.random() < 0.7:
                conv = Conversacion(alumno_id=u.id, tema_id=temas[TA], titulo="Dudas de circuitos", tipo="chat", fecha=_hora(rng, 2))
                s.add(conv)
                s.flush()
                for pregunta, respuesta in rng.sample(DUDAS, rng.randint(1, 3)):
                    f = _hora(rng, rng.randint(0, 5))
                    s.add(Mensaje(conversacion_id=conv.id, rol="user", contenido=pregunta, fecha=f))
                    s.add(Mensaje(conversacion_id=conv.id, rol="assistant", contenido=respuesta, fecha=f + timedelta(seconds=20)))
        s.flush()
        for q, uid, elegido, acierta, fecha in quizzes:
            s.add(RespuestaQuiz(quiz_id=q.id, alumno_id=uid, indice_elegido=elegido, es_correcta=bool(acierta),
                                fecha=fecha + timedelta(minutes=2)))
            respuestas_hechas += 1
        # lo que el material no cubre (aparece en «Falta material»)
        activos = [u for u, p in alumnos if p["activo"]]
        for i, texto in enumerate(SIN_RESPUESTA):
            for u in rng.sample(activos, rng.randint(1, 3)):
                s.add(PreguntaSinRespuesta(alumno_id=u.id, tema_id=temas[TA], pregunta=texto, fecha=_hora(rng, rng.randint(0, 6))))
        lista_cuentas = [(u.nombre, u.email, p["nivel"], p["activo"]) for u, p in alumnos]

    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write(f"Grupo «{NOMBRE_CLASE}» del maestro {MAESTRO_EMAIL}. Código de la clase: {codigo}\n")
        f.write(f"Contraseña de todas las cuentas de alumno: {PASSWORD}\n\n")
        for nombre, email, nivel, activo in sorted(lista_cuentas):
            f.write(f"{email:42} {nombre:44} {nivel}{'' if activo else ' (sin actividad esta semana)'}\n")
    print(f"Listo: {len(lista_cuentas)} alumnos en «{NOMBRE_CLASE}» (código {codigo}), {respuestas_hechas} respuestas de examen.")
    print(f"Cuentas y contraseña en {SALIDA}")


if __name__ == "__main__":
    borrar() if "--borrar" in sys.argv else crear()
