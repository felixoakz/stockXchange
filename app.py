import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd
import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


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
    userID = session["user_id"]
    try:
        # querrying symbol and shares from user (symbol, shares)SELECT symbol, SUM(shares) as shares, SUM(share_price) as price
        portifolio = db.execute("SELECT symbol, SUM(shares) as shares, SUM(share_price) as price FROM history WHERE user_id = ? GROUP BY symbol", userID)
        # loop to add current stock value and details to the portifolio variable (name, price)
        for i in range(0, len(portifolio)):
            currentValue = lookup(portifolio[i]["symbol"])
            portifolio[i].update(currentValue)
        # inserting into TOTAL variable the user balance and formatting it with the USD function from helpers
        cash = db.execute("SELECT cash from users WHERE id = :id", id=userID)
        cash = round(float(cash[0]['cash']), 2)
        # inserting into CASH variable the total of all stocks user has (total cash from stocks)
        total = db.execute("SELECT SUM(shares * share_price) as cash FROM history WHERE user_id = :id", id=userID)
        total = round(float(total[0]['cash']), 2)
        total = usd(total + cash)
        return render_template("index.html", portifolio=portifolio, cash=cash, total=total)
    except:
        return apology("buy some stocks first!", 200)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    # user reaching route via GET
    if request.method == "GET":
        return render_template("buy.html")
    # client reaching route via POST
    else:
        # requesting SYMBOL and SHARES via POST from HTML form
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        try:
            shares = float(shares)
            if shares <= 0 or not shares.is_integer():
                return apology("apology, must be a positive integer", 400)
        except ValueError:
            return apology("apology, must be a numeric value", 400)
        # returning apology if stock or shares input is none via the variable symbol from HTML form on /buy
        if not symbol or not shares:
            return apology("must inform stock symbol and ammount of shares", 400)
        # lookup function on symbol, inserting value into stock variable (is a dictionary with 'name','price','symbol')
        stock = lookup(symbol)
        # show apollogy if symbol does not exists
        if stock == None:
            return apology("stock symbol does not exist", 400)
        # insert into total variable the transaction total casted to type:FLOAT
        total = stock["price"] * float(shares)
        # new variable to store user id as an INT
        userID = session['user_id']
        # verifing users current balance and inserting it to a variable
        userbalance = db.execute("SELECT cash from users WHERE id = :id", id=userID)
        userbalance = userbalance[0]["cash"]
        # return apology if balance less than transaction cost
        if total > userbalance:
            return apology("not enough funds", 400)
        # inserting into variable new balance after buying
        newbalance = userbalance - total
        # updating balance in table users, by userID
        db.execute("UPDATE users SET cash = (?) WHERE id = (?)", newbalance, userID)
        # inserting into new table history the transaction details
        db.execute("INSERT INTO history (user_id, symbol, shares, share_price, date) VALUES (?, ?, ?, ?, ?)",
                   userID, stock["symbol"], shares, stock["price"], datetime.datetime.now())
        # flasks flashing message to display confirmation temporary message
        flash("Shares successfully bought!")
        return redirect("/")


@app.route("/history")
@login_required
def history():
    if request.method == "GET":
        userID = session["user_id"]
        # querry all transactions data database
        transactions = db.execute("SELECT * FROM history WHERE user_id = :id", id=userID)
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    # Forget any user_id
    session.clear()
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password")
        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        # Redirect user to home page
        return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    # Forget any user_id
    session.clear()
    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    # user reaching route via GET
    if request.method == "GET":
        return render_template("quote.html")
    # client reaching route via POST
    else:
        # casting symbol from HMTL from to a variable SYMBOL
        symbol = request.form.get("symbol")
        # returning apology if stock input is none via the variable symbol from HTML form on /quote
        if not symbol:
            return apology("must inform stock symbol", 400)
        # using lookup for retrieving stock data and if it does not exist, return an apology
        quoted = lookup(symbol)
        # this case would return None or empty string, using if not is better than try/except(mostly used for RUNTIME errors)
        if quoted == None:
            return apology("stock symbol does not exist", 400)
        # rendering quoted form with details from the variable quoted
    return render_template("quoted.html", quoted=quoted)


@app.route("/register", methods=["GET", "POST"])
def register():
    # Forget any user_id
    session.clear()
    # User reached route via GET
    if request.method == "GET":
        return render_template("register.html")
    # User reached route via POST (as by submitting a form via POST)
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        # Ensure username was submitted
        if not username:
            return apology("must provide username")
        # Ensure password was submitted
        elif not password:
            return apology("must provide password")
        # Ensure confirmation was submitted
        elif not confirmation:
            return apology("must confirm password")
        # ensure password fields are not the same
        elif password != confirmation:
            return apology("password and confirmation are not the same")

    # all that being ok, creating user and sending to the database
        # hashing the password
        hash = generate_password_hash(password)
        # register user and password, throw exception if user already exists (SQLite3 IntegrityError exception will be raised)
        try:
            user = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
        except:
            return apology("username already exists!", 400)
        # save user session, redirect user to index
        session["user_id"] = user
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # showing all stocks user has
    if request.method == "GET":
        userID = session["user_id"]
        stocks = db.execute("SELECT symbol FROM history WHERE user_id = :id", id=userID)
        return render_template("sell.html", stocks=stocks)
    else:
        # casting selected options to its variables
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        userID = session["user_id"]
        # error handling if symbol was not selected
        if not symbol:
            return apology("must select a symbol")
        # querrying user shares
        user_shares = db.execute("SELECT shares FROM history WHERE user_id = :id AND symbol = :symbol", id=userID, symbol=symbol)
        user_shares = int(user_shares[0]['shares'])
        # displayt apology if user has less shares than what selected
        if shares > user_shares:
            return apology("too much stocks selected")
        # lookup function for inserting selected stock current value and user cash
        stock = lookup(symbol)
        userbalance = db.execute("SELECT cash from users WHERE id = :id", id=userID)
        userbalance = userbalance[0]["cash"]
        # doing calculation of new balance after the transaction
        transactiontotal = shares * stock["price"]
        usernewbalance = userbalance + transactiontotal
        # querries for update user balance on USER table and user transaction into history table
        db.execute("UPDATE users SET cash = ? WHERE id = ?", usernewbalance, userID)
        db.execute("INSERT INTO history (user_id, symbol, shares, share_price, date) VALUES(?, ?, ?, ?, ?)",
                   userID, stock["symbol"], (-1)*shares, (-1)*stock["price"], datetime.datetime.now())
        # flash confirmation message on redirection to homepage
        flash("Shares successfully sold!")
        return redirect("/")


@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    if request.method == "GET":
        return render_template("addcash.html")
    # client reaching route via POST
    else:
        # casting symbol from HMTL from to a variable ADDCASH
        addcash = request.form.get("addcash")
        # returning apology if user did not input anything
        if not addcash:
            return apology("must inform some value")
        userID = session["user_id"]
        # checking user balance then addint to selected value
        userbalance = db.execute("SELECT cash from users WHERE id = :id", id=userID)
        userbalance = userbalance[0]["cash"]
        add = userbalance + float(addcash)
        # inserting new sum according to new value to database
        db.execute("UPDATE users SET cash = :add WHERE id = :id", add=add, id=userID)
        flash("Amount successfully added!")
        return redirect("/")

# write updates before publishing
