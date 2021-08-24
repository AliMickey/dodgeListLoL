import requests, json
from riotwatcher import LolWatcher, ApiError
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, current_app
)
from dodgeListLoL.db import get_db
from dodgeListLoL.auth import login_required
from dodgeListLoL.notifications import sendNotifAddPlayer

bp = Blueprint('main', __name__)

riotApi = None
my_region = 'oc1'
championNames = {}

#Get all champions in game latest patch with caching32
gameVersion = requests.get('https://ddragon.leagueoflegends.com/api/versions.json').json()[0]
localChamps = {}
with open('files/champion.json', 'r+', encoding='utf-8') as champFile:
    localChamps = json.load(champFile)        
    #if localChamps['version'] != gameVersion:
       # champFile.seek(0)
        #localChamps = requests.get('http://ddragon.leagueoflegends.com/cdn/{}/data/en_US/champion.json'.format(gameVersion)).json()
        #json.dump(localChamps, champFile, indent = 4)
        
apiChampionList =  localChamps['data']        

#Map each champion ID to its name 
for champion in apiChampionList:
    key = int(apiChampionList[champion]["key"])
    championNames[key] = apiChampionList[champion]["id"]

# Routes

#Index
@bp.route('/')
def index():
    return render_template('index.html')


#Search for username provided by user
@bp.route('/search', methods = ['POST', 'GET'])
def search(username=None):
    requestSummonerDict = {}
    summonerList = ""
    if request.method == 'GET':   
        summonerList = formatSummoners(request.args.get('username', ''))
    if request.method == 'POST':
        req = request.form
        summonerList = formatSummoners(req["username"])

    #Multithread
    threads = []
    with ThreadPoolExecutor(max_workers=len(summonerList)) as executor:
        for summoner in summonerList:
            apiSummoner = getSummoner(summoner)
            dodge = "No"
            if apiSummoner is not None:
                if summonerInDodgeList(apiSummoner['name'], -1): 
                    dodge = "Yes"
                threads.append(executor.submit(summonerAnalyser, apiSummoner, summoner, dodge, requestSummonerDict))
            else:
                flash("No Such Summoner Exists: " + summoner)
    return render_template('search.html', summoners=requestSummonerDict) # Show summoner/s details in next page


#Add a player to dodge list
@bp.route('/add-player', methods = ['POST', 'GET'])
@login_required
def addPlayer(username=None):
    req = request.form    
    privateListDict = {}
    sharedListDict = {}
    if request.method == 'GET':
        summonerVar = formatSummoners(request.args.get('username', ''))
        #Get all shared/private lists ID for current user and pass them through to view.
        db = get_db()
        tempSharedList = db.execute('''
            SELECT l.id, l.title
            FROM lists l LEFT OUTER JOIN memberOf mo ON l.id = mo.list_id
            JOIN users u ON u.id = mo.u_id
            WHERE mo.u_id = ? AND l.type = "shared"
            UNION
            SELECT l.id, l.title
            FROM lists l LEFT OUTER JOIN ownerOf oo ON l.id = oo.list_id
            JOIN users u ON u.id = oo.u_id
            WHERE oo.u_id = ? AND l.type = "shared"
            ''', (g.user['id'], g.user['id'])).fetchall()

        for row in tempSharedList: 
            listID, listName = row
            sharedListDict[listID] = listName

        tempPrivateList = db.execute('''
            SELECT l.id, l.title
            FROM lists l JOIN ownerOF mo ON l.id = mo.list_id
            JOIN users u ON u.id = mo.u_id
            WHERE mo.u_id = ? AND l.type = "private"
            ''', (g.user['id'],)).fetchall()

        for row in tempPrivateList:
            listID, listName = row
            privateListDict[listID] = listName
        
        return render_template('add-player.html', privateLists=privateListDict, sharedLists=sharedListDict, preFill=summonerVar[0])
        
    elif request.method == 'POST':
        summonerList = formatSummoners(req["username"])

    for summoner in summonerList:
        apiSummoner = getSummoner(summoner)
        listID = request.form.get('lists')
        db = get_db()
        # Get list data
        listData = db.execute('''
            SELECT l.title, l.type
            FROM lists l
            WHERE l.id = ?
        ''', (listID,)).fetchone()
        if apiSummoner is not None and not summonerInDodgeList(apiSummoner['name'], int(listID)):
            addEntryToList(apiSummoner['name'], req["reason"], int(listID))
            flash("Player Added to List")
            # Send notification if list is of shared or global type
            if listData[1] == "global":
                sendNotifAddPlayer(apiSummoner['name'], listData[0], g.user['username'], req["reason"])
        else:
            flash("Player Does Not Exist or is Already in List: " + summoner)

    return redirect(url_for('main.addPlayer'))


