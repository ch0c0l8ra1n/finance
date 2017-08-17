from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    rows = db.execute("SELECT * FROM portfolio WHERE userid = :userid AND shares > 0",userid=session["user_id"])
    usercash = db.execute("SELECT cash FROM users WHERE id = :id",id=session["user_id"])
    uc = usercash[0]["cash"]
    sv = 0
    for row in rows:
        sv = sv + float(row["price"]) * float(row["shares"])
    return render_template("index.html",stocks=rows,cash=uc,total=sv+uc)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        if request.form.get("symbol") == "":
            return apology("Must provide symbol")
        elif request.form.get("shares") == "":
            return apology("must provide no of shares")
        elif float(request.form.get("shares")) % 1 != 0:
            return apology("Must be integer")
        temp = lookup(request.form.get("symbol"))
        if temp == None:
            return apology("No such share")
        row = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        if float(temp["price"]) * int(request.form.get("shares")) > float(row[0]["cash"]):
            return apology("You peasant")
        result = db.execute("INSERT INTO transactions (userid,symbol,name,shares,price) VALUES (:userid,:symbol,:name,:shares,:price)",userid=session["user_id"],symbol=temp["symbol"],name=temp["name"],shares=request.form.get("shares"),price=temp["price"])
        if result == None:
            return apology("Failed")
        cost = row[0]["cash"] - (float(temp["price"]) * int(request.form.get("shares")))
        new = db.execute("SELECT * FROM portfolio WHERE symbol = :symbol ",symbol=temp["symbol"])
        if not new:
            db.execute("INSERT INTO portfolio (userid,symbol,name,shares,price) VALUES (:userid,:symbol,:name,:shares,:price)",userid=session["user_id"],symbol=temp["symbol"],name=temp["name"],shares=request.form.get("shares"),price=temp["price"])
        else:
            newshares = 0
            newshares = float(request.form.get("shares"))+float(new[0]["shares"])
            db.execute("UPDATE portfolio SET shares = :shares WHERE userid = :userid AND symbol = :symbol",shares=newshares,userid=session["user_id"],symbol=temp["symbol"])
        db.execute("UPDATE users SET cash = :cash WHERE id = :id ",cash=cost,id=session["user_id"])
        return redirect(url_for("index"))
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    rows = db.execute("SELECT * FROM transactions WHERE userid = :userid",userid=session["user_id"])
    return render_template("history.html",stocks=rows)
    
@app.route("/cashadd", methods=["GET", "POST"])
@login_required
def cashadd():
    if request.method == "POST":
        if request.form.get("extracash") == "":
            return apology("Must provide cash value")
        else:
            usercash = db.execute("SELECT cash FROM users WHERE id = :id",id=session["user_id"])
            addedcash = usercash[0]["cash"] + float(request.form.get("extracash"))
            db.execute("UPDATE users SET cash = :cash WHERE id = :id ",cash=addedcash ,id=session["user_id"])
            return redirect(url_for("index"))
    else:
        return render_template("cashadd.html")
    
    
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    #if user submitted form via post
    if request.method == "POST":
        #ensure quote was submitted
        if request.form.get("symbol") == "":
            return apology("Enter a Symbol")
        else:
            quote = lookup(request.form.get("symbol"))
            if quote == None:
                return apology("quote not found")
            return render_template("quoteresult.html",name=quote["name"],price=quote["price"])
    else:
        return render_template("quote.html")
        

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    #if user submitted form via post
    if request.method == "POST":
        #ensure username was submitted
        if request.form.get("username") == "":
            return apology("Enter Username")
        elif request.form.get("password") == "":
            return apology("Enter Password")
        elif request.form.get("repassword") != request.form.get("password"):
            return apology("Passwords incorrect")
        hash = pwd_context.encrypt(request.form.get("password"))
        result = db.execute("INSERT INTO users (username,hash) VALUES(:username,:hash)",username=request.form.get("username"),hash=hash)
        if not result:
            return apology("Username already exists ")
        session["user_id"] = result
        # redirect user to home page
        return redirect(url_for("index"))
        
    else:
        return render_template("register.html")
        
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        if request.form.get("symbol") == "":
            return apology("Enter symbol")
        elif request.form.get("shares") == "":
            return apology("Enter shares")
        elif float(request.form.get("shares")) % 1 != 0:
            return apology("Must be integer")
        temp = lookup(request.form.get("symbol"))
        if temp == None:
            return apology("No such share")
        test = db.execute("SELECT * FROM portfolio WHERE userid = :userid AND symbol = :symbol",userid=session["user_id"],symbol=temp["symbol"])
        if float(test[0]["shares"]) <  float(request.form.get("shares")):
            return apology("You dont own such share")
        else:
            db.execute("INSERT INTO transactions (userid,symbol,name,shares,price) VALUES (:userid,:symbol,:name,:shares,:price)",userid=session["user_id"],symbol=temp["symbol"],name=temp["name"],shares="-"+request.form.get("shares"),price=temp["price"])
            newshares = 0
            new = db.execute("SELECT * FROM portfolio WHERE symbol = :symbol ",symbol=temp["symbol"])
            newshares = float(new[0]["shares"]) - float(request.form.get("shares"))
            db.execute("UPDATE portfolio SET shares = :shares WHERE userid = :userid AND symbol = :symbol",shares=newshares,userid=session["user_id"],symbol=temp["symbol"])
        row = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        cost = row[0]["cash"] + (float(temp["price"]) * int(request.form.get("shares")))
        db.execute("UPDATE users SET cash = :cash WHERE id = :id ",cash=cost,id=session["user_id"])
        return redirect(url_for("index"))
    else:
        return render_template("sell.html")
        
