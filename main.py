import discord
from discord.ext import commands
import yt_dlp
import asyncio
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# ================= SETUP =================
intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None  # 🔥 default help OFF
)


queues = {}
repeat_mode = {}

# ================= SPOTIFY =================
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    )
)


# ================= READY =================
@bot.event
async def on_ready():
    print(f"✅ Bot Online: {bot.user}")

# ================= MUSIC CORE =================
async def play_next(ctx):
    gid = ctx.guild.id

    if gid not in queues or len(queues[gid]) == 0:
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        return

    url, title = queues[gid][0]

    ctx.voice_client.play(
        discord.FFmpegPCMAudio(
        url,
        executable="ffmpeg",  # just ffmpeg, no full path
        before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        options="-vn"
        ),
        after=lambda e: asyncio.run_coroutine_threadsafe(handle_after(ctx), bot.loop)
    )

    embed = discord.Embed(
        title="🎶 Now Playing",
        description=f"**{title}**",
        color=0x1DB954
    )
    embed.set_footer(text="Enjoy the music 🎧")
    await ctx.send(embed=embed, view=MusicButtons(ctx))


async def handle_after(ctx):
    gid = ctx.guild.id

    if repeat_mode.get(gid, False):
        await play_next(ctx)
    else:
        if queues.get(gid):
            queues[gid].pop(0)

        if queues.get(gid):
            await play_next(ctx)
        else:
            if ctx.voice_client:
                await ctx.voice_client.disconnect()

