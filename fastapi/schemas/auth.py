from pydantic import BaseModel, EmailStr, Field


class SignupBody(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=8, max_length=40)
    password: str = Field(..., min_length=8, max_length=200)


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=200)
