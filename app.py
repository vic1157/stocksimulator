import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, execute_buy, execute_sell, verify_password


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


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""

    portfolio = db.execute("SELECT stock, SUM(share_amt) AS stock_qty, SUM(price) AS tstock_price FROM transactions WHERE user_id = ? GROUP BY stock HAVING SUM(share_amt) > 0", session["user_id"])
    print(portfolio)

    stocks_info = {}
    total_val = 0

    for i in range(len(portfolio)):
        stocks = portfolio[i]["stock"]
        stock_qty = portfolio[i]["stock_qty"]

        lkp = lookup(stocks)
        print(lkp)
        uptd_price = float(lkp["price"])
        current_val = uptd_price*(stock_qty)

        stocks_info[stocks] = [stock_qty, uptd_price, usd(current_val)]
        total_val += current_val

    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = round(cash[0]["cash"], 2)

    grand_total = cash + total_val
    grand_total = usd(round(grand_total, 2))
    cash = usd(cash)
    total_val = usd(total_val)

    if request.method == "POST":
        user = session["user_id"]

        stock_buy = request.form.get("stock_buy")
        stock_sell = request.form.get("stock_sell")

        if stock_buy and not stock_sell:
            stock_buy = lookup(stock_buy)
            buy_shares = request.form.get("buy_shares")
            if not buy_shares:
                return apology("Please enter the amt of shares you want to buy")

            try:
                buy_shares = int(buy_shares)
            except ValueError:
                return apology("Please enter an integer!")

            buy = execute_buy(buy_shares, user, stock_buy)
            if buy:
                return buy
            else:
                return redirect("/")

        elif stock_sell and not stock_buy:
            stock_price = float(request.form.get("stock_price"))
            if not stock_price:
                return apology("Cannot locate the stock price for the shares you want to sell")

            shares_sell = request.form.get("shares_sell")
            if not shares_sell:
                return apology("Please enter the amount of shares you want to sell")

            try:
                shares_sell = int(shares_sell)
            except ValueError:
                return apology("Please enter an integer!")

            sell = execute_sell(user, stock_sell, shares_sell, stock_price)

            if sell:
                return sell
            else:
                return redirect("/")


        elif not stock_sell and not stock_buy:
            return apology("Please enter a value for either stock_sell or stock_buy!")
        else:
            return apology("You cannot enter values for both stock_sell and stock_buy!")


    return render_template("portfolio.html", stocks_info=stocks_info, total_val=total_val, cash=cash, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        symbol = request.form.get("symbol")
        lkp_symbol = lookup(symbol)

        if not symbol or not lkp_symbol:
            return apology("please input a valid stock")

        shares = request.form.get("shares")

        try:
            shares = int(shares)
        except ValueError:
            return apology("please input a number!")

        else:
            if execute_buy(shares, session["user_id"], lkp_symbol) is not None:
                return execute_buy(shares, session["user_id"], lkp_symbol)
            else:
                return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    print("show out")
    stocks = db.execute("SELECT stock, share_amt, price, type FROM transactions WHERE user_id = ? ORDER BY stock", session["user_id"])

    for i in range(len(stocks)):
        stocks[i]["price"] = usd(float(stocks[i]["price"]))

    return render_template("history.html", stocks=stocks)


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

@app.route("/add-cash", methods=["GET", "POST"])
def add_cash():
    """Allocate add'l cash for user"""

    if request.method == "POST":
        add_cash = request.form.get("cash")

        if not add_cash:
            return apology("Please enter add'l cash you want to add")

        try:
            add_cash = round(float(add_cash), 2)
        except ValueError:
            return apology("Please enter a number!")

        if not 0 <= add_cash <= 5_000:
            return apology("You can only add amounts between $0 and $5,000")

        orig_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        orig_cash = round(orig_cash[0]["cash"], 2)

        new_bal = orig_cash + add_cash

        if new_bal > 20_000:
            amt_exceed = new_bal - 20_000
            return apology(f"Not successful. You have exceeded the limit by ${amt_exceed:,.2f}")

        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_bal, session["user_id"])
        return redirect("/")


    return render_template("newcash.html")



@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        print(symbol)

        if not symbol:
            return apology("Please enter a stock ticker value")

        symbol = lookup(symbol)

        if not symbol:
            return apology("Please enter a valid stock ticker")

        name = symbol["symbol"]
        price = usd(symbol["price"])

        return render_template("quoted.html", name=name, price=price)

    else:
        return render_template("quote.html")


@app.route("/reset-password", methods=["GET", "POST"])
@login_required
def reset_password():

    if request.method == "POST":
        old_pw = request.form.get("old_pw")
        if not old_pw:
            return apology("Please enter a password")

        oldpw_hash = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])
        oldpw_hash = oldpw_hash[0]["hash"]

        if not check_password_hash(oldpw_hash, old_pw):
            return apology("Old password is incorrect!")

        new_pw = request.form.get("new_pw")
        cnew_pw = request.form.get("cnew_pw")

        if not new_pw and not cnew_pw:
            return apology("Please enter a new password")

        if not new_pw == cnew_pw:
            return apology("New and old passwords do not match!")

        if verify_password(new_pw):
            return verify_password(new_pw)

        db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(new_pw), session["user_id"])
        return redirect("/")


    return render_template("rpassword.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation  = request.form.get("confirmation")

        if not username:
            return apology("please enter a username!")

        check_username = db.execute("SELECT username from users WHERE username = ?", username)

        if not check_username:
                pass
        else:
            return apology("please enter a username that doesn't exist!")

        if not password:
            return apology("please enter a password!")

        if not password == confirmation:
            return apology("please make sure that both passwords match!")

        if verify_password(password):
            return verify_password(password)

        password = generate_password_hash(password)

        db.execute("INSERT INTO users (username, hash) VALUES (?,?)", username, password)
        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    portfolio = db.execute("SELECT stock, SUM(share_amt) AS stock_qty, SUM(price) AS tstock_price FROM transactions WHERE user_id = ? GROUP BY stock HAVING SUM(share_amt) > 0", session["user_id"])
    stock_info = {}

    for i in range(len(portfolio)):
        stock_name = portfolio[i]["stock"]
        stock_info[stock_name] = portfolio[i]["stock_qty"]

    if request.method == "POST":

        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please submit a valid stock")

        shares = request.form.get("shares")
        if not shares:
            return apology("Please enter a proper amount of shares")

        try:
            shares = int(shares)
        except ValueError:
            return apology("Please enter an integer")

        share_price = lookup(symbol)["price"]

        if execute_sell(session["user_id"], symbol, shares, share_price) is not None:
            return execute_sell(session["user_id"], symbol, shares, share_price)
        else:
            return redirect("/")

    return render_template("sell.html", stocks=stock_info)
