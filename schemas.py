from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime
from models import ThemeEnum

# ==================== AUTH ====================
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ==================== PROFILE ====================
class UserProfileUpdate(BaseModel):
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = None
    header_url: Optional[str] = None
    theme_preference: Optional[ThemeEnum] = None

class UserProfileResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    bio: Optional[str]
    avatar_url: Optional[str]
    header_url: Optional[str]
    theme_preference: ThemeEnum
    created_at: datetime
    last_seen: Optional[datetime]
    is_online: bool
    model_config = ConfigDict(from_attributes=True)

class PublicProfileResponse(BaseModel):
    id: int
    username: str
    bio: Optional[str]
    avatar_url: Optional[str]
    header_url: Optional[str]
    is_online: bool
    last_seen: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)

# ==================== CHAT & FRIENDS ====================
class ChatCreate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = None
    chat_type: str = "direct"
    member_ids: List[int] = Field(..., min_length=1)

class ChatResponse(BaseModel):
    id: int
    name: Optional[str]
    avatar_url: Optional[str]
    chat_type: str
    created_by: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class FriendshipResponse(BaseModel):
    id: int
    user1_id: int
    user2_id: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ==================== MESSAGES & REACTIONS ====================
class MessageCreate(BaseModel):
    chat_id: int
    content: Optional[str] = Field(None, max_length=2000)
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None

class MessageUpdate(BaseModel):
    content: str = Field(..., max_length=2000)

class ReactionCreate(BaseModel):
    emoji: str = Field(..., max_length=10)

class ReactionResponse(BaseModel):
    emoji: str
    user_id: int
    username: str
    model_config = ConfigDict(from_attributes=True)

class MessageResponse(BaseModel):
    id: int
    chat_id: int
    sender_id: int
    sender_name: str
    content: Optional[str]
    file_path: Optional[str]
    file_type: Optional[str]
    file_name: Optional[str]
    file_size: Optional[int]
    created_at: datetime
    edited_at: Optional[datetime]
    is_pinned: bool
    reactions: List[ReactionResponse] = []
    model_config = ConfigDict(from_attributes=True)

# ==================== SYSTEM ====================
class FileUploadResponse(BaseModel):
    file_path: str
    file_type: str
    file_name: str
    file_size: int

class PinnedMessageResponse(BaseModel):
    id: int
    content: str
    sender_name: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)