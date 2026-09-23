"""Security and Role-Based Access Control (RBAC) for RAVEL Forensic Workstation."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from ravel.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


class AnalystUser(BaseModel):
    analyst_id: str
    username: str
    role: str  # L1, L2, COMPLIANCE, ADMIN

    @property
    def is_lead(self) -> bool:
        return self.role in {"L2", "ADMIN"}

    @property
    def is_compliance(self) -> bool:
        return self.role in {"COMPLIANCE", "ADMIN"}


def get_current_analyst(
    auth: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)] = None,
    x_analyst_id: Annotated[str | None, Header(alias="X-Analyst-Id")] = None,
    x_analyst_role: Annotated[str | None, Header(alias="X-Analyst-Role")] = None,
) -> AnalystUser:
    """Authenticate incoming API request.

    In development/demo mode (or when auth_enabled=False), defaults to an L1/L2 analyst
    or accepts explicit X-Analyst-Role/Id headers. In production mode, validates the Bearer token.
    """
    # 1. Bearer Token Check
    if auth and auth.credentials:
        if auth.credentials == settings.analyst_api_key or not settings.auth_enabled:
            role = (x_analyst_role or "L2").upper()
            return AnalystUser(
                analyst_id=x_analyst_id or "analyst-token",
                username="authenticated_analyst",
                role=role if role in {"L1", "L2", "COMPLIANCE", "ADMIN"} else "L2",
            )
        elif settings.auth_enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid analyst authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 2. Development / Header override
    if not settings.auth_enabled:
        role = (x_analyst_role or "L1").upper()
        if role not in {"L1", "L2", "COMPLIANCE", "ADMIN"}:
            role = "L1"
        return AnalystUser(
            analyst_id=x_analyst_id or "dev_analyst_01",
            username=x_analyst_id or "local_analyst",
            role=role,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(*allowed_roles: str):
    """Dependency factory checking that the authenticated analyst possesses one of the allowed roles."""

    def _role_checker(analyst: Annotated[AnalystUser, Depends(get_current_analyst)]) -> AnalystUser:
        normalized_allowed = {r.upper() for r in allowed_roles}
        if analyst.role.upper() not in normalized_allowed and analyst.role.upper() != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of roles {allowed_roles}; user has {analyst.role}",
            )
        return analyst

    return _role_checker
