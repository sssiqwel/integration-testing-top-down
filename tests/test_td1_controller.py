"""Этап 1. Верхний модуль — контроллер Orders API (`orders_service/app/main.py`).

Все нижние модули заменены заглушками:
- `auth.require_token` — пропускает любой запрос;
- `storage` — StubOrderStorage;
- `users_client.get_user` — StubUsersClient, без HTTP и без Users API.
"""

import pytest
from stubs import ANNA

pytestmark = [pytest.mark.topdown, pytest.mark.usefixtures("stub_auth")]

ORDER = {"user_id": 1, "item": "Настольная лампа", "quantity": 2}


def test_td1_01_health(orders_api):
    response = orders_api.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_td1_02_create_order_uses_stubbed_user(orders_api, stub_storage, stub_users):
    response = orders_api.post("/api/v1/orders", json=ORDER, headers={"X-Request-ID": "td1-create"})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body == {"id": 1, **ORDER, "user": ANNA}
    assert response.headers["Location"] == "/api/v1/orders/1"
    assert response.headers["X-User-Service-Time-Ms"] == "1.50"
    assert response.headers["X-Request-ID"] == "td1-create"
    assert stub_users.calls == [(1, "td1-create")]
    assert len(stub_storage.created) == 1


@pytest.mark.parametrize(
    ("unavailable", "user_id", "status", "detail"),
    [
        (False, 404, 404, "User 404 not found"),
        (True, 1, 503, "User service is unavailable: stub"),
    ],
    ids=["user-missing", "users-api-down"],
)
def test_td1_03_failed_user_lookup_does_not_create_order(
    orders_api, stub_storage, stub_users, unavailable, user_id, status, detail
):
    stub_users.unavailable = unavailable
    response = orders_api.post("/api/v1/orders", json={**ORDER, "user_id": user_id})

    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert stub_storage.created == []


def test_td1_04_invalid_body_never_reaches_lower_modules(orders_api, stub_storage, stub_users):
    response = orders_api.post("/api/v1/orders", json={"user_id": 0, "item": " ", "quantity": 0})

    assert response.status_code == 422
    assert stub_users.calls == []
    assert stub_storage.created == []


def test_td1_05_unknown_order_is_404_without_user_lookup(orders_api, stub_storage, stub_users):
    response = orders_api.get("/api/v1/orders/77")

    assert response.status_code == 404
    assert response.json() == {"detail": "Order 77 not found"}
    assert stub_users.calls == []


def test_td1_06_list_calls_users_client_once_per_order(orders_api, stub_storage, stub_users):
    """Наблюдение N+1: заглушка считает вызовы, время не нужно."""
    stub_storage.add(*({"id": i, "user_id": 1, "item": f"Товар-{i}", "quantity": 1} for i in range(1, 6)))

    response = orders_api.get("/api/v1/orders")

    assert response.status_code == 200
    assert len(response.json()) == 5
    assert [user_id for user_id, _ in stub_users.calls] == [1, 1, 1, 1, 1]
    assert response.headers["X-User-Service-Time-Ms"] == "7.50"


@pytest.mark.defect
@pytest.mark.xfail(strict=True, reason="TD-D1: один заказ с пропавшим пользователем роняет весь GET /orders")
def test_td1_07_list_survives_one_missing_user(orders_api, stub_storage, stub_users):
    stub_storage.add(
        {"id": 1, "user_id": 1, "item": "Лампа", "quantity": 1},
        {"id": 2, "user_id": 3, "item": "Кружка", "quantity": 1},
    )

    response = orders_api.get("/api/v1/orders")

    assert response.status_code == 200, response.text
    assert 1 in {order["id"] for order in response.json()}


@pytest.mark.defect
@pytest.mark.xfail(strict=True, reason="TD-D2: существующий заказ отвечает 404, как будто его нет")
def test_td1_08_existing_order_is_not_reported_as_missing(orders_api, stub_storage, stub_users):
    stub_storage.add({"id": 1, "user_id": 3, "item": "Кружка", "quantity": 1})

    response = orders_api.get("/api/v1/orders/1")

    assert response.status_code != 404, response.text


@pytest.mark.defect
@pytest.mark.xfail(strict=True, reason="TD-D3: лишнее поле в ответе Users API даёт 500 в Orders API")
def test_td1_09_extra_field_from_users_is_ignored(orders_api, stub_storage, stub_users):
    stub_users.users[1] = {**ANNA, "phone": "+7 900 000-00-00"}

    response = orders_api.post("/api/v1/orders", json=ORDER)

    assert response.status_code == 201, f"{response.status_code} {response.text}"


@pytest.mark.defect
@pytest.mark.xfail(strict=True, reason="TD-D3: неполный ответ Users API даёт 500 вместо 503")
def test_td1_10_incomplete_user_is_reported_as_dependency_error(orders_api, stub_storage, stub_users):
    stub_users.users[1] = {"id": 1, "name": "Анна Иванова"}

    response = orders_api.post("/api/v1/orders", json=ORDER)

    assert response.status_code == 503, f"{response.status_code} {response.text}"
