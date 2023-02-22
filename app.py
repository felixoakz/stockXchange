import os
import datetime

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv
from helpers import apology, login_required, lookup, usd, execute_query


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded while editing aplication
app.config["TEMPLATES_AUTO_RELOAD"] = True

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# aplication routes


@app.route("/")
@login_required
def index():
    user_id = session["user_id"]
    try:
        # querrying symbol and shares from user (symbol, shares)SELECT symbol, SUM(shares) as shares, SUM(share_price) as price
        portifolio = execute_query("""SELECT symbol, SUM(shares) as shares, SUM(share_price) as price FROM history 
                                   WHERE user_id = %s GROUP BY symbol""", (user_id,), fetch=True
                                   )

        # loop to add current stock value and details to the portifolio variable (name, price)
        for i in range(0, len(portifolio)):
            try:
                current_value = lookup(portifolio[i]["symbol"])
                portifolio[i].update(current_value)
            except TypeError:
                return apology("Sorry, the API reached its limits\n(5 requests/minute)\nTry again in a few minutes.")

        cash = execute_query("SELECT cash from users WHERE id = %s", (user_id,), fetch=True
                             )  # returns a list with a key value pair

        # formatting to a float with 2 decimals
        cash = round(float(cash[0]['cash']), 2)

        total = execute_query("""
                              SELECT SUM(shares * share_price) AS cash
                                FROM (
                                SELECT user_id, symbol, SUM(shares) AS shares, share_price
                                FROM history
                                WHERE user_id = %s
                                GROUP BY symbol
                                )
                                GROUP BY user_id;
                              """, (user_id,), fetch=True
                              )

        total = round(float(total[0]['cash']), 2)
        total = usd(total + cash)

        return render_template("index.html", portifolio=portifolio, cash=cash, total=total)

    except Exception as Ex:
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(Ex).__name__, Ex.args)
        print(message)

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
        try:
            stock = lookup(symbol)
        except TypeError:
            return apology("Sorry, the API reached its limits\n(5 requests/minute)\nTry again in a few minutes.")

        # show apollogy if symbol does not exists
        if stock == None:
            return apology("stock symbol does not exist", 400)

        # insert into total variable the transaction total casted to type:FLOAT
        total = stock["price"] * float(shares)

        # new variable to store user id as an INT
        user_id = session['user_id']

        # verifing users current balance and inserting it to a variable
        userbalance = execute_query(
            "SELECT cash from users WHERE id = %s", (user_id,), fetch=True
        )
        userbalance = userbalance[0]["cash"]

        # return apology if balance less than transaction cost
        if total > userbalance:
            return apology("not enough funds", 400)

        # inserting into variable new balance after buying
        newbalance = userbalance - total

        # updating balance in table users, by user_id
        execute_query("UPDATE users SET cash = %s WHERE id = %s",
                      (newbalance, user_id), fetch=False
                      )

        # inserting into new table history the transaction details
        execute_query("INSERT INTO history (user_id, symbol, shares, share_price, date) VALUES (%s, %s, %s, %s, %s)",
                      (user_id, stock["symbol"], shares,
                       stock["price"], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                      fetch=False
                      )

        # flasks flashing message to display confirmation temporary message
        flash("Shares successfully bought!")
        return redirect("/")


@app.route("/history")
@login_required
def history():
    if request.method == "GET":
        user_id = session["user_id"]

        # querry all transactions data database
        transactions = execute_query(
            "SELECT * FROM history WHERE user_id = %s", (user_id,), fetch=True
        )

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure username was submitted
        if not username:
            return apology("must provide username")

        # Ensure password was submitted
        elif not password:
            return apology("must provide password")

        # Query database for username
        rows = execute_query(
            "SELECT * FROM users WHERE username = %s", (username,), fetch=True
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
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
        try:
            quoted = lookup(symbol)
        except TypeError:
            return apology("Sorry, the API reached its limits\n(5 requests/minute)\nTry again in a few minutes.")

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
        email = request.form.get("email")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", "error")

        # validating email with @
        elif not '@' in email:
            return apology("aparently not an email", "error")

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", "error")

        # Ensure confirmation was submitted
        elif not confirmation:
            return apology("must confirm password", "error")

        # Ensure password fields are not the same
        elif password != confirmation:
            return apology("password and confirmation are not the same")

    # all that being ok, creating user and sending to the database
        # hashing the password
        hash = generate_password_hash(password)

        # register user and password, throw exception if user already exists (SQLite3 IntegrityError exception will be raised)
        try:
            user = execute_query(
                "INSERT INTO users (username, email, hash) VALUES (%s, %s, %s)", (username, email, hash), fetch=False
            )
        except:
            return apology("username or email already exists!", "error")

        # save user session, redirect user to index
        session["user_id"] = user
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # showing all stocks user has
    if request.method == "GET":
        user_id = session["user_id"]

        stocks = execute_query(
            "SELECT DISTINCT symbol FROM history WHERE user_id = %s", (user_id,), fetch=True
        )

        return render_template("sell.html", stocks=stocks)

    else:
        # casting selected options to its variables
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        user_id = session["user_id"]

        # error handling if symbol was not selected
        if not symbol:
            return apology("must select a symbol")

        # querrying user shares
        user_shares = execute_query(
            "SELECT shares FROM history WHERE user_id = %s AND symbol = %s", (user_id, symbol), fetch=True
        )

        user_shares = int(user_shares[0]['shares'])

        # displayt apology if user has less shares than what selected
        if shares > user_shares:
            return apology("too much stocks selected")

        # lookup function for inserting selected stock current value and user cash
        try:
            stock = lookup(symbol)
        except TypeError:
            return apology("Sorry, the API reached its limits\n(5 requests/minute)\nTry again in a few minutes.")

        userbalance = execute_query(
            "SELECT cash from users WHERE id = %s", (user_id,), fetch=True
        )

        userbalance = userbalance[0]["cash"]

        # doing calculation of new balance after the transaction
        transaction_total = shares * stock["price"]
        usernewbalance = userbalance + transaction_total

        # querries for update user balance on USER table and user transaction into history table
        execute_query("UPDATE users SET cash = %s WHERE id = %s",
                      (usernewbalance, user_id), fetch=False
                      )

        execute_query("""INSERT INTO history (user_id, symbol,
                      shares, share_price, date) VALUES (%s, %s, %s, %s, %s)""",
                      (user_id, stock["symbol"], (-1)*shares, (-1)*stock["price"],
                       datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")), fetch=False
                      )

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
        user_id = session["user_id"]

        # checking user balance then addint to selected value
        userbalance = execute_query(
            "SELECT cash from users WHERE id = %s", (user_id,), fetch=True
        )

        userbalance = userbalance[0]["cash"]
        add = userbalance + float(addcash)

        # inserting new sum according to new value to database
        execute_query("UPDATE users SET cash = %s WHERE id = %s",
                      (add, user_id), fetch=False)
        flash("Amount successfully added!")
        return redirect("/")


@app.route("/users")
def users():
    if request.method == "GET":

        users = execute_query("SELECT * FROM users")

    return render_template("users.html", users=users)


# live preview flask app edits (will leave this here just in case)
if __name__ == "__main__":
    app.debug = True
    app.run()
