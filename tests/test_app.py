"""CI 自動測試:每次 push 到 GitHub 都會跑這些測試"""
import os, sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import init_db
import app as appmod


@pytest.fixture(scope="module", autouse=True)
def build_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("db")
    db_path = str(d / "orders.db")
    init_db.DB = db_path
    init_db.main()
    appmod.DB = db_path


@pytest.fixture
def client():
    appmod.app.config["TESTING"] = True
    with appmod.app.test_client() as c:
        yield c


def login(c):
    return c.post("/login", data={"username": "admin", "password": "tkucsa1234"},
                  follow_redirects=True)


def test_healthz(client):
    assert client.get("/healthz").status_code == 200


def test_home_page(client):
    assert client.get("/").status_code == 200


def test_admin_requires_login(client):
    """未登入不得進入後台 — 權限的底線"""
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_login_with_wrong_password_fails(client):
    r = client.post("/login", data={"username": "admin", "password": "wrong"},
                    follow_redirects=True)
    assert "錯誤" in r.get_data(as_text=True)


def test_login_and_dashboard(client):
    assert login(client).status_code == 200
    assert client.get("/admin").status_code == 200


def test_unknown_order_returns_404(client):
    assert client.get("/order/SO_NOT_EXIST").status_code == 404


def test_order_total_matches_items(client):
    """驗證金額 = 明細小計加總 — 業務邏輯的守門員"""
    import sqlite3
    conn = sqlite3.connect(appmod.DB)
    conn.row_factory = sqlite3.Row
    oid = conn.execute("SELECT order_id FROM orders LIMIT 1").fetchone()["order_id"]
    expect = conn.execute(
        "SELECT SUM(qty*unit_price) s FROM order_item WHERE order_id=?", (oid,)
    ).fetchone()["s"]
    conn.close()
    html = client.get("/order/%s" % oid).get_data(as_text=True)
    assert "{:,.0f}".format(expect) in html


def test_qty_must_be_positive_integer(client):
    """後端驗證:數量不是正整數就要擋下來"""
    login(client)
    r = client.post("/admin/orders/new",
                    data={"order_id": "SO9999999", "customer_id": "C001",
                          "order_date": "2026-09-20", "qty_P101": "-3"},
                    follow_redirects=True)
    assert "正整數" in r.get_data(as_text=True)
