#!/usr/bin/python3
import os
import discord
from dotenv import load_dotenv
from discord.ext import commands
from discord.utils import get
from quart import Quart, jsonify
import asyncio
import json
from quart import request

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = int(os.getenv('DISCORD_GUILD'))

# Initialize Discord bot
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
my_guild = None  # Will store the reference to the guild

# Initialize Quart app
app = Quart(__name__)

# Event triggered when the bot is ready
@bot.event
async def on_ready():
    global my_guild
    print(f'{bot.user} has connected to Discord!')

    # Locate the guild
    for guild in bot.guilds:
        if guild.id == GUILD:
            my_guild = guild
            print(f"Connected to guild: {guild.name}")
            break
    if not my_guild:
        print("Guild not found. Exiting.")
        return

    user = my_guild.get_member(686293944904187935)
    if user:
        await user.send("Hello from Boot!")

# API Endpoints
@app.route("/")
async def hello():
    return "Hello, world!"

@app.route('/api/kick/<int:user_id>', methods=['POST'])
async def kick_member(user_id):
    """Kick a member by user_id."""
    if not my_guild:
        return api_error(500, 'Guild not initialized')
    user = my_guild.get_member(user_id)
    if user:
        await my_guild.kick(user)
        return jsonify({"status": "success", "message": f"User {user_id} kicked"}), 200
    return api_error(404, 'User not found')

@app.route('/api/get_roles/<int:user_id>', methods=['GET'])
async def get_roles(user_id):
    """Get roles of a member by user_id."""
    if not my_guild:
        return api_error(500, 'Guild not initialized')
    user = my_guild.get_member(user_id)
    if user:
        roles = {role.name: role.id for role in user.roles}
        return jsonify({"roles": roles}), 200
    return api_error(404, 'User not found')

@app.route('/api/del_roles/<int:user_id>/<string:role_str>', methods=['POST'])
async def remove_roles(user_id, role_str):
    """Remove a role from a member."""
    if not my_guild:
        return api_error(500, 'Guild not initialized')
    user = my_guild.get_member(user_id)
    if user:
        role = get(my_guild.roles, name=role_str)
        if role:
            await user.remove_roles(role)
            return jsonify({"status": "success", "message": f"Role {role_str} removed from user {user_id}"}), 200
        return api_error(404, 'Role not found')
    return api_error(404, 'User not found')

@app.route('/api/add_roles/<int:user_id>/<string:role_str>', methods=['POST'])
async def add_roles(user_id, role_str):
    """Add a role to a member."""
    if not my_guild:
        return api_error(500, 'Guild not initialized')
    user = my_guild.get_member(user_id)
    if user:
        role = get(my_guild.roles, name=role_str)
        if role:
            await user.add_roles(role)
            return jsonify({"status": "success", "message": f"Role {role_str} added to user {user_id}"}), 200
        return api_error(404, 'Role not found')
    return api_error(404, 'User not found')

@app.route('/api/post_message', methods=['POST'])
async def post_message():
    """
    Post a message to the #project-hq channel in the guild.
    Expects JSON: {"message": "Your message here", "channel_name": "optional-channel-name"}
    """
    if not my_guild:
        return api_error(500, 'Guild not initialized')

    data = await request.get_json()
    if not data or 'message' not in data:
        return api_error(400, 'Missing message in request body')

    message = data['message']
    channel_name = data.get('channel_name', 'project-hq')

    # Find the text channel by name
    channel = discord.utils.get(my_guild.text_channels, name=channel_name)
    if not channel:
        return api_error(404, f'Channel "{channel_name}" not found')

    try:
        await channel.send(message)
        return jsonify({"status": "success", "message": f"Message posted to #{channel_name}"}), 200
    except Exception as e:
        return api_error(500, f"Failed to send message: {str(e)}")


# Helper to find user by ID or username
def get_user(identifier):
    # Try numeric ID first
    try:
        user_id = int(identifier)
        user = my_guild.get_member(user_id)
        if user:
            return user
    except ValueError:
        pass  # Not an ID

    # Try username (case-insensitive)
    for member in my_guild.members:
        if member.name.lower() == identifier.lower() or f"{member.name}#{member.discriminator}" == identifier:
            return member

    return None

@app.route('/api/soft_ban/<string:identifier>', methods=['POST'])
async def soft_ban(identifier):
    """Soft-ban a user by ID or username."""
    if not my_guild:
        return api_error(500, 'Guild not initialized')

    user = get_user(identifier)
    if not user:
        return api_error(404, 'User not found')

    banned_role = get(my_guild.roles, name="banned")
    newmember_role = get(my_guild.roles, name="newmember")
    member_role = get(my_guild.roles, name="member")

    if get(user.roles, name="admin"):
        return api_error(403, 'Cannot soft-ban an admin user')

    if not banned_role:
        return api_error(404, 'Banned role not found')

    await user.remove_roles(*[r for r in [newmember_role, member_role] if r in user.roles])
    await user.add_roles(banned_role)

    return jsonify({"status": "success", "message": f"User {user.name} soft-banned"}), 200

@app.route('/api/timeout/<string:identifier>/<int:duration>', methods=['POST'])
async def timeout(identifier, duration):
    """Timeout a user by ID or username."""
    if not my_guild:
        return api_error(500, 'Guild not initialized')

    user = get_user(identifier)
    if not user:
        return api_error(404, 'User not found')


    timeout_role = get(my_guild.roles, name="timeout")
    newmember_role = get(my_guild.roles, name="newmember")
    member_role = get(my_guild.roles, name="member")

    if get(user.roles, name="admin"):
        return api_error(403, 'Cannot soft-ban an admin user')


    if not timeout_role:
        return api_error(404, 'Timeout role not found')

    # Save previous roles except excluded ones
    excluded = {"@everyone", "newmember", "timeout", "banned"}
    previous_roles = [r for r in user.roles if r.name not in excluded]

    # Remove newmember + member, assign timeout
    await user.remove_roles(*[r for r in [newmember_role, member_role] if r in user.roles])
    await user.edit(roles=[timeout_role])

    async def restore():
        await asyncio.sleep(duration)
        try:
            await user.edit(roles=previous_roles)
            print(f"Restored roles for {user.name}")
        except Exception as e:
            print(f"Error restoring roles: {e}")

    asyncio.create_task(restore())

    return jsonify({
        "status": "success",
        "message": f"User {user.name} timed out for {duration} seconds"
    }), 200



# Helper function for API errors
def api_error(status, message):
    """Return a standardized API error response."""
    return jsonify({"error": {"code": status, "message": message}}), status

# Run both the bot and the Quart app
async def main():
    bot_task = asyncio.create_task(bot.start(TOKEN))
    app_task = asyncio.create_task(app.run_task(host="0.0.0.0", port=5000))
    await asyncio.gather(bot_task, app_task)


if __name__ == "__main__":
    asyncio.run(main())
