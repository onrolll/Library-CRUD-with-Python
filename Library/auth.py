import functools
from flask import (Blueprint, flash, g, redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from Library.db import get_db
from datetime import datetime as d

bp = Blueprint('auth',__name__,url_prefix='/auth')


@bp.route('/register', methods=('GET','POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        elif db.execute('SELECT id FROM user WHERE username = ?',(username,)).fetchone() is not None:
            error = 'User %s is already registered.'%(username)

        if error is None:
            db.execute('INSERT INTO user (username,password) VALUES (?,?)'
            ,(username, generate_password_hash(password)))
            db.commit()
            return redirect(url_for('auth.login'))

        flash(error)

    return render_template('auth/register.html')

@bp.route('login',methods=('GET','POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        user = db.execute('SELECT * FROM user WHERE username = ?',(username,)).fetchone()

        if user is None:
            error = 'Incorrect user'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password'
        
        user_books = db.execute('SELECT return_by, b.title AS title FROM user_book as ub JOIN books AS b ON ub.book_id = b.id WHERE user_id = ? ORDER BY return_by',(user['id'],)).fetchall()
        books_to_return = []
        for book in user_books:
            if book['return_by'] < d.today():
                books_to_return.append(book['title'])
        if books_to_return != []:
            flash('You need to return %s before you could log in again.'%(', '.join(books_to_return)))
            return redirect(url_for('auth.login'))
        
        
        if error is None:
            session.clear()
            session['user_id'] = user['id']
            if user_books !=[] and user['borrowed' != -1]:
                book_to_return = user_books[0]
                flash(('Hello, %s! Please return %s by %s. Thank you!'%(username, book_to_return['title'], book_to_return['return_by'].strftime('%Y-%m-%d'))))
            elif user['borrowed'] == -1:
                pending_orders = db.execute('SELECT id FROM orders').fetchall()
                if pending_orders:
                    if len(pending_orders) == 1:
                        flash(('Hello, %s! You have %d pending order.'%(username, len(pending_orders))))
                    else:
                        flash(('Hello, %s! You have %d pending orders.'%(username, len(pending_orders))))
            return redirect(url_for('index'))
        flash(error)

    return render_template('auth/login.html')

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute('SELECT * FROM user WHERE id = ?',(user_id,)).fetchone()

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view

def superuser_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user['borrowed'] != -1:
            flash('You need to log in as a superuser')
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view
@bp.route('/register_superuser', methods=('GET','POST'))
@login_required
@superuser_required
def register_superuser():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        elif db.execute('SELECT id FROM user WHERE username = ?',(username,)).fetchone() is not None:
            error = 'User %s is already registered.'%(username)

        if error is None:
            db.execute('INSERT INTO user (username,password,borrowed) VALUES (?,?,-1)'
            ,(username, generate_password_hash(password)))
            db.commit()
            return redirect(url_for('auth.login'))

        flash(error)
    return render_template('auth/register.html')