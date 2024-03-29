import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)
app.debug = True
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
def index():

    if 'user_id' not in session:
        total_transactions = db.execute('SELECT COUNT(*) FROM transactions')[0]['COUNT(*)']
        return render_template('home.html', total_transactions = total_transactions)
    """Show portfolio of stocks"""

    user = db.execute('SELECT * FROM users WHERE id = ? LIMIT 1', session['user_id'])[0]
    rows = db.execute('SELECT * FROM inventory WHERE user_id = ?', session['user_id'])
    total = user['cash']
    for row in rows:
        quote = lookup(row['symbol'])
        row['total_price'] = int(row['shares']) * quote['price']
        row['price'] = quote['price']
        row['name'] = quote['name']
        row['symbol'] = quote['symbol']
        total += row['total_price']
    return render_template('index.html', cash=user['cash'], rows=rows, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    elif request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not symbol or symbol == "":
            return render_template("buy.html", error="Invalid symbol")

        # Check if shares is a valid positive number (non-fractional)
        try:
            shares = float(shares)
            if shares <= 0 or not shares.is_integer():
                raise ValueError("Shares must be a positive integer.")
            shares = int(shares)  # Convert back to int if it's a whole number
        except ValueError:
            return render_template("buy.html", error="Invalid shares")
        shares = int(shares)
        # check if symbol exists in Yahoo Finance
        quote = lookup(symbol)
        if quote is None:
            return render_template("buy.html", error = "There is no stock with this symbol")
        user = db.execute('SELECT * FROM users WHERE id = ? LIMIT 1', session['user_id'])[0]

        total_cost = shares * quote['price']
        if user['cash'] < total_cost:
            return render_template("buy.html", error = "Not enough cash")

        # Update user's cash
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", total_cost, session['user_id'])

        # Insert transaction record
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, transaction_date) VALUES (?, ?, ?, ?, datetime('now'))",
                   session['user_id'], symbol, shares, quote['price'])

        # Update inventory
        inventory = db.execute('SELECT * FROM inventory WHERE user_id = ? AND symbol = ?', session['user_id'], symbol)

        if len(inventory) == 0:
            # If row does not exist, create new row with shares as amount
            db.execute("INSERT INTO inventory (user_id, symbol, shares) VALUES (?, ?, ?)",
                       session['user_id'], symbol, shares)
        else:
            # If row exist, add shares to amount
            db.execute("UPDATE inventory SET shares = shares + ? WHERE user_id = ? AND symbol = ?",
                       shares, session['user_id'], symbol)

        return redirect("/")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("select * from transactions")
    return render_template('history.html', rows = rows)


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
    """Get stock quote."""
    if request.method == 'GET':
        return render_template('quote.html')
    else:
        symbol = request.form.get('symbol')
        if not symbol or symbol == "":
            return render_template('quote.html', error = "Symbol cannot be blank")
        #Check if symbol is a valid symbol
        quote = lookup(symbol)
        if quote is None:
            return render_template('quote.html', error = "Invalid symbol")
        print(quote)

        return render_template('quote.html', quote = quote)




@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get('confirmation')

        if username == "":
            return apology("")
        if password != confirmation:
            return apology("")
        print(username)
        print(password)
        hashed_password = generate_password_hash(password)
        try:
            result = db.execute(
                "INSERT INTO users (username, hash) VALUES (:username, :hash)",
                username=username,
                hash=hashed_password,
            )
            rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username"))
            session["user_id"] = rows[0]["id"]
            return redirect("/")
        except:
            return apology("Failed creating an account")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == 'GET':
        symbols = db.execute('SELECT symbol FROM inventory WHERE user_id = ?', session['user_id'])
        return render_template("sell.html", symbols = symbols)
    elif request.method == 'POST':
        symbol = request.form.get('symbol')
        amount = int(request.form.get('shares'))
        symbols = db.execute('SELECT symbol FROM inventory WHERE user_id = ?', session['user_id'])
        # Get the current stock price
        quote = lookup(symbol)
        if quote is None:
            return render_template("sell.html", error = "Invalid symbol", symbols = symbols)

        # Get current shares of the symbol for the user
        row = db.execute('SELECT * FROM inventory WHERE user_id = ? AND symbol = ?', session['user_id'], symbol)[0]
        print(row)
        # Check if there are enough shares
        if not row or amount > row['shares']:
            return render_template('sell.html', error = "You don't own that much share", symbols = symbols)

        # Update cash
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", amount * quote['price'], session['user_id'])

        # Update inventory and remove row if row has 0 share
        new_shares = row['shares'] - amount
        if new_shares == 0:
            db.execute("DELETE FROM inventory WHERE user_id = ? AND symbol = ?", session['user_id'], symbol)
        else:
            db.execute("UPDATE inventory SET shares = ? WHERE user_id = ? AND symbol = ?", new_shares, session['user_id'], symbol)

        # Update transactions
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, transaction_date) VALUES (?, ?, ?, ?, datetime('now'))",
                   session['user_id'], symbol, -amount, quote['price'])

        return redirect("/")

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)