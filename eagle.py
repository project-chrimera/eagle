#!/usr/bin/python3
import os
import discord
from dotenv import load_dotenv
from discord.ext import commands
from discord.utils import get
from quart import Quart, jsonify, request
import asyncio
from functools import wraps

# ----------------------
# Load environment variables
# ----------------------
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD'))
API_TOKEN = os.getenv('API_TOKEN')

# ----------------------
# Initialize Discord bot
# ----------------------
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)
my_guild = None  # Will store the reference to the guild

# ----------------------
# Initialize Quart app
# ----------------------
app = Quart(__name__)

# ----------------------
# Helper functions
# ----------------------
def token_required(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != API_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return await f(*args, **kwargs)
    return decorated_function

def api_error(status, message):
    """Return a standardized API error response."""
    return jsonify({"error": {"code": status, "message": message}}), status

def get_user(identifier):
    """Find user by ID or username#discriminator."""
    try:
        user_id = int(identifier)
        user = my_guild.get_member(user_id)
        if user:
            return user
    except ValueError:
        pass
    for member in my_guild.members:
        if member.name.lower() == identifier.lower() or f"{member.name}#{member.discriminator}" == identifier:
            return member
    return None

def is_mod():
    async def predicate(ctx):
        if ctx.author.id in MOD_IDS:
            print(f"✅ [MOD] {ctx.author} ran `{ctx.command}`")
            return True
        else:
            print(f"❌ [DENY] {ctx.author} tried `{ctx.command}`")
            return False
    return commands.check(predicate)

# ----------------------
# Discord events
# ----------------------
@bot.event
async def on_ready():
    global my_guild
    print(f'{bot.user} has connected to Discord!')
    for guild in bot.guilds:
        if guild.id == GUILD_ID:
            my_guild = guild
            print(f"Connected to guild: {guild.name}")
            break
    if not my_guild:
        print("Guild not found!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You do not have permission to run this command.")
    else:
        print(f"[ERROR] {error}")

# ----------------------
# Quart API endpoints
# ----------------------
@app.route("/")
async def hello():
    return "Hello, world!"

@app.route('/api/kick/<int:user_id>', methods=['POST'])
@token_required
async def kick_member(user_id):
    if not my_guild:
        return api_error(500, 'Guild not initialized')
    user = my_guild.get_member(user_id)
    if user:
        await my_guild.kick(user)
        return jsonify({"status": "success", "message": f"User {user_id} kicked"}), 200
    return api_error(404, 'User not found')

@app.route('/api/get_roles/<int:user_id>', methods=['GET'])
@token_required
async def get_roles(user_id):
    if not my_guild:
        return api_error(500, 'Guild not initialized')
    user = my_guild.get_member(user_id)
    if user:
        roles = {role.name: role.id for role in user.roles}
        return jsonify({"roles": roles}), 200
    return api_error(404, 'User not found')

@app.route('/api/add_roles/<int:user_id>/<string:role_str>', methods=['POST'])
@token_required
async def add_roles(user_id, role_str):
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

@app.route('/api/del_roles/<int:user_id>/<string:role_str>', methods=['POST'])
@token_required
async def remove_roles(user_id, role_str):
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

@app.route('/api/post_message', methods=['POST'])
@token_required
async def post_message():
    if not my_guild:
        return api_error(500, 'Guild not initialized')
    data = await request.get_json()
    if not data or 'message' not in data:
        return api_error(400, 'Missing message in request body')

    message = data['message']
    channel_name = data.get('channel_name', 'project-hq')
    channel = get(my_guild.text_channels, name=channel_name)
    if not channel:
        return api_error(404, f'Channel "{channel_name}" not found')

    try:
        await channel.send(message)
        return jsonify({"status": "success", "message": f"Message posted to #{channel_name}"}), 200
    except Exception as e:
        return api_error(500, f"Failed to send message: {str(e)}")

@app.route('/api/soft_ban/<string:identifier>', methods=['POST'])
@token_required
async def soft_ban(identifier):
    if not my_guild:
        return api_error(500, 'Guild not initialized')
    user = get_user(identifier)
    if not user:
        return api_error(404, 'User not found')

    banned_role = get(my_guild.roles, name="banned")
    newMember_role = get(my_guild.roles, name="newMember")
    member_role = get(my_guild.roles, name="member")

    if get(user.roles, name="admin"):
        return api_error(403, 'Cannot soft-ban an admin user')
    if not banned_role:
        return api_error(404, 'Banned role not found')

    await user.remove_roles(*[r for r in [newMember_role, member_role] if r in user.roles])
    await user.add_roles(banned_role)
    return jsonify({"status": "success", "message": f"User {user.name} soft-banned"}), 200

@app.route('/api/timeout/<string:identifier>/<int:duration>', methods=['POST'])
@token_required
async def timeout(identifier, duration):
    if not my_guild:
        return api_error(500, 'Guild not initialized')
    user = get_user(identifier)
    if not user:
        return api_error(404, 'User not found')

    timeout_role = get(my_guild.roles, name="timeout")
    newMember_role = get(my_guild.roles, name="newMember")
    member_role = get(my_guild.roles, name="member")

    if get(user.roles, name="admin"):
        return api_error(403, 'Cannot soft-ban an admin user')
    if not timeout_role:
        return api_error(404, 'Timeout role not found')

    excluded = {"@everyone", "timeout", "banned"}
    previous_roles = [r for r in user.roles if r.name not in excluded]

    await user.remove_roles(*[r for r in [newMember_role, member_role] if r in user.roles])
    await user.add_roles(timeout_role)

    async def restore():
        await asyncio.sleep(duration)
        try:
            await user.remove_roles(timeout_role)
            if previous_roles:
                await user.add_roles(*previous_roles)
        except Exception as e:
            print(f"[ERROR] Restoring roles for {user.name}: {e}")

    asyncio.create_task(restore())
    return jsonify({"status": "success", "message": f"User {user.name} timed out for {duration} seconds"}), 200

# ----------------------
# Main entry point
# ----------------------
async def main():
    bot_task = asyncio.create_task(bot.start(TOKEN))
    quart_task = asyncio.create_task(app.run_task(host="0.0.0.0", port=5000))
    await asyncio.gather(bot_task, quart_task)

if __name__ == "__main__":
    asyncio.run(main())