# ================= PLAY =================
@bot.command()
async def play(ctx, *, query):
    if not ctx.author.voice:
        await ctx.send("❌ Pehle voice channel join karo")
        return

    gid = ctx.guild.id
    queues.setdefault(gid, [])
    repeat_mode.setdefault(gid, False)

    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()

    msg = await ctx.send("🔍 Searching")
    frames = ["🔍 Searching", "🔍 Searching.", "🔍 Searching..", "🔍 Searching..."]
    for f in frames:
        await asyncio.sleep(0.35)
        await msg.edit(content=f)
    await msg.delete()

    # Spotify link
    if "open.spotify.com/track/" in query:
        track = sp.track(query)
        query = f"{track['name']} {track['artists'][0]['name']}"

    ydl_opts = {
        "format": "bestaudio",
        "default_search": "ytsearch",
        "quiet": True,
        "noplaylist": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        if "entries" in info:
            info = info["entries"][0]

    queues[gid].append((info["url"], info["title"]))

    if not ctx.voice_client.is_playing():
        await play_next(ctx)
    else:
        await ctx.send(f"➕ **Added to Queue:** {info['title']}")

# ================= CONTROLS =================
@bot.command()
async def skip(ctx):
    vc = ctx.voice_client
    if not vc:
        return

    vc.stop()

    q = queues.get(ctx.guild.id, [])
    if len(q) <= 1:
        queues[ctx.guild.id] = []
        await vc.disconnect()
        await ctx.send("⏹️ Queue khatam, music stopped")
    else:
        await ctx.send("⏭️ Skipped")

@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Paused")

@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Resumed")

@bot.command()
async def stop(ctx):
    queues[ctx.guild.id] = []
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    await ctx.send("⏹️ Stopped")

@bot.command()
async def repeat(ctx):
    gid = ctx.guild.id
    repeat_mode[gid] = not repeat_mode.get(gid, False)
    await ctx.send(f"🔁 Repeat {'ON' if repeat_mode[gid] else 'OFF'}")

@bot.command()
async def queue(ctx):
    q = queues.get(ctx.guild.id, [])
    if not q:
        await ctx.send("Queue khaali hai")
        return

    embed = discord.Embed(title="🎵 Queue", color=0x00ff00)
    for i, (_, title) in enumerate(q, 1):
        embed.add_field(name=f"{i}.", value=title, inline=False)
    await ctx.send(embed=embed)

# ================= BUTTONS =================
class MusicButtons(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=120)
        self.ctx = ctx

    @discord.ui.button(label="⏯ Pause", style=discord.ButtonStyle.gray)
    async def pause(self, interaction, button):
        vc = self.ctx.voice_client
        if vc and vc.is_playing():
            vc.pause()
        await interaction.response.send_message("⏸ Paused", ephemeral=True)

    @discord.ui.button(label="▶ Resume", style=discord.ButtonStyle.green)
    async def resume(self, interaction, button):
        vc = self.ctx.voice_client
        if vc and vc.is_paused():
            vc.resume()
        await interaction.response.send_message("▶ Resumed", ephemeral=True)

    @discord.ui.button(label="⏭ Skip", style=discord.ButtonStyle.blurple)
    async def skip(self, interaction, button):
        if self.ctx.voice_client:
            self.ctx.voice_client.stop()
        await interaction.response.send_message("⏭ Skipped", ephemeral=True)

    @discord.ui.button(label="⏹ Stop", style=discord.ButtonStyle.red)
    async def stop(self, interaction, button):
        queues[self.ctx.guild.id] = []
        if self.ctx.voice_client:
            await self.ctx.voice_client.disconnect()
        await interaction.response.send_message("⏹ Stopped", ephemeral=True)

# ================= FUN =================
# ======================================================
# =============== EXTENDABLE ROAST SYSTEM ===============
# ======================================================
last_roast = {}

ROASTS = [
    "Tu error 404 hai 🤡",
    "Tera dimaag buffering pe hai 😂",
    "Tu Windows Vista jaisa slow hai 🐌",
    "Tu bug nahi virus hai 😈",
    "Tu WiFi ke bina router hai 📡",
    "Tu infinite loop hai 🔁",
    "Tu logic ke khilaaf hai 🤯",
    "Tu debug hone layak bhi nahi 💀",
    "Tu null pointer exception hai 🤦",
    "Tu semicolon bhool gaya hai ;",
    "Tu syntax error ka poster boy hai 📛",
    "Tu compile se pehle hi fail hai ❌",
    "Tu runtime error ka reason hai 🔥",
    "Tu comment me zyada kaam karta hai 📝",
    "Tu copy-paste developer hai 📋",
    "Tu StackOverflow ka silent reader hai 👀",
    "Tu production me print() use karta hai 🖨️",
    "Tu Git commit bina message ke karta hai 😶",
    "Tu main branch pe direct push karta hai 🚨",
    "Tu indentation ka dushman hai 📐",
    "Tu Python ko Java samajhta hai 🤡",
    "Tu code dekh ke hi dar jata hai 😱",
    "Tu TODO likh ke bhool jata hai 📌",
    "Tu test case ka naam bhi nahi janta 🧪",
    "Tu hardcode ka brand ambassador hai 🏆",
    "Tu infinite while loop hai 🌀",
    "Tu documentation skip karta hai 📖❌",
    "Tu variable ko x, y, z se aage nahi badhata 😵",
    "Tu logic likhne se pehle run karta hai 🏃",
    "Tu error aaye to system ko gaali deta hai 💢",
    "Tu code formatting ka criminal hai 🚔",
    "Tu exception ko ignore karta hai 🙈",
    "Tu password = 1234 rakhta hai 🔓",
    "Tu backup lena bhool jata hai 💾❌",
    "Tu server restart pe hi zinda rehta hai 🔄",
    "Tu CSS me bhi !important use karta hai 😤",
    "Tu frontend me backend dhundhta hai 🤔",
    "Tu backend me UI fix karta hai 🎨",
    "Tu API bina auth ke bana deta hai 🔓",
    "Tu database me bhi typo karta hai 🗄️",
    "Tu SELECT * ka fanboy hai ⭐",
    "Tu code review se bhaagta hai 🏃‍♂️",
    "Tu warning ko error samajhta hi nahi ⚠️",
    "Tu memory leak ka source hai 💧",
    "Tu framework change karta rehta hai 🔄",
    "Tu tutorial hell me atka hua hai 📺",
    "Tu hello world pe hi proud hai 🎉",
    "Tu exception ka stack trace delete karta hai 🗑️",
    "Tu cache clear karke hero banta hai 🦸",
    "Tu localhost ka hi developer hai 🏠",
    "Tu production me experiment karta hai 💣",
    "Tu merge conflict ka creator hai ⚔️",
    "Tu branch ka naam test123 rakhta hai 🌿",
    "Tu pull request bina description ke bhejta hai 📭",
    "Tu bug ko feature bol deta hai 🐛✨",
    "Tu UI break karke bolta hai design hai 🎨",
    "Tu deadline se pehle gayab ho jata hai 🕳️",
    "Tu meeting me sirf mute rehta hai 🎧",
    "Tu code me magic numbers bharta hai 🔢",
    "Tu logic ko comment me likh deta hai 📝",
    "Tu naming convention ka dushman hai 📛",
    "Tu variable reuse ka champion hai 🏅",
    "Tu exception handling ko ignore karta hai 🚫",
    "Tu server down hone pe chai peene chala jata hai ☕",
    "Tu regex ko kala jadoo samajhta hai 🪄",
    "Tu API response bina check ke use karta hai 📦",
    "Tu code ko samajhne se pehle delete karta hai 🗑️",
    "Tu indentation error ka king hai 👑",
    "Tu documentation me bhi typo karta hai 📚",
    "Tu config file me secrets daal deta hai 🔑",
    "Tu env file ko git me push karta hai 🚨",
    "Tu testing ko time waste bolta hai ⏳",
    "Tu bug milne pe system format karta hai 💽",
    "Tu production bug pe bolta hai mere me to chal raha tha 🤷",
    "Tu code likh ke khud hi bhool jata hai 🧠❌",
    "Tu logic se zyada luck pe depend karta hai 🍀",
    "Tu error message padhe bina Google karta hai 🔍",
    "Tu GitHub repo me sirf README change karta hai 📄",
    "Tu code ko bhi copy-paste karna sikhata hai 🤡",
    "Tu programming me bhi shortcut dhundhta hai ⚡",
    "Tu crash hone pe blame network pe daal deta hai 🌐",
    "Tu developer kam tester zyada hai 🧪",
    "Tu bug ko ignore karke release kar deta hai 🚀",
    "Tu infinite console.log() hai 📢",
    "Tu logic likhne se pehle excuse ready rakhta hai 🗣️",
    "Tu code kam comments zyada hai 💬",
    "Tu final_final_v3.py banata hai 📂",
    "Tu deadline ka enemy hai ⏰",
    "Tu error aaye to bolta hai kal dekhte hain 😴",
]

@bot.command()
async def roast(ctx, member: discord.Member):
    user_id = member.id
    choices = ROASTS.copy()
    
    # Remove last roast for this user to avoid consecutive repeat
    if user_id in last_roast and last_roast[user_id] in choices:
        choices.remove(last_roast[user_id])
    
    roast_text = random.choice(choices)
    last_roast[user_id] = roast_text  # Save this roast
    
    await ctx.send(f"{member.mention} {roast_text}")

# ======================================================
# =============== EXTENDABLE GIF SYSTEM =================
# ======================================================
last_gif_used = {}
GIF_ACTIONS = {
    "slap": [
        "https://i.giphy.com/media/Gf3AUz3eBNbTW/giphy.gif",
        "https://i.giphy.com/media/Zau0yrl17uzdK/giphy.gif",
    ],
    "hug": [
        "https://i.giphy.com/media/l2QDM9Jnim1YVILXa/giphy.gif",
        "https://i.giphy.com/media/od5H3PmEG5EVq/giphy.gif",
        "https://tenor.com/view/don-gif-9520776680112053549",
        "https://tenor.com/view/love-hug-gif-17621374351848281543",
        "https://tenor.com/view/love-language-gif-13060693434493746516",
    ],
    "kiss": [
        "https://i.giphy.com/media/G3va31oEEnIkM/giphy.gif",
        "https://i.giphy.com/media/FqBTvSNjNzeZG/giphy.gif",
        "https://cdn.weeb.sh/images/Sk1k3TdPW.gif",
        "https://cdn.weeb.sh/images/B1yv36_PZ.gif",
        "https://cdn.weeb.sh/images/SJQRoTdDZ.gif",
        "https://cdn.weeb.sh/images/SJ3dXCKtW.gif",
        "https://cdn.weeb.sh/images/BJLP3a_Pb.gif",
        "https://cdn.weeb.sh/images/S1VEna_v-.gif",
        "https://cdn.weeb.sh/images/S1E1npuvb.gif",
    ],
    "kick": [
        "https://tenor.com/view/milk-and-mocha-bear-couple-bear-hug-kick-shut-up-gif-17443923",
        "https://tenor.com/view/kicking-him-alan-smiling-friends-knocked-out-kicking-his-teeth-out-gif-14787404105374321547",
        "https://tenor.com/view/kick-go-away-clannad-anime-gif-15250837843769760584",
    ],
    "punch": [
        "https://i.giphy.com/media/11HeubLHnQJSAU/giphy.gif",
        "https://i.giphy.com/media/arbHBoiUWUgmc/giphy.gif",
        "https://media.giphy.com/media/XDRoTw2Fs6rlIW7yQL/giphy.gif",
    ],
}

def create_gif_command(action_name):

    @bot.command(name=action_name)
    async def action(ctx, member: discord.Member = None):
        if member is None:
            await ctx.send(f"❌ Use like this: `!{action_name} @user`")
            return

        gifs = GIF_ACTIONS[action_name]

        # --- Anti-repeat logic ---
        last = last_gif_used.get(action_name)

        if len(gifs) > 1:
            gif = random.choice([g for g in gifs if g != last])
        else:
            gif = gifs[0]

        last_gif_used[action_name] = gif
        # -------------------------

        embed = discord.Embed(
            description=f"{ctx.author.mention} **{action_name}** {member.mention}",
            color=0xff0055
        )
        embed.set_image(url=gif)
        await ctx.send(embed=embed)


for action in GIF_ACTIONS:
    create_gif_command(action)





# ================= HELP =================

@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="🤖 Bot Help Menu",
        description="Neeche saari available commands category wise di gayi hain 👇",
        color=0x5865F2
    )

    embed.set_thumbnail(url=ctx.bot.user.avatar.url)

    # 🎵 MUSIC
    embed.add_field(
        name="🎵 Music Commands",
        value=(
            "`!play <song name / link>` – Song play / queue me add\n"
            "`!skip` – Current song skip\n"
            "`!pause` – Music pause\n"
            "`!resume` – Music resume\n"
            "`!stop` – Music stop & leave VC\n"
            "`!repeat` – Repeat ON / OFF\n"
            "`!queue` – Current queue dekho"
        ),
        inline=False
    )

    # 🎮 BUTTONS
    embed.add_field(
        name="🎛️ Music Buttons",
        value=(
            "⏯ Pause Button\n"
            "▶ Resume Button\n"
            "⏭ Skip Button\n"
            "⏹ Stop Button\n"
            "_(Buttons Now Playing message ke niche hote hain)_"
        ),
        inline=False
    )

    # 🎬 GIF ACTIONS
    embed.add_field(
        name="🎬 GIF Actions",
        value=(
            "`!slap @user`\n"
            "`!hug @user`\n"
            "`!kiss @user`\n"
            "`!kick @user`\n"
            "`!punch @user`\n"
            "_Random GIF har baar aata hai_"
        ),
        inline=False
    )

    # 😈 ROAST
    embed.add_field(
        name="😈 Roast Commands",
        value="`!roast @user` – Random savage roast 😈",
        inline=False
    )

    # ℹ️ INFO
    embed.add_field(
        name="ℹ️ Info",
        value="Prefix: `!`\nBot banaya gaya hai full entertainment + music ke liye 🎧🔥",
        inline=False
    )

    embed.set_footer(
        text=f"Requested by {ctx.author}",
        icon_url=ctx.author.avatar.url
    )

    await ctx.send(embed=embed)














# ================= Correct Command =================
@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.CommandNotFound):
        await ctx.send(
            "❌ Ye command exist nahi karti.\n"
            "📌 `!help` likho saari commands dekhne ke liye"
        )
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"❌ Galat usage.\n"
            f"📌 Correct use: `{ctx.prefix}{ctx.command} @user`"
        )
        return

    # Optional: ignore other errors
    raise error



# ================= RUN =================
bot.run(DISCORD_TOKEN)