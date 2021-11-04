import asyncpraw as praw
import discord
from discord.ext import commands,tasks
from discord.ext.commands import Bot
from TermManip import *
from yaml import safe_load as load
import asyncio
import re
import time
import subprocess
from datetime import datetime
import hashlib
try: 
	from BeautifulSoup import BeautifulSoup
except ImportError:
	from bs4 import BeautifulSoup
import requests

def unixtime(unix):
	return time.strftime("%D %H:%M", time.localtime(int(unix)))

start=unixtime(time.time())
uses=0

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
		self.refreshed=None

	@staticmethod
	def tipname(name): 
		title=re.findall(r"Eitra and Emi(?:'s (?:[Ss]ex )?[Tt]ips)?[: ]+#?\d+(?: \(.+\))?",name)
		if len(title)==0:
			return None
		else:
			return (title[0],int(re.findall(r"\d+",title[0])[0]))

	async def refresh(self):
		self.subreddit=await reddit.subreddit(self.subredditname, fetch=True)
		self.tips={}
		clashing={}

		async for post in self.subreddit.search(f"Eitra and Emi",sort="new",limit=None):
			index=self.tipname(post.title)
			if index:
				if index[1] in self.tips:
					clashing[index[1]]=[self.tips[index[1]],self.Tip(self,post,index[0])]
				if index[1] in clashing:
					clashing[index[1]]+=[self.Tip(self,post,index[0])]
				else:
					self.tips[index[1]]=self.Tip(self,post,index[0])

		missing=[]
		for post in range(1,max(self.tips.keys())+1):
			if not post in self.tips:
				missing+=[post]

		if missing!=[]:
			log("Missing tips "+", ".join(str(val) for val in missing),type="error")
		if clashing!={}:
			log("Tips {} have conflicting posts".format(", ".join(str(val) for val in clashing.keys())),type="error")

		leftovers=[]
		for clash in clashing:
			previous=self.tips[clash-1]
			candidates=clashing[clash]
			closest=[float("inf"),None]
			for candidateN,candidate in enumerate(candidates):
				if candidate.post.created_utc-previous.post.created_utc < closest[0]:
					closest[1]=candidateN
			self.tips[clash]=candidates.pop(closest[1])
			leftovers+=candidates

		for missingN in reversed(range(len(missing))):
			gone=missing[missingN]
			previous=self.tips[gone-1]
			closest=[float("inf"),None]
			for candidateN,candidate in enumerate(leftovers):
				if candidate.post.created_utc-previous.post.created_utc < closest[0]:
					closest[1]=candidateN
			self.tips[gone]=leftovers.pop(closest[1])
			missing.pop(missingN)

		if missing!=[]:
			log("Could not resolve missing tips "+", ".join(str(val) for val in missing),type="error")

		self.refreshed=unixtime(time.time())

	class Tip:
		def __init__(self,parent,post,index):
			self.parent=parent
			self.post=post
			self.index=index

		async def refresh(self):
			self.image=self.post.url
			if "ibb.co" in self.image:
				page=requests.get(self.image).text 
				page=BeautifulSoup(page,features="lxml")
				self.image=page.find("link",attrs={'rel':'image_src'})["href"]
			self.title=self.post.title
			self.url="https://reddit.com/"+self.post.id
			self.creation=unixtime(self.post.created_utc)
			self.votes=self.post.score
			self.comments=self.post.num_comments
			self.flair=self.post.link_flair_text

		async def embed(self):
			if not hasattr(self,"image"):
				try:
					await self.refresh()
				except Exception as e:
					log("Met '{}: {}'".format(type(e),str(e)),type="error")
					return None
			embed=discord.Embed(
				title=self.title, url=self.url,
				description="["+self.flair+"]" if self.flair!=None else "",
				color=int(hashlib.md5(self.flair.encode("utf-8")).hexdigest()[:6],16) if self.flair!=None else 0xe9d357
			)
			embed.set_footer(
				text="Created at {} | {} Votes | {} Comment{}".format(
					self.creation,self.votes,self.comments,
					"s" if self.comments!=1 else ""
				)
			)
			embed.set_image(url=self.image)
			return embed

	def tip(self,index):
		return self.tips[index]

	def __len__(self):
		return max(self.tips.keys())

bot=commands.Bot(command_prefix="-")

def ranges(ranges):
	for arange in ranges:
		if arange=="": continue
		elif "-" not in arange:
			yield int(arange)
		else:
			arange=arange.split("-")
			arange[0]=int(arange[0])
			arange[1]=int(arange[1])
			if arange[0]>arange[1]: 
				arange.push(arange[0])
				arange.pop(0)
			for n in range(arange[0],arange[1]+1):
				yield n

