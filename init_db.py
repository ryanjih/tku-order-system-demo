"""建立資料庫並塞入測試資料。執行:python init_db.py"""
import sqlite3, random
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

DB = "orders.db"

SCHEMA = """
DROP TABLE IF EXISTS order_item;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS product;
DROP TABLE IF EXISTS customer;
DROP TABLE IF EXISTS admin_user;

CREATE TABLE customer (
    customer_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT,
    address     TEXT,
    created_at  TEXT
);

CREATE TABLE product (
    product_id  TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    unit_price  REAL NOT NULL CHECK (unit_price >= 0),
    stock       INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    category    TEXT
);

CREATE TABLE orders (
    order_id    TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customer(customer_id),
    order_date  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT '處理中',
    sales_rep   TEXT
);

-- 訂單與商品的「多對多」中間表;單價存「下單當時」的價格
CREATE TABLE order_item (
    order_id   TEXT NOT NULL REFERENCES orders(order_id),
    product_id TEXT NOT NULL REFERENCES product(product_id),
    qty        INTEGER NOT NULL CHECK (qty > 0),
    unit_price REAL NOT NULL,
    PRIMARY KEY (order_id, product_id)
);

CREATE TABLE admin_user (
    username TEXT PRIMARY KEY,
    pw_hash  TEXT NOT NULL,
    role     TEXT NOT NULL DEFAULT 'admin'
);
"""

CUSTOMERS = [
    ("C001", "沐光咖啡工作室", "02-2721-5566", "台北市大安區復興南路一段 12 號"),
    ("C002", "晴日烘焙坊",     "02-8912-3344", "新北市新店區北新路三段 88 號"),
    ("C003", "海風選物店",     "03-9325-7788", "宜蘭縣宜蘭市中山路二段 45 號"),
    ("C004", "青禾有機農園",   "04-2325-1199", "台中市西區民生路 210 號"),
    ("C005", "南方書店",       "07-2360-4422", "高雄市新興區中正三路 30 號"),
]

PRODUCTS = [
    ("P101", "阿拉比卡咖啡豆 1kg", 780.0, 120, "原物料"),
    ("P102", "手沖濾紙 100入",     120.0, 400, "耗材"),
    ("P103", "陶瓷濾杯 V60",       450.0,  80, "器具"),
    ("P104", "電子秤 0.1g",       1250.0,  35, "器具"),
    ("P105", "外帶紙杯 12oz 50入",  260.0, 300, "包材"),
    ("P106", "冷萃瓶 500ml",       340.0,  60, "包材"),
]

STATUS = ["已完成", "已完成", "已完成", "處理中", "已出貨", "已取消"]
REPS = ["林佳穎", "陳柏宇", "王思涵"]


def main():
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)
    cur = conn.cursor()
    today = date.today()

    cur.executemany(
        "INSERT INTO customer VALUES (?,?,?,?,?)",
        [(c[0], c[1], c[2], c[3], str(today - timedelta(days=200))) for c in CUSTOMERS])
    cur.executemany("INSERT INTO product VALUES (?,?,?,?,?)", PRODUCTS)
    cur.execute("INSERT INTO admin_user VALUES (?,?,?)",
                ("admin", generate_password_hash("tkucsa1234"), "admin"))

    random.seed(20260920)
    n = 1
    for days_ago in range(175, -1, -1):
        if random.random() > 0.42:
            continue
        d = today - timedelta(days=days_ago)
        oid = "SO%s%03d" % (d.strftime("%y%m"), n)
        n += 1
        cust = random.choice(CUSTOMERS)[0]
        cur.execute("INSERT INTO orders VALUES (?,?,?,?,?)",
                    (oid, cust, str(d), random.choice(STATUS), random.choice(REPS)))
        for p in random.sample(PRODUCTS, random.randint(1, 3)):
            cur.execute("INSERT INTO order_item VALUES (?,?,?,?)",
                        (oid, p[0], random.randint(1, 8), p[2]))

    conn.commit()
    print("已建立 %s" % DB)
    for t in ("customer", "product", "orders", "order_item"):
        print("  %-12s %3d 筆" % (t, cur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]))
    conn.close()


if __name__ == "__main__":
    main()
