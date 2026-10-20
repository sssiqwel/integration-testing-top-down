"""Этап 2. Контроллер + настоящий `auth.require_token`.

Заглушки остаются у `storage` и `users_client`.
"""

import pytest
from stubs import ANNA

from lab_kit import AUTH

pytestmark = [pytest.mark.topdown, pytest.mark.usefixtures("stub_storage", "stub_users")]

ORDER = {"user_id": 1, "item": "Настольная лампа", "quantity": 2}


def test_td2_01_valid_token_creates_order(orders_api):
    response = orders_api.post("/api/v1/orders", json=ORDER, headers=AUTH)

    assert response.status_code == 201
    assert response.json()["user"] == ANNA


def test_td2_02_missing_token(orders_api, stub_users, stub_storage):
    response = orders_api.post("/api/v1/orders", json=ORDER)

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing Authorization header"}
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert stub_users.calls == []
    assert stub_storage.created == []


def test_td2_03_wrong_token(orders_api, stub_storage):
    response = orders_api.post("/api/v1/orders", json=ORDER, headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}
    assert stub_storage.created == []


def test_td2_04_scheme_is_case_insensitive(orders_api):
    response = orders_api.post("/api/v1/orders", json=ORDER, headers={"Authorization": "bearer secret-token"})

    assert response.status_code == 201


def test_td2_05_reading_does_not_require_token(orders_api, stub_storage):
    stub_storage.add({"id": 1, "user_id": 1, "item": "Лампа", "quantity": 1})

    assert orders_api.get("/api/v1/orders").status_code == 200
    assert orders_api.get("/api/v1/orders/1").status_code == 200


def test_td2_06_auth_is_checked_before_body_validation(orders_api):
    response = orders_api.post("/api/v1/orders", json={"user_id": 0})

    assert response.status_code == 401


@pytest.mark.defect
@pytest.mark.xfail(strict=True, reason="TD-D4: при схеме Basic ответ «Missing Authorization header», хотя заголовок есть")
def test_td2_07_wrong_scheme_has_clear_message(orders_api):
    response = orders_api.post("/api/v1/orders", json=ORDER, headers={"Authorization": "Basic c2VjcmV0"})

    assert response.status_code == 401
    assert response.json()["detail"] != "Missing Authorization header"
