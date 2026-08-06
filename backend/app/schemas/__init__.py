"""Pydantic schemas exported for API use."""

from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    OAuth2TokenResponse,
    TokenResponse,
)
from app.schemas.delivery import DeliveryCreate, DeliveryRead, DeliveryUpdate
from app.schemas.fuel_type import FuelTypeCreate, FuelTypeRead, FuelTypeUpdate
from app.schemas.pump import PumpCreate, PumpRead, PumpUpdate
from app.schemas.sale import SaleCreate, SaleRead, SaleUpdate
from app.schemas.station import StationCreate, StationRead, StationUpdate
from app.schemas.tank import TankCreate, TankRead, TankUpdate
from app.schemas.user import UserCreate, UserRead, UserUpdate

__all__ = [
    "CurrentUserResponse",
    "DeliveryCreate",
    "DeliveryRead",
    "DeliveryUpdate",
    "FuelTypeCreate",
    "FuelTypeRead",
    "FuelTypeUpdate",
    "LoginRequest",
    "PumpCreate",
    "PumpRead",
    "PumpUpdate",
    "SaleCreate",
    "SaleRead",
    "SaleUpdate",
    "StationCreate",
    "StationRead",
    "StationUpdate",
    "TankCreate",
    "TankRead",
    "TankUpdate",
    "TokenResponse",
    "OAuth2TokenResponse",
    "UserCreate",
    "UserRead",
    "UserUpdate",
]
