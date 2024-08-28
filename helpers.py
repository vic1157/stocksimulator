import csv
import datetime
import pytz
import requests
import urllib
import uuid
import string

from cs50 import SQL
from flask import redirect, render_template, request, session
from functools import wraps

db = SQL("sqlite:///finance.db")

def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Prepare API request
    symbol = symbol.upper()
    end = datetime.datetime.now(pytz.timezone("US/Eastern"))
    start = end - datetime.timedelta(days=7)

    # Yahoo Finance API
    url = (
        f"https://query1.finance.yahoo.com/v7/finance/download/{urllib.parse.quote_plus(symbol)}"
        f"?period1={int(start.timestamp())}"
        f"&period2={int(end.timestamp())}"
        f"&interval=1d&events=history&includeAdjustedClose=true"
    )

    # Query API
    try:
        response = requests.get(
            url,
            cookies={"session": str(uuid.uuid4())},
            headers={"Accept": "*/*", "User-Agent": request.headers.get("User-Agent")},
        )
        response.raise_for_status()

        # CSV header: Date,Open,High,Low,Close,Adj Close,Volume
        quotes = list(csv.DictReader(response.content.decode("utf-8").splitlines()))
        price = round(float(quotes[-1]["Adj Close"]), 2)
        return {"price": price, "symbol": symbol}
    except (KeyError, IndexError, requests.RequestException, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


def execute_buy(shares, user, symbol):
	stock_name = symbol["symbol"]
	price = float(symbol["price"])

	if shares < 1:
			return apology("please enter a positive amount of shares")
	pur_price = (shares)*(price)

	cash_query = db.execute("SELECT cash FROM users WHERE id = ?", user)
	cash = cash_query[0]["cash"]

	if cash > pur_price:
		upd_cash = cash - pur_price
		db.execute("UPDATE users SET cash = ? WHERE id = ?", upd_cash, user)
		db.execute("INSERT INTO transactions (user_id, stock, share_amt, price, type) VALUES (?,?,?,?,?)",
						user, stock_name, shares, pur_price, "buy")
	else:
		return apology("NOT ENOUGH MUGG$$$!!")


def execute_sell(user, symbol, shares_sell, share_price):
	shares_owned = db.execute("SELECT SUM(share_amt) AS share_amt FROM transactions WHERE user_id = ? AND stock LIKE ? GROUP BY stock", session["user_id"], "%" + symbol + "%")
	shares_owned = shares_owned[0]["share_amt"]

	if shares_sell > shares_owned:
		return apology("Insufficient Shares!")
	elif shares_sell < 1:
		return apology("Please enter an integer of 1 or a larger value")
	else:
		sell_price = (shares_sell)*(share_price)
		db.execute("INSERT INTO transactions (user_id, stock, share_amt, price, type) VALUES (?,?,?,?,?)",
							user, symbol, (-1)*(shares_sell), sell_price, "sell")

	cash_query = db.execute("SELECT cash FROM users WHERE id = ?", user)
	cash = cash_query[0]["cash"]

	upd_cash = cash + sell_price
	db.execute("UPDATE users SET cash = ? WHERE id = ?", upd_cash, user)


def verify_password(password):

	def is_special(char):
		return char in string.punctuation

	length_count = 0
	lower_bool = False
	upper_bool = False
	numeric_bool = False
	special_bool = False


	for i in range(len(password)):
		if password[i].islower():
			lower_bool = True
		if password[i].isupper():
			upper_bool = True
		if password[i].isnumeric():
			numeric_bool = True
		if is_special(password[i]):
			special_bool = True
		length_count += 1

	if lower_bool and upper_bool and numeric_bool and special_bool:
		if not length_count >= 8:
			return apology("Please enter a password at least 8 characters long")
	else:
		return apology("Please the criteria required for the password")
