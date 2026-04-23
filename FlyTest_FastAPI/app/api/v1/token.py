from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.responses import success_response
from app.schemas.auth import TokenObtainRequest, TokenRefreshRequest
from app.services.auth.service import authenticate_user, build_token_pair, refresh_access_token


router = APIRouter(prefix="/token", tags=["auth"])


@router.post("/")
def obtain_token(payload: TokenObtainRequest, db: Session = Depends(get_db)) -> dict:
    user = authenticate_user(db, payload.username, payload.password)
    return success_response(build_token_pair(user))


@router.post("/refresh/")
def refresh_token(payload: TokenRefreshRequest) -> dict:
    return success_response(refresh_access_token(payload.refresh))
