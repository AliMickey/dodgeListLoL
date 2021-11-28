from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort
from dodgeListLoL.auth import login_required
from dodgeListLoL.db import get_db

bp = Blueprint('lists', __name__, url_prefix='/lists')


## Routes
# Global list
@bp.route('/global')
def globalList():
    db = get_db()
    listDict = {}
    tempList = db.execute('''
        SELECT e.username, e.reason, u.username as authorName, e.id
        FROM entries e JOIN entryPartOf ep ON ep.entry_id = e.id JOIN lists l ON ep.list_id = l.id
        JOIN users u on e.author_id = u.id
        WHERE l.type = "global"
        ''').fetchall()
    for row in tempList:
        entryName, entryReason, authorName, entryID = row
        listDict[entryName] = [entryReason, entryID, authorName]
    return render_template('list.html', listDict=listDict, listInfo={'ID': 1, 'title': "Global"})

# Private list
@bp.route('/private')
@login_required
def privateList():
    db = get_db()
    listDict = {}
    listID = 0
    tempList = db.execute('''
        SELECT e.username, e.reason, e.id, l.id
        FROM entries e JOIN entryPartOf ep ON ep.entry_id = e.id JOIN lists l ON ep.list_id = l.id
        WHERE l.type = "private" AND e.author_id = ?
        ''', [g.user['id']]).fetchall()
    for row in tempList:
        entryName, entryReason, entryID, listID = row
        listDict[entryName] = [entryReason, entryID] 
    return render_template('list.html', listDict=listDict, listInfo={'ID': listID, 'title': "Private"})

# Shared lists
@bp.route('/shared/<int:listID>', methods=('GET',))
@login_required
def sharedList(listID):
    if checkAuthentication(listID, checkMember=True):
        db = get_db()
        listDict = {}
        tempList = db.execute('''
            SELECT entry_id, author_id, username, reason
            FROM entries e JOIN entryPartOf ep ON ep.entry_id = e.id JOIN lists l ON ep.list_id = l.id
            WHERE l.id = ?
        ''', (listID,)).fetchall()

        for row in tempList:
            entryID, authorID, username, reason = row
            authorName = db.execute('SELECT username FROM users WHERE id = ?', (authorID,)).fetchone()
            listDict[username] = [reason, entryID, authorName[0]]

        listTitle = db.execute('SELECT title FROM lists WHERE id = ?', (listID,)).fetchone()[0]
    
        isOwner = checkAuthentication(listID, checkMember=False)
        ownerName = db.execute('''
            SELECT u.username
            FROM users u JOIN ownerOf o ON o.u_id = u.id JOIN lists l ON l.id = o.list_id
            WHERE l.id = ?
        ''', (listID,)).fetchone()[0]

        return render_template('list.html', listDict=listDict, listInfo={'ID': listID, 'title': listTitle, 'isOwner': isOwner, 'ownerName': ownerName, 'currentUserID': g.user['id']}, sharedUsersDetails=getUserInShareList(listID))

    else:
        abort(403)

#Create a new list
@bp.route('/create', methods=('POST',))
@login_required
def create():
    listTitle = request.form['title']
    error = None

    if listTitle is None:
        error = 'Title is Required'
    if len(listTitle) > 20:
        error = 'Title is Too Long. Maximum 20 Characters'
    if error is not None:
        flash(error, "warning")
    else:
        db = get_db()
        # Create the list with type and title
        db.execute('''
            INSERT INTO lists (type, title)
            VALUES (?, ?)
        ''', ("shared", listTitle))
        db.commit()

        # Get list ID
        list_id = db.execute('''
            SELECT l.id 
            FROM lists l
            WHERE l.type = ? AND l.title = ?
            ''', ("shared", listTitle)).fetchone()

        # Connect list to user
        db.execute('INSERT INTO ownerOf (u_id, list_id) VALUES (?, ?)', (g.user['id'], list_id[0]))
        db.commit()
        flash("List created.", "success")
        return redirect(url_for('lists.sharedList', listID=list_id[0]))

