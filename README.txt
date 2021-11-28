# Dodge List LoL
## Description
A web app to provide League of Legends players easy access to player tracking through the use of lists.
[Live Version](https://dodge.app.mickit.net) ~ Invite Code: `github`

## Motivation
Some League of Legends players needed to have the ability to track certain players that they have played with. This idea was initially done through the use of a shared online notebook, this did not prove to be efficient nor easy to use.

## Technologies Used
[Flask](https://flask.palletsprojects.com)
[Bootstrap](https://getbootstrap.com)
[Docker](https://www.docker.com)
[Riot API](https://developer.riotgames.com/apis)

## Build from source
1. Clone the repository
2. Move into the directory `cd dodgeListLoL`
3. Initialise a virtual environment `python -m venv venv`
4. Activate the virtual environment, Linux: `source venv/bin/activate`
5. Install requirements `pip install -r requirements.txt`
6. Edit the config file with your keys `dodgeListLoL/instance/config.py`
7. Set Flask environment `export FLASK_APP=dodgeListLoL`
8. Initialise a new database `flask init-db`
9. Run the app `flask run`