#Live game functionality
# @bp.route('/live',  methods = ['POST', 'GET'])
# @login_required
# def getLiveGame(summoner=None):
#     if request.method == 'GET':
#         summonerName = request.args.get('username', '')
#         apiSummoner = getSummoner(summonerName)
#         if apiSummoner is not None:
#             print(apiSummoner)
#             teamDict = {}
#             enemyDict = {}

#         else:
#             flash("Player Does Not Exist: " + summoner)
#         render_template('live.html', summonersTeam=teamDict, summonersEnemy=enemyDict)


# Functions
#Format client side input to comma seperated string
def formatSummoners(usernames):
    # Format input to list of summoners
    summonerList = usernames.replace(' - ', ',').strip().split(',')
    return summonerList


#Check if player is in selected dodge list
def summonerInDodgeList(entryName, listID):
    db = get_db()
    if listID == -1:
        #Query to check if entry name exists in any dodge list
        dbUser = db.execute('''
            SELECT e.username 
            FROM entries e JOIN entryPartOf ep ON e.id = ep.entry_id
            JOIN lists l ON ep.list_id = l.id
            WHERE e.username = ?
            ''', (entryName,)).fetchone()

    else:
        # Query to check if entry name exists in specific dodge list
        dbUser = db.execute('''
            SELECT e.username
            FROM entries e JOIN entryPartOf ep ON e.id = ep.entry_id
            JOIN lists l ON ep.list_id = l.id
            WHERE e.username = ? AND ep.list_id = ?
            ''', (entryName, listID)).fetchone()

    if dbUser is None:
        return False

    return True
    
#Add entry to specific list
def addEntryToList(entryName, entryReason, listID):
    user_id = g.user['id']
    db = get_db()
    # Add entry
    db.execute(
        ' INSERT INTO entries (author_id, username, reason) VALUES (?, ?, ?) ', (user_id, entryName, entryReason))
    db.commit()

    # Get entry ID
    entry_id = db.execute('''
        SELECT e.id 
        FROM entries e
        WHERE e.username = ? AND e.reason = ? 
        ''', (entryName, entryReason)).fetchone()

    # Connect entry to list
    db.execute(
        'INSERT INTO entryPartOf (entry_id, list_id) VALUES (?, ?)', (entry_id[0], listID) 
    )
    db.commit()


def getSummoner(summoner):
    try: 
        apiSummoner = riotApi.summoner.by_name(my_region, summoner)
        return apiSummoner
    except ApiError as err:
        if err.response.status_code == 404:
            return None


