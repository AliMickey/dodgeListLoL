import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from dodgeListLoL.db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        #code = request.form['inv-code']
        db = get_db()
        error = None

        tempUserID = db.execute(
            'SELECT id FROM users WHERE username = ?', (username,)
        ).fetchone() 

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        #elif not code:
            #error = 'Invite Code is required.'
        #elif code != "legend":
            #error = "Invite Code not valid."
        elif tempUserID is not None:
            error = 'User {} is already registered.'.format(username)

        if error is None:
            # Create user
            db.execute(
                'INSERT INTO users (username, password) VALUES (?, ?)',
                (username, generate_password_hash(password))
            )

            # Create user's private list
            tempPrivateTitle = username + "'s Private List"
            db.execute(
                'INSERT INTO lists (type, title) VALUES (?, ?) ',
                ("private", tempPrivateTitle)
            )
            db.commit()

            # Get ID of current user's private list
            currentUserPrivateListID = db.execute('''
                SELECT l.id 
                FROM lists l
                WHERE l.title = ?
                ''', (tempPrivateTitle,)).fetchone()

            # Get ID of newly registered current user
            currentUserID = db.execute(
                'SELECT id FROM users WHERE username = ?', (username,)
            ).fetchone() 

            # Make user owner of private list
            db.execute(
                'INSERT INTO ownerOf VALUES (?, ?)',
                (int(currentUserID[0]), int(currentUserPrivateListID[0]))
            )
            db.execute(
                'INSERT INTO ownerOf VALUES (?, ?)',
                (int(currentUserID[0]), 1)
            )
            db.commit()
            return redirect(url_for('auth.login'))

        flash(error)

    return render_template('auth/register.html')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))

        flash(error)

    return render_template('auth/login.html')


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM users WHERE id = ?', (user_id,)
        ).fetchone()


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


# Get all shared lists for current user
@bp.context_processor
def getSharedLists():
    listsDict = {}
    if g.user:
        db = get_db() 
        tempList = db.execute('''
            SELECT l.title, l.id
            FROM users u JOIN ownerOf o ON o.u_id = u.id JOIN lists l ON l.id = o.list_id 
            WHERE u.id = ? and l.type = "shared"
            ''', [g.user['id']]).fetchall()
        for row in tempList: 
            listName, listID = row
            listsDict[listName] = [listID]
    return dict(sharedListsDict=listsDict)
