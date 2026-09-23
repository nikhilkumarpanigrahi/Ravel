import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from ravel.config import settings
from ravel.interfaces.security import AnalystUser, get_current_analyst, require_role


def test_get_current_analyst_dev_mode():
    settings.auth_enabled = False
    # Defaults to L1 analyst in dev mode without headers
    analyst = get_current_analyst()
    assert analyst.role == "L1"

    # Respects X-Analyst-Role header in dev mode
    analyst_l2 = get_current_analyst(x_analyst_id="lead_01", x_analyst_role="L2")
    assert analyst_l2.role == "L2"
    assert analyst_l2.is_lead is True


def test_get_current_analyst_prod_mode_auth():
    settings.auth_enabled = True
    settings.analyst_api_key = "test-secret-key"

    # Missing auth token raises 401
    with pytest.raises(HTTPException) as exc_info:
        get_current_analyst()
    assert exc_info.value.status_code == 401

    # Invalid token raises 401
    bad_cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-key")
    with pytest.raises(HTTPException) as exc_info:
        get_current_analyst(auth=bad_cred)
    assert exc_info.value.status_code == 401

    # Valid token succeeds
    good_cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-secret-key")
    analyst = get_current_analyst(auth=good_cred, x_analyst_role="L2")
    assert analyst.role == "L2"
    assert analyst.is_lead is True

    # Reset
    settings.auth_enabled = False


def test_require_role_enforcement():
    l1_analyst = AnalystUser(analyst_id="a1", username="analyst1", role="L1")
    l2_analyst = AnalystUser(analyst_id="a2", username="analyst2", role="L2")

    checker_l2 = require_role("L2")

    # L1 analyst fails L2 check
    with pytest.raises(HTTPException) as exc_info:
        checker_l2(l1_analyst)
    assert exc_info.value.status_code == 403

    # L2 analyst passes L2 check
    passed = checker_l2(l2_analyst)
    assert passed.role == "L2"
