from pydantic import BaseModel, EmailStr, Field
from email_validator import validate_email, EmailNotValidError


class _LooseEmail(str):
    """EmailStr-like type that also accepts RFC 2606 reserved TLDs (.test, .example, .invalid, .localhost)
    so demo and educational accounts work seamlessly. Format is still validated."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, _info=None):
        if not isinstance(v, str):
            raise TypeError("Email must be a string.")
        try:
            info = validate_email(
                v,
                check_deliverability=False,
                allow_smtputf8=True,
                test_environment=True,  # accept .test/.example/.invalid/.localhost (RFC 2606)
            )
            return cls(info.normalized)
        except EmailNotValidError as e:
            raise ValueError(str(e)) from e

    # Pydantic v2 hook
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        from pydantic_core import core_schema
        return core_schema.no_info_after_validator_function(
            cls.validate, core_schema.str_schema()
        )


class SignupBody(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    email: _LooseEmail
    phone: str = Field(..., min_length=8, max_length=40)
    password: str = Field(..., min_length=8, max_length=200)


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class ForgotPasswordBody(BaseModel):
    email: _LooseEmail


class ResetPasswordBody(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=200)
