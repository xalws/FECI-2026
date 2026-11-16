# PRACTIC_APP: tutor universitario con IA (FECI-2026)

Aplicación web hecha con Streamlit que funciona como tutor universitario. Los maestros suben su material de
clase en PDF y los alumnos conversan con una IA que **responde solo con ese material**, practica con ellos
mediante quizzes y ejercicios, y se adapta a su nivel en cada tema.

## Qué hace

**Alumno**
- Chat de estudio por tema. La respuesta incluye las fuentes (archivo y página del PDF).
- Puede estudiar las materias de su cuatrimestre o elegir **«Todas las materias»**, y cambiar su universidad,
  carrera y cuatrimestre desde el menú lateral.
- Tres vistas separadas en la página de estudio: **Conversación**, **Ejercicio práctico** y **Examen**. Cada una
  guarda su propia conversación en el historial.
- **Conversación guiada por el tutor:** en un chat nuevo el tutor saluda y pregunta si inician la lección o hay una
  pregunta. Al volver a una conversación anterior (se elige en el selector de arriba) pregunta si quieres
  retroalimentación, continuar donde lo dejaron u otra pregunta. También entiende órdenes escritas como
  «comencemos», «continuemos» o «dame retroalimentación», que no son preguntas sobre el contenido.
- **Examen** de varias preguntas (de 3 a 10) en **modo concentración**: mientras dura, se oculta el menú lateral,
  la conversación y las otras vistas. Después de cada pregunta se ve la respuesta correcta y su explicación. La
  dificultad empieza según su nivel en el tema, sube un nivel cuando acierta y baja uno cuando falla (básica,
  intermedia, avanzada y experta). Al terminar muestra el resultado y la dificultad más alta que resolvió.
- **🔁 Repasar errores:** las preguntas que fallaste y todavía no has acertado, con su respuesta y explicación, y
  una práctica sin distracciones que las vuelve a plantear. Las que corriges salen de la lista.
- **Qué estudiar ahora** (en «Mi progreso»): sugiere los siguientes temas según la retícula y tus niveles: primero
  reforzar lo de precisión baja, luego continuar lo empezado y después un tema nuevo. Solo propone temas con material.
- **Ejercicio práctico** en su propia pantalla: el enunciado, tu respuesta y la calificación de la IA (0 a 10).
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
- **Editar la retícula:** renombrar la materia, las unidades y los temas, y corregir lo que el alumno debe saber
  y saber hacer. Cambiar un nombre no afecta el material ni el avance de los alumnos (cuelgan del tema, no de
  su nombre).
- **Avance por unidad:** en Estadísticas, el nivel y el % de cada alumno por unidad de la retícula.
- **Material:** sube los PDFs de toda la materia y la app reparte cada fragmento entre los temas de la
  retícula según su parecido (lo que no se parece a ningún tema no se guarda). También puede subir un PDF
  a un tema específico. Los PDF deben tener texto, no ser escaneos.
- **Cobertura de la materia:** qué temas ya tienen material, cuáles no, y los temas con un PDF registrado
  cuyo contenido no está en la base. Desde ahí también se puede borrar un PDF.
- Estadísticas: preguntas por tema, aciertos, alumnos más activos, preguntas de quiz más falladas.
- **Preguntas sin respuesta:** lo que el tutor no pudo contestar, es decir, material que falta subir.
- **Tiempo en la app** por alumno y **actividad a revisar** (respuestas demasiado rápidas, ráfagas de
  respuestas, mejoras bruscas). Son indicios, no prueba de trampa.
- **Aviso de material faltante:** si varios alumnos distintos preguntan lo que el material no cubre en un mismo
  tema, aparece un aviso en Estadísticas y en la página de material.
- **Descargas:** resumen por alumno en CSV y reporte completo en Excel (una hoja por tabla; respeta las materias
  y la búsqueda elegidas).

**Administrador**
- Crea usuarios, asigna materias a maestros y ve lo mismo que el maestro.
- **Restablece la contraseña** de cualquier usuario que la olvidó (en «Mi cuenta»).

**Clases**
- **Clases del maestro** (menú «Clases»): cada clase es un grupo de UNA materia que el maestro tiene asignada (el
  administrador puede crearlas de cualquiera). Tiene un código de 6 letras y números que se comparte; se puede
  cambiar si se filtra. La clase puede pedir que el maestro apruebe a cada alumno o dejar entrar al instante.
  Desde ahí el maestro ve la lista de alumnos, acepta o rechaza solicitudes, quita alumnos, publica avisos,
  desactiva o elimina la clase (el progreso de los alumnos no se borra).
- **Mis clases** (alumno): se une escribiendo el código (5 intentos fallidos por sesión), ve sus clases, su estado
  (aceptado o esperando aprobación), puede salirse y lee los avisos. En Estudio, «Mis clases» muestra las materias
  de las clases donde ya fue aceptado, y los últimos avisos aparecen arriba.
- **Estadísticas por clase:** filtro «Clase» en Estadísticas (también afecta al reporte de Excel y al aviso de
  material faltante). Tablas `clases`, `inscripciones` y `avisos`.

**Alumno: metas y logros**
- **Respuestas en vivo:** el tutor escribe la respuesta mientras el modelo la genera. Si la IA falla (límite del
  plan gratuito, sin conexión) se muestra un mensaje claro con botón «Reintentar».
