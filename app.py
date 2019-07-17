import os

from flask import Flask, session, render_template, request, redirect, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


import requests
app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    if session.get("user_id") is None:
        return redirect("/login")
    else:
        return render_template('index.html', message = session.get("user_name"))

@app.route("/login", methods=['POST', 'GET'])
def login():


    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        user = db.execute("SELECT * FROM users WHERE username = :username AND password = :password",
                            {"username": username, "password": password})
        result = user.fetchone()

        if result == None:
            return render_template('error.html', message="Incorrect Username and/or Password.")




        session["user_id"] = result[0]
        session["user_name"] = result[1]

        return redirect("/")
    else:
        return render_template('login.html')



@app.route("/register", methods=['POST', 'GET'])
def register():
    session.clear()

    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']

        userCheck = db.execute("SELECT * FROM users WHERE username = :username",
                            {"username": username}).fetchone()

        if userCheck:
            return render_template('error.html', message="Username already exists.")
        else:
            db.execute("INSERT INTO users (username, password) VALUES (:username, :password)",
                                {"username":username,
                                 "password":password})
            db.commit()

            return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect('/')



@app.route("/search", methods=['GET'])
def search():
    if session.get("user_id") is None:
            return redirect("/login")
    search = "%" + request.args.get("book") + "%"

    rows = db.execute("SELECT isbn, title, author, year FROM books WHERE isbn ILIKE :search OR title ILIKE :search OR author ILIKE :search", {"search": search})
    if rows.rowcount == 0:
        return render_template("error.html", message="No book with such details exist.")
    else:
        books = rows.fetchall()
        return render_template("results.html", books=books)



@app.route('/book/<isbn>', methods=["GET","POST"])
def book(isbn):
    if session.get("user_id") is None:
        return redirect("/login")

    if request.method == "POST":
        currentuser = session["user_name"]

        rating = request.form.get("rating")
        comment = request.form.get("comment")

        row = db.execute("SELECT * FROM reviews WHERE username = :username AND isbn = :isbn",
                     {"username": currentuser,
                     "isbn": isbn})

        if row.rowcount == 1:
            return render_template("error.html", message="Sorry, you cannot submit another review.")

        else:
            rating = int(rating)
            db.execute("INSERT INTO reviews (isbn, review, rating, username) VALUES(:isbn, :comment, :rating, :username)",
            {"isbn": isbn,
            "comment": comment,
            "rating": rating,
            "username" : currentuser})

            db.commit()

            return redirect("/book/"+isbn)

    else:
        row = db.execute("select isbn, title, author, year FROM books WHERE isbn = :isbn", {"isbn": isbn})
        book_details = row.fetchone()


        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "1KDsLIzpbQ1aEdgZYWVVZg", "isbns": isbn})
        res = res.json()

        results = db.execute("SELECT users.username, review, rating FROM users INNER JOIN reviews ON users.username = reviews.username WHERE isbn = :isbn", {"isbn": isbn})

        reviews = results.fetchall()

        return render_template("book.html", book_details=book_details, reviews=reviews, res=res)


@app.route("/api/<isbn>", methods=['GET'])
def api_call(isbn):
    if session.get("user_id") is None:
        return redirect("/login")

    row = db.execute("SELECT books.isbn,title,author,year, COUNT(reviews.isbn) AS review_count, AVG(reviews.rating) AS average_rating FROM books INNER JOIN reviews ON books.isbn=reviews.isbn WHERE books.isbn= :isbn GROUP BY books.isbn",{"isbn": isbn})

    if row.rowcount != 1:
        return jsonify({"Error": "Invalid book ISBN"}), 422

    tmp = row.fetchone()

    result = dict(tmp.items())

    result['average_rating'] = float('%.2f'%(result['average_rating']))

    return jsonify(result)
