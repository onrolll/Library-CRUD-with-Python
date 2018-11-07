from flask import (Blueprint, flash, g, redirect, render_template, request, url_for, session)
from werkzeug.exceptions import abort
from Library.auth import login_required, superuser_required
from Library.db import get_db
from datetime import datetime as d, timedelta

bp = Blueprint('library',__name__)

@bp.route('/')
@login_required
def index():
    db = get_db()
    books = db.execute('SELECT b.id AS id, available, published, pending_orders, title, name  FROM books b JOIN authors a ON b.author_id = a.id ORDER BY name DESC').fetchall()
    return render_template('library/index.html', books=books)

@bp.route('/add',methods=('GET','POST'))
@login_required
@superuser_required
def add():
    if request.method == 'POST':
        title = request.form['title']
        published = request.form['published']
        author_name = request.form['author_name']
        quantity = request.form['quantity']
        published_splitted = published.split('-')
        error = None

        if not title:
            error = 'Book title is required.'
        elif not published or published == 'YYYY-MM-DD':
            error = 'Date of publishing is required.'
        elif len(published)!= 10 or len(published_splitted)!=3 or len(published_splitted[0])!= 4 or len(published_splitted[1])!=2:
            error = 'Invalid date of publishing format. Please stay true to the example.'
        elif not author_name:
            error = 'Author is required.'
        
        if error is not None:
            flash(error)
        else:
            published+=' 12:00:00'
            db = get_db()
            author_id = db.execute('SELECT id FROM authors WHERE name = ?',(author_name,)).fetchone()
            if author_id is None:
                db.execute('INSERT INTO authors (name) VALUES (?)',(author_name,))
                db.commit()
                author_id = db.execute('SELECT id FROM authors WHERE name = ?',(author_name,)).fetchone()
            try:
                if not quantity:
                    db.execute('INSERT INTO books (title, published, author_id) VALUES (?, ?, ?)',(title, published, author_id['id']))
                
                else:
                    try:
                        quantity = int(quantity)
                        db.execute('INSERT INTO books (title, published, author_id, available) VALUES (?, ?, ?, ?)',(title, published, author_id['id'], quantity))
                    except ValueError:
                        flash('Provide a positive number for quantity')
                        return render_template('library/add.html')
                db.commit()
            except ValueError:
                error='Invalid date of publishing format. Please stay true to the example.'
                flash(error)
                return render_template('library/add.html')
            return redirect(url_for('library.index'))
            
    return render_template('library/add.html')

@bp.route('/<int:id>/borrow', methods=('POST',))
@login_required
def borrow(id):
    db = get_db()
    book = db.execute('SELECT * FROM books WHERE id = ?',(id,)).fetchone()
    #Check if the user already tried to borrow/borrowed the book

    book_in_user = db.execute('SELECT * FROM user_book WHERE book_id = ? AND user_id =?',(id, session['user_id'])).fetchone()
    if book_in_user is not None:
        return_by = db.execute('SELECT return_by FROM user_book WHERE user_id = ? AND book_id = ?',(session['user_id'], id)).fetchone()
        return_by = return_by[0].strftime('%Y-%m-%d')
        flash('This book is currently at your disposal. You have to return it by %s.'%(return_by))
        return redirect(url_for('library.index'))
   
    book_in_order = db.execute('SELECT * FROM orders WHERE book_id = ? AND user_id = ?',(id, session['user_id'])).fetchone()
    if book_in_order is not None:
        flash('You already tried to borrow the book.')
        return redirect(url_for('library.index'))

    book_out_of_stock = db.execute('SELECT available, pending_orders FROM books WHERE id = ?',(id,)).fetchone()
    if book_out_of_stock['available'] - book_out_of_stock['pending_orders'] == 0:
        flash('Sorry, this book is out of stock.')
        return redirect(url_for('library.index'))

    borrow_for = request.form['borrow']
   
    if not borrow_for:
        today = d.today()
        return_by = today.replace(month=today.month + 1)
        db.execute('INSERT INTO orders (book_id, user_id, borrow, return_by) VALUES (?, ?, 1, ?)',(id, session['user_id'],return_by))    
    else:
        try:
            return_by = d.today() + timedelta(days=int(borrow_for))
            db.execute('INSERT INTO orders (book_id, user_id, borrow, return_by) VALUES (?, ?, 1, ?)',(id, session['user_id'],return_by))
        except ValueError:
            flash('Please provide a valid number of days.')
            return redirect(url_for('library.index'))
    db.execute('UPDATE books SET pending_orders = pending_orders + 1 WHERE id = ?',(id,))
    db.commit()
    order = db.execute('SELECT id FROM orders WHERE book_id = ? AND user_id = ?',(id,session['user_id'] )).fetchone()
    flash('%s on its way. Please wait in line. Your order ID is %d'%(book['title'],order['id']))
    return redirect(url_for('library.index'))
    