async def tipembed(id):
	try:
		embed=await tips.tip(int(id)).embed()
	except KeyError:
		return discord.Embed(title="Error!", description=f"Tip {id} does not exist!", color=0xff0000)
	return embed

@bot.command(
	pass_context=True,aliases=["tip","tips","sextips"],
	usage="[tip number(s)]",
	description="Get sex tip"
)
async def sextip(ctx,*id):
	panels=list(ranges(" ".join(id).replace(","," ").split(" ")))
	if len(panels)==1:
		await ctx.send(embed=await tipembed(panels[0]))
		return

	pos=0
	embed=await tipembed(panels[0])
	embed.set_footer(text=embed.footer.text+" ({}/{})".format(pos+1,len(panels)))
	msg=await ctx.send(embed=embed)
	for reaction in ['⬅️','➡️']:
		await msg.add_reaction(reaction)

	def check(reaction, user):
		return reaction.message==msg and str(reaction.emoji) in ['⬅️','➡️'] and user!=bot.user

	try:
		while True:
			reaction, user = await bot.wait_for('reaction_add', timeout=300, check=check)
			await reaction.remove(user)
			emoji=str(reaction)
			if emoji=='⬅️':
				pos-=1
			elif emoji=='➡️':
				pos+=1
			pos=pos%len(panels)
			embed=await tipembed(panels[pos])
			embed.set_footer(text=embed.footer.text+" ({}/{})".format(pos+1,len(panels)))
			await msg.edit(embed=embed)

	except asyncio.TimeoutError:
		for reaction in ['⬅️','➡️']:
			await msg.clear_reaction(reaction)
		embed=await tipembed(panels[pos])
		embed.set_footer(text=embed.footer.text+" (timed out)")
		await msg.edit(embed=embed)

@bot.command(pass_context=True,description="Shows subreddit stats")
async def reddit(ctx):
	subreddit=tips.subreddit
	embed=discord.Embed(description=subreddit.public_description)
	embed.set_author(
		name="Eitra and Emi's Sex Tips\nr/"+tips.subredditname, 
		url="https://reddit.com/r/"+tips.subredditname, 
		icon_url=tips.subreddit.icon_img if tips.subreddit.icon_img else bot.user.avatar_url
	)
	embed.add_field(name="Members", value=subreddit.subscribers, inline=True)
	embed.add_field(
		name="Created at", 
		value=time.strftime("%D %H:%M", time.localtime(subreddit.created_utc)), inline=True
	)
	embed.add_field(
		name="Panels",
		value=str(len(tips)), inline=True
	)
	await ctx.send(embed=embed)

@bot.command(pass_context=True,description="Shows bot info")
async def info(ctx):
	embed=discord.Embed(
		description="Report bugs: Dalithop#2545\n"
		            "Source code: https://github.com/lomnom/Emi/"
	)
	embed.set_author(
		name="Eitra & Emi bot, a bot that fetches sex tips from r/EritraAndEmi",
		url="https://github.com/lomnom/Emi", icon_url=bot.user.avatar_url
	)
	embed.add_field(name="Times invoked", value=uses, inline=True)
	embed.add_field(name="Last reload", value=tips.refreshed, inline=True)
	embed.add_field(name="Last restart", value=start, inline=True)
	embed.add_field(
		name="Last commit (local)", 
		value=unixtime(int(str(
			subprocess.check_output("git log -1 --date=unix --pretty=format:%cd".split(" "))
		,encoding="ascii"))),
		inline=True
	)
	embed.set_footer(text="Made by u/dalithop, with boredom:tm:")
	await ctx.send(embed=embed)

@tasks.loop(minutes=1)
async def reload():
	log("Auto-reloading...")
	await tips.refresh()
	log("Reloaded!",type="success")

@bot.command(pass_context=True,description="Reload panels from reddit. Already happens every 30mins. Admin command.")
@commands.has_permissions(administrator=True)
async def reload(ctx):
	msg=await ctx.send(embed=
		discord.Embed(description="Reloading panels...",title="Progress")
	)
	await tips.refresh()
	await msg.edit(embed=
		discord.Embed(description="Reloaded panels!",title="Success",color=0x00ff44)
	)

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
				await tips.refresh()
			except Exception as e:
				log("Met '{}: {}' while getting Tips object".format(type(e),str(e)),type="error")
				await bot.close()
			else:
				log("Initialised!",type="success")
		except Exception as e:
			log("Met '{}: {}'".format(type(e),str(e)),type="error")
			await bot.close()

@bot.event
async def on_command(ctx):
	global uses
	uses+=1

try:
	log("Logging into discord...")
	bot.run(credentials["discordt"])
except discord.errors.LoginFailure as e:
	log("Your token was invalid! Met error '{}: {}'".format(type(e),str(e)),type="error")