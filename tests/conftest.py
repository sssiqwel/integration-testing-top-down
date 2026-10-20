import pytest
from stubs import ANNA, PETR, FakeUsersApi, StubOrderStorage, StubUsersClient

from lab_kit import DEAD_URL, ApiClient, ThreadServer, load_service


@pytest.fixture(scope="session")
def users_svc():
    return load_service("users")


@pytest.fixture(scope="session")
def orders_svc():
    return load_service("orders")


@pytest.fixture(scope="session")
def users_server(users_svc):
    server = ThreadServer(users_svc.main.app).start()
    yield server
    server.stop()


@pytest.fixture(scope="session")
def orders_server(orders_svc):
    server = ThreadServer(orders_svc.main.app).start()
    yield server
    server.stop()


@pytest.fixture
def users_api(users_server):
    with ApiClient(users_server.url) as client:
        yield client


@pytest.fixture
def orders_api(orders_server):
    with ApiClient(orders_server.url) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_state(users_svc, orders_svc, monkeypatch):
    """Каждый тест начинает с чистых хранилищ и без подмен.

    Адрес Users API по умолчанию указывает в никуда, чтобы тест случайно
    не обратился к сервису, запущенному на машине вручную.
    """
    users_svc.storage.storage.reset()
    orders_svc.storage.storage.reset()
    monkeypatch.setattr(orders_svc.users_client, "USER_SERVICE_URL", DEAD_URL)
    yield
    orders_svc.main.app.dependency_overrides.clear()


@pytest.fixture
def stub_auth(orders_svc):
    """Заглушка проверки токена: любой запрос считается авторизованным."""
    orders_svc.main.app.dependency_overrides[orders_svc.auth.require_token] = lambda: None


@pytest.fixture
def stub_storage(orders_svc, monkeypatch):
    stub = StubOrderStorage()
    monkeypatch.setattr(orders_svc.main, "storage", stub)
    return stub


@pytest.fixture
def stub_users(orders_svc, monkeypatch):
    stub = StubUsersClient(orders_svc, {1: ANNA, 2: PETR})
    monkeypatch.setattr(orders_svc.main, "get_user", stub)
    return stub


@pytest.fixture(scope="session")
def fake_users_server():
    fake = FakeUsersApi()
    server = ThreadServer(fake.app).start()
    server.fake = fake
    yield server
    server.stop()


@pytest.fixture
def fake_users(fake_users_server, orders_svc, monkeypatch):
    """Настоящий users_client смотрит на ненастоящий Users API."""
    fake = fake_users_server.fake
    fake.reset()
    monkeypatch.setattr(orders_svc.users_client, "USER_SERVICE_URL", fake_users_server.url)
    return fake
