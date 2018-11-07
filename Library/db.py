import sqlite3

import click
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def init_db():
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

@click.command('add-su')
@click.argument('username')
@click.argument('password')
@with_appcontext
def add_superuser_command(username, password):
    """Add a superuser to the user table."""
    db = get_db()
    db.execute('INSERT INTO user (username, password, borrowed) VALUES (?, ?, -1)',(username, generate_password_hash(password)))
    db.commit()
    user = db.execute('SELECT * FROM user WHERE username = username').fetchone()
    click.echo(user['username'])
    click.echo('Super user in.')

def init_app(app):
    # Tells Flask to call function when cleaning up after returning response
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(add_superuser_command)