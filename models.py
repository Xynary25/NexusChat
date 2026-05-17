from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from database import Base
import enum


class ThemeEnum(str, enum.Enum):
    light = "light"
    dark = "dark"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)

    # Профиль пользователя
    avatar_url = Column(String(255), default=None)  # URL аватарки
    header_url = Column(String(255), default=None)  # URL шапки профиля
    bio = Column(Text, default="", nullable=True)  # "О себе"
    theme_preference = Column(Enum(ThemeEnum), default=ThemeEnum.light)

    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), default=None)
    is_online = Column(Boolean, default=False)

    # Связи
    messages = relationship("Message", back_populates="sender", cascade="all, delete-orphan")
    reactions = relationship("Reaction", back_populates="user", cascade="all, delete-orphan")
    pinned_messages = relationship("PinnedMessage", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Контент сообщения
    content = Column(Text, nullable=True)

    # Вложения
    file_path = Column(String(255), nullable=True)
    file_type = Column(String(20), nullable=True)  # 'image', 'video', 'document', 'audio'
    file_name = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)  # размер в байтах

    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    edited_at = Column(DateTime(timezone=True), default=None, nullable=True)

    # Удаление: "мягкое" удаление для конкретных пользователей
    deleted_for = Column(Text, default="[]")  # JSON-массив username'ов

    # Статусы
    is_pinned = Column(Boolean, default=False)
    pin_expires_at = Column(DateTime(timezone=True), default=None, nullable=True)

    # Связи
    sender = relationship("User", back_populates="messages")
    reactions = relationship("Reaction", back_populates="message", cascade="all, delete-orphan")
    pinned_by = relationship("PinnedMessage", back_populates="message", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Message(id={self.id}, sender_id={self.sender_id})>"


class Reaction(Base):
    __tablename__ = "reactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    emoji = Column(String(10), nullable=False)  # эмодзи как строка

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Уникальная реакция: один пользователь — одна реакция на сообщение
    __table_args__ = (
        # Позволяем несколько разных реакций от одного пользователя
        # но удаляем старую при добавлении новой (логика в коде)
    )

    # Связи
    message = relationship("Message", back_populates="reactions")
    user = relationship("User", back_populates="reactions")

    def __repr__(self):
        return f"<Reaction(emoji='{self.emoji}', user_id={self.user_id})>"


class PinnedMessage(Base):
    """Таблица для закреплённых сообщений с привязкой к пользователю"""
    __tablename__ = "pinned_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    pinned_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), default=None, nullable=True)

    # Связи
    message = relationship("Message", back_populates="pinned_by")
    user = relationship("User", back_populates="pinned_messages")

    __table_args__ = (
        # Один пользователь может закрепить сообщение только один раз
        # (но разные пользователи могут закрепить одно и то же)
    )

    def __repr__(self):
        return f"<PinnedMessage(message_id={self.message_id}, user_id={self.user_id})>"


class ForwardedMessage(Base):
    """Таблица для отслеживания пересланных сообщений"""
    __tablename__ = "forwarded_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    original_message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    forwarded_message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    forwarded_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    forwarded_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ForwardedMessage(original={self.original_message_id}, forwarded={self.forwarded_message_id})>"