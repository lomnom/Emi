import praw #literally what it says
import discord
from discord.ext import commands
from discord.ext.commands import Bot
from TermManip import *
from yaml import safe_load as load

try:
	credentials=load(open("passwords.yaml","r").read())["passwords"]
except (FileNotFoundError,KeyError):
	log("passwords.yaml was not found or was invalid!\n"
		"Create one following this format in the current directory!\n"
		"passwords: \n"
		"  redditu: [reddit username]\n"
		"  redditp: [reddit password]\n"
		"  redditcid: [reddit client id]\n"
		"  redditcs: [reddit client secret]"
		"  discordt: [discord bot token]"
		,type="error"
	)
	quit()

bot=commands.Bot(command_prefix='e:') 

@bot.command(pass_context=True)
async def command(ctx,*args):
	pass

@bot.event
async def on_ready(): #show on ready logs
	global reddit
	log("logged into discord as '{0.user}'".format(bot),type='success')
	log("Attempting to connect to reddit...")
	try:
		reddit=praw.Reddit(
			client_id=credentials["redditcid"],
			client_secret=credentials["redditcs"],
			password=credentials["redditp"],
			user_agent="Eitra & Emi bot in https://github.com/lomnom/Emi",
			username=credentials["redditp"]
		)
	except Exception as e:
		log("Met '{}: {}'".format(type(e),str(e)),type="error")
		await bot.close()
	else:
		log("Success!",type="success")

try:
	bot.run(credentials["discordt"])
except discord.errors.LoginFailure as e:
	log("Your token was invalid! Met error '{}: {}'".format(type(e),str(e)),type="error")