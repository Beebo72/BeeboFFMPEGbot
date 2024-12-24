import discord
from discord.ext import commands
import subprocess
import shlex
import os
import asyncio
import aiohttp
import re
from PIL import Image, ImageOps, ImageFilter
from io import BytesIO
from wand.image import Image


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="bfb!", intents=intents)

# Directory to store user-uploaded files
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {bot.user}")

@bot.command()
async def ffmpeg(ctx, *, command):
    """
    Execute an FFmpeg command on a Discord video link, uploaded file, or reply.
    Example usage: !ffmpeg -vf "scale=320:240"
    """
    # Check for admin role or user permissions if necessary
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You don't have permission to use this command.")
        return

    # Get the attachment or link from the message or reply
    attachment_url = None

    # Check if the user replied to a message
    if ctx.message.reference:
        referenced_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if referenced_message.attachments:  # Check for attachments in the replied-to message
            attachment_url = referenced_message.attachments[0].url
        else:  # Check for a video link in the replied-to message
            match = re.search(r'https?://cdn\.discordapp\.com/attachments/\S+', referenced_message.content)
            if match:
                attachment_url = match.group(0)

    # If no reply, check the user's own message for attachments or links
    if not attachment_url:
        if ctx.message.attachments:  # Check for attachments
            attachment_url = ctx.message.attachments[0].url
        else:  # Check for a video link in the user's message
            match = re.search(r'https?://cdn\.discordapp\.com/attachments/\S+', ctx.message.content)
            if match:
                attachment_url = match.group(0)

    if not attachment_url:
        await ctx.send("Please provide a video attachment, link, or reply to a video/link.")
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

        # Sanitize input FFmpeg command
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
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)  # 60-second timeout
        except asyncio.TimeoutError:
            process.kill()
            await ctx.send("Command timed out.")
            return

        # Send the output or error message
        if os.path.exists(output_file):
            await ctx.send("Command executed successfully.", file=discord.File(output_file))
            os.remove(output_file)
        else:
            await ctx.send(f"Error executing command:\n```{stderr.decode()}```")

        # Clean up
        if os.path.exists(file_name):
            os.remove(file_name)

    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")
@bot.command()
async def magik(ctx):
    """
    Apply a liquid rescale 'magik' effect to an image.
    Accepts uploaded images, image links, or replies to messages with images.
    """
    # Fetch the image from the message or reply
    image_url = None

    # Check if the user replied to a message with an image
    if ctx.message.reference:
        referenced_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if referenced_message.attachments:
            image_url = referenced_message.attachments[0].url

    # Check for attachments in the user's own message
    if not image_url and ctx.message.attachments:
        image_url = ctx.message.attachments[0].url

    # Check for an image link in the user's message
    if not image_url:
        await ctx.send("Please upload an image, link to one, or reply to a message with an image.")
        return

    try:
        # Download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    await ctx.send("Failed to download the image.")
                    return
                data = BytesIO(await response.read())

        # Process the image using Wand (ImageMagick)
        with Image(file=data) as img:
            original_width, original_height = img.width, img.height

            # Perform liquid rescale
            img.liquid_rescale(
                width=int(original_width * 0.5),
                height=int(original_height * 0.5),
                delta_x=1,
                rigidity=0
            )
            img.liquid_rescale(
                width=int(original_width * 1.5),
                height=int(original_height * 1.5),
                delta_x=1,
                rigidity=0
            )

            # Save the processed image to a BytesIO object
            output = BytesIO()
            img.format = 'png'
            img.save(file=output)
            output.seek(0)

        # Send the processed image
        await ctx.send("Here's your magik image!", file=discord.File(output, filename="magik.png"))

    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")


bot.run("PUTINTOKEN")