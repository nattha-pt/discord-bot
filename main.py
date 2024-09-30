import discord
import asyncio
import random
import yt_dlp
from discord.ext import commands
from discord.ui import Button, View
from collections import deque
import os
from dotenv import load_dotenv

# โหลด environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ตรวจสอบว่า TOKEN ถูกตั้งค่าหรือไม่
if TOKEN is None:
    print("Error: DISCORD_TOKEN is not set in .env")
    exit(1)

# กำหนด intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# สร้าง bot
bot = commands.Bot(command_prefix='.', intents=intents)

class MusicControlView(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(label="⏸️ หยุดชั่วคราว", style=discord.ButtonStyle.secondary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await pause(self.ctx)

    @discord.ui.button(label="▶️ เล่นต่อ", style=discord.ButtonStyle.success)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await resume(self.ctx)

    @discord.ui.button(label="⏭️ เพลงถัดไป", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await next_song(self.ctx)

    @discord.ui.button(label="💽 คิวเพลง", style=discord.ButtonStyle.secondary)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_queue(self.ctx)

    @discord.ui.button(label="❌ ปิดเพลง", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await stop(self.ctx)

    @discord.ui.button(label="👋 ออกไป", style=discord.ButtonStyle.danger)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await leave(self.ctx)

# สร้างคิวเพลงสำหรับแต่ละเซิร์ฟเวอร์
music_queues = {}

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

def get_youtube_info(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        return info_dict

async def play_next(ctx):
    if ctx.guild.id in music_queues and music_queues[ctx.guild.id]:
        next_song = music_queues[ctx.guild.id].popleft()
        await play_song(ctx, next_song['url'])
    else:
        await ctx.send("ไม่มีเพลงในคิวแล้วค่ะ")

async def play_song(ctx, url):
    voice_client = ctx.voice_client

    youtube_info = get_youtube_info(url)
    youtube_url = youtube_info['url']
    title = youtube_info['title']

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }

    if voice_client.is_playing():
        voice_client.stop()

    voice_client.play(discord.FFmpegPCMAudio(youtube_url, **ffmpeg_options), after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))

    embed = discord.Embed(title="กำลังเล่นเพลง", description=title, color=discord.Color.blue())
    embed.add_field(name="URL", value=url)
    
    view = MusicControlView(ctx)
    await ctx.send(embed=embed, view=view)

@bot.command(name='เล่น')
async def play(ctx, url: str):
    if not ctx.author.voice:
        await ctx.send("คุณต้องอยู่ในช่องเสียงเพื่อใช้คำสั่งนี้")
        return
    
    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()
    elif ctx.voice_client.channel != channel:
        await ctx.voice_client.move_to(channel)
    
    if ctx.guild.id not in music_queues:
        music_queues[ctx.guild.id] = deque()

    youtube_info = get_youtube_info(url)
    title = youtube_info['title']

    if ctx.voice_client.is_playing():
        music_queues[ctx.guild.id].append({'url': url, 'title': title})
        await ctx.send(f"เพิ่มเพลง '{title}' ลงในคิวแล้ว")
    else:
        await play_song(ctx, url)

@bot.command(name='ต่อไป')
async def next_song(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    else:
        await ctx.send("ไม่มีเพลงที่กำลังเล่นอยู่ค่ะ")

@bot.command(name='คิว')
async def show_queue(ctx):
    if ctx.guild.id in music_queues and music_queues[ctx.guild.id]:
        queue_list = "\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(music_queues[ctx.guild.id])])
        embed = discord.Embed(title="คิวเพลง", description=queue_list, color=discord.Color.green())
        await ctx.send(embed=embed)
    else:
        await ctx.send("ไม่มีเพลงในคิวค่ะ")

@bot.command(name='ปิดเพลง')
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        if ctx.guild.id in music_queues:
            music_queues[ctx.guild.id].clear()
        await ctx.send("แคทเทอรีนปิดเพลงและล้างคิวแล้ว")

@bot.command(name='ออกไป')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        if ctx.guild.id in music_queues:
            music_queues[ctx.guild.id].clear()
        await ctx.send("แคทเทอรีนออกจากช่องเสียงแล้ว 😢")

@bot.command(name='หยุด')
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send('หยุดเล่นเพลงชั่วคราว หากต้องการเล่นเพลงต่อ ให้พิมพ์คำสั่ง "เล่นต่อ"')

@bot.command(name='เล่นต่อ')
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("กำลังเล่นเพลงต่อ")
                
# BOT EVENTS
@bot.event
async def on_message(message):
    # ไม่ทำงานกับข้อความที่บอทเองส่ง
    if message.author == bot.user:
        return

    # เพิ่มข้อความ debug
    print(f"Received message: {message.content} from {message.author}")

    # ตรวจสอบว่าข้อความมีคำว่า 'เรียก' และการแท็กผู้ใช้
    if 'เรียก' in message.content and message.mentions:
        print(f"Message contains 'เรียก' and mentions: {message.mentions}")

        for user in message.mentions:
            try:
                dm_channel = await user.create_dm()
                await dm_channel.send(
                    f"คุณ {user.mention} ถูกตามให้มาเข้าร่วมการสนทนา 💬 โดย {message.author.mention}"
                )
                await message.channel.send(f"แคทเทอรีนไปตาม {user.mention} แล้วค่ะ")
            except discord.Forbidden:
                await message.channel.send(f"ไม่สามารถส่ง DM ไปยัง {user.mention}")
                print(f"ไม่สามารถส่ง DM ไปยัง {user.mention}")
            except Exception as e:
                await message.channel.send(f"เกิดข้อผิดพลาด: {e}")
                print(f"เกิดข้อผิดพลาด: {e}")

    await bot.process_commands(message)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    trigger_words = ['ยิงมัน', 'ยิงมันสิ', 'แคทเทอรีนยิงมัน', 'แคทเทอรีนยิง', 'ยิงมันสิแคทเทอรีน', 'แคทยิง']
    if any(word in message.content for word in trigger_words):
        if isinstance(message.channel, discord.TextChannel):
            try:
                mention = message.mentions[0]
            except IndexError:
                await message.channel.send("กรุณาระบุเป้าหมายค่ะ")
                return
            if mention and isinstance(mention, discord.Member):
                if message.author.guild_permissions.administrator or message.author.top_role > mention.top_role:
                    if mention.voice and mention.voice.channel:
                        await mention.edit(mute=True)
                        embed = discord.Embed(
                            description=f"ได้ค่ะ {mention.mention} ถูกปิดไมค์ 💀",
                            color=discord.Color.dark_grey()
                        )
                        embed.set_image(url="https://i.makeagif.com/media/6-19-2021/fWA1bv.gif")
                        await message.channel.send(embed=embed)
                        await asyncio.sleep(30)
                        await mention.edit(mute=False)
                        await message.channel.send(f"{mention.mention} ฟื้นแล้ว")
                    else:
                        await message.channel.send("เป้าหมายไม่อยู่แถวนี้ค่ะ")
                else:
                    if message.author.voice and message.author.voice.channel:
                        await message.author.edit(mute=True)
                        embed = discord.Embed(
                            description=f"คุณไม่ได้รับสิทธิ์นั้นค่ะ 😝 {message.author.mention} ถูกปิดไมค์แทน 💀",
                            color=discord.Color.red()
                        )
                        await message.channel.send(embed=embed)
                        await asyncio.sleep(15)
                        await message.author.edit(mute=False)
                        await message.channel.send(f"{message.author.mention} ฟื้นแล้ว")
                    else:
                        await message.channel.send("🤔")
            else:
                await message.channel.send("ฉันไม่รู้จักบุคคลที่ระบุค่ะ")
    await bot.process_commands(message)

# WELCOME MESSAGE
@bot.event
async def on_member_join(member):
    channel = bot.get_channel(952617523847778394)
    if channel:
        embed = discord.Embed(
            title="\u200B\n😤 **มุ่ ง สู ด ด ม ก า ว แ ล ะ ข อ ง เ ห ล ว** 🍻",
            description=f"ยินดีต้อนรับ {member.mention} เข้าสู่กิลด์นักผจญภัย!",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(
            name="\u200B\n📃 **วิธีเริ่มต้น**",
            value="กรุณาอ่านกฎและปฏิบัติตามให้เรียบร้อย",
            inline=False
        )
        embed.add_field(
            name="\n💬 **เข้าร่วมการสนทนา**",
            value="มาพูดคุยและทำความรู้จักกับเพื่อนๆ ในห้องแชทต่างๆ!",
            inline=False
        )
        embed.set_footer(
            text="\n🎉 เราหวังว่าคุณจะมีช่วงเวลาที่ดีในกิลด์ของเรา! 🎉"
        )

        await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(952617523847778394)
    if channel:
        embed = discord.Embed(
            title="👋 👋 👋 👋 👋 👋 👋",
            description=f"{member.name} ได้ลาออกจากกิลด์นักผจญภัย {member.guild.name}!",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=member.avatar.url)
        await channel.send(embed=embed)

bot.run(TOKEN)
