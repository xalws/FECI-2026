"""Siembra un grupo ficticio de 34 alumnos con actividad variada en una clase de Inglés I del maestro José Miguel.

Sirve para ver cómo se ven las gráficas, el boletín y las estadísticas del maestro con un grupo de tamaño real.

Uso, desde la carpeta del proyecto y con el entorno virtual activo:
    python scripts/sembrar_grupo_ingles.py            # crea (o rehace) el grupo
    python scripts/sembrar_grupo_ingles.py --borrar   # lo elimina por completo

Todas las cuentas usan el dominio `@estudiantes.example.com`, así que --borrar solo toca lo que este script creó: no toca
otras cuentas ni otras clases. Si el maestro no tenía asignada Inglés I, el script se la asigna (y --borrar no la quita).
Las credenciales se guardan en `cuentas_alumnos_ingles.txt` (archivo ignorado por git). Los datos son inventados.
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

DOMINIO = "@estudiantes.example.com"
MAESTRO_EMAIL = "jose@gmail.com"
MATERIA = "Inglés I"
NOMBRE_CLASE = "Inglés I · Grupo 2A"
PASSWORD = "English-2026"
SALIDA = Path(__file__).resolve().parent.parent / "cuentas_alumnos_ingles.txt"
ahora = datetime.now(timezone.utc)

NOMBRES = ["Sofía", "Emilio", "Lucía", "Gael", "Abigail", "Maximiliano", "Julieta", "Thiago", "Ivanna", "Dylan",
           "Aranza", "Joaquín", "Frida", "Cristian", "Melanie", "Axel", "Jimena", "Bruno", "Nayeli", "Josué",
           "Samantha", "Aarón", "Yareli", "Ricardo", "Esmeralda", "Héctor", "Ariadna", "Enrique", "Citlali", "Marco",
           "Lizbeth", "Uriel", "Abril", "Nicolás"]
APELLIDOS = ["Salazar", "Ibarra", "Escobar", "Delgado", "Rangel", "Cortés", "Navarro", "Pacheco", "Zamora", "Villa",
             "Bautista", "Cervantes", "Montes", "Esquivel", "Lara", "Solís", "Tapia", "Valdez", "Orozco", "Ponce",
             "Carrillo", "Beltrán", "Mejía", "Rojas", "Aguirre", "Meza", "Padilla", "Quintero", "Ruvalcaba", "Soto",
             "Trejo", "Urquidi", "Varela", "Zúñiga"]

# (tema, pregunta, opciones con la correcta primero, explicación, dificultad 1-4)
T_INTRO, T_PERS, T_ACT, T_UBIC = "Introducción", "Información personal", "Mis actividades cotidianas", "Ubicaciones"
BANCO = [
    (T_INTRO, "Choose the correct greeting for the morning:", ["Good morning", "Good night", "Good evening", "Goodbye"],
     "«Good morning» se usa para saludar por la mañana.", 1),
    (T_INTRO, "Complete: I ___ a student.", ["am", "is", "are", "be"], "Con «I» se usa «am».", 1),
    (T_INTRO, "Complete: She ___ from Mexico.", ["is", "am", "are", "be"], "Con she, he e it se usa «is».", 1),
    (T_INTRO, "Complete: They ___ my friends.", ["are", "is", "am", "be"], "Con they, we y you se usa «are».", 1),
    (T_INTRO, "What is the short form of «I am»?", ["I'm", "I'am", "Im'", "I's"], "La contracción de I am es I'm.", 2),
    (T_PERS, "Which question asks for someone's name?", ["What's your name?", "Where's your name?", "How old is your name?", "Who is name?"],
     "Para preguntar el nombre se dice «What's your name?».", 1),
    (T_PERS, "Complete: How ___ are you?", ["old", "many", "much", "long"], "«How old are you?» pregunta la edad.", 2),
    (T_PERS, "Choose the correct answer to «Where are you from?»", ["I'm from Chihuahua.", "I'm fine, thanks.", "I'm 20 years old.", "I have two brothers."],
     "Se responde con el lugar de origen: «I'm from…».", 2),
    (T_PERS, "Complete: My phone number ___ 614-555-0123.", ["is", "are", "am", "be"], "«Number» es singular: se usa «is».", 2),
    (T_PERS, "Which word is a possessive adjective?", ["my", "I", "me", "am"], "«My» indica posesión: my name, my phone.", 2),
    (T_PERS, "What is the plural of «person»?", ["people", "persons", "peoples", "persones"], "El plural habitual de person es people.", 3),
    (T_ACT, "Complete: She ___ up at 6:00 every day.", ["gets", "get", "getting", "got"], "En presente simple, con she se agrega -s.", 2),
    (T_ACT, "Complete: I ___ breakfast at 7:30.", ["have", "has", "having", "am have"], "Con «I» se usa «have».", 2),
    (T_ACT, "Which sentence is correct?", ["He doesn't work on Sundays.", "He don't work on Sundays.", "He not works on Sundays.", "He doesn't works on Sundays."],
     "Con doesn't el verbo va sin -s.", 3),
    (T_ACT, "Choose the correct preposition: I start work ___ 9:00.", ["at", "on", "in", "to"], "Con horas se usa «at».", 2),
    (T_ACT, "Choose the correct preposition: We have English class ___ Mondays.", ["on", "at", "in", "by"], "Con días de la semana se usa «on».", 2),
    (T_ACT, "Which adverb of frequency means 100% of the time?", ["always", "never", "sometimes", "rarely"], "«Always» significa siempre.", 2),
    (T_ACT, "Complete: My brother ___ TV in the evening.", ["watches", "watch", "watchs", "watching"],
     "Los verbos terminados en -ch agregan -es en tercera persona.", 3),
    (T_UBIC, "Choose the correct preposition: The book is ___ the table.", ["on", "of", "to", "from"], "«On» indica que algo está encima de una superficie.", 1),
    (T_UBIC, "What does «next to» mean?", ["Beside", "Far from", "Inside", "Behind"], "«Next to» significa al lado de.", 2),
    (T_UBIC, "Complete: There ___ two chairs in the room.", ["are", "is", "am", "be"], "Con plural se usa «There are».", 2),
    (T_UBIC, "Choose the correct preposition: The bank is ___ the supermarket and the pharmacy.", ["between", "among", "into", "over"],
     "«Between» se usa para dos referencias.", 3),
]
TEMAS_PESO = {T_INTRO: 3, T_PERS: 4, T_ACT: 5, T_UBIC: 3}
ENUNCIADOS = ["Write five sentences about your daily routine using the present simple.",
              "Introduce yourself in a short paragraph: your name, age, city and hobbies.",
              "Describe where things are in your bedroom using prepositions of place."]
DUDAS = [("¿Cuándo uso «is» y cuándo «are»?", "Usa «is» con he, she, it y «are» con you, we, they."),
         ("¿Cómo se forma el presente simple en tercera persona?", "Agrega -s o -es al verbo: she works, he watches."),
         ("¿Cuál es la diferencia entre «at», «on» e «in»?", "«At» para horas, «on» para días e «in» para meses y años."),
         ("¿Cómo digo mi edad en inglés?", "Se dice «I am 20 years old».")]
SIN_RESPUESTA = ["¿Cómo funciona el present perfect?", "¿Qué es un phrasal verb?", "¿Cómo se pronuncia «thorough»?"]


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
    print("Grupo de Inglés eliminado.")


def _hora(rng: random.Random, dia: int) -> datetime:
    f = (ahora - timedelta(days=dia)).replace(hour=rng.randint(14, 23), minute=rng.randint(0, 59), second=rng.randint(0, 59))
    # nunca en el futuro: si no, lo de «hoy» contaría como hecho después de cualquier tarea que se cree ahora
    return f - timedelta(days=1) if f > ahora else f


def perfiles(rng: random.Random) -> list[dict]:
    """34 perfiles: unos destacan, otros van regular, otros batallan, dos dejaron de entrar y uno nunca ha entrado."""
    p = []
    p += [{"nivel": "alto", "habilidad": rng.uniform(0.82, 0.95), "n": rng.randint(24, 40), "activo": True} for _ in range(9)]
    p += [{"nivel": "medio", "habilidad": rng.uniform(0.58, 0.78), "n": rng.randint(12, 26), "activo": True} for _ in range(15)]
    p += [{"nivel": "bajo", "habilidad": rng.uniform(0.28, 0.48), "n": rng.randint(8, 16), "activo": True} for _ in range(6)]
    p += [{"nivel": "medio", "habilidad": rng.uniform(0.5, 0.7), "n": rng.randint(6, 10), "activo": False} for _ in range(3)]
    p += [{"nivel": "nunca", "habilidad": 0.5, "n": 0, "activo": False}]
    rng.shuffle(p)
    return p


def crear() -> None:
    init_db()
    borrar()
    rng = random.Random(2027)
    with get_session() as s:
        maestro = s.scalar(select(Usuario).where(Usuario.email == MAESTRO_EMAIL, Usuario.rol == "maestro"))
        if maestro is None:
            raise SystemExit(f"No existe el maestro {MAESTRO_EMAIL}.")
        materia = s.scalar(select(Materia).where(Materia.nombre == MATERIA))
        if materia is None:
            raise SystemExit(f"No existe la materia {MATERIA}.")
        if not s.scalar(select(Asignacion.id).where(Asignacion.maestro_id == maestro.id, Asignacion.materia_id == materia.id)):
            s.add(Asignacion(maestro_id=maestro.id, materia_id=materia.id))  # sin asignación el maestro no puede tener clases
            s.flush()
            print(f"Se asignó {MATERIA} a {maestro.nombre}.")
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
        TA, TB, TC = T_ACT, T_PERS, T_INTRO
        tarea("preguntas", TA, 10, 5, 2, "Repasen el presente simple antes de empezar.")
        tarea("ejercicios", TB, 2, 4, 5, "Escriban con oraciones completas.")
        tarea("nivel", TC, 2, 9, -1, "Entrega cerrada.")
        s.add(Aviso(clase_id=clase_id, autor_id=maestro_id, fecha=ahora - timedelta(days=2),
                    texto="El examen oral será la próxima semana. Practiquen su presentación personal y las rutinas diarias."))

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
                                           respuesta="I wake up at 6:30. I have breakfast at 7:00 and I go to school at 8:00.",
                                           puntaje=puntaje, retroalimentacion="Good structure; check the third-person -s in your verbs."
                                           if puntaje >= 7 else "Review the verb forms: some sentences need the auxiliary «does».",
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
                conv = Conversacion(alumno_id=u.id, tema_id=temas[TA], titulo="Dudas de inglés", tipo="chat", fecha=_hora(rng, 2))
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
