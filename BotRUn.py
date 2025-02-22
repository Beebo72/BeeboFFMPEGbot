import discord
from discord.ext import commands
from discord import app_commands
import subprocess
import shlex
import os
import asyncio
import aiohttp
import aiofiles
import tempfile
import random
import string
import wave
import struct
import time
import platform
import psutil
import json
from wand.image import Image
from wand.color import Color
import yt_dlp

# Create the bot instance with command prefix
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="bfb!", intents=intents)
bot.owner_id = 917183936940113931  # Set the bot owner's ID

# Directory for uploads
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)



# On bot ready event
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'We have logged in as {bot.user}')

    activity = discord.Activity(type=discord.ActivityType.listening, name="Weird AL Albuquerque")
    await bot.change_presence(status=discord.Status.idle, activity=activity)


# FFMPEG command to process video
@bot.command()
async def ffmpeg(ctx, *, command):
    """
    Execute an FFmpeg command on a Discord video link, uploaded file, or reply.
    Example usage: !ffmpeg -vf "scale=320:240"
    """
    attachment_url = None

    # Check for attachments or replied media
    if ctx.message.reference:
        referenced_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if referenced_message.attachments:
            attachment_url = referenced_message.attachments[0].url
    if not attachment_url and ctx.message.attachments:
        attachment_url = ctx.message.attachments[0].url

    if not attachment_url:
        await ctx.send("Please provide a video attachment or link.")
        return

    try:
        # Download the file
        file_name = os.path.join(UPLOAD_DIR, f"input_{ctx.author.id}.mp4")
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment_url) as response:
                if response.status == 200:
                    with open(file_name, "wb") as f:
                        f.write(await response.read())
                else:
                    await ctx.send("Failed to download the video.")
                    return

        sanitized_command = shlex.split(command)

        # Prepare output file
        output_file = os.path.join(UPLOAD_DIR, f"output_{ctx.author.id}.mp4")
        if not any(arg.endswith(".mp4") for arg in sanitized_command):
            sanitized_command.append(output_file)

        # Run FFmpeg command asynchronously
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i", file_name,
            *sanitized_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if os.path.exists(output_file):
            await ctx.send("Command executed successfully.", file=discord.File(output_file))
            os.remove(output_file)
        else:
            await ctx.send(f"Error executing command:\n```{stderr.decode()}```")

        if os.path.exists(file_name):
            os.remove(file_name)

    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

# Slash command to process video with FFmpeg (synchronous)
@bot.tree.command(name="ffmpeg_any", description="Execute an FFmpeg command on a video")
async def ffmpeg_any(interaction: discord.Interaction, command: str, attachment: discord.Attachment = None, url: str = None):
    """Process a video from attachment or URL using FFmpeg."""
    await interaction.response.defer()

    if not attachment and not url:
        await interaction.followup.send("Please provide a video attachment or URL.")
        return

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    output_file = temp_file.name.replace(".mp4", "_output.mp4")

    try:
        if attachment:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as response:
                    if response.status == 200:
                        with open(temp_file.name, "wb") as f:
                            f.write(await response.read())
                    else:
                        await interaction.followup.send("Failed to download the video.")
                        return
            input_source = temp_file.name

        elif url:
            input_source = url

        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", input_source, *shlex.split(command), output_file,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            await interaction.followup.send(f"Error executing FFmpeg:\n```{stderr.decode()}```")
            return

        if os.path.exists(output_file):
            await interaction.followup.send("Here is your processed video:", file=discord.File(output_file))

    finally:
        os.remove(temp_file.name)
        if os.path.exists(output_file):
            os.remove(output_file)

# Command to edit video audio using SoX

