from pydantic import EmailStr, BaseModel
from typing import Optional

class DeletedUserSummary(BaseModel):
    user_id: int
    email: EmailStr

class DeleteResponse(BaseModel):
    message: str
    deleted: DeletedUserSummary


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
