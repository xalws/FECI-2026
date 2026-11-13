# Tutor Universitario con IA (FECI-2026)

Aplicación web hecha con Streamlit que funciona como tutor universitario. Los maestros suben su material de
clase en PDF y los alumnos conversan con una IA que **responde solo con ese material**, practica con ellos
mediante quizzes y ejercicios, y se adapta a su nivel en cada tema.

## Qué hace

**Alumno**
- Chat de estudio por tema. La respuesta incluye las fuentes (archivo y página del PDF).
- Puede estudiar las materias de su cuatrimestre o elegir **«Todas las materias»**, y cambiar su universidad,
  carrera y cuatrimestre desde el menú lateral.
- **Examen de varias preguntas** (de 3 a 10) con dificultad progresiva: empieza según su nivel en el tema,
  sube un nivel cuando acierta y baja uno cuando falla. Hay 4 niveles: básica, intermedia, avanzada y experta.
  Al terminar muestra el resultado y la dificultad más alta que resolvió.
- Ejercicios prácticos que la IA califica de 0 a 10.
- La explicación y el nivel inicial se adaptan por tema: modo *refuerzo* si le cuesta (menos de 50% de
  aciertos), *normal*, o *avanzado* (80% o más).
- Las preguntas priorizan el material de lo que el alumno falló y evitan repetir las recientes.
- **Revisión de cada pregunta:** antes de mostrarla, una segunda llamada a la IA la resuelve sin ver la
  respuesta. Si elige otra opción, la considera ambigua o la clave no coincide con el cálculo, se descarta y se
  genera otra (hasta 4 intentos). Las preguntas deben indicar si el circuito es en serie, en paralelo o mixto y
  llevar unidades. Esto usa unas 2 llamadas a Groq por pregunta.
- **Niveles por tema, unidad y materia (según la retícula):** cada acierto suma XP igual a su dificultad (1 a 4) y
  los ejercicios de 0 a 3. Niveles: Principiante (1 XP), Intermedio (6), Avanzado (14) y Experto (24). Con menos
  de 50% de aciertos en 4 o más intentos no pasa de Principiante. El nivel de una unidad o de la materia es el
  promedio de sus temas. Se ve en «Mi progreso», en el chat y al terminar cada examen.
- Página «Mi progreso» con tiempo de estudio, aciertos por tema, promedio en ejercicios y temas por repasar.
- Historial de conversaciones con búsqueda.

**Maestro**
- **Retícula:** sube el programa de la asignatura (PDF). La IA extrae las unidades, los temas y lo que el
  alumno debe saber y saber hacer en cada uno, muestra una vista previa y crea la materia con su universidad,
  carrera y cuatrimestre. Si la materia ya existe, la completa sin duplicar.
- **Avance por unidad:** en Estadísticas, el nivel y el % de cada alumno por unidad de la retícula.
- **Material:** sube los PDFs de toda la materia y la app reparte cada fragmento entre los temas de la
  retícula según su parecido (lo que no se parece a ningún tema no se guarda). También puede subir un PDF
  a un tema específico. Los PDF deben tener texto, no ser escaneos.
- Estadísticas: preguntas por tema, aciertos, alumnos más activos, preguntas de quiz más falladas.
- **Preguntas sin respuesta:** lo que el tutor no pudo contestar, es decir, material que falta subir.
- **Tiempo en la app** por alumno y **actividad a revisar** (respuestas demasiado rápidas, ráfagas de
  respuestas, mejoras bruscas). Son indicios, no prueba de trampa.
- Descarga del resumen por alumno en CSV.

**Administrador**
- Crea usuarios, asigna materias a maestros y ve lo mismo que el maestro.

## Cómo funciona

1. El PDF se divide en fragmentos y se guarda en ChromaDB, una colección por tema.
2. Cuando el alumno pregunta, se buscan los fragmentos más parecidos (embeddings locales con FastEmbed).
3. Groq recibe los fragmentos como contexto y responde solo con ellos. Si el material no contiene la
   respuesta, el tutor lo dice y la pregunta se guarda para el maestro.

## Estructura del proyecto

