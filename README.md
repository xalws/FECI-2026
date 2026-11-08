Parte 1 - Configuracion del Entorno Local

Asegurate de contar con Python 3.11 o 3.12 instalado.
Nota: No utilices versiones superiores para evitar conflictos de compatibilidad con las dependencias del proyecto.

Clonar el repositorio
Abre tu terminal o consola de comandos y clona este repositorio:

git clone URL_DEL_REPOSITORIO
cd NOMBRE_DE_LA_CARPETA

Crear y activar el entorno virtual

py -3.12 -m venv venv
venv\Scripts\activate

Instalar librerias
Con el entorno virtual activo, instala todas las dependencias requeridas:

pip install -r requirements.txt

Parte 2 - Configuracion de Servicios y Variables de Entorno

Crea un archivo llamado .env en la raiz del proyecto (al mismo nivel que app.py). Agrega las siguientes llaves:

GROQ_API_KEY=gsk_tu_clave_aqui
DATABASE_URL=postgresql://usuario:password@ep-host-name.region.aws.neon.tech/neondb?sslmode=require

Base de Datos en la Nube (Neon PostgreSQL)

Ingresa a la consola de Neon (https://console.neon.tech/).
En la seccion de proyectos, dirigete a la pestana "Shared with you" y selecciona el proyecto.
Haz clic en el boton Connect.
Copia la cadena de conexion (Connection string) generada y pegala directamente en el archivo .env como valor de DATABASE_URL.

Proveedor de LLM (Groq API)

API Key de Groq:

Crea o inicia sesion en tu cuenta dentro del portal GroqCloud Console (https://console.groq.com/).
En el menu lateral izquierdo, haz clic en API Keys.
Haz clic en el boton Create API Key.
Copia la clave generada (comienza con gsk_...).
Pega la clave en tu archivo .env en la variable GROQ_API_KEY.

Parte 3 - Ejecucion de la Aplicacion

Con el entorno virtual activado y el archivo .env configurado, inicia la aplicacion ejecutando:

streamlit run app.py

La aplicacion se abrira en tu navegador en la direccion local:
http://localhost:8501