@bot.tree.command(name="sox_edit", description="Edit video audio using a SoX command")
async def sox_edit(interaction: discord.Interaction, video: discord.Attachment, sox_command: str):
    await interaction.response.defer()  # Avoid timeout

    # File paths
    input_video = "input.mp4"
    extracted_audio = "audio.wav"
    processed_audio = "processed_audio.wav"
    output_video = "output.mp4"

    # Download the video
    await video.save(input_video)

    try:
        # Extract audio from video
        subprocess.run(["ffmpeg", "-i", input_video, "-q:a", "0", "-map", "a", extracted_audio], check=True)

        # Construct the SoX command dynamically
        sox_cmd = f"sox {extracted_audio} {processed_audio} {sox_command}"
        process = subprocess.run(sox_cmd, shell=True, text=True, capture_output=True)

        # Check for warnings but allow the process to continue
        if "clipped" in process.stderr.lower():
            await interaction.followup.send(f"Warning: SoX reported clipping: {process.stderr}")

        # Merge processed audio back to video
        subprocess.run([
            "ffmpeg", "-i", input_video, "-i", processed_audio, "-c:v", "copy",
            "-map", "0:v:0", "-map", "1:a:0", "-shortest", output_video
        ], check=True)

        # Send the processed video
        await interaction.followup.send(file=discord.File(output_video))

    except subprocess.CalledProcessError as e:
        await interaction.followup.send(f"Error processing video: {e}")

    finally:
        # Clean up
        for f in [input_video, extracted_audio, processed_audio, output_video]:
            if os.path.exists(f):
                os.remove(f)

# Function to generate Bytebeat audio
def generate_bytebeat(formula: str, sample_rate: int, duration: int, filename="bytebeat.wav"):
    num_samples = sample_rate * duration
    samples = []

    for t in range(num_samples):
        try:
            sample = eval(formula, {"t": t}, {})
            sample = max(0, min(255, int(sample)))
        except Exception as e:
            return str(e)

        sample = (sample - 128) * 256
        samples.append(sample)

    with wave.open(filename, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        for sample in samples:
            wav_file.writeframes(struct.pack('<h', sample))

    return None

# Slash command to generate Bytebeat audio
@bot.tree.command(name="bytebeat", description="Generate a Bytebeat audio file.")
async def bytebeat(interaction: discord.Interaction, formula: str, sample_rate: int):
    await interaction.response.defer()

    error = generate_bytebeat(formula, sample_rate, 30)

    if error:
        await interaction.followup.send(f"Error in formula: {error}")
        return

    with open("bytebeat.wav", "rb") as f:
        await interaction.followup.send(file=discord.File(f, "bytebeat.wav"))


OPENWEATHER_API_KEY = "api key 1"
GOOGLE_MAPS_API_KEY = "api key 2"

async def get_weather(location):
    """Fetch weather data from OpenWeatherMap."""
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&units=metric&appid={OPENWEATHER_API_KEY}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            return None

async def send_weather_embed(ctx, location):
    """Fetch weather and send an embed with a location map."""
    weather_data = await get_weather(location)
    if not weather_data or weather_data.get("cod") != 200:
        await ctx.send(f"Couldn't find weather data for `{location}`.")
        return

    # Extract weather info
    city = weather_data["name"]
    country = weather_data["sys"]["country"]
    temp = weather_data["main"]["temp"]
    weather_desc = weather_data["weather"][0]["description"].capitalize()
    icon = weather_data["weather"][0]["icon"]
    lat, lon = weather_data["coord"]["lat"], weather_data["coord"]["lon"]

    # Google Maps Static Image URL
    map_url = f"https://maps.googleapis.com/maps/api/staticmap?center={lat},{lon}&zoom=10&size=600x300&markers=color:red%7C{lat},{lon}&key={GOOGLE_MAPS_API_KEY}"

    # Create Embed
    embed = discord.Embed(title=f"Weather in {city}, {country}", color=discord.Color.blue())
    embed.set_thumbnail(url=f"http://openweathermap.org/img/wn/{icon}.png")
    embed.add_field(name="Temperature", value=f"{temp}°C", inline=True)
    embed.add_field(name="Condition", value=weather_desc, inline=True)
    embed.add_field(name="Location", value=f"Lat: {lat}, Lon: {lon}", inline=False)
    embed.set_image(url=map_url)  # Map Image

    await ctx.send(embed=embed)

@bot.command(name="weather")
async def weather_command(ctx, *, location: str):
    """Prefixed command: !weather <location>"""
    await send_weather_embed(ctx, location)

@bot.tree.command(name="weather", description="Get weather information for a location")
async def weather_slash(interaction: discord.Interaction, location: str):
    """Slash command: /weather <location>"""
    await interaction.response.defer()  # Defer response to avoid timeout
    await send_weather_embed(interaction.followup, location)  # Use followup to send messages


bot.run("token")
