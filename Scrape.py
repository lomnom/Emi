############ import stuff
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

############ initialise stats
def unixtime(unix):
	return time.strftime("%D %H:%M", time.localtime(int(unix)))

start=unixtime(time.time())
uses=0

############ load passwords
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

############ scraper defenition
class Tips:
	def __init__(self,bot):
		self.subredditname="r/EitraAndEmi".lstrip("r/")
		self.bot=bot
		self.loop=self.bot.loop
		self.refreshed=None

	@staticmethod
	def tipname(name): #gets a tip title and tip index
		title=re.findall(r"Eitra and Emi(?:'s (?:[Ss]ex )?[Tt]ips)?[: ]+#?\d+(?: \(.+\))?",name)
		if len(title)==0:
			return None
		else:
			return (title[0],int(re.findall(r"\d+",title[0])[0]))

	async def refresh(self): #load tips
		self.subreddit=await reddit.subreddit(self.subredditname, fetch=True)
		self.tips={}
		clashing={}

		# look through all posts in subreddit that may be panels
		async for post in self.subreddit.search(f"Eitra and Emi",sort="new",limit=None):
			index=self.tipname(post.title)
			if index: #check if post is actually panel
				if index[1] in clashing: #add to list of candidates for clashing panel, if clashing
					clashing[index[1]]+=[self.Tip(self,post,index[1])]
				elif index[1] in self.tips: #make clashing candidate entry
					clashing[index[1]]=[self.tips[index[1]],self.Tip(self,post,index[1])]
				else: # add normal panels to list of tips
					self.tips[index[1]]=self.Tip(self,post,index[1])

		#get missing panels
		missing=[]
		for post in range(1,max(self.tips.keys())+1):
			if not post in self.tips:
				missing+=[post]

		#print stats
		if missing!=[]:
			log("Missing tips "+", ".join(str(val) for val in missing),type="error")
		if clashing!={}:
			log("Tips {} have conflicting posts".format(", ".join(str(val) for val in clashing.keys())),type="error")

		leftovers=[] #list of tips not used to resolve clash
		for clash in clashing:
			previous=self.tips[clash-1]
			candidates=clashing[clash]
			closest=[float("inf"),None]
			for candidateN,candidate in enumerate(candidates): # get panel closest to previous panel in terms of time
				if candidate.post.created_utc-previous.post.created_utc < closest[0]:
					closest[1]=candidateN
			log("Resolved clash {} -> {}".format(candidates[closest[1]].post.id,clash),type="success")
			self.tips[clash]=candidates.pop(closest[1]) #resolve clash
			leftovers+=candidates

		#resolve missing panels with panels that did not resolve clashes
		for missingN in reversed(range(len(missing))):
			gone=missing[missingN]
			previous=self.tips[gone-1]
			closest=[float("inf"),None]
			for candidateN,candidate in enumerate(leftovers): #get panel closest to previous panel in time
				if abs(candidate.post.created_utc-previous.post.created_utc) < closest[0]:
					closest[1]=candidateN
					closest[0]=abs(candidate.post.created_utc-previous.post.created_utc)
			log(
				"Resolved missing {} ({}) -> {}".format(
					leftovers[closest[1]].post.id,
					leftovers[closest[1]].index,
					gone
				),type="success"
			)
			self.tips[gone]=leftovers.pop(closest[1]) #resolve missing
			missing.pop(missingN)

		if missing!=[]: #log failure
			log("Could not resolve missing tips "+", ".join(str(val) for val in missing),type="error")

		self.refreshed=unixtime(time.time()) #set refreshed stat

	############ scraper result
	class Tip:
		def __init__(self,parent,post,index):
			self.parent=parent
			self.post=post
			self.index=index

		#load
		async def refresh(self):
			self.image=self.post.url
			if "ibb.co" in self.image: #replace ibb.co links with image in site
				page=requests.get(self.image).text 
				page=BeautifulSoup(page,features="lxml")
				self.image=page.find("link",attrs={'rel':'image_src'})["href"]
			self.title=self.post.title
			self.url="https://reddit.com/"+self.post.id
			self.creation=unixtime(self.post.created_utc)
			self.votes=self.post.score
			self.comments=self.post.num_comments
			self.flair=self.post.link_flair_text

		# discord embed generator
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
				color=
					int(hashlib.md5(self.flair.encode("utf-8")).hexdigest()[:6],16) 
						if self.flair!=None 
						else 0xe9d357
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

