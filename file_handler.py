"""
File Handler for NexusChat.
Отвечает за:
- Валидацию типов файлов (безопасность)
- Генерацию уникальных имен файлов (чтобы файлы не перезаписывались)
- Сохранение файлов на сервере в папку uploads/
- Возврат метаданных для отображения в чате (превью изображений, ссылки на документы)
"""

import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException

# ==================== КОНФИГУРАЦИЯ ====================
UPLOAD_DIR = Path("uploads")
# Автоматически создаем папку uploads, если её нет
UPLOAD_DIR.mkdir(exist_ok=True)

# Разрешенные расширения файлов и их категории для фронтенда
ALLOWED_EXTENSIONS = {
    # Изображения
    '.jpg': 'image', '.jpeg': 'image', '.png': 'image',
    '.gif': 'image', '.webp': 'image', '.svg': 'image',
    # Видео
    '.mp4': 'video', '.webm': 'video', '.mov': 'video', '.ogg': 'video',
    # Документы и архивы
    '.pdf': 'document', '.doc': 'document', '.docx': 'document',
    '.txt': 'document', '.zip': 'document', '.rar': 'document', '.xlsx': 'document'
}


def get_file_category(filename: str) -> str:
    """
    Определяет категорию файла (image/video/document) по расширению.
    Возвращает 'document' по умолчанию, если расширение неизвестно.
    """
    ext = Path(filename).suffix.lower()
    return ALLOWED_EXTENSIONS.get(ext, 'document')


def is_file_allowed(filename: str) -> bool:
    """Проверяет, разрешено ли загружать данный тип файла"""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


async def save_upload_file(file: UploadFile, user_id: int) -> dict:
    """
    Асинхронно сохраняет загруженный файл на диск.

    Args:
        file: Объект UploadFile из FastAPI
        user_id: ID пользователя (можно использовать для разделения папок, сейчас используется для логов)

    Returns:
        dict: Метаданные файла (путь, тип, имя) для сохранения в БД и отправки клиенту
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="У файла отсутствует имя")

    # 1. Проверка безопасности: разрешен ли тип файла?
    if not is_file_allowed(file.filename):
        raise HTTPException(status_code=400, detail="Недопустимый тип файла")

    # 2. Генерация уникального имени файла
    # Используем UUID, чтобы два файла с одинаковым именем (например photo.jpg) не перезаписали друг друга
    file_ext = Path(file.filename).suffix.lower()
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = UPLOAD_DIR / unique_filename

    # 3. Сохранение файла на диск
    # Используем shutil для эффективного копирования потока данных
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении файла: {str(e)}")

    # 4. Возвращаем метаданные
    return {
        "file_path": f"uploads/{unique_filename}",  # Относительный путь для веб-доступа
        "file_type": get_file_category(file.filename),  # Тип для рендеринга (img/video/link)
        "file_name": file.filename,  # Оригинальное имя для отображения
        "file_id": unique_filename  # Уникальный ID для БД
    }