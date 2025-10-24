from pydantic import EmailStr, BaseModel

class UserDeleteRequest(BaseModel):
    email: EmailStr