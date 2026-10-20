"""Этап 3. Контроллер + auth + настоящий `storage.OrderStorage`.

Заглушка остаётся только у `users_client`.
"""

import pytest
from stubs import PETR

from lab_kit import AUTH

pytestmark = [pytest.mark.topdown, pytest.mark.usefixtures("stub_users")]


def order(user_id=1, item="Настольная лампа", quantity=2):
    return {"user_id": user_id, "item": item, "quantity": quantity}


def test_td3_01_ids_are_sequential_and_location_resolves(orders_api):
    ids = []
    for i in range(3):
        created = orders_api.post("/api/v1/orders", json=order(item=f"Товар-{i}"), headers=AUTH)
        assert created.status_code == 201
        ids.append(created.json()["id"])
        fetched = orders_api.get(created.headers["Location"])
        assert fetched.status_code == 200
        assert fetched.json() == created.json()

    assert ids == [1, 2, 3]


def test_td3_02_list_returns_saved_orders_in_creation_order(orders_api):
    orders_api.post("/api/v1/orders", json=order(item="Лампа"), headers=AUTH)
    orders_api.post("/api/v1/orders", json=order(user_id=2, item="Кружка"), headers=AUTH)

    listed = orders_api.get("/api/v1/orders").json()

    assert [o["item"] for o in listed] == ["Лампа", "Кружка"]
    assert listed[1]["user"] == PETR


def test_td3_03_item_is_stored_trimmed(orders_api):
    created = orders_api.post("/api/v1/orders", json=order(item="  Лампа  "), headers=AUTH).json()

    assert orders_api.get(f"/api/v1/orders/{created['id']}").json()["item"] == "Лампа"


def test_td3_04_rejected_requests_do_not_consume_ids(orders_api, orders_svc):
    assert orders_api.post("/api/v1/orders", json=order(user_id=99), headers=AUTH).status_code == 404
    assert orders_api.post("/api/v1/orders", json=order(quantity=0), headers=AUTH).status_code == 422
    assert orders_api.post("/api/v1/orders", json=order()).status_code == 401

    created = orders_api.post("/api/v1/orders", json=order(), headers=AUTH)

    assert created.json()["id"] == 1
    assert len(orders_svc.storage.storage.list()) == 1


def test_td3_05_unavailable_users_leaves_storage_untouched(orders_api, orders_svc, stub_users):
    stub_users.unavailable = True

    assert orders_api.post("/api/v1/orders", json=order(), headers=AUTH).status_code == 503
    assert orders_svc.storage.storage.list() == []
