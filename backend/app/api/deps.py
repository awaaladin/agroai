"""Shared FastAPI dependencies. Long-lived objects live on app.state (built in main.create_app)."""
from fastapi import Request

from app.services.chat_service import ChatService
from app.services.diagnose_service import DiagnoseService
from app.services.session_store import SessionStore


def get_sessions(request: Request) -> SessionStore:
    return request.app.state.sessions


def get_diagnose_service(request: Request) -> DiagnoseService:
    return request.app.state.diagnose_service


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def get_accounts(request: Request):
    return request.app.state.accounts
