from flask import current_app
from discord_webhook import DiscordWebhook, DiscordEmbed

def sendNotifAddPlayer(playerName, listName, addedBy, reason):
    webhook = DiscordWebhook(url=current_app.config['DISCORD_WEBHOOK'])
    title = "'" + playerName + "' was added to '" + listName + "' by '" + addedBy + "'"
    description = "Reason: " + reason
    embed = DiscordEmbed(title=title, description=description, color=242424)
    webhook.add_embed(embed)
    response = webhook.execute()