@bp.route('/orders')
@login_required
@superuser_required
def orders():
    db = get_db()
    orders = db.execute('SELECT o.return_by AS return_by, ub.return_by AS return_by, b.id AS book_id, o.placed AS placed, o.borrow AS borrow, o.id AS id, u.username AS username, b.title AS title, a.name AS author FROM orders AS o JOIN user AS u ON o.user_id = u.id JOIN books AS b ON o.book_id = b.id JOIN authors AS a ON a.id = b.author_id LEFT JOIN user_book AS ub ON (ub.book_id = b.id AND ub.user_id = u.id) ORDER BY o.placed ').fetchall()
   # orders = db.execute('SELECT b.id AS book_id, o.placed AS placed, o.borrow AS borrow, o.id AS id, u.username AS username, b.title AS title, a.name AS author FROM orders AS o JOIN user AS u ON o.user_id = u.id JOIN books AS b ON o.book_id = b.id JOIN authors AS a ON a.id = b.author_id ORDER BY o.placed ').fetchall()
    if orders == []:
        flash('No pending orders')
        return redirect(url_for('library.index'))
    return render_template('library/orders.html', orders = orders)

@bp.route('/<int:id>/order', methods=('POST',))
@login_required
@superuser_required
def order(id):
    db = get_db()
    order = db.execute('SELECT * FROM orders WHERE id = ?',(id,)).fetchone()
    date = order['placed']
    return_date = order['return_by']
    book = db.execute('SELECT * FROM books WHERE id = ?',(order['book_id'],)).fetchone()
    user = db.execute('SELECT borrowed FROM user WHERE id = ?',(order['user_id'],)).fetchone()
    if book['available'] < 1:
        flash('Unable to place order. Book is out of stock.')
        return redirect(url_for('library.orders'))
    db.execute('INSERT INTO user_book (book_id, user_id, return_by, taken_on) VALUES (?, ?, ?, ?)',(order['book_id'], order['user_id'], return_date, date))
    db.execute('UPDATE books SET available = ?, pending_orders = ? WHERE id = ?',(book['available']-1,book['pending_orders']-1, book['id']))
    db.execute('UPDATE user SET borrowed = ? WHERE id = ?',(user['borrowed']+1,order['user_id']))
    db.execute('DELETE FROM orders WHERE id = ?',(id,))
    db.commit()
    flash('Order placed.')
    return redirect(url_for('library.orders'))

@bp.route('/user_books')
@login_required
def user_books():
    db = get_db()
    books = db.execute('SELECT b.id, b.title AS title, a.name AS author, b.published AS published, ub.return_by AS return_by FROM user_book AS ub JOIN books AS b ON ub.book_id = b.id JOIN authors AS a ON b.author_id = a.id WHERE ub.user_id = ?',(session['user_id'],)).fetchall()
    #books = db.execute('SELECT * FROM user_book WHERE user_id = ?',(session['user_id'],)).fetchall()
    #books =db.execute('SELECT b.title AS title, a.name AS author, b.published AS published, ub.return_by AS return_by FROM user_book AS ub JOIN books AS b ON ub.book_id = b.id JOIN authors AS a ON ub.user_id = a.id').fetchall()
    if books == []:
        flash('You hold no books.')
        return redirect(url_for('library.index'))
    # for book in books:
    #     flash(book[3])
    #flash('SHOULD HAVE BOOOKS')
    return render_template('library/user_books.html',books = books)
    #return redirect(url_for('library.index'))

@bp.route('/books_in_use')
@login_required
@superuser_required
def books_in_use():
    db = get_db()
    books = db.execute('SELECT b.id AS id, b.title AS title, a.name AS author, b.published AS published, ub.return_by AS return_by, u.username AS user FROM user_book AS ub JOIN books AS b ON ub.book_id = b.id JOIN authors AS a ON b.author_id = a.id JOIN user AS u ON u.id = ub.user_id').fetchall()

    if books == []:
        flash('No books in use.')
        return redirect(url_for('library.index'))

    
    return render_template('library/user_books.html',books = books)

@bp.route('/<int:id>/book_returned', methods=('POST',))
@login_required
@superuser_required
def book_returned(id):
    print('hello')
    db = get_db()
    user_id = db.execute('SELECT user_id FROM user_book WHERE book_id = ?',(id,)).fetchone()
    usr = user_id['user_id']
    db.execute('DELETE FROM user_book WHERE book_id = ?',(id,))
    db.execute('UPDATE books SET available = available + 1 WHERE id = ?',(id,))
    db.execute('UPDATE user SET borrowed = borrowed - 1 WHERE id = ?',(usr,))
    db.execute('DELETE FROM orders WHERE book_id = ? AND user_id = ?',(id,usr))
    db.commit()
    flash('Book returned.')
    return redirect(url_for('library.books_in_use'))

