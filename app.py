"""訂單管理系統 — 單元12/13 參考實作 (Flask + SQLite)"""
import io, os, sqlite3
from datetime import date
from functools import wraps

import qrcode
from flask import (Flask, flash, redirect, render_template, request,
                   send_file, session, url_for)
from werkzeug.security import check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "orders.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")


# ---------- 資料庫 ----------
def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def q(sql, args=(), one=False):
    with db() as conn:
        rows = conn.execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows


def run(sql, args=()):
    with db() as conn:
        conn.execute(sql, args)
        conn.commit()


# ---------- 權限 ----------
def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if session.get("role") != "admin":
            flash("請先登入管理後台", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


# ---------- 前台 ----------
@app.route("/")
def index():
    return render_template("index.html", today=date.today())


@app.route("/order/<order_id>")
def order_detail(order_id):
    """出貨單 QRCode 掃描後導向的訂單查詢頁(免登入)"""
    order = q("""SELECT o.*, c.name AS customer_name, c.phone, c.address
                 FROM orders o JOIN customer c ON o.customer_id = c.customer_id
                 WHERE o.order_id = ?""", (order_id,), one=True)
    if not order:
        return render_template("not_found.html", order_id=order_id), 404
    items = q("""SELECT p.name, p.product_id, i.qty, i.unit_price,
                        i.qty * i.unit_price AS subtotal
                 FROM order_item i JOIN product p ON i.product_id = p.product_id
                 WHERE i.order_id = ?""", (order_id,))
    total = sum(r["subtotal"] for r in items)
    return render_template("order_detail.html", o=order, items=items, total=total)


@app.route("/order/<order_id>/qrcode.png")
def order_qrcode(order_id):
    url = request.url_root.rstrip("/") + url_for("order_detail", order_id=order_id)
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# ---------- 登入 ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "")
        row = q("SELECT * FROM admin_user WHERE username = ?", (u,), one=True)
        if row and check_password_hash(row["pw_hash"], p):
            session["user"] = u
            session["role"] = row["role"]
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("帳號或密碼錯誤", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------- 後台:營運儀表板 ----------
@app.route("/admin")
@admin_required
def dashboard():
    valid = "o.status <> '已取消'"
    kpi_rev = q("""SELECT IFNULL(SUM(i.qty * i.unit_price), 0) v
                   FROM orders o JOIN order_item i ON o.order_id = i.order_id
                   WHERE %s""" % valid, one=True)["v"]
    kpi_ord = q("SELECT COUNT(*) v FROM orders o WHERE %s" % valid, one=True)["v"]
    kpi_cus = q("SELECT COUNT(*) v FROM customer", one=True)["v"]
    aov = kpi_rev / kpi_ord if kpi_ord else 0

    monthly = q("""SELECT substr(o.order_date,1,7) ym,
                          SUM(i.qty * i.unit_price) rev
                   FROM orders o JOIN order_item i ON o.order_id = i.order_id
                   WHERE %s GROUP BY ym ORDER BY ym""" % valid)
    top_products = q("""SELECT p.name, SUM(i.qty) qty,
                               SUM(i.qty * i.unit_price) rev
                        FROM order_item i
                        JOIN orders o ON o.order_id = i.order_id
                        JOIN product p ON p.product_id = i.product_id
                        WHERE %s GROUP BY p.product_id
                        ORDER BY rev DESC LIMIT 5""" % valid)
    by_status = q("SELECT status, COUNT(*) n FROM orders GROUP BY status ORDER BY n DESC")
    top_customers = q("""SELECT c.name, COUNT(DISTINCT o.order_id) n,
                                SUM(i.qty * i.unit_price) rev
                         FROM orders o
                         JOIN customer c ON c.customer_id = o.customer_id
                         JOIN order_item i ON i.order_id = o.order_id
                         WHERE %s GROUP BY c.customer_id
                         ORDER BY rev DESC LIMIT 5""" % valid)
    return render_template("dashboard.html", kpi_rev=kpi_rev, kpi_ord=kpi_ord,
                           kpi_cus=kpi_cus, aov=aov, monthly=monthly,
                           top_products=top_products, by_status=by_status,
                           top_customers=top_customers)


# ---------- 後台:訂單 ----------
@app.route("/admin/orders")
@admin_required
def admin_orders():
    kw = request.args.get("kw", "").strip()
    sql = """SELECT o.order_id, o.order_date, o.status, o.sales_rep,
                    c.name AS customer_name,
                    IFNULL(SUM(i.qty * i.unit_price), 0) AS total
             FROM orders o
             JOIN customer c ON c.customer_id = o.customer_id
             LEFT JOIN order_item i ON i.order_id = o.order_id
             WHERE (? = '' OR o.order_id LIKE ? OR c.name LIKE ?)
             GROUP BY o.order_id ORDER BY o.order_date DESC, o.order_id DESC
             LIMIT 60"""
    rows = q(sql, (kw, "%" + kw + "%", "%" + kw + "%"))
    return render_template("admin_orders.html", rows=rows, kw=kw)


@app.route("/admin/orders/new", methods=["GET", "POST"])
@admin_required
def new_order():
    products = q("SELECT * FROM product ORDER BY product_id")
    customers = q("SELECT * FROM customer ORDER BY customer_id")
    if request.method == "POST":
        oid = request.form.get("order_id", "").strip().upper()
        cid = request.form.get("customer_id", "")
        odate = request.form.get("order_date") or str(date.today())
        rep = request.form.get("sales_rep", "").strip()

        errors = []
        if not oid.startswith("SO") or len(oid) < 6:
            errors.append("訂單編號格式需為 SO + 數字(例:SO2609001)")
        if q("SELECT 1 FROM orders WHERE order_id = ?", (oid,), one=True):
            errors.append("訂單編號 %s 已存在" % oid)
        if not q("SELECT 1 FROM customer WHERE customer_id = ?", (cid,), one=True):
            errors.append("請選擇有效的客戶")

        picked = []
        for p in products:
            raw = request.form.get("qty_" + p["product_id"], "").strip()
            if raw:
                if not raw.isdigit() or int(raw) <= 0:
                    errors.append("%s 的數量必須是正整數" % p["name"])
                else:
                    picked.append((p["product_id"], int(raw), p["unit_price"]))
        if not picked:
            errors.append("至少要選擇一項商品")

        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            with db() as conn:
                conn.execute("INSERT INTO orders VALUES (?,?,?,?,?)",
                             (oid, cid, odate, "處理中", rep))
                conn.executemany("INSERT INTO order_item VALUES (?,?,?,?)",
                                 [(oid, pid, qty, price) for pid, qty, price in picked])
                conn.commit()
            flash("訂單 %s 已建立,共 %d 項商品" % (oid, len(picked)), "success")
            return redirect(url_for("order_detail", order_id=oid))

    nxt = q("SELECT COUNT(*) n FROM orders", one=True)["n"] + 1
    suggest = "SO%s%03d" % (date.today().strftime("%y%m"), nxt)
    return render_template("order_form.html", products=products,
                           customers=customers, today=date.today(), suggest=suggest)


@app.route("/admin/orders/<order_id>/status", methods=["POST"])
@admin_required
def update_status(order_id):
    new = request.form.get("status", "")
    if new in ("處理中", "已出貨", "已完成", "已取消"):
        run("UPDATE orders SET status = ? WHERE order_id = ?", (new, order_id))
        flash("訂單 %s 狀態已更新為「%s」" % (order_id, new), "success")
    return redirect(request.referrer or url_for("admin_orders"))


# ---------- 後台:商品 / 客戶 ----------
@app.route("/admin/products")
@admin_required
def admin_products():
    return render_template("admin_products.html",
                           rows=q("SELECT * FROM product ORDER BY product_id"))


@app.route("/admin/customers")
@admin_required
def admin_customers():
    rows = q("""SELECT c.*, COUNT(o.order_id) n
                FROM customer c LEFT JOIN orders o ON o.customer_id = c.customer_id
                GROUP BY c.customer_id ORDER BY c.customer_id""")
    return render_template("admin_customers.html", rows=rows)


@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8899)), debug=True)
