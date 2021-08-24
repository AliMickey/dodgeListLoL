from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort
from dodgeListLoL.auth import login_required
from dodgeListLoL.db import get_db

bp = Blueprint('lists', __name__, url_prefix='/lists')


# Route

#Global list
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
        listDict[entryName] = [entryReason, authorName, entryID]
    return render_template('lists/global.html', data=listDict)


#Private list
@bp.route('/private')
@login_required
def privateList():
    db = get_db()
    listDict = {}
    #JOIN users u ON u.id = ?
    tempList = db.execute('''
        SELECT e.username, e.reason, e.id, l.id
        FROM entries e JOIN entryPartOf ep ON ep.entry_id = e.id JOIN lists l ON ep.list_id = l.id
        WHERE l.type = "private" AND e.author_id = ?
        ''', [g.user['id']]).fetchall()
    for row in tempList:
        entryName, entryReason, entryID, listID = row
        listDict[entryName] = [entryReason, entryID, listID]
    return render_template('lists/private.html', data=listDict)


# All shared lists ##CHECK
@bp.route('/shared/<int:listID>', methods=('GET',))
@login_required
def sharedList(listID):
    db = get_db()
    listDict = {}
    listTitle = ""
    if checkAuthentication(listID, True):
        tempList = db.execute('''
            SELECT e.username, e.reason, e.author_id, e.id, l.id, l.title
            FROM users u JOIN ownerOf o ON o.u_id = u.id JOIN lists l ON l.id = o.list_id 
            JOIN entryPartOf p ON p.list_id = l.id 
            JOIN entries e ON e.id = p.entry_id 
            WHERE l.id = ? and u.id = ? and l.type = "shared"
            UNION
            SELECT e.username, e.reason, e.author_id, e.id, l.id, l.title
            FROM users u JOIN memberOf o ON o.u_id = u.id JOIN lists l ON l.id = o.list_id 
            JOIN entryPartOf p ON p.list_id = l.id 
            JOIN entries e ON e.id = p.entry_id 
            WHERE l.id = ? and u.id = ? and l.type = "shared"
        ''', (listID, g.user['id'], listID, g.user['id']))

        for row in tempList:
            entryName, entryReason, authorID, entryID, listIdentity, listT = row
            authorName = db.execute('SELECT username FROM users WHERE id = ?', (authorID,)).fetchone()
            listDict[entryName] = [entryReason, authorName[0], entryID]
            listTitle = listT
            listID = listIdentity
        if listTitle == "":
            listTitle = db.execute('SELECT title FROM lists WHERE id = ?', (listID,)).fetchone()[0]

        return render_template('lists/shared.html', data=listDict, listDetails=[listID, listTitle], sharedUsersDetails=getUserInShareList(listID))
    else:
        abort(403)


#Create a new list
@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        listTitle = request.form['title']
        listType = "shared"
        error = None

        if listTitle is None:
            error = 'Title is Required'
        if len(listTitle) > 20:
            error = 'Title is Too Long. Maximum 20 Characters'
        if error is not None:
            flash(error)
        else:
            db = get_db()
            # Create the list with type and title
            db.execute('''
                INSERT INTO lists (type, title)
                VALUES (?, ?)
            ''', (listType, listTitle))
            db.commit()

            # Get list ID
            list_id = db.execute('''
                SELECT l.id 
                FROM lists l
                WHERE l.type = ? AND l.title = ?
                ''', (listType, listTitle)).fetchone()

            # Connect list to user
            db.execute('INSERT INTO ownerOf (u_id, list_id) VALUES (?, ?)', (g.user['id'], list_id[0]))
            db.commit()
            flash("List Created")
            return redirect(url_for('main.addPlayer'))
            
    return render_template('lists/create.html')


#Add user to a share list
@bp.route('/shared/<int:listID>/share/add', methods=('POST',))
@login_required
def addUserToShareList(userName=None, listID=None):
    userName = request.form['userName']
    db = get_db()
    userID = db.execute('SELECT id FROM users WHERE username = ?', (userName,)).fetchone()
    #Check if logged in user is owner/member of list.
    if checkAuthentication(listID, True):
        if userID:
            db.execute('INSERT INTO memberOf (u_id, list_id) VALUES (?, ?)', (userID[0], listID))
            db.commit()
            return redirect(url_for('lists.sharedList', listID=listID))
        else: 
            flash("No Such User Exists")
            return redirect(url_for('lists.sharedList', listID=listID))
    else:
        abort(403)


#Remove user from a share list
@bp.route('/shared/<int:listID>/share/remove', methods=('GET',))
@login_required
def removeUserFromShareList(userName=None, listID=None):
    userName = request.args.get('userName', '')
    db = get_db()
    userID = db.execute('SELECT id FROM users WHERE username = ?', (userName,)).fetchone()
    if userID and checkAuthentication(listID, True):
        db.execute('DELETE FROM memberOf WHERE u_id = ? AND list_id = ?', (userID[0], listID))
        db.commit()
        return redirect(url_for('lists.sharedList', listID=listID))
    else:
        abort(403)
    

##Do checks if user is owner to be able to delete. 
#Delete an entry
@bp.route('/<string:listType>/<int:listID>/<int:entryID>/entry/delete', methods=('GET',))
@login_required
def deleteEntry(listType, entryID, listID):
    if checkAuthentication(listID, True):
        db = get_db()
        db.execute('DELETE FROM entryPartOf WHERE entry_id = ? AND list_id = ?', (entryID,listID))
        db.commit()
        flash("Entry Deleted")
        if listType == "global":
            return redirect(url_for('lists.globalList'))
        elif listType == "private":
            return redirect(url_for('lists.privateList'))
        elif listType == "shared":
            return redirect(url_for('lists.sharedList', listID=listID))
    else:
        abort(403)


#Delete a list
@bp.route('/<int:listID>/delete', methods=('GET',))
@login_required
def deleteList(listID):
    db = get_db()
    if checkAuthentication(listID, False):
        db.execute('DELETE FROM ownerOf WHERE list_id = ?', (listID,))
        db.execute('DELETE FROM memberOf WHERE list_id = ?', (listID,))
        db.execute('DELETE FROM entryPartOf WHERE list_id = ?', (listID,))
        db.execute('DELETE FROM lists WHERE id = ?', (listID,))
        db.commit()
        flash("List Deleted")  
        return redirect(url_for('main.index'))
    else:
        abort(403)


#Functions
def checkAuthentication(listID, checkMember):
    db = get_db()
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
            

#Get users in current share list
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
        tempList = db.execute('''
            SELECT l.title, l.id
            FROM users u JOIN memberOf o ON o.u_id = u.id JOIN lists l ON l.id = o.list_id 
            WHERE u.id = ? and l.type = "shared"
            ''', [g.user['id']]).fetchall()
        for row in tempList: 
            listName, listID = row
            listsDict[listName] = [listID]
    return dict(sharedListsDict=listsDict)