from pydantic import EmailStr, BaseModel
from typing import Optional

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    age: Optional[int] = None
    role: Optional[str] = None

class UserOut(BaseModel):
    user_id: int
    name: str
    email: EmailStr
    age: int
    role: str

class UserDeleteRequest(BaseModel):
    email: EmailStr