```
app.py              Router principal: páginas según el rol
core/               Lógica
  auth.py             login, usuarios y sesión
  llm.py              prompts y llamadas a Groq (tutor, quiz, calificación)
  rag.py              indexado y búsqueda en ChromaDB
  quiz.py             generación y evaluación de preguntas
  examen.py           reglas del examen con dificultad progresiva
  niveles.py          XP, niveles por tema y avance por unidad de la retícula
  reticula.py         lectura del programa de asignatura y creación de materia, unidades y temas
  material.py         subida de PDFs de toda la materia, repartidos por temas
  progreso.py         nivel por tema, ejercicios calificados
  actividad.py        registro del tiempo de uso
  sospechas.py        reglas de actividad a revisar
  stats.py            consultas de estadísticas para el maestro
  chat.py, perfil.py, pdf_loader.py, db.py, config.py, passwords.py, ui.py
models/schema.py    Tablas (SQLAlchemy)
vistas/             Pantallas de Streamlit (login, chat, progreso, historial, admin, maestro, estadísticas)
scripts/            datos_demo.py: crea o borra datos de ejemplo
tests/              Pruebas automáticas
```

Jerarquía académica: universidad → carrera → cuatrimestre → materia → unidad → tema.

## Parte 1 - Configuración del entorno local

Necesitas Python 3.11 o 3.12. No uses versiones superiores, porque las dependencias del proyecto pueden no
funcionar.

Clona el repositorio:

```bash
git clone https://github.com/xalws/FECI-2026.git
cd FECI-2026
```

Crea y activa el entorno virtual (Windows):

```bash
py -3.12 -m venv venv
venv\Scripts\activate
```

Instala las librerías:

```bash
pip install -r requirements.txt
```

## Parte 2 - Servicios y variables de entorno

Crea un archivo `.env` en la raíz del proyecto (junto a `app.py`) con estas llaves:

```
GROQ_API_KEY=gsk_tu_clave_aqui
DATABASE_URL=postgresql://usuario:password@ep-host-name.region.aws.neon.tech/neondb?sslmode=require
```

Opcionales: `GROQ_MODEL`, `MIN_SCORE` (similitud mínima para responder), `UMBRAL_TEMA` (similitud mínima para
asignar un fragmento a un tema de la retícula, 0.30 por defecto), `ADMIN_EMAIL` y `ADMIN_PASSWORD`
(credenciales del administrador inicial). Si no defines `ADMIN_EMAIL` y `ADMIN_PASSWORD`, se usan valores de ejemplo: cámbialos fuera de un
demo.

**Base de datos en la nube (Neon PostgreSQL)**

1. Entra a la consola de Neon (https://console.neon.tech/).
2. En la sección de proyectos, abre la pestaña «Shared with you» y selecciona el proyecto.
3. Haz clic en **Connect**, copia la cadena de conexión y pégala en `.env` como `DATABASE_URL`.

**Proveedor de LLM (Groq)**

1. Entra a GroqCloud (https://console.groq.com/) y abre **API Keys** en el menú izquierdo.
2. Pulsa **Create API Key** y copia la clave (empieza con `gsk_`).
3. Pégala en `.env` como `GROQ_API_KEY`.

Sin `DATABASE_URL` la app usa una base SQLite local (`local.db`). El material indexado (`chroma_data/`) se
guarda siempre en tu computadora, no en la nube.

## Parte 3 - Ejecución

Con el entorno virtual activado y el `.env` listo:

```bash
streamlit run app.py
```

La aplicación se abre en http://localhost:8501. La primera vez que subas un PDF se descarga el modelo de
embeddings (unos 200 MB).

Reinicia el servidor cada vez que cambies código de `core/`: Streamlit no siempre recarga los módulos ya
importados.

## Datos de ejemplo para un demo

```bash
python scripts/datos_demo.py            # crea un maestro y tres alumnos de ejemplo
python scripts/datos_demo.py --borrar   # elimina solo esos datos
```

Los usuarios usan el dominio `@demo.local` y la contraseña `demo1234`: `maestro@demo.local`,
`ana@demo.local`, `beto@demo.local` y `carla@demo.local`. El script escribe en la base de `DATABASE_URL`,
así que quien comparta esa base verá los datos de ejemplo.

## Pruebas

```bash
python -m unittest discover tests
```

Las pruebas usan una base SQLite temporal y no llaman a Groq.