def summonerAnalyser(apiSummoner, userInput, dodge, requestSummonerDict):
    #Init all summoner details
    summonerId = apiSummoner['id']
    summonerPuid = apiSummoner['accountId']
    summonerName = apiSummoner['name']
    summonerLevel = apiSummoner['summonerLevel']
    summonerImage = apiSummoner['profileIconId']
    rankSolo = "No Rank"
    rankFlex = "No Rank"
    rankSoloWins = 0
    rankSoloLosses = 0

    # Ranking
    summonerRanks = riotApi.league.by_summoner(my_region, summonerId)

    for queueType in summonerRanks:
        if queueType['queueType'] == "RANKED_SOLO_5x5":
            rankSolo = queueType['tier'] + " " + queueType['rank']
            rankSoloWins = queueType['wins']
            rankSoloLosses = queueType['losses']
        if queueType['queueType'] == "RANKED_FLEX_SR":
            rankFlex = queueType['tier'] + " " + queueType['rank']

    #Local Dicts/Lists
    championWinratesList = {}
    summonerMatchHistory = {}
    championWinratesDict = {}
    winRateDict = [0,0]
    bestChamps = {}
    worstChamps = {} 

    #Get all matches
    summonerMatchHistory = riotApi.match.matchlist_by_account(region=my_region, encrypted_account_id=summonerPuid, season=[13], begin_index = 0, end_index=20)
    matchAnalyserRunner(summonerMatchHistory, summonerName, championWinratesDict, winRateDict) #Multithread

    # Descending order of games
    #championWinratesDict = dict(sorted(championWinratesDict.items(), reverse=True, key=lambda x: x[1]))

    #Calculate win rate
    winRate = ('%.1f'%((winRateDict[0] / (winRateDict[0] + winRateDict[1]) * 100)) + "%")

    #Calculates win rates for individual champs
    for champion in championWinratesDict:      
        championWinratesList[champion] = ((championWinratesDict[champion][0] / (championWinratesDict[champion][0] + championWinratesDict[champion][1])) * 100)

    # Sort champs W/L, filter name and select best/worst champs (3 each)
    championWinratesListSorted = sorted(championWinratesList.items(), key=lambda x: x[1], reverse=True)
    bestChamps = [championWinratesListSorted[0][0], championWinratesListSorted[1][0], championWinratesListSorted[2][0]]
    worstChamps = [championWinratesListSorted[-1][0], championWinratesListSorted[-2][0], championWinratesListSorted[-3][0]]
    
    # Adds info to final return dictionary
    requestSummonerDict[summonerName] = {'solo' : rankSolo, 'flex' : rankFlex, 'soloWins' : rankSoloWins, 'soloLosses' : rankSoloLosses, 'level' : summonerLevel, 'icon' : summonerImage, 'dodge' : dodge, 'bestChamps' : bestChamps, 'worstChamps' : worstChamps, 'winRate' : winRate }
    

def matchAnalyserRunner(summonerMatchHistory, summonerName, championWinratesDict, winRateDict):
    threads = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        for match in summonerMatchHistory['matches']:
            threads.append(executor.submit(matchAnalyser, match, summonerName, championWinratesDict, winRateDict))


def matchAnalyser(match, summonerName, championWinratesDict, winRateDict):
    #Map champion id to name played by player
    champion = championNames[match['champion']]
    playerTeamId = 0
    
    #Get detailed match info for current match
    currentMatchDetails = riotApi.match.by_id(my_region, match['gameId'])

    # Check which team player was on
    for player in currentMatchDetails['participantIdentities']:
        if player['player']['summonerName'] == summonerName: 
            playerTeamId = player['participantId']
    #If less than 5 means was on team 0, otherwise team 1
    if playerTeamId <= 5: 
        playerTeamId = 0
    else: 
        playerTeamId = 1

    #Check if remake, and if game was won
    if (currentMatchDetails['gameDuration'] >= 210):
        if (currentMatchDetails['teams'][playerTeamId]['win'] == "Win"):
            winRateDict[0] += 1   
            if champion in championWinratesDict: 
                championWinratesDict[champion][0] += 1
            else: 
                championWinratesDict[champion] = [1,0]
        else: 
            winRateDict[1] += 1
            if champion in championWinratesDict: 
                championWinratesDict[champion][1] += 1
            else: 
                championWinratesDict[champion] = [0,1]


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
            UNION
            SELECT l.title, l.id
            FROM users u JOIN memberOf m on m.u_id JOIN lists l on l.id = m.list_id
            WHERE u.id = ? and l.type = "shared"
            ''', [g.user['id'], g.user['id']]).fetchall()
        for row in tempList: 
            listName, listID = row
            listsDict[listName] = [listID]
    return dict(sharedListsDict=listsDict)


def setApiInstance(app):
    global riotApi
    riotApi = LolWatcher(app.config['RIOT_API'])

#Error Handling
@bp.app_errorhandler(404)
def page_not_found(e):
    return render_template('error/404.html'), 404

@bp.app_errorhandler(403)
def authorisation_error(e):
    return render_template('error/403.html'), 403