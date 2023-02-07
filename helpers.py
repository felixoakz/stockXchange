import os
from dotenv import load_dotenv
import requests
import csv
import sqlite3

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


def load_nasdaq_symbols():
    """Load list of nasdaq companies"""
    symbols = {}
    try:
        with open('nasdaq_companies.csv', 'r') as f:
            reader = csv.reader(f)
            next(reader)  # skip the header row
            for row in reader:
                symbol, name = row
                symbols[symbol] = name

    except Exception as e:
        print("An error occurred while reading the CSV file", e)
        return {}
    return symbols


# this function should have been 2 functions for  better viewing and maitenance
# but as i wrote a function to fit the place of an older one, i wrote as a single function
def lookup(symbol):
    """Look up quote for symbol."""
    symbol = symbol.upper().strip()

    # contact api
    load_dotenv()
    api_key = os.getenv("API_KEY")
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
    try:
        response = requests.get(url)

        # parse response
        stock_data = response.json()
        company_symbol = stock_data["Global Quote"]["01. symbol"]
        closing_price = float(stock_data["Global Quote"]["05. price"])

    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None

    nasdaq_symbols = load_nasdaq_symbols()
    company_name = nasdaq_symbols.get(symbol, "Unknown Company")

    return {
        "name": company_name,
        "price": closing_price,
        "symbol": company_symbol
    }


def execute_query(query, params=None, fetch=True):
    with sqlite3.connect("finance.db") as conn:
        cursor = conn.cursor()

        if params is None:
            cursor.execute(query)

        else:
            cursor.execute(query, params)

        if fetch:
            columns = [col[0] for col in cursor.description]
            result = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return result

        else:
            conn.commit()
