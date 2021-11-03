import asyncpraw as praw
import discord
from discord.ext import commands
from discord.ext import tasks
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

start=str(datetime.now()).split(" ")[0]
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
		self.loop.create_task(self.refresh())

	@staticmethod
	def tipname(name): 
		title=re.findall(r"Eitra and Emi's (?:[Ss]ex )?[Tt]ips[: ]+#?\d+(?: \(.+\))?",name)
		if len(title)==0:
			return None
		else:
			return (title[0],int(re.findall(r"\d+",name)[0]))

	async def refresh(self):
		self.subreddit=await reddit.subreddit(self.subredditname, fetch=True)
		self.tips={}
		async for post in self.subreddit.search(f"Eitra and Emi's Tips: ",sort="new",limit=None):
			index=self.tipname(post.title)
			try:
				self.tips[index[1]]=self.Tip(self,post,index[1])
			except TypeError:
				raise TypeError("Title '{}'' couldnt be proccessed properly".format(post.title))

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
			self.creation=time.strftime("%D %H:%M", time.localtime(self.post.created_utc))
			self.votes=self.post.score
			self.comments=self.post.num_comments
			self.flair=self.post.link_flair_text
			self.embed=discord.Embed(
				title=self.title, url=self.url,
				description="["+self.flair+"]" if self.flair!=None else "",
				color=int(hashlib.md5(self.flair.encode("utf-8")).hexdigest()[:6],16) if self.flair!=None else 0xe9d357
			)
			self.embed.set_footer(
				text="Created at {} | {} Votes | {} Comment{}".format(
					self.creation,self.votes,self.comments,
					"s" if self.comments!=1 else ""
				)
			)
			self.embed.set_image(url=self.image)

	def tip(self,index):
		return self.tips[index]

bot=commands.Bot(command_prefix="-")

def ranges(ranges):
	for arange in ranges:
		if "-" not in arange:
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
		tip=tips.tip(int(id))
	except KeyError:
		return discord.Embed(title="Error!", description=f"Tip {id} does not exist!", color=0xff0000)
	if not hasattr(tips.tip(int(id)),"image"):
		try:
			await tip.refresh()
		except Exception as e:
			log("Met '{}: {}'".format(type(e),str(e)),type="error")
			return None
	return tip.embed

@bot.command(
	pass_context=True,aliases=["tip","tips","sextips"],
	usage="[tip number(s)]",
	description="Get sex tip"
)
async def sextip(ctx,*id):
	panels=list(ranges(id))
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
	embed.add_field(name="Last restart", value=start, inline=True)
	embed.add_field(
		name="Last commit (local)", 
		value=str(
			subprocess.check_output("git log -1 --date=short --pretty=format:%cd".split(" "))
		,encoding="ascii"),
		inline=True
	)
	embed.add_field(name="Times used", value=uses, inline=True)
	embed.set_footer(text="Made by u/dalithop, with boredom:tm:")
	await ctx.send(embed=embed)

@tasks.loop(minutes=30)
async def reload():
	tips.refresh()

@bot.command(pass_context=True,description="Reload panels from reddit. Already happens every 30mins")
@commands.has_permissions(administrator=True)
async def reload(ctx):
	await tips.refresh()
	await ctx.send(embed=
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