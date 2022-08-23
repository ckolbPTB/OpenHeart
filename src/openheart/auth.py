from sqlite3 import IntegrityError
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash


from openheart.db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route("/register", methods=['GET','POST'])
def register():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        db = get_db()

        error = None
        if not email:
            error = "Email is required."
        elif not password:
            error = "Password is required."
        if error is None:
            try:
                db.execute(
                    "INSERT INTO user (email, password) VALUES (?, ?)",
                    (email, generate_password_hash(password)),
                    )
                db.commit()
            except db.IntegrityError:
                error = f"Email {email} is already registered."
            else:
                return redirect(url_for("auth.login"))
        flash(error)

    return render_template('auth/register.html')


@bp.route("/login", methods=['GET', 'POST'])
def login():

    # if request.method == "POST":
    #     pass

    return render_template("auth/login.html")
