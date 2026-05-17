"""
NexusChat Main Server.
Исправления:
- Безопасное управление сессией БД в WebSocket (убран Depends, предотвращает 'database is locked')
- Изоляция ошибок в цикле обработки сообщений (одно битое сообщение не рвёт соединение)
- Исправлен эндпоинт загрузки аватара (убран несуществующий get_current_user_ws)
- Добавлен эндпоинт получения закреплённых сообщений для инициализации чата
- Улучшена валидация токенов и обработка ошибок 401/403
"""
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, Depends, HTTPException, UploadFile, File, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import Optional, List
import json
from datetime import datetime
from pathlib import Path
import traceback

# Импорт наших модулей
from database import engine, Base, SessionLocal, get_db
from models import User, Message, Reaction, ThemeEnum, PinnedMessage
from auth import verify_password, get_password_hash, create_access_token, decode_token
from schemas import UserRegister, UserLogin, Token, UserProfileUpdate
from websocket_manager import manager
from file_handler import save_upload_file

# Инициализация базы данных
Base.metadata.create_all(bind=engine)

app = FastAPI(title="NexusChat")
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Монтируем папку uploads для доступа к файлам через браузер
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_current_user(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Зависимость для получения текущего пользователя из токена (HTTP)"""
    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization[7:]
    elif token:
        auth_token = token
    else:
        raise HTTPException(status_code=401, detail="Токен не предоставлен")

    payload = decode_token(auth_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Невалидный или истёкший токен")

    user = db.query(User).filter(User.id == payload.get("user_id")).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


# ==================== HTML МАРШРУТЫ ====================

@app.get("/", response_class=HTMLResponse)
async def get_auth():
    html_path = TEMPLATES_DIR / "auth.html"
    if not html_path.exists():
        return HTMLResponse(content="<h1>Ошибка: auth.html не найден</h1>", status_code=500)
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)


@app.get("/chat", response_class=HTMLResponse)
async def get_chat(token: Optional[str] = None):
    if not token:
        return HTMLResponse(
            status_code=307,
            content="<script>window.location.href='/'</script>"
        )
    html_path = TEMPLATES_DIR / "chat.html"
    if not html_path.exists():
        return HTMLResponse(content="<h1>Ошибка: chat.html не найден</h1>", status_code=500)

    html_content = html_path.read_text(encoding="utf-8")
    html_content = html_content.replace('const token = null;', f'const token = "{token}";')
    return HTMLResponse(content=html_content, status_code=200)


# ==================== AUTH & PROFILE API ====================

@app.post("/api/register", status_code=201)
async def register(user: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(400, "Имя пользователя занято")
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(400, "Email уже зарегистрирован")

    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=get_password_hash(user.password),
        theme_preference=ThemeEnum.light
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Регистрация успешна"}


@app.post("/api/login", response_model=Token)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(401, "Неверные учетные данные")

    user.last_seen = datetime.utcnow()
    user.is_online = True
    db.commit()

    access_token = create_access_token({"sub": user.username, "user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/me")
async def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "bio": current_user.bio,
        "avatar_url": current_user.avatar_url,
        "header_url": current_user.header_url,
        "theme_preference": current_user.theme_preference.value,
        "created_at": current_user.created_at,
        "last_seen": current_user.last_seen,
        "is_online": current_user.is_online
    }


@app.patch("/api/me/profile")
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if profile_data.bio is not None:
        current_user.bio = profile_data.bio
    if profile_data.avatar_url is not None:
        current_user.avatar_url = profile_data.avatar_url
    if profile_data.header_url is not None:
        current_user.header_url = profile_data.header_url
    if profile_data.theme_preference is not None:
        current_user.theme_preference = profile_data.theme_preference
    db.commit()
    return {"message": "Профиль обновлен"}


# ==================== FILE UPLOAD API ====================

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, "Невалидный токен")
    result = await save_upload_file(file, payload.get("user_id"))
    return result


@app.post("/api/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    file_meta = await save_upload_file(file, current_user.id)
    current_user.avatar_url = file_meta["file_path"]
    db.commit()
    return {"avatar_url": current_user.avatar_url, "message": "Аватар обновлен"}


# ==================== PINNED MESSAGES API ====================

@app.get("/api/pinned")
async def get_pinned_messages(db: Session = Depends(get_db)):
    """Возвращает последнее закреплённое сообщение для отображения в шапке чата"""
    pinned = db.query(Message).filter(
        Message.is_pinned == True
    ).order_by(Message.created_at.desc()).first()

    if not pinned:
        return {"is_pinned": False}

    sender = db.query(User).filter(User.id == pinned.sender_id).first()
    return {
        "is_pinned": True,
        "id": pinned.id,
        "content": pinned.content[:50] + ("..." if len(pinned.content) > 50 else ""),
        "sender_name": sender.username if sender else "Unknown",
        "created_at": pinned.created_at.isoformat()
    }


# ==================== WEBSOCKET CHAT LOGIC ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """Основной обработчик чата. Исправлено управление БД и изоляция ошибок."""

    # 1. Аутентификация
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=1008, reason="Invalid token")
        return

    # Создаём сессию БД вручную (Depends не работает корректно в WebSocket)
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.id == payload.get("user_id")).first()
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return

        # 2. Подключение
        await manager.connect(websocket, user.id, user.username)
        user.is_online = True
        db.commit()

        await manager.broadcast_to_all({
            "type": "online_users",
            "users": manager.get_online_users_list()
        })

        # 3. История сообщений
        messages = db.query(Message).order_by(Message.created_at.desc()).limit(50).all()
        messages.reverse()

        for msg in messages:
            deleted_for = json.loads(msg.deleted_for or "[]")
            if user.username not in deleted_for:
                sender = db.query(User).filter(User.id == msg.sender_id).first()
                reactions = [{"emoji": r.emoji, "user_id": r.user_id} for r in msg.reactions]

                await manager.send_personal({
                    "type": "message",
                    "id": msg.id,
                    "sender_id": msg.sender_id,
                    "sender_name": sender.username if sender else "Unknown",
                    "content": msg.content,
                    "file_path": msg.file_path,
                    "file_type": msg.file_type,
                    "file_name": msg.file_name,
                    "created_at": msg.created_at.isoformat(),
                    "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
                    "is_pinned": msg.is_pinned,
                    "reactions": reactions
                }, websocket)

        # 4. Цикл обработки сообщений
        while True:
            try:
                data = await websocket.receive_text()
                msg_data = json.loads(data)
                msg_type = msg_data.get("type")

                # --- ОБЫЧНОЕ СООБЩЕНИЕ ---
                if msg_type == "text":
                    content = (msg_data.get("content") or "").strip()
                    file_path = msg_data.get("file_path")
                    file_type = msg_data.get("file_type")
                    file_name = msg_data.get("file_name")

                    if not content and not file_path:
                        continue

                    new_msg = Message(
                        sender_id=user.id,
                        content=content if content else None,
                        file_path=file_path,
                        file_type=file_type,
                        file_name=file_name
                    )
                    db.add(new_msg)
                    db.commit()
                    db.refresh(new_msg)

                    await manager.broadcast_to_all({
                        "type": "message",
                        "id": new_msg.id,
                        "sender_id": user.id,
                        "sender_name": user.username,
                        "content": new_msg.content,
                        "file_path": new_msg.file_path,
                        "file_type": new_msg.file_type,
                        "file_name": new_msg.file_name,
                        "created_at": new_msg.created_at.isoformat(),
                        "edited_at": None,
                        "is_pinned": False,
                        "reactions": []
                    })

                # --- РЕДАКТИРОВАНИЕ ---
                elif msg_type == "edit":
                    msg_id = msg_data.get("message_id")
                    new_content = (msg_data.get("content", "") or "").strip()
                    db_msg = db.query(Message).filter(Message.id == msg_id).first()

                    if db_msg and db_msg.sender_id == user.id:
                        db_msg.content = new_content
                        db_msg.edited_at = datetime.utcnow()
                        db.commit()
                        await manager.broadcast_to_all({
                            "type": "edit",
                            "id": msg_id,
                            "content": new_content,
                            "edited_at": db_msg.edited_at.isoformat()
                        })

                # --- УДАЛЕНИЕ ---
                elif msg_type == "delete":
                    msg_id = msg_data.get("message_id")
                    mode = msg_data.get("mode", "self")
                    db_msg = db.query(Message).filter(Message.id == msg_id).first()

                    if db_msg and db_msg.sender_id == user.id:
                        if mode == "all":
                            db.delete(db_msg)
                            db.commit()
                            await manager.broadcast_to_all({"type": "deleted", "id": msg_id})
                        else:
                            deleted_list = json.loads(db_msg.deleted_for or "[]")
                            if user.username not in deleted_list:
                                deleted_list.append(user.username)
                                db_msg.deleted_for = json.dumps(deleted_list)
                                db.commit()
                                await manager.send_personal({"type": "deleted", "id": msg_id}, websocket)

                # --- РЕАКЦИИ ---
                elif msg_type == "reaction":
                    msg_id = msg_data.get("message_id")
                    emoji = msg_data.get("emoji")
                    existing = db.query(Reaction).filter_by(
                        message_id=msg_id, user_id=user.id, emoji=emoji
                    ).first()

                    if existing:
                        db.delete(existing)
                    else:
                        db.add(Reaction(message_id=msg_id, user_id=user.id, emoji=emoji))
                    db.commit()

                    await manager.broadcast_to_all({
                        "type": "reaction_update",
                        "message_id": msg_id,
                        "emoji": emoji,
                        "user_id": user.id,
                        "username": user.username
                    })

                # --- ЗАКРЕПЛЕНИЕ ---
                elif msg_type == "pin":
                    msg_id = msg_data.get("message_id")
                    db_msg = db.query(Message).filter(Message.id == msg_id).first()
                    if db_msg:
                        db_msg.is_pinned = not db_msg.is_pinned
                        db.commit()
                        await manager.broadcast_to_all({
                            "type": "pin_update",
                            "id": msg_id,
                            "is_pinned": db_msg.is_pinned
                        })

                # --- ПЕРЕСЫЛКА ---
                elif msg_type == "forward":
                    original_msg_id = msg_data.get("message_id")
                    db_original = db.query(Message).filter(Message.id == original_msg_id).first()
                    if db_original:
                        sender_name = db.query(User).filter(
                            User.id == db_original.sender_id
                        ).first().username
                        forward_content = f"↪️ Переслано от {sender_name}: {db_original.content or '[Файл]'}"

                        new_forward = Message(
                            sender_id=user.id,
                            content=forward_content,
                            file_path=db_original.file_path,
                            file_type=db_original.file_type,
                            file_name=db_original.file_name
                        )
                        db.add(new_forward)
                        db.commit()
                        db.refresh(new_forward)

                        await manager.broadcast_to_all({
                            "type": "message",
                            "id": new_forward.id,
                            "sender_id": user.id,
                            "sender_name": user.username,
                            "content": new_forward.content,
                            "file_path": new_forward.file_path,
                            "file_type": new_forward.file_type,
                            "file_name": new_forward.file_name,
                            "created_at": new_forward.created_at.isoformat(),
                            "edited_at": None,
                            "is_pinned": False,
                            "reactions": []
                        })

                # --- СТАТУС "ПЕЧАТАЕТ" ---
                elif msg_type == "typing":
                    is_typing = msg_data.get("is_typing", False)
                    await manager.broadcast({
                        "type": "typing",
                        "username": user.username,
                        "is_typing": is_typing
                    }, sender_id=user.id)

            except json.JSONDecodeError:
                continue  # Игнорируем битые JSON-пакеты
            except Exception as e:
                db.rollback()  # Откатываем транзакцию при ошибке
                print(f"WebSocket Message Error: {e}")
                traceback.print_exc()
                continue

    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
        user.is_online = False
        user.last_seen = datetime.utcnow()
        db.commit()
        await manager.broadcast_to_all({
            "type": "online_users",
            "users": manager.get_online_users_list()
        })
    except Exception as e:
        print(f"WebSocket Critical Error: {e}")
        traceback.print_exc()
    finally:
        db.close()


# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)