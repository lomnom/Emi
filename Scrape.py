import asyncpraw as praw
import discord
from discord.ext import commands
from discord.ext.commands import Bot
from TermManip import *
from yaml import safe_load as load
import asyncio
import re

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
	exit(1)

class Tips:
	def __init__(self,bot):
		self.subredditname="r/EitraAndEmi".lstrip("r/")
		self.bot=bot
		self.loop=self.bot.loop
		self.loop.create_task(self.refresh())

	async def refresh(self):
		self.subreddit=await reddit.subreddit(self.subredditname, fetch=True)
		async for post in self.subreddit.search(f"Eitra and Emi's Tips: #",sort="new"):
			index=re.findall(r"(?<=Eitra and Emi's Tips: #)\d+",post.title)
			if len(index)==1:
				self.lasttip=int(index[0])

	class Tip:
		def __init__(self,parent,id):
			self.parent=parent
			self.id=id

		async def refresh(self):
			async for post in self.parent.subreddit.search(f"Eitra and Emi's Tips: #{self.id}"):
				self.post=None
				if post.title==f"Eitra and Emi's Tips: #{self.id}":
					self.post=post
					self.image=post.url
					break
				if self.post==None:
					raise FileNotFoundError

	def tip(self,index):
		if index>self.lasttip or index<=0:
			return self.Tip(self,index)

bot=commands.Bot(command_prefix="-")

@bot.command(pass_context=True,aliases=["tip","sextip"])
async def gettip(ctx,id):
	tip=tips.tip(int(id))
	await tip.refresh()
	await ctx.send(tip.image)

reddit=None
tips=None
@bot.event
async def on_ready(): #show on ready logs
	global reddit,tips
	log("logged into discord as '{0.user}'".format(bot),type='success')
	if reddit==None:
		log("Attempting to connect to reddit...")
		try:
			reddit=praw.Reddit(
				client_id=credentials["redditcid"],
				client_secret=credentials["redditcs"],
				password=credentials["redditp"],
				user_agent="Eitra & Emi bot in https://github.com/lomnom/Emi",
				username=credentials["redditu"]
			)
			log("Logged into reddit as u/{}".format(await reddit.user.me()),type="success")
			log("Pre-initialised!")
			log("Getting Tips object...")
			tips=Tips(bot)
			try:
				tips.refresh()
			except Exception as e:
				log("Met '{}: {}' while getting Tips object".format(type(e),str(e)),type="error")
				await bot.close()
			else:
				log("Initialised!",type="success")
		except Exception as e:
			log("Met '{}: {}'".format(type(e),str(e)),type="error")
			await bot.close()

try:
	log("Logging into discord...")
	bot.run(credentials["discordt"])
except discord.errors.LoginFailure as e:
	log("Your token was invalid! Met error '{}: {}'".format(type(e),str(e)),type="error")