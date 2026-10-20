"""Заглушки нижних модулей Orders API для интеграции «сверху вниз»."""

from __future__ import annotations

import time
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

ANNA = {"id": 1, "name": "Анна Иванова", "email": "anna@example.com"}
PETR = {"id": 2, "name": "Пётр Петров", "email": "petr@example.com"}


class StubOrderStorage:
    """Заглушка `storage.OrderStorage`: заказы задаются заранее, вызовы записываются."""

    def __init__(self) -> None:
        self.orders: dict[int, SimpleNamespace] = {}
        self.created: list = []

    def add(self, *rows: dict) -> None:
        for row in rows:
            self.orders[row["id"]] = SimpleNamespace(**row)

    def list(self):
        return list(self.orders.values())

    def get(self, order_id: int):
        return self.orders.get(order_id)

    def create(self, data):
        order = SimpleNamespace(
            id=max(self.orders, default=0) + 1,
            user_id=data.user_id,
            item=data.item,
            quantity=data.quantity,
        )
        self.orders[order.id] = order
        self.created.append(order)
        return order


class StubUsersClient:
    """Заглушка `users_client.get_user`: отвечает из словаря, без HTTP."""

    def __init__(self, orders_svc, users: dict[int, dict], elapsed_ms: float = 1.5) -> None:
        self._error = orders_svc.users_client.UserServiceError
        self._lookup = orders_svc.users_client.UserLookup
        self.users = users
        self.elapsed_ms = elapsed_ms
        self.unavailable = False
        self.calls: list[tuple[int, str | None]] = []

    def __call__(self, user_id: int, request_id: str | None = None):
        self.calls.append((user_id, request_id))
        if self.unavailable:
            raise self._error(503, "User service is unavailable: stub")
        if user_id not in self.users:
            raise self._error(404, f"User {user_id} not found")
        return self._lookup(dict(self.users[user_id]), self.elapsed_ms)


class FakeUsersApi:
    """Ненастоящий Users API: отвечает по HTTP так, как скажет тест."""

    def __init__(self) -> None:
        self.app = FastAPI()
        self.app.get("/api/v1/users/{user_id}")(self._get_user)
        self.reset()

    def reset(self) -> None:
        self.users: dict[int, dict] = {1: dict(ANNA)}
        self.mode = "normal"
        self.delay_s = 0.0
        self.extra_fields: dict = {}
        self.seen_request_ids: list[str | None] = []

    def _get_user(self, user_id: int, request: Request):
        self.seen_request_ids.append(request.headers.get("X-Request-ID"))
        if self.delay_s:
            time.sleep(self.delay_s)
        if self.mode == "error500":
            return JSONResponse({"detail": "boom"}, status_code=500)
        if self.mode == "not_json":
            return PlainTextResponse("<html>maintenance</html>")
        if user_id not in self.users:
            return JSONResponse({"detail": f"User {user_id} not found"}, status_code=404)
        return {**self.users[user_id], **self.extra_fields}