def ranges(ranges): # ["1","1-2"] -> [1,1,2]
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

async def tipembed(id): #get tip's embed
	try:
		embed=await tips.tip(int(id)).embed()
	except KeyError:
		return discord.Embed(title="Error!", description=f"Tip {id} does not exist!", color=0xff0000)
	return embed

def appendFooter(embed,text): #append text to discord embed footer
	try:
		embed.set_footer(text=embed.footer.text+text)
	except TypeError:
		embed.set_footer(text=text.lstrip(" "))

#scraper command
@bot.command(
	pass_context=True,aliases=["tip","tips","sextips"],
	usage="[tip number(s)]",
	description="Get sex tip"
)
async def sextip(ctx,*id):
	panels=list(ranges(" ".join(id).replace(","," ").split(" ")))
	if len(panels)==1: #dont do fancy pagination if only one panel
		await ctx.send(embed=await tipembed(panels[0]))
		return

	pos=0 #panel index
	embed=await tipembed(panels[0])
	appendFooter(embed," ({}/{})".format(pos+1,len(panels))) #add position to footer ((1/2))
	msg=await ctx.send(embed=embed) #send first panel
	for reaction in ['⬅️','➡️']: #add reactions to scroll
		await msg.add_reaction(reaction)

	def check(reaction, user): #reaction checker
		return reaction.message==msg and str(reaction.emoji) in ['⬅️','➡️'] and user!=bot.user

	try:
		while True:
			reaction, user = await bot.wait_for('reaction_add', timeout=300, check=check) #wait for reaction
			await reaction.remove(user) #clear found reaction
			emoji=str(reaction)
			if emoji=='⬅️': #move based on reaction
				pos-=1
			elif emoji=='➡️':
				pos+=1
			pos=pos%len(panels) #make the position wrap around
			embed=await tipembed(panels[pos])
			appendFooter(embed," ({}/{})".format(pos+1,len(panels))) 
			await msg.edit(embed=embed) #update panel

	except asyncio.TimeoutError: #user didnt click anything for 5 mins
		for reaction in ['⬅️','➡️']: #remove scroll buttons
			await msg.clear_reaction(reaction)
		embed=await tipembed(panels[pos]) 
		appendFooter(embed," (timed out)") #add (timed out) to footer
		await msg.edit(embed=embed) #update embed

@bot.command(pass_context=True,description="Shows subreddit stats")
async def reddit(ctx): #show reddit stats
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
async def info(ctx): #show bot stats
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
	embed.add_field( #last commit
		name="Last commit (local)", 
		value=unixtime(int(str(
			subprocess.check_output("git log -1 --date=unix --pretty=format:%cd".split(" "))
		,encoding="ascii"))),
		inline=True
	)
	embed.set_footer(text="Made by u/dalithop, with boredom:tm:")
	await ctx.send(embed=embed)

refreshTime=30 #delay between refreshes
#refresh command
@bot.command(
	pass_context=True,
	description="Reload panels from reddit. Already happens every {}mins. Admin command.".format(refreshTime)
)
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
async def on_ready(): #initialize
	global reddit,tips,refreshTime
	log("logged into discord as '{0.user}'".format(bot),type='success')
	if reddit==None:
		log("Attempting to connect to reddit...")
		try:
			reddit=praw.Reddit( #log into reddit
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
				await tips.refresh() #load tips
			except Exception as e:
				log("Met '{}: {}' while getting Tips object".format(type(e),str(e)),type="error")
				await bot.close()
			else:
				log("Initialised!",type="success")
		except Exception as e:
			log("Met '{}: {}'".format(type(e),str(e)),type="error")
			await bot.close()
		#refresh task
		while True:
			await asyncio.sleep(refreshTime*60)
			log("Auto-reloading...")
			try:
				await tips.refresh() #load tips
			except Exception as e:
				log("Met '{}: {}' while auto-refreshing".format(type(e),str(e)),type="error")
			else:
				log("Reloaded!",type="success")

@bot.event
async def on_command(ctx):
	global uses
	uses+=1

try:
	log("Logging into discord...")
	bot.run(credentials["discordt"])
except discord.errors.LoginFailure as e:
	log("Your token was invalid! Met error '{}: {}'".format(type(e),str(e)),type="error")