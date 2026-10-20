"""Этап 4. Контроллер + auth + storage + настоящий `users_client`.

Вместо Users API работает FakeUsersApi — ненастоящий сервис, который
по HTTP отвечает так, как нужно тесту: 200, 404, 500, медленно, не JSON.
"""

import pytest
from stubs import ANNA

from lab_kit import AUTH, DEAD_URL

pytestmark = pytest.mark.topdown

ORDER = {"user_id": 1, "item": "Настольная лампа", "quantity": 2}


def create(orders_api, **headers):
    return orders_api.post("/api/v1/orders", json=ORDER, headers={**AUTH, **headers})


def test_td4_01_user_comes_over_http(orders_api, fake_users):
    response = create(orders_api)

    assert response.status_code == 201
    assert response.json()["user"] == ANNA
    assert float(response.headers["X-User-Service-Time-Ms"]) > 0


def test_td4_02_request_id_reaches_users_api(orders_api, fake_users):
    create(orders_api, **{"X-Request-ID": "td4-trace"})

    assert fake_users.seen_request_ids == ["td4-trace"]


def test_td4_03_users_404_becomes_orders_404(orders_api, fake_users, orders_svc):
    fake_users.users = {}

    response = create(orders_api)

    assert response.status_code == 404
    assert response.json() == {"detail": "User 1 not found"}
    assert orders_svc.storage.storage.list() == []


@pytest.mark.parametrize(
    ("mode", "detail_start"),
    [
        ("error500", "User service returned 500"),
        ("not_json", "User service returned an invalid response"),
    ],
)
def test_td4_04_broken_users_api_becomes_503(orders_api, fake_users, orders_svc, mode, detail_start):
    fake_users.mode = mode

    response = create(orders_api)

    assert response.status_code == 503
    assert response.json()["detail"].startswith(detail_start)
    assert orders_svc.storage.storage.list() == []


def test_td4_05_slow_users_api_hits_timeout(orders_api, fake_users, orders_svc, monkeypatch):
    monkeypatch.setattr(orders_svc.users_client, "USER_SERVICE_TIMEOUT", 0.3)
    fake_users.delay_s = 0.6

    response = create(orders_api)

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


def test_td4_06_health_is_ok_while_users_api_is_down(orders_api, orders_svc, monkeypatch):
    """Наблюдение: /health не показывает, что зависимость недоступна."""
    monkeypatch.setattr(orders_svc.users_client, "USER_SERVICE_URL", DEAD_URL)

    assert create(orders_api).status_code == 503
    assert orders_api.get("/health").status_code == 200


@pytest.mark.defect
@pytest.mark.xfail(strict=True, reason="TD-D3: новое поле в ответе Users API даёт 500 в Orders API")
def test_td4_07_extra_field_over_http_is_ignored(orders_api, fake_users):
    fake_users.extra_fields = {"created_at": "2026-10-20T10:00:00Z"}

    response = create(orders_api)

    assert response.status_code == 201, f"{response.status_code} {response.text}"
