from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# Jerarquía académica 
class Universidad(Base):
    __tablename__ = "universidades"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), unique=True)


class Carrera(Base):
    __tablename__ = "carreras"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    universidad_id: Mapped[int] = mapped_column(ForeignKey("universidades.id"))


class Cuatrimestre(Base):
    __tablename__ = "cuatrimestres"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    carrera_id: Mapped[int] = mapped_column(ForeignKey("carreras.id"))


class Materia(Base):
    __tablename__ = "materias"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    cuatrimestre_id: Mapped[int] = mapped_column(ForeignKey("cuatrimestres.id"))


class Unidad(Base):
    __tablename__ = "unidades"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    materia_id: Mapped[int] = mapped_column(ForeignKey("materias.id"))


class Tema(Base):
    __tablename__ = "temas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"))
    # Lo que el alumno debe saber y saber hacer en este tema (viene de la retícula)
    objetivos: Mapped[str | None] = mapped_column(Text, nullable=True)


# Usuarios 
class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    # alumno | maestro | admin
    rol: Mapped[str] = mapped_column(String(20))  
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Alumnos
    cuatrimestre_id: Mapped[int | None] = mapped_column(ForeignKey("cuatrimestres.id"), nullable=True)
    # Meta diaria de estudio en minutos (el alumno la elige en «Mi progreso»)
    meta_diaria_min: Mapped[int | None] = mapped_column(nullable=True)
    # Logros que el alumno muestra en su perfil (ids separados por comas; ver core/logros.py)
    vitrina: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class Asignacion(Base):
    __tablename__ = "asignaciones"
    __table_args__ = (UniqueConstraint("maestro_id", "materia_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    maestro_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    materia_id: Mapped[int] = mapped_column(ForeignKey("materias.id"))


# Clases: grupos de alumnos de una materia que crea un maestro (ver core/clases.py)
class Clase(Base):
    __tablename__ = "clases"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    materia_id: Mapped[int] = mapped_column(ForeignKey("materias.id"), index=True)
    maestro_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(8), unique=True, index=True)  # el que el alumno escribe para unirse
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    aprobacion: Mapped[bool] = mapped_column(Boolean, default=True)  # el maestro debe aprobar a quien entra con el código
    creada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class Inscripcion(Base):
    __tablename__ = "inscripciones"
    __table_args__ = (UniqueConstraint("clase_id", "alumno_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    clase_id: Mapped[int] = mapped_column(ForeignKey("clases.id"), index=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    estado: Mapped[str] = mapped_column(String(12), default="activo")  # activo | pendiente
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class Aviso(Base):
    __tablename__ = "avisos"
    id: Mapped[int] = mapped_column(primary_key=True)
    clase_id: Mapped[int] = mapped_column(ForeignKey("clases.id"), index=True)
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    texto: Mapped[str] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    # El aviso automático de una tarea («Nueva tarea: …»): se borra junto con la tarea
    tarea_id: Mapped[int | None] = mapped_column(nullable=True, index=True)


class Tarea(Base):
    """Algo que el maestro pide a su clase en un tema, con fecha límite."""
    __tablename__ = "tareas"
    id: Mapped[int] = mapped_column(primary_key=True)
    clase_id: Mapped[int] = mapped_column(ForeignKey("clases.id"), index=True)
    tema_id: Mapped[int] = mapped_column(ForeignKey("temas.id"))
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    tipo: Mapped[str] = mapped_column(String(12))  # preguntas | ejercicios | nivel
    meta: Mapped[int] = mapped_column()  # cuántas preguntas o ejercicios, o el nivel (1 a 4) que debe alcanzar
    instrucciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_limite: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    creada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    # Tarea programada: los alumnos la ven (y se cuenta lo que hacen) a partir de esta fecha. None = publicada de inmediato
    visible_desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Tarjeta(Base):
    """Una pregunta que el alumno falló y que vuelve a ver cada vez más espaciada (repaso espaciado)."""
    __tablename__ = "tarjetas_repaso"
    __table_args__ = (UniqueConstraint("alumno_id", "quiz_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"))
    caja: Mapped[int] = mapped_column(default=0)  # 0 a 3 = en repaso; 4 = dominada
    proxima: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actualizada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# Sesiones recordadas («Recordarme»): solo se guarda la huella SHA-256 del código que lleva el navegador
class Sesion(Base):
    __tablename__ = "sesiones"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    creada: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    expira: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# Material de entrenamiento
class Documento(Base):
    __tablename__ = "documentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    tema_id: Mapped[int] = mapped_column(ForeignKey("temas.id"))
    maestro_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    nombre_archivo: Mapped[str] = mapped_column(String(300))
    num_chunks: Mapped[int] = mapped_column(default=0)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# Registro de actividad (para calcular el tiempo de uso)
class Actividad(Base):
    __tablename__ = "actividad"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# Preguntas que el tutor no pudo responder con el material (indican material faltante)
class PreguntaSinRespuesta(Base):
    __tablename__ = "preguntas_sin_respuesta"
    id: Mapped[int] = mapped_column(primary_key=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    tema_id: Mapped[int] = mapped_column(ForeignKey("temas.id"))
    pregunta: Mapped[str] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# Fragmentos del material de cada tema con su vector, para buscar por significado. Viven en la base de datos
# compartida (antes estaban en una carpeta local) para que toda persona que use la app vea el mismo contenido.
class Fragmento(Base):
    __tablename__ = "fragmentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    tema_id: Mapped[int] = mapped_column(ForeignKey("temas.id"), index=True)
    # Sin llave foránea a propósito: el fragmento se guarda mientras el documento aún se está registrando
    documento_id: Mapped[int | None] = mapped_column(index=True, nullable=True)
    texto: Mapped[str] = mapped_column(Text)
    archivo: Mapped[str] = mapped_column(String(300), default="")
    pagina: Mapped[int | None] = mapped_column(nullable=True)
    embedding: Mapped[list] = mapped_column(JSON)


# Ejercicios prácticos calificados por la IA
class IntentoEjercicio(Base):
    __tablename__ = "intentos_ejercicio"
    id: Mapped[int] = mapped_column(primary_key=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    tema_id: Mapped[int] = mapped_column(ForeignKey("temas.id"))
    enunciado: Mapped[str] = mapped_column(Text)
    respuesta: Mapped[str] = mapped_column(Text)
    puntaje: Mapped[int] = mapped_column()  # 0 a 10
    retroalimentacion: Mapped[str] = mapped_column(Text, default="")
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


# Chats y quizzes
class Conversacion(Base):
    __tablename__ = "conversaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    tema_id: Mapped[int] = mapped_column(ForeignKey("temas.id"))
    titulo: Mapped[str] = mapped_column(String(200), default="")
    # chat | ejercicio | examen (las conversaciones antiguas no lo tienen y se tratan como chat)
    tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class Mensaje(Base):
    __tablename__ = "mensajes"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversacion_id: Mapped[int] = mapped_column(ForeignKey("conversaciones.id"))
    rol: Mapped[str] = mapped_column(String(20)) 
    contenido: Mapped[str] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class Quiz(Base):
    __tablename__ = "quizzes"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversacion_id: Mapped[int] = mapped_column(ForeignKey("conversaciones.id"))
    tema_id: Mapped[int] = mapped_column(ForeignKey("temas.id"))
    pregunta: Mapped[str] = mapped_column(Text)
    opciones: Mapped[list] = mapped_column(JSON)
    indice_correcto: Mapped[int] = mapped_column()
    explicacion: Mapped[str] = mapped_column(Text, default="")
    dificultad: Mapped[int | None] = mapped_column(nullable=True)  # 1 (básica) a 4 (experta)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class RespuestaQuiz(Base):
    __tablename__ = "respuestas_quiz"
    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"))
    alumno_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    indice_elegido: Mapped[int] = mapped_column()
    es_correcta: Mapped[bool] = mapped_column(Boolean)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class IntentoLogin(Base):
    """Un intento fallido de iniciar sesión (sirve para bloquear un rato al correo que lo repite; ver core/seguridad.py)."""
    __tablename__ = "intentos_login"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)


class ErrorApp(Base):
    """Un fallo de la app (ver core/errores.py): qué pasó y dónde; sin contraseñas ni claves."""
    __tablename__ = "errores_app"
    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)
    origen: Mapped[str] = mapped_column(String(60))
    tipo: Mapped[str] = mapped_column(String(80))
    mensaje: Mapped[str] = mapped_column(Text, default="")
    detalle: Mapped[str] = mapped_column(Text, default="")
    usuario_id: Mapped[int | None] = mapped_column(nullable=True)  # sin llave foránea: el registro sobrevive al usuario