- **Meta diaria de estudio** (10 a 60 minutos) y calendario de las últimas 5 semanas en «Mi progreso».
- **Logros:** 75 logros en 7 categorías (Constancia, Dominio, Práctica, Exámenes, Exploración, Comunidad y
  Especiales), cada uno con 4 niveles: Bronce, Plata, Élite (con el color de su categoría) y Oro, que es el más alto
  y brilla con una animación. Son 300 medallas. Se calculan con la actividad ya guardada.
- **Mi perfil:** título según los XP (Novato a Leyenda), gráfica de XP por semana, temas que domina y el catálogo
  completo de logros. El alumno elige hasta 6 logros para su **vitrina** (`usuarios.vitrina`).
- **Competencia en la clase:** ranking por XP de todos los compañeros (total o de la semana) y perfil de cada uno
  con su vitrina, racha, minutos de estudio, temas dominados y gráfica de XP por semana. Solo se comparte esfuerzo:
  no se muestran calificaciones ni errores. Solo lo ven los compañeros de clase, su maestro y el administrador.

**Todos los roles**
- **Animación de carga:** mientras la IA prepara una pregunta, un ejercicio, una calificación o una explicación, debajo
  del indicador aparece una animación distinta cada vez (11 en total, sin repetir la anterior): un libro que pasa sus páginas, un lápiz que
  escribe, un birrete que se lanza, una pila de libros, una lupa, una bombilla, engranes, barras, una lista de tareas,
  un cohete y un átomo (`core/estudiante.py` y `core/cargas.py`). Es un SVG con
  CSS (`core/estudiante.py`), funciona en tema claro y oscuro, y con «reducir movimiento» queda quieta.
- **Sesión recordada:** al marcar «Mantener mi sesión iniciada» (14 días) no hay que volver a entrar al recargar
  la página. En el navegador solo queda un código aleatorio; la base guarda su huella SHA-256 (tabla `sesiones`).
  Cerrar sesión, cambiar la contraseña o desactivar la cuenta lo invalidan. No usarla en equipos compartidos.
- **Mi cuenta:** cambiar la propia contraseña (pide la actual y una confirmación). El mínimo son 6 caracteres y el
  máximo 72 bytes.
- Si el administrador olvida la suya, se restablece desde la terminal, con el entorno virtual activo y el `.env`:

```bash
python scripts/restablecer_password.py correo@ejemplo.com
```

## Cómo funciona

1. El PDF se divide en fragmentos y cada uno se guarda con su vector en la tabla `fragmentos` de la base de
   datos compartida (así todas las personas que usen la app ven el mismo contenido).
2. Cuando el alumno pregunta, se buscan los fragmentos más parecidos (embeddings locales con FastEmbed y
   similitud coseno).
3. Groq recibe los fragmentos como contexto y responde solo con ellos. Si el material no contiene la
   respuesta, el tutor lo dice y la pregunta se guarda para el maestro.

## Estructura del proyecto

```
app.py              Router principal: páginas según el rol
.streamlit/         config.toml: tema visual (colores, tipografías, menú lateral)
assets/             Logo e ícono de la app
core/               Lógica
  estilo.py           diseño compartido: encabezados, tarjetas, íconos, gráficas y hoja de estilos
  auth.py             login, usuarios y sesión
  llm.py              prompts y llamadas a Groq (tutor, quiz, calificación)
  rag.py              indexado y búsqueda por significado (tabla `fragmentos` de la base de datos)
  quiz.py             generación y evaluación de preguntas
  examen.py           reglas del examen con dificultad progresiva
  niveles.py          XP, niveles por tema y avance por unidad de la retícula
  reticula.py         lectura del programa de asignatura y creación de materia, unidades y temas
  material.py         subida de PDFs de toda la materia, repartidos por temas
  tutoria.py          el tutor como guía: iniciar la lección, continuarla, retroalimentar, detectar órdenes
  progreso.py         nivel por tema, ejercicios calificados
  actividad.py        registro del tiempo de uso y racha de días seguidos
  sospechas.py        reglas de actividad a revisar
  stats.py            consultas de estadísticas para el maestro
  cuenta.py           cambio y restablecimiento de contraseñas
  logros.py           meta diaria, calendario y logros del alumno
  clases.py           clases: códigos, inscripciones, aprobación y avisos
  competencia.py      XP, ranking de la clase y perfil público de un alumno
  perfil_ui.py        pantalla de perfil (propio y de compañeros)
  sesion.py           sesión recordada (cookie con código aleatorio; la base guarda solo su huella)
  tema.py             botón de modo claro/oscuro que conserva la sesión
  chat.py, perfil.py, pdf_loader.py, db.py, config.py, passwords.py, ui.py
models/schema.py    Tablas (SQLAlchemy)
vistas/             Pantallas de Streamlit (login, estudio, progreso, historial, cuenta, admin, maestro, estadísticas)
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

Sin `DATABASE_URL` la app usa una base SQLite local (`local.db`).

**Si venías usando una versión anterior** (el material indexado estaba en la carpeta local `chroma_data/`), copia
ese material a la base de datos una sola vez con el entorno virtual activo:

```bash
python scripts/migrar_chroma_a_bd.py
```

Es seguro repetirlo (salta lo ya copiado) y no borra `chroma_data/`. Hazlo en **cada computadora** donde se subió
material con la versión anterior; si no, esos temas aparecen en el panel de cobertura como «Documento sin contenido
indexado» y el tutor no podrá responder con ellos.

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