# Add user to a share list
@bp.route('/shared/<int:listID>/share/add', methods=('POST',))
@login_required
def addUserToShareList(listID):
    username = request.form['addShareUsername']
    if checkAuthentication(listID, checkMember=False):
        db = get_db()
        userID = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if userID:
            if userID[0] == g.user['id']:
                flash("You cannot share this list with yourself.", "warning")
            else:
                db.execute('INSERT INTO memberOf (u_id, list_id) VALUES (?, ?)', (userID[0], listID))
                db.commit()
                flash("User has been added.", "success")
        else: 
            flash("No such user exists.", "warning")
    else:
        flash("Only the owner can share this list other users.", "warning")

    return redirect(url_for('lists.sharedList', listID=listID))

# Remove user from a share list
@bp.route('/shared/<int:listID>/share/remove', methods=('POST',))
@login_required
def removeUserFromShareList(listID):
    userID = int(request.form['removeShareUserID'])
    # If user is removing themselves or user is owner of list
    if userID == g.user['id'] or checkAuthentication(listID, checkMember=False):
        db = get_db()
        db.execute('DELETE FROM memberOf WHERE u_id = ? AND list_id = ?', (userID, listID))
        db.commit() 
        flash("User has been removed.", "success")
    else:
        flash("Only the owner can remove shared users from this list.", "warning")

    return redirect(url_for('lists.sharedList', listID=listID))
    
# Remove a player from a list
@bp.route('/<int:listID>/<int:entryID>/remove', methods=('POST',))
@login_required
def removePlayer(listID, entryID):
    if checkAuthentication(listID, checkMember=True):
        db = get_db()
        db.execute('DELETE FROM entryPartOf WHERE entry_id = ? AND list_id = ?', (entryID, listID))
        db.execute('DELETE FROM entries WHERE id = ?', (entryID,))
        db.commit()
        flash("Player has been removed.", "success")
    else:
        abort(403)
    return redirect(request.referrer)

# Delete a list
@bp.route('/shared/<int:listID>/delete', methods=('POST',))
@login_required
def deleteList(listID):
    if checkAuthentication(listID, checkMember=False):
        db = get_db()
        db.execute('DELETE FROM ownerOf WHERE list_id = ?', (listID,))
        db.execute('DELETE FROM memberOf WHERE list_id = ?', (listID,))
        db.execute('DELETE FROM entryPartOf WHERE list_id = ?', (listID,))
        db.execute('DELETE FROM lists WHERE id = ?', (listID,))
        db.commit()
        flash("List deleted.", "success")  
        return redirect(url_for('main.index'))
    else:
        flash("Only the owner can delete this list.", "warning")


## Functions
def checkAuthentication(listID, checkMember):
    db = get_db()
    # Checks for member and owner
    if checkMember:
        tempUser = db.execute('''
            SELECT o.u_id
            FROM users u JOIN ownerOf o ON o.u_id = u.id JOIN lists l ON l.id = o.list_id
            WHERE l.id = ? and u.id = ?
            UNION
            SELECT o.u_id
            FROM users u JOIN memberOf o ON o.u_id = u.id JOIN lists l ON l.id = o.list_id
            WHERE l.id = ? and u.id = ?
        ''', (listID, g.user['id'], listID, g.user['id'])).fetchone()
        if tempUser: 
            return True
        else:
            return False
    # Checks for owner only
    else:
        tempUser = db.execute('''
            SELECT o.u_id
            FROM users u JOIN ownerOf o ON o.u_id = u.id JOIN lists l ON l.id = o.list_id
            WHERE l.id = ? and u.id = ?
        ''', (listID, g.user['id'])).fetchone()
        if tempUser: 
            return True
        else:
            return False
            
# Get members in current share list
#@login_required
def getUserInShareList(listID):
    db = get_db()
    userList = {}
    tempList = db.execute('''
        SELECT u.username, u.id
        FROM users u JOIN memberOf m ON m.u_id = u.id
        WHERE m.list_id = ?
        ''', (listID,)).fetchall()
    for row in tempList:
        username, id = row
        userList[username] = id
    return userList

# Get all shared lists for current user
@bp.app_context_processor
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
        tempList = db.execute('''
            SELECT l.title, l.id
            FROM users u JOIN memberOf o ON o.u_id = u.id JOIN lists l ON l.id = o.list_id 
            WHERE u.id = ? and l.type = "shared"
            ''', [g.user['id']]).fetchall()
        for row in tempList: 
            listName, listID = row
            listsDict[listName] = [listID]
    return dict(sharedListsDict=listsDict)