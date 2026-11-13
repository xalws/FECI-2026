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
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class Asignacion(Base):
    __tablename__ = "asignaciones"
    __table_args__ = (UniqueConstraint("maestro_id", "materia_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    maestro_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    materia_id: Mapped[int] = mapped_column(ForeignKey("materias.id"))


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
