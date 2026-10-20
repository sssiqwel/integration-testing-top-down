"""Этап 5. Заглушек нет: Orders API работает с настоящим Users API.

Users API хранит данные в памяти, поэтому его перезапуск имитируется
сбросом хранилища (`storage.reset()`): остаются только Анна и Пётр,
счётчик id начинается заново — ровно то, что происходит при рестарте процесса.
"""

import pytest

from lab_kit import AUTH

pytestmark = pytest.mark.topdown


@pytest.fixture
def system(orders_svc, users_server, monkeypatch):
    monkeypatch.setattr(orders_svc.users_client, "USER_SERVICE_URL", users_server.url)


@pytest.fixture
def restart_users(users_svc):
    return users_svc.storage.storage.reset


def new_user(users_api, name="Иван Новиков", email="ivan@example.com"):
    response = users_api.post("/api/v1/users", json={"name": name, "email": email}, headers=AUTH)
    assert response.status_code == 201, response.text
    return response.json()


def new_order(orders_api, user_id, item="Настольная лампа"):
    response = orders_api.post(
        "/api/v1/orders", json={"user_id": user_id, "item": item, "quantity": 1}, headers=AUTH
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.usefixtures("system")
def test_td5_01_end_to_end(users_api, orders_api):
    user = new_user(users_api)
    order = new_order(orders_api, user["id"])

    assert order["user"] == user
    assert orders_api.get(f"/api/v1/orders/{order['id']}").json()["user"] == user
    assert [o["id"] for o in orders_api.get("/api/v1/orders").json()] == [order["id"]]


@pytest.mark.usefixtures("system")
def test_td5_02_missing_user_in_real_users_api(orders_api):
    response = orders_api.post(
        "/api/v1/orders", json={"user_id": 999, "item": "Кружка", "quantity": 1}, headers=AUTH
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "User 999 not found"}


@pytest.mark.usefixtures("system")
def test_td5_03_order_reflects_current_user_data(users_api, orders_api, users_svc):
    order = new_order(orders_api, 1)
    users_svc.storage.storage._users[1] = users_svc.models.User(id=1, name="Анна Смирнова", email="anna@example.com")

    assert orders_api.get(f"/api/v1/orders/{order['id']}").json()["user"]["name"] == "Анна Смирнова"


@pytest.mark.defect
@pytest.mark.usefixtures("system")
@pytest.mark.xfail(strict=True, reason="TD-D1 подтверждён на реальной системе: после рестарта Users GET /orders = 404")
def test_td5_04_list_after_users_restart(users_api, orders_api, restart_users):
    kept = new_order(orders_api, 1, "Лампа для Анны")
    new_order(orders_api, new_user(users_api)["id"], "Временный товар")

    restart_users()
    response = orders_api.get("/api/v1/orders")

    assert response.status_code == 200, response.text
    assert kept["id"] in {o["id"] for o in response.json()}


@pytest.mark.defect
@pytest.mark.usefixtures("system")
@pytest.mark.xfail(strict=True, reason="TD-D5: после рестарта Users id переиспользуются, заказ показывает чужого человека")
def test_td5_05_user_id_is_not_reused_after_restart(users_api, orders_api, restart_users):
    ivan = new_user(users_api, "Иван Новиков", "ivan@example.com")
    order = new_order(orders_api, ivan["id"], "Подарок Ивану")

    restart_users()
    maria = new_user(users_api, "Мария Сидорова", "maria@example.com")
    shown = orders_api.get(f"/api/v1/orders/{order['id']}")

    assert maria["id"] != ivan["id"], f"id={maria['id']} выдан повторно"
    assert shown.json().get("user", {}).get("email") != "maria@example.com", shown.text