@bp.route('/<int:id>/return_book', methods=('POST',))
@login_required
def return_book(id):
    db = get_db()
    already_in_order = db.execute('SELECT * FROM orders WHERE book_id = ? AND user_id = ?',(id, session['user_id'])).fetchone()
    if already_in_order:
        flash('Please, wait for your turn in line.')
        return redirect(url_for('library.user_books'))
    db.execute('INSERT INTO orders (book_id, user_id, borrow) VALUES (?, ?, 0)',(id, session['user_id'])).fetchone()
    db.commit() 
    order_id = db.execute('SELECT id FROM orders WHERE book_id = ? AND user_id = ?',(id, session['user_id'])).fetchone()
    flash('Thank you. Please wait in line. Your order ID is %d'%(order_id[0]))
    return redirect(url_for('library.user_books'))

@bp.route('/<int:id>/cancel_order', methods=('POST',))
@login_required
@superuser_required
def cancel_order(id):
    db = get_db()
    order = db.execute('SELECT borrow, book_id FROM orders WHERE id = ?',(id,)).fetchone()
    if order['borrow'] == 1:
        db.execute('UPDATE books SET pending_orders = pending_orders - 1 WHERE id = ?',(order['book_id'],))
    db.execute('DELETE FROM orders WHERE id = ?',(id,))
    db.commit()
    return redirect(url_for('library.orders'))


@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
@superuser_required
def delete(id):
    db = get_db()
    book_in_use = db.execute('SELECT * FROM user_book WHERE book_id = ?',(id,)).fetchone()
    if book_in_use is not None:
        flash('Unable to delete book. It is currently in use.')
        return redirect(url_for('library.index'))
    book_in_order = db.execute('SELECT * FROM orders WHERE book_id = ?',(id,)).fetchone()
    if book_in_order is not None:
        flash('Unable to delete book. It is currently in order.')
        return redirect(url_for('library.index'))

    db.execute('DELETE FROM books WHERE id = ?',(id,))
    db.commit()
    flash('Book deleted successfully.')
    return redirect(url_for('library.index'))

@bp.route('/search', methods=('GET','POST'))
@login_required
def search():
    if request.method == 'POST':
        db = get_db()
        title = request.form['title']
        author = request.form['author_name']
        published = request.form['published']
        
        if title:
            title = "%" + title + "%"
            if author:
                author = '%' + author + '%'
                if published:
                    published = published + ' 12:00:00'
                    books = db.execute("SELECT b.id AS id, b.title AS title, b.available AS available, b.pending_orders AS pending_orders, b.published as published, a.name AS name FROM books AS b JOIN authors AS a ON b.author_id = a.id WHERE b.title LIKE ? OR a.name LIKE ? OR b.published = ?",(title, author, published)).fetchall()
                    return render_template('/library/index.html', books = books)
                books = db.execute("SELECT b.id AS id, b.title AS title, b.available AS available, b.pending_orders AS pending_orders, b.published as published, a.name AS name FROM books AS b JOIN authors AS a ON b.author_id = a.id WHERE b.title LIKE ? OR a.name LIKE ?",(title,author)).fetchall()
                return render_template('/library/index.html', books = books)
            if published:
                published = published + ' 12:00:00'
                books = db.execute("SELECT b.id AS id, b.title AS title, b.available AS available, b.pending_orders AS pending_orders, b.published as published, a.name AS name FROM books AS b JOIN authors AS a ON b.author_id = a.id WHERE b.title LIKE ? OR b.published = ?",(title, published)).fetchall()
                return render_template('/library/index.html', books = books)
        if author:
            author = '%' + author + '%'
            if published:
                published = published + ' 12:00:00'
                books = db.execute("SELECT b.id AS id, b.title AS title, b.available AS available, b.pending_orders AS pending_orders, b.published as published, a.name AS name FROM books AS b JOIN authors AS a ON b.author_id = a.id WHERE a.name LIKE ? OR b.published = ?",( author, published)).fetchall()
                return render_template('/library/index.html', books = books)
            books = db.execute("SELECT b.id AS id, b.title AS title, b.available AS available, b.pending_orders AS pending_orders, b.published as published, a.name AS name FROM books AS b JOIN authors AS a ON b.author_id = a.id WHERE a.name LIKE ? ",(author,)).fetchall()
            return render_template('/library/index.html', books = books)

        if published:
            published = published + ' 12:00:00'
            books = db.execute("SELECT b.id AS id, b.title AS title, b.available AS available, b.pending_orders AS pending_orders, b.published as published, a.name AS name FROM books AS b JOIN authors AS a ON b.author_id = a.id WHERE b.published = ?",(published,)).fetchall()
            return render_template('/library/index.html', books = books)
    return render_template('library/search.html')


