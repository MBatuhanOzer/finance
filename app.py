import os

import datetime
import pytz
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    stocks = db.execute(
        "SELECT properties.symbol, properties.shares FROM properties WHERE properties.user_id = ?", session["user_id"])
    rowlist = []
    total = 0.00
    for row in stocks:
        stock = lookup(row["symbol"])
        totalprice = stock["price"] * row["shares"]
        x = dict(symbol=stock["symbol"], shares=row["shares"],
                 price=stock["price"], totshares=totalprice)
        rowlist.append(x)
        total = total + totalprice
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cashdict = cash[0]
    total = total + cashdict["cash"]
    return render_template("index.html", rowlist=rowlist, cash=cashdict, total=total, usd=usd)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("shares") or not request.form.get("shares").isdigit():
            return apology(message="INVALID INPUT")
        if lookup(request.form.get("symbol")) == None:
            return apology(message="INVALID SYMBOL")
        stock = lookup(request.form.get("symbol"))
        sum = stock["price"] * int(request.form.get("shares"))
        funds = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        fund = funds[0]["cash"]
        if sum > fund:
            return apology(message="INSUFFICIENT FUNDS")
        fund = fund - sum
        db.execute("UPDATE users SET cash = ? WHERE id = ?", fund, session["user_id"])
        rows = db.execute("SELECT * FROM properties WHERE properties.symbol = ? AND properties.user_id = ?",
                          stock["symbol"], session["user_id"])
        if len(rows) == 0:
            db.execute("INSERT INTO properties (symbol, shares, user_id) VALUES (?, ?, ?)",
                       stock["symbol"], request.form.get("shares"), session["user_id"])
        else:
            nsum = rows[0]["shares"] + int(request.form.get("shares"))
            db.execute("UPDATE properties SET shares = ? WHERE symbol = ? AND user_id = ?",
                       nsum, stock["symbol"], session["user_id"])
        t = datetime.datetime.now(pytz.timezone("Turkey")).strftime('%Y-%m-%d %H:%M:%S')
        db.execute("INSERT INTO history (user_id, symbol, shares, price, time) VALUES(?, ?, ?, ?, ?)",
                   session["user_id"], stock["symbol"], int(request.form.get("shares")), stock["price"], t)
        return redirect("/")
    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    rows = db.execute(
        "SELECT symbol, shares, price, time FROM history WHERE user_id = ? ORDER BY time DESC", session["user_id"])
    return render_template("history.html", rows=rows, usd=usd)


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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
    '''Acts differently depends on the method'''
    if request.method == "POST":
        # Checks if the symbol is valid.
        if not request.form.get("symbol") or lookup(request.form.get("symbol")) == None:
            return apology(message="INVALID SYMBOL")
        stock = lookup(request.form.get("symbol"))
        return render_template("quote.html", stock=stock, usd=usd)
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Displays a feedback error for every possible unwanted submission
        if not request.form.get("username"):
            return apology(message="You need to provide a username.")
        if not request.form.get("password"):
            return apology(message="You need to set a password.")
        if not request.form.get("confirmation"):
            return apology(message="You need to confirm your password.")
        if request.form.get("password") != request.form.get("confirmation"):
            return apology(message="Passwords do not match.")
        # Checks if user already exists. If not, creates a password hash and registers user.
        try:
            name = request.form.get("username")
            passhash = generate_password_hash(request.form.get("password"))
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", name, passhash)
            userid = db.execute("SELECT id FROM users WHERE username = ?", name)
            session["user_id"] = userid[0]["id"]
            return redirect("/")
        # Displays an error message for already existing users.
        except ValueError:
            return apology(message="This username already exists.")
    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("shares") or int(request.form.get("shares")) < 1:
            return apology(message="INVALID INPUT")
        if lookup(request.form.get("symbol")) == None:
            return apology(message="INVALID SYMBOL")
        stock = lookup(request.form.get("symbol"))
        row = db.execute("SELECT * FROM properties WHERE user_id = ? AND symbol = ?",
                         session["user_id"], stock["symbol"])
        if len(row) != 1:
            return apology(message="You do not have any share for this stock.")
        sharenum = int(request.form.get("shares"))
        if sharenum > row[0]["shares"]:
            return apology(message="You do not have enough shares.")
        funds = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        fund = funds[0]["cash"]
        gain = sharenum * stock["price"]
        fund = fund + gain
        db.execute("UPDATE users SET cash = ? WHERE id = ?", fund, session["user_id"])
        if sharenum == row[0]["shares"]:
            db.execute("DELETE FROM properties WHERE user_id = ? AND symbol = ?",
                       session["user_id"], stock["symbol"])
        else:
            row[0]["shares"] = row[0]["shares"] - sharenum
            db.execute("UPDATE properties SET shares = ? WHERE user_id = ? AND symbol = ?",
                       row[0]["shares"], session["user_id"], stock["symbol"])
        t = datetime.datetime.now(pytz.timezone("Turkey")).strftime('%Y-%m-%d %H:%M:%S')
        db.execute("INSERT INTO history (user_id, symbol, shares, price, time) VALUES(?, ?, ?, ?, ?)",
                   session["user_id"], stock["symbol"], -int(request.form.get("shares")), stock["price"], t)
        return redirect("/")
    signs = db.execute(
        "SELECT properties.symbol FROM properties WHERE properties.user_id = ?", session["user_id"])
    return render_template("sell.html", symbols=signs)
