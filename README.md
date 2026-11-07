# 🎓 Tutor IA Universitario

Chatbot educativo con roles **alumno / maestro / admin**. El maestro sube PDFs por tema; la IA solo responde con ese material. Incluye quizzes, ejercicios, historial y estadísticas.

**Stack:** Streamlit · Python · Pandas · LlamaIndex · Groq · PyPDF2 · ChromaDB · PostgreSQL (Neon)

---

## Parte 1 — Preparar tu computadora

### Paso 1. Instalar Python **3.11 o 3.12** (no 3.13 ni 3.14)

> ⚠️ Importante: con Python 3.13+ la librería de embeddings de LlamaIndex no se instala (lo comprobé). Usa 3.12.

1. Descarga Python 3.12 desde <https://www.python.org/downloads/>.
2. En el instalador (Windows) **marca la casilla "Add python.exe to PATH"** antes de instalar.
3. Abre una terminal (Windows: buscar "PowerShell") y verifica:
   ```
   py -3.12 --version
   ```
   Debe mostrar `Python 3.12.x`. (En Mac/Linux: `python3.12 --version`.)

### Paso 2. Poner el proyecto en una carpeta

Descomprime el zip, por ejemplo en `C:\Users\TuUsuario\chatbot-educativo`. En la terminal entra a esa carpeta:
```
cd C:\Users\TuUsuario\chatbot-educativo
```
(`cd` = "change directory". Todos los comandos siguientes se ejecutan **dentro de esta carpeta**.)

### Paso 3. Crear y activar el entorno virtual

**¿Qué es?** Una carpeta (`venv`) con una copia aislada de Python donde se instalan las librerías de *este* proyecto, sin mezclarlas con otros proyectos ni con tu Python global.

Crear (solo una vez):
```
py -3.12 -m venv venv
```
Activar (**cada vez que abras una terminal nueva** para trabajar en el proyecto):
```
venv\Scripts\activate
```
Si todo salió bien, verás `(venv)` al inicio de la línea de la terminal.

- **Si PowerShell dice "la ejecución de scripts está deshabilitada":** ejecuta una vez
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, responde `S`, y vuelve a activar.
- **Mac/Linux:** `python3.12 -m venv venv` y `source venv/bin/activate`.

### Paso 4. Instalar las librerías

Con `(venv)` activo:
```
pip install -r requirements.txt
```
`pip` es el instalador de librerías de Python; `requirements.txt` es la lista de lo que necesita el proyecto. Tarda varios minutos (ChromaDB y otras son pesadas). Es normal ver mucho texto.

---

## Parte 2 — Servicios externos (gratis)

### Paso 5. API key de Groq (el motor de IA)

1. Entra a <https://console.groq.com> y crea una cuenta.
2. Menú **API Keys → Create API Key**. Ponle un nombre y **copia la clave** (solo se muestra una vez; empieza con `gsk_`).

### Paso 6. Base de datos PostgreSQL en Neon

**¿Qué es PostgreSQL?** Un programa que guarda datos en *tablas* (como hojas de Excel relacionadas entre sí): usuarios, mensajes, resultados de quizzes, etc. **Neon** lo aloja en internet gratis, así no instalas nada en tu PC. **No necesitas escribir SQL**: el proyecto crea las tablas solo la primera vez.

1. Entra a <https://neon.tech> y crea una cuenta.
2. **Create project** (nombre libre, ej. `tutor-ia`; región la más cercana).
3. En el panel del proyecto pulsa **Connect** y copia la **connection string**. Se ve así:
   ```
   postgresql://usuario:contraseña@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   (Si trae `&channel_binding=require` al final y te da error de conexión, bórralo.)

> 💡 Si quieres probar primero sin Neon, deja `DATABASE_URL` vacío: el proyecto usa un archivo local `local.db` (SQLite). Luego cambias a Neon sin tocar código.

### Paso 7. Crear tu archivo `.env`

Aquí guardas tus claves (este archivo **nunca** se sube a GitHub; ya está en `.gitignore`).

1. Copia `.env.example` y renombra la copia a `.env` (exactamente así, con el punto al inicio).
2. Ábrelo con el Bloc de notas / VS Code y llena:
   ```
   GROQ_API_KEY=gsk_tu_clave
   DATABASE_URL=postgresql://...tu cadena de Neon...
   ADMIN_EMAIL=tucorreo@ejemplo.com
   ADMIN_PASSWORD=una_contraseña_segura
   ```
   Sin comillas ni espacios alrededor del `=`.

---

## Parte 3 — Ejecutar

### Paso 8. Iniciar la aplicación
```
streamlit run app.py
```
Se abre el navegador en <http://localhost:8501>. Para detenerla: `Ctrl + C` en la terminal.

La primera vez que subas un PDF o hagas una pregunta, se **descarga el modelo de embeddings (~220 MB)**; solo pasa una vez.

### Paso 9. Primer uso (en este orden)

1. **Admin**: inicia sesión con `ADMIN_EMAIL` / `ADMIN_PASSWORD` → página **Administración**:
   - *Catálogo*: crea Universidad → Carrera → Cuatrimestre → Materia → Unidad → Tema (en ese orden).
   - *Usuarios*: crea un usuario con rol **maestro**.
   - *Asignar maestros*: asigna la materia al maestro.
2. **Maestro**: cierra sesión, entra como maestro → **Subir material** → elige el tema → sube un PDF → **Procesar y entrenar**.
3. **Alumno**: en el login usa la pestaña **Registrarme** → entra → **Chat de estudio** → elige la cascada → pregunta, pide quiz o ejercicio.
4. **Maestro**: página **Estadísticas** para ver el uso.

> Atajo para probar rápido: `python crear_datos_demo.py` crea un catálogo de ejemplo y las cuentas `maestro@demo.com / maestro123` y `alumno@demo.com / alumno123` (ya asignado). Bórralas antes de usar el sistema de verdad.

---

## Roles y menú

| Rol | Ve en el menú |
|---|---|
| Sin sesión | Solo la pantalla de login (cualquier otra dirección redirige al login) |
| Alumno | Chat de estudio · Mi historial |
| Maestro | Material de la IA · Estadísticas (solo de sus materias) |
| Admin | Administración · Material de la IA · Estadísticas |

Cada página además revisa el rol por su cuenta (doble barrera). Si recargas el navegador (F5) la sesión se cierra y vuelves a iniciar sesión.

## Buscadores

- **Cascada** (chat, material, asignaciones): escribe parte del nombre de una materia, unidad, tema o carrera y elige la ruta completa. Los selectores también permiten escribir para filtrar.
- **Historial**: busca por tema, materia o palabras dentro de los mensajes.
- **Material**: busca documentos por nombre. **Admin**: busca usuarios y asignaciones. **Estadísticas**: busca por alumno o tema.

## Cómo funciona (resumen)

```
PDF ──PyPDF2──▶ texto ──LlamaIndex──▶ chunks + embeddings ──▶ ChromaDB (1 colección por tema)

