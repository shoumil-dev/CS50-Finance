import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/", methods=["GET", "POST"])
@login_required
def index():

    if request.method == "GET":
        main = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])
        if main[0]["cash"] == None:
            return apology("101")

        cash = main[0]["cash"]
        cash = round(cash, 2)
        stocks = db.execute('SELECT stocksymbol FROM purchases WHERE id=?', session["user_id"])
        if len(stocks) > 0:
            for stock in stocks:        #checks live prices
                d = stock["stocksymbol"]
                s = lookup(d)
                value = s["price"]
                db.execute("UPDATE purchases SET single=?, total=(single * quantity) WHERE stocksymbol=? AND id=?", value, d, session["user_id"])

        purchases = db.execute("SELECT * FROM purchases WHERE id=?", session["user_id"])

        totaldict = db.execute("SELECT SUM(total) FROM purchases WHERE id=?", session["user_id"])

        if totaldict[0]["SUM(total)"] == None:
            final = cash

        else:
            total = totaldict[0]["SUM(total)"]
            final = ((total) + cash)
            final = round(final, 2)
        return render_template("homepage.html", cash=cash, purchases=purchases, final=final)

    if request.method == "POST":
        amount = float(request.form.get("add"))
        db.execute("UPDATE users SET cash=(cash + ?) WHERE id=?", amount, session["user_id"])
        return redirect("/")




@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        shares = request.form.get("shares")
        buy_symbol = request.form.get("symbol")
        row = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
        current_cash = row[0]['cash']

        if not shares.isnumeric():
            return apology("invalid share amount")

        if not buy_symbol:
            return apology("no symbol entered")

        bdetails = lookup(buy_symbol)
        if not bdetails:
                return apology("invalid symbol")

        b_price = bdetails["price"]
        b_name = bdetails["name"]
        b_symbol = bdetails["symbol"]

        bought = float(shares) * b_price
        bought = round(bought, 2)
        if current_cash < bought:
            return("not enough cash")
        new_cash = float(current_cash) - bought

        existing = db.execute('SELECT * FROM purchases WHERE stocksymbol=? AND id=?', b_symbol, session["user_id"])
        if not len(existing) == 0:
            db.execute('UPDATE purchases SET quantity=(quantity + ?) WHERE stocksymbol=? AND id=?', shares, b_symbol, session["user_id"])
        else:
            db.execute("INSERT INTO purchases (id, stockname, stocksymbol, quantity, single, total) VALUES (?, ?, ?, ?, ?, ?)", session["user_id"], b_name, b_symbol, shares, b_price, bought)

        db.execute("INSERT INTO history (id, symbol, shares, price) VALUES (?,?,?,?)", session["user_id"], b_symbol, shares, b_price)
        db.execute("UPDATE users SET cash=? WHERE id=?", new_cash, session["user_id"])


        return redirect("/")

    if request.method == "GET":
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    details = db.execute("SELECT * FROM history WHERE id=?", session["user_id"])
    return render_template("history.html", details=details)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")

    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("no symbol entered")

        details = lookup(symbol)

        if not details:
            return apology("symbol does not exist")

        c_name = details["name"]
        c_price = details["price"]
        c_symbol = details["symbol"]
        return render_template("quote2.html", name=c_name, price=c_price, symbol=c_symbol)




@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    if request.method == "POST":
        usr = request.form.get("username")
        pwd = request.form.get("password")
        pwd2 = request.form.get("confirmation")
        usertable = db.execute("SELECT username FROM users")

        if not usr or not pwd or not pwd2:
            return apology("failure")


        rows = db.execute("SELECT * FROM users WHERE username = ?", usr)
        if len(rows) == 1:
            return apology("username taken")

        elif pwd != pwd2:
            return apology("passwords don't match")

        else:
            hashvalue = generate_password_hash(pwd)
            db.execute("INSERT INTO users (username,hash) VALUES (?,?)", usr, hashvalue)
            return redirect("/")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    stocks = db.execute('SELECT stocksymbol FROM purchases WHERE id=?', session["user_id"])
    d = [] #list of stocksymbols
    for stock in stocks:
        d.append(stock["stocksymbol"])

    if request.method == "GET":
        return render_template("sell.html", stocklist=d)

    if request.method == "POST":
        symbol = request.form.get("symbol")
        quantity = request.form.get("shares")

        if not symbol or symbol not in d or not quantity:
            return apology("failure")


        qt = db.execute("SELECT quantity FROM purchases WHERE stocksymbol=? AND id=?", symbol, session["user_id"])
        amountof = qt[0]["quantity"]

        if int(quantity) > int(amountof):
            return apology("you do not own that many shares")

        bdetails = lookup(symbol)
        if not bdetails:
                return apology("invalid symbol")

        b_price = bdetails["price"]
        b_name = bdetails["name"]
        b_symbol = bdetails["symbol"]

        refund = float(quantity) * b_price

        db.execute("UPDATE users SET cash = (cash + ?) WHERE id=?", refund, session["user_id"])
        db.execute("UPDATE purchases SET quantity = (quantity - ?) WHERE id=? AND stocksymbol=?", quantity, session["user_id"], symbol)
        db.execute("DELETE FROM purchases WHERE quantity = '0'")
        db.execute("INSERT INTO history (id, symbol, shares, price) VALUES (?,?,?,?)", session["user_id"], symbol, quantity, b_price)
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