Pregunta del alumno
   └▶ búsqueda en la colección de ESE tema
        ├─ nada relevante (< MIN_SCORE) ─▶ "No tengo información..." (no se llama a la IA)
        └─ fragmentos ─▶ Groq (temperature 0.1 + prompt restrictivo) ─▶ respuesta
   └▶ todo se guarda en PostgreSQL (conversaciones, mensajes, quizzes, respuestas)
```

| Archivo | Para qué sirve |
|---|---|
| `app.py` | Router: sin sesión solo existe el login; con sesión, el menú muestra solo las páginas de tu rol |
| `vistas/login.py` | Login y registro de alumnos |
| `vistas/chat_alumno.py` | Buscador + cascada de selección, chat, quiz, ejercicios (alumno) |
| `vistas/historial.py` | Historial de chats con buscador (alumno) |
| `vistas/panel_maestro.py` | Subir/eliminar/buscar PDFs por tema (maestro y admin) |
| `vistas/estadisticas.py` | Dashboard con buscador (maestro y admin) |
| `vistas/admin.py` | Catálogo, usuarios y asignación de maestros (solo admin) |
| `core/rag.py` | LlamaIndex + ChromaDB |
| `core/llm.py` | Groq y prompts (aquí está la regla "no inventar") |
| `core/pdf_loader.py` | Lectura de PDFs con PyPDF2 |
| `core/stats.py` | Consultas + Pandas |
| `core/auth.py`, `core/passwords.py` | Sesión, roles, bcrypt |
| `core/db.py`, `models/schema.py` | Conexión y tablas |

---

## Qué se probó y qué no

✅ Probado: instalación en Python 3.12, creación de tablas, login/roles, subida y borrado de PDF en ChromaDB, búsqueda con umbral, chat, historial, quiz, estadísticas y todas las páginas.
⚠️ **No pude probar** (el entorno de pruebas no tiene acceso): el modelo de embeddings real, Groq real y Neon real. Las pruebas usaron simulaciones de esas tres piezas. Por eso:

- **Calibra `MIN_SCORE`** (en `.env`, por defecto 0.25): sube a 0.35 si responde cosas fuera del tema; baja a 0.15 si dice "no tengo información" sobre cosas que sí están en el PDF.
- Groq retira modelos con frecuencia. Si aparece "el modelo no existe", cambia `GROQ_MODEL` en `.env` (lista en console.groq.com/docs/models). Modelo por defecto actual: `openai/gpt-oss-120b`; alternativas gratis: `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`.

---

## Problemas comunes

| Síntoma | Solución |
|---|---|
| `'streamlit' no se reconoce...` | No activaste el entorno: `venv\Scripts\activate` |
| `No matching distribution found...` al instalar | Estás con Python 3.13+; usa 3.12 (Paso 1 y 3) |
| `Falta GROQ_API_KEY` | El `.env` no está en la carpeta raíz o tiene otro nombre (¿`.env.txt`?) |
| Error de conexión a la base | Revisa `DATABASE_URL`; debe empezar con `postgresql://` |
| "No se encontró texto" al subir PDF | El PDF es escaneado (imágenes). PyPDF2 no hace OCR; usa PDFs con texto seleccionable |
| Error de límite / 429 de Groq | Plan gratuito con límite por minuto; espera un momento |

---

## Antes de publicar en internet

- Cambia la contraseña del admin y borra las cuentas demo.
- **Streamlit Cloud tiene disco temporal**: `chroma_data/` se pierde al reiniciar. Soluciones: guardar los PDFs (p. ej. en la BD) y reindexar al arrancar, o usar Chroma en modo servidor.
- En despliegue, las variables van en *Secrets* (el código ya las lee de `st.secrets`).

## Ideas para después

Reintentar quizzes con distintos niveles de dificultad, exportar estadísticas a Excel, OCR para PDFs escaneados, restringir alumnos por materia inscrita.
