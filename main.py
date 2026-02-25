import os
import json
import asyncio
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ChatJoinRequestHandler,
    ContextTypes,
    filters
)
from telegram.constants import ChatMemberStatus
from telegram.request import HTTPXRequest

# ================== CONFIG ==================
BOT_TOKEN = "8530816226:AAHKlBmbHqUTu0EA_trQCGCF-A4KG5qcooo"

ADMINS = [8510426359]  # apna telegram user id

CHANNELS_FILE = "channels.json"
VERIFIED_FILE = "verified.json"

USERS_FILE = "users.json"         # /start users
AGENTS_FILE = "agents.json"       # numbers list
CLAIMS_FILE = "claims.json"       # user_id -> agent/link
LINK_FILE = "link.json"           # optional single link mode

REF_FILE = "referrals.json"       # referral database

# ================== TEXTS ==================
START_TEXT = (
    "👋* Hey There User Welcome To Bot !*\n\n"
    "🛑 *Must Join All Channels To Use Our Bot*\n\n"
    "💣* After Joining, Click '✅ Joined'*\n"
)

NOT_VERIFIED_TEXT = (
    "👋* Hey There User Welcome To Bot !*\n\n"
    "🛑 *Must Join All Channels To Use Our Bot*\n\n"
    "💣 *After Joining, Click 'Joined* 📢'\n"
)

HOME_TEXT = (
    "🏛* MEGA — Google Map Agents*\n\n"
    "*Welcome!*\n\n"
    "*This Is The Official NSE Agent Assignment Bot.*\n\n"
    "📜 *System Rules*\n"
    "• *Each user can claim one agent only*\n"
    "• *Agent assignments are permanent*\n"
    "•* All claims are recorded & verifiable*\n"
)

# claim output templates
CLAIM_NUMBER_TEMPLATE = (
    "🏛* NSE Agent Assigned Successfully*\n\n"
    "📞* WhatsApp Agent:*\n"
    "https://wa.me/{num}\n\n"
    "*This Is Your Agent If Replay Not Get Go Back And Claim New Agent*"
)

CLAIM_LINK_TEMPLATE = (
    "🏛 *NSE Agent Assigned Successfully*\n\n"
    "*📞 Link :* {link}\n\n"
    "*This Is Your Agent If Replay Not Get Go Back And Claim New Agent*"
)

NO_NUMBERS_TEXT = "*No Numbers Available*"

# ================== FILE HELPERS ==================
def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_channels():
    return _load_json(CHANNELS_FILE, [])

def save_channels(channels):
    _save_json(CHANNELS_FILE, channels)

def load_verified():
    return _load_json(VERIFIED_FILE, {})

def save_verified(data):
    _save_json(VERIFIED_FILE, data)

def load_users():
    return _load_json(USERS_FILE, [])

def save_users(users):
    _save_json(USERS_FILE, users)

def load_agents():
    # list of numbers as strings (without +)
    return _load_json(AGENTS_FILE, [])

def save_agents(agents):
    _save_json(AGENTS_FILE, agents)

def load_claims():
    # dict: user_id(str) -> {"type":"number/link", "value":"...", "time":"..."}
    return _load_json(CLAIMS_FILE, {})

def save_claims(claims):
    _save_json(CLAIMS_FILE, claims)

def load_link():
    # {"link": "..."} or {}
    return _load_json(LINK_FILE, {})

def save_link(data):
    _save_json(LINK_FILE, data)

def load_ref():
    # dict: user_id(str) -> {"referred_by": int/None, "referrals": [ids], "pending": int}
    return _load_json(REF_FILE, {})

def save_ref(data):
    _save_json(REF_FILE, data)

# ================== GLOBAL DATA ==================
CHANNELS = load_channels()
VERIFIED = load_verified()

USERS = load_users()
AGENTS = load_agents()
CLAIMS = load_claims()
LINKDATA = load_link()

REFDATA = load_ref()

# ================== UTILS ==================
def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

def add_user(user_id: int):
    uid = int(user_id)
    if uid not in USERS:
        USERS.append(uid)
        save_users(USERS)

def ensure_ref_user(uid: int):
    k = str(uid)
    if k not in REFDATA:
        REFDATA[k] = {"referred_by": None, "referrals": [], "pending": 0}
        save_ref(REFDATA)

def get_referred_by(uid: int):
    ensure_ref_user(uid)
    return REFDATA[str(uid)].get("referred_by")

def add_pending(uid: int, count: int = 1):
    ensure_ref_user(uid)
    REFDATA[str(uid)]["pending"] = int(REFDATA[str(uid)].get("pending", 0)) + count
    save_ref(REFDATA)

def dec_pending(uid: int, count: int = 1):
    ensure_ref_user(uid)
    cur = int(REFDATA[str(uid)].get("pending", 0))
    cur = max(0, cur - count)
    REFDATA[str(uid)]["pending"] = cur
    save_ref(REFDATA)

def add_referral(referrer: int, new_user: int):
    ensure_ref_user(referrer)
    ensure_ref_user(new_user)

    if new_user not in REFDATA[str(referrer)]["referrals"]:
        REFDATA[str(referrer)]["referrals"].append(new_user)

    save_ref(REFDATA)

async def bot_is_admin_in_channel(bot, chat_id: int) -> bool:
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id, me.id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except:
        return False

async def user_is_member(bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        )
    except:
        return False

def get_verified_set(chat_id: int):
    key = str(chat_id)
    if key not in VERIFIED:
        VERIFIED[key] = []
    return set(VERIFIED[key])

def add_verified(chat_id: int, user_id: int):
    key = str(chat_id)
    if key not in VERIFIED:
        VERIFIED[key] = []
    if user_id not in VERIFIED[key]:
        VERIFIED[key].append(user_id)
        save_verified(VERIFIED)

def build_join_keyboard(pending_channels):
    rows = []
    temp = []
    for ch in pending_channels:
        temp.append(InlineKeyboardButton("📢 Join", url=ch["link"]))
        if len(temp) == 2:
            rows.append(temp)
            temp = []
    if temp:
        rows.append(temp)

    rows.append([InlineKeyboardButton("Joined ✅", callback_data="joined_check")])
    return InlineKeyboardMarkup(rows)

def home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Claim Agent", callback_data="claim_agent")],
        [InlineKeyboardButton("📊 Statistics", callback_data="stats")],
        [InlineKeyboardButton("💸 Refer & Earn", callback_data="refer_earn")]
    ])

# ================== ADMIN PANEL KEYBOARD ==================
def adminpanel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Set Channel ⚙️", callback_data="set_channel")],
        [InlineKeyboardButton("Manage Channels 🔁", callback_data="manage_channels")],
        [InlineKeyboardButton("Remove Channel ❌", callback_data="remove_channel")],
        [InlineKeyboardButton("────────────", callback_data="noop")],
        [InlineKeyboardButton("⚙️ Set Numbers", callback_data="set_numbers")],
        [InlineKeyboardButton("👀 Check Numbers", callback_data="check_numbers")],
        [InlineKeyboardButton("❌ Clear Numbers", callback_data="clear_numbers")],
        [InlineKeyboardButton("🔗 Set Link", callback_data="set_link")],
        [InlineKeyboardButton("🧹 Clear Link", callback_data="clear_link")],
    ])

# ================== JOIN CHECK ==================
async def get_pending_channels(bot, user_id: int):
    pending = []
    for ch in CHANNELS:
        cid = int(ch["id"])

        if user_id in get_verified_set(cid):
            continue

        if await user_is_member(bot, cid, user_id):
            add_verified(cid, user_id)
            continue

        pending.append(ch)

    return pending

# ================== ADMIN NOTIFY ==================
async def admin_notify_new_user(context, new_user_id: int):
    try:
        referred_by = get_referred_by(new_user_id)
        ref_text = "None"
        if referred_by:
            try:
                chat = await context.bot.get_chat(referred_by)
                if chat.username:
                    ref_text = f"@{chat.username}"
                else:
                    ref_text = str(referred_by)
            except:
                ref_text = str(referred_by)

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("View Users", callback_data=f"view_user_{new_user_id}")],
            [InlineKeyboardButton("View Refferal", callback_data=f"view_ref_{new_user_id}")]
        ])

        for admin_id in ADMINS:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    "🔍 *New User Joined*\n"
                    f"🙂* User -* {new_user_id}\n"
                    f"✅ *Referred By:* {ref_text}\n"
                    "⚡️* Promoter: Sher *🦁"
                ),
                reply_markup=kb
            )
    except:
        pass

# ================== USER COMMANDS ==================
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)
    ensure_ref_user(user_id)

    # referral arg
    referrer = None
    if context.args and context.args[0].isdigit():
        referrer = int(context.args[0])

    # save referral only first time
    if referrer and referrer != user_id:
        ensure_ref_user(referrer)
        if get_referred_by(user_id) is None:
            REFDATA[str(user_id)]["referred_by"] = referrer
            save_ref(REFDATA)

            # add referral to referrer + pending reward
            add_referral(referrer, user_id)
            add_pending(referrer, 1)

            # notify referrer
            try:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Show Agent 🟢", callback_data="ref_show_agent")]
                ])
                await context.bot.send_message(
                    chat_id=referrer,
                    text="😌* New Refferal Found*\n⚡️* Promoter: Sher* 🦁",
                    reply_markup=kb
                )
            except:
                pass

    # notify admin
    await admin_notify_new_user(context, user_id)

    if len(CHANNELS) == 0:
        await update.message.reply_text("⚠️* No channels set yet. Admin must add channels using /adminpanel*")
        return

    pending = await get_pending_channels(context.bot, user_id)

    if len(pending) == 0:
        await update.message.reply_text(HOME_TEXT, reply_markup=home_keyboard())
        return

    text = START_TEXT + f"\n🔻 Pending Channels: {len(pending)}/{len(CHANNELS)}"
    await update.message.reply_text(text, reply_markup=build_join_keyboard(pending))

async def joined_check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    add_user(user_id)
    ensure_ref_user(user_id)

    pending = await get_pending_channels(context.bot, user_id)

    if len(pending) == 0:
        await query.message.reply_text(HOME_TEXT, reply_markup=home_keyboard())
    else:
        text = NOT_VERIFIED_TEXT + f"\n🔻 Pending Channels: {len(pending)}/{len(CHANNELS)}"
        await query.message.reply_text(text, reply_markup=build_join_keyboard(pending))
        
        # ================== JOIN REQUEST TRACK ==================
async def on_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    user_id = req.from_user.id
    chat_id = req.chat.id
    add_verified(chat_id, user_id)

# ================== ADMIN PANEL ==================
async def adminpanel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not allowed.")
        return

    await update.message.reply_text("🛠 Admin Panel", reply_markup=adminpanel_keyboard())

# ---------- Add Channel ----------
async def set_channel_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.message.reply_text("❌ You are not allowed.")
        return

    context.user_data["WAIT_CHANNEL_LINK"] = True
    context.user_data["NEW_CHANNEL_LINK"] = None
    context.user_data["NEW_CHANNEL_ID"] = None

    await query.message.reply_text("🔗 Enter Your Channel Link:")

# ---------- Manage Channels (Reorder) ----------
def build_manage_channels_keyboard():
    rows = []
    for i, ch in enumerate(CHANNELS):
        cid = ch["id"]
        rows.append([
            InlineKeyboardButton(f"{i+1}) {cid}", callback_data=f"info_{i}"),
            InlineKeyboardButton("⬆️", callback_data=f"up_{i}"),
            InlineKeyboardButton("⬇️", callback_data=f"down_{i}"),
        ])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="back_admin")])
    return InlineKeyboardMarkup(rows)

async def manage_channels_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.message.reply_text("❌ You are not allowed.")
        return

    if len(CHANNELS) == 0:
        await query.message.reply_text("⚠️ No channels found.")
        return

    await query.message.reply_text("📌 Manage Channels (Reorder)", reply_markup=build_manage_channels_keyboard())

async def reorder_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.message.reply_text("❌ You are not allowed.")
        return

    data = query.data

    if data.startswith("up_"):
        idx = int(data.split("_")[1])
        if idx > 0:
            CHANNELS[idx-1], CHANNELS[idx] = CHANNELS[idx], CHANNELS[idx-1]
            save_channels(CHANNELS)

    elif data.startswith("down_"):
        idx = int(data.split("_")[1])
        if idx < len(CHANNELS) - 1:
            CHANNELS[idx+1], CHANNELS[idx] = CHANNELS[idx], CHANNELS[idx+1]
            save_channels(CHANNELS)

    elif data.startswith("info_"):
        idx = int(data.split("_")[1])
        ch = CHANNELS[idx]
        await query.message.reply_text(
            f"👀 Channel Info\n\n🆔 Chat ID: {ch['id']}\n🔗 Link: {ch['link']}"
        )

    await query.message.reply_text("📌 Updated Channel Order:", reply_markup=build_manage_channels_keyboard())

# ---------- Remove Channel ----------
def build_remove_channels_keyboard():
    rows = []
    for i, ch in enumerate(CHANNELS):
        cid = ch["id"]
        rows.append([
            InlineKeyboardButton(f"{i+1}) {cid}", callback_data=f"rem_info_{i}"),
            InlineKeyboardButton("❌ Delete", callback_data=f"del_{i}")
        ])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="back_admin")])
    return InlineKeyboardMarkup(rows)

async def remove_channel_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.message.reply_text("❌ You are not allowed.")
        return

    if len(CHANNELS) == 0:
        await query.message.reply_text("⚠️ No channels to remove.")
        return

    await query.message.reply_text("❌ Remove Channel Panel", reply_markup=build_remove_channels_keyboard())

async def delete_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.message.reply_text("❌ You are not allowed.")
        return

    data = query.data

    if data.startswith("del_"):
        idx = int(data.split("_")[1])
        try:
            removed = CHANNELS.pop(idx)
            save_channels(CHANNELS)
            await query.message.reply_text(f"✅ Removed Channel: {removed['id']}")
        except:
            await query.message.reply_text("❌ Error removing channel.")

    elif data.startswith("rem_info_"):
        idx = int(data.split("_")[2])
        ch = CHANNELS[idx]
        await query.message.reply_text(
            f"👀 Channel Info\n\n🆔 Chat ID: {ch['id']}\n🔗 Link: {ch['link']}"
        )

    await query.message.reply_text("❌ Updated Channel List:", reply_markup=build_remove_channels_keyboard())

# ---------- Back ----------
async def back_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    await query.message.reply_text("🛠 Admin Panel", reply_markup=adminpanel_keyboard())

# ================== ADMIN: NUMBERS + LINK ==================
async def set_numbers_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.message.reply_text("❌ You are not allowed.")
        return

    context.user_data["WAIT_NUMBERS"] = True
    await q.message.reply_text(
        "📥* Enter your numbers (comma separated)*\n\n"
        "*Example:*\n"
        "*919592365413,918373847303,918374844770*"
    )

async def check_numbers_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.message.reply_text("❌ You are not allowed.")
        return

    if len(AGENTS) == 0:
        await q.message.reply_text(NO_NUMBERS_TEXT)
        return

    text = "*📦 Current Numbers Stock:*\n\n" + "\n".join([f"{i+1}) {n}" for i, n in enumerate(AGENTS[:200])])
    if len(AGENTS) > 200:
        text += f"\n\n...and {len(AGENTS)-200} more"
    await q.message.reply_text(text)

async def clear_numbers_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.message.reply_text("❌ You are not allowed.")
        return

    AGENTS.clear()
    save_agents(AGENTS)
    await q.message.reply_text("✅ *All numbers cleared!*")

async def set_link_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.message.reply_text("❌ You are not allowed.")
        return

    context.user_data["WAIT_LINK"] = True
    await q.message.reply_text("🔗 Enter your link:")

async def clear_link_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.message.reply_text("❌ You are not allowed.")
        return

    LINKDATA.clear()
    save_link(LINKDATA)
    await q.message.reply_text("✅ Link cleared! Now Claim Agent will use numbers.")

# ================== HOME: REFER & EARN ==================
async def refer_earn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    bot_username = (await context.bot.get_me()).username

    text = (
        "💰 *Per Refer :- 1 Agent Number*\n\n"
        f"👤*Your Refferal Link:* https://t.me/{bot_username}?start={uid}\n\n"
        "*Share With Your Friend's & Family And Earn Refer Bonus Easily* ✨🤑"
    )
    await q.message.reply_text(text)

async def ref_show_agent_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    # must have pending
    ensure_ref_user(user_id)
    pending = int(REFDATA[str(user_id)].get("pending", 0))
    if pending <= 0:
        await q.message.reply_text("❌ No referral reward pending.")
        return

    # assign from link mode OR number mode
    uid = str(user_id)

    # If already claimed permanently, show same claim
    if uid in CLAIMS:
        data = CLAIMS[uid]
        if data.get("type") == "link":
            msg = CLAIM_LINK_TEMPLATE.format(link=data.get("value"))
        else:
            msg = CLAIM_NUMBER_TEMPLATE.format(num=data.get("value"))
        await q.message.reply_text(msg)
        return

    link = LINKDATA.get("link")
    if link:
        CLAIMS[uid] = {"type": "link", "value": link, "time": datetime.now().isoformat()}
        save_claims(CLAIMS)
        dec_pending(user_id, 1)
        await q.message.reply_text(CLAIM_LINK_TEMPLATE.format(link=link))
        return

    if len(AGENTS) == 0:
        await q.message.reply_text(NO_NUMBERS_TEXT)
        return

    num = AGENTS.pop(0)
    save_agents(AGENTS)

    CLAIMS[uid] = {"type": "number", "value": num, "time": datetime.now().isoformat()}
    save_claims(CLAIMS)

    dec_pending(user_id, 1)
    await q.message.reply_text(CLAIM_NUMBER_TEMPLATE.format(num=num))

# ================== HOME: CLAIM + STATS ==================
async def claim_agent_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    add_user(user_id)
    ensure_ref_user(user_id)

    # first verify channels
    pending = await get_pending_channels(context.bot, user_id)
    if len(pending) > 0:
        text = NOT_VERIFIED_TEXT + f"\n🔻 Pending Channels: {len(pending)}/{len(CHANNELS)}"
        await query.message.reply_text(text, reply_markup=build_join_keyboard(pending))
        return

    uid = str(user_id)

    # already claimed
    if uid in CLAIMS:
        data = CLAIMS[uid]
        if data.get("type") == "link":
            msg = CLAIM_LINK_TEMPLATE.format(link=data.get("value"))
        else:
            msg = CLAIM_NUMBER_TEMPLATE.format(num=data.get("value"))
        await query.message.reply_text(msg)
        return

    # link mode
    link = LINKDATA.get("link")
    if link:
        CLAIMS[uid] = {"type": "link", "value": link, "time": datetime.now().isoformat()}
        save_claims(CLAIMS)
        await query.message.reply_text(CLAIM_LINK_TEMPLATE.format(link=link))
        return

    # numbers mode
    if len(AGENTS) == 0:
        await query.message.reply_text(NO_NUMBERS_TEXT)
        return

    num = AGENTS.pop(0)  # assign first number
    save_agents(AGENTS)

    CLAIMS[uid] = {"type": "number", "value": num, "time": datetime.now().isoformat()}
    save_claims(CLAIMS)

    await query.message.reply_text(CLAIM_NUMBER_TEMPLATE.format(num=num))

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    total_users = len(USERS)
    total_claims = len(CLAIMS)
    stock = len(AGENTS)

    text = (
        f"👍*Total Members In Bot:* {total_users} *Users*\n\n"
        f"👍*Total Agent Claim In Bot* : {total_claims}* Users*\n\n"
        f"👍*Total Agent Stock In Bot :* {stock} *Numbers*\n\n"
        f"📍 *Powered By - 🦁𝕾𝖍𝖊𝖗 ️!!*"
    )
    await query.message.reply_text(text)

# ================== ADMIN VIEW USER/REF ==================
async def view_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if not is_admin(q.from_user.id):
        await q.message.reply_text("❌ You are not allowed.")
        return

    uid = int(q.data.split("_")[2])
    try:
        chat = await context.bot.get_chat(uid)
        name = chat.full_name or ""
        username = f"@{chat.username}" if chat.username else "None"
        link = f"tg://user?id={uid}"

        text = (
            "👤 *User Profile*\n\n"
            f"🆔 *ID: *{uid}\n"
            f"👤 *Name:* {name}\n"
            f"🔗* Username:* {username}\n"
            f"📎* Profile Link: *{link}"
        )
    except:
        text = f"❌ User not found.\nID: {uid}"

    await q.message.reply_text(text)

async def view_ref_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if not is_admin(q.from_user.id):
        await q.message.reply_text("❌ You are not allowed.")
        return

    uid = int(q.data.split("_")[2])
    rb = get_referred_by(uid)

    if not rb:
        await q.message.reply_text("❌ No referrer (Direct /start).")
        return

    try:
        chat = await context.bot.get_chat(rb)
        username = f"@{chat.username}" if chat.username else str(rb)
    except:
        username = str(rb)

    await q.message.reply_text(
        "👀 Referrer Info\n\n"
        f"🙂 User: {uid}\n"
        f"✅ Referred By: {username}"
    )

# ================== BROADCAST ==================
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You are not allowed.")
        return

    context.user_data["WAIT_BROADCAST"] = True
    await update.message.reply_text("📢 Send your broadcast post now (text/photo/video/gif/forward).")

async def senduser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You are not allowed.")
        return

    context.user_data["WAIT_SENDUSER_ID"] = True
    await update.message.reply_text("🆔 Enter User ID:")

async def handle_admin_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles admin text inputs + broadcast posts + senduser flow"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
        
        # ----- existing channel add flow -----
    text = (update.message.text or "").strip()

    if context.user_data.get("WAIT_CHANNEL_LINK"):
        context.user_data["NEW_CHANNEL_LINK"] = text
        context.user_data["WAIT_CHANNEL_LINK"] = False
        context.user_data["WAIT_CHANNEL_ID"] = True
        await update.message.reply_text("🆔 Enter Your Channel Chat ID (example: -1001234567890):")
        return

    if context.user_data.get("WAIT_CHANNEL_ID"):
        context.user_data["WAIT_CHANNEL_ID"] = False

        try:
            cid = int(text)
        except:
            await update.message.reply_text("❌ Invalid Chat ID. Try again /adminpanel")
            return

        link = context.user_data.get("NEW_CHANNEL_LINK")

        ok = await bot_is_admin_in_channel(context.bot, cid)
        if not ok:
            await update.message.reply_text(f"👀* Bot is not admin in* {cid}!")
            return

        for ch in CHANNELS:
            if int(ch["id"]) == cid:
                await update.message.reply_text("⚠️* This channel already exists.*")
                return

        CHANNELS.append({"id": cid, "link": link})
        save_channels(CHANNELS)

        await update.message.reply_text("*congratulations 🎉 your channel settled Successfully 🤗*")
        return

    # ----- numbers input -----
    if context.user_data.get("WAIT_NUMBERS"):
        context.user_data["WAIT_NUMBERS"] = False

        raw = update.message.text.strip()
        parts = [p.strip() for p in raw.split(",") if p.strip()]

        # sanitize: remove + and spaces
        cleaned = []
        for p in parts:
            p = p.replace("+", "").replace(" ", "")
            if p.isdigit():
                cleaned.append(p)

        if len(cleaned) == 0:
            await update.message.reply_text("❌ No valid numbers found. Try again.")
            return

        # add numbers
        AGENTS.extend(cleaned)
        save_agents(AGENTS)

        await update.message.reply_text(f"✅ Added {len(cleaned)} numbers!\n📦 Total Stock: {len(AGENTS)}")
        return

    # ----- set link input -----
    if context.user_data.get("WAIT_LINK"):
        context.user_data["WAIT_LINK"] = False
        link = update.message.text.strip()
        LINKDATA["link"] = link
        save_link(LINKDATA)
        await update.message.reply_text("✅ Link set successfully! Now Claim Agent will use link mode.")
        return

    # ----- senduser flow -----
    if context.user_data.get("WAIT_SENDUSER_ID"):
        context.user_data["WAIT_SENDUSER_ID"] = False
        try:
            target = int(update.message.text.strip())
        except:
            await update.message.reply_text("❌ Invalid user id.")
            return

        context.user_data["SENDUSER_TARGET"] = target
        context.user_data["WAIT_SENDUSER_MSG"] = True
        await update.message.reply_text("✉️ Now send the message you want to send to that user.")
        return

    if context.user_data.get("WAIT_SENDUSER_MSG"):
        context.user_data["WAIT_SENDUSER_MSG"] = False
        target = context.user_data.get("SENDUSER_TARGET")
        if not target:
            await update.message.reply_text("❌ Target not found.")
            return

        try:
            await context.bot.copy_message(
                chat_id=target,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            await update.message.reply_text("✅ Sent successfully!")
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to send.\n{e}")
        return

    # ----- broadcast flow (any post) -----
    if context.user_data.get("WAIT_BROADCAST"):
        context.user_data["WAIT_BROADCAST"] = False

        all_users = USERS[:]  # list of ids
        total = len(all_users)
        sent = 0
        blocked = 0

        msg = await update.message.reply_text("🚀 Broadcast started...")

        for i, uid in enumerate(all_users, start=1):
            try:
                await context.bot.copy_message(
                    chat_id=uid,
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                )
                sent += 1
            except Exception:
                blocked += 1

            # update every 50 users
            if i % 50 == 0 or i == total:
                percent = int((i / total) * 100) if total else 100
                waiting = total - i
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await msg.edit_text(
                    f"Sent: {sent} from {total} ({percent}%)\n"
                    f"Blocked: {blocked}\n"
                    f"Waiting: {waiting}\n\n"
                    f"Date and time of statistics update: {now}"
                )
                await asyncio.sleep(0.4)

        await update.message.reply_text("Broadcast done ✅")
        return
        
        # ================== CALLBACK NOOP ==================
async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

# ================== MAIN ==================
def main():
    request = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30)

    app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()

    # user
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CallbackQueryHandler(joined_check_handler, pattern="^joined_check$"))

    # join request tracking
    app.add_handler(ChatJoinRequestHandler(on_join_request))

    # admin
    app.add_handler(CommandHandler("adminpanel", adminpanel_cmd))
    app.add_handler(CallbackQueryHandler(set_channel_button, pattern="^set_channel$"))
    app.add_handler(CallbackQueryHandler(manage_channels_button, pattern="^manage_channels$"))
    app.add_handler(CallbackQueryHandler(remove_channel_button, pattern="^remove_channel$"))
    app.add_handler(CallbackQueryHandler(reorder_handler, pattern="^(up_|down_|info_).+"))
    app.add_handler(CallbackQueryHandler(delete_channel_handler, pattern="^(del_|rem_info_).+"))
    app.add_handler(CallbackQueryHandler(back_admin_handler, pattern="^back_admin$"))

    # admin numbers/link
    app.add_handler(CallbackQueryHandler(set_numbers_button, pattern="^set_numbers$"))
    app.add_handler(CallbackQueryHandler(check_numbers_button, pattern="^check_numbers$"))
    app.add_handler(CallbackQueryHandler(clear_numbers_button, pattern="^clear_numbers$"))
    app.add_handler(CallbackQueryHandler(set_link_button, pattern="^set_link$"))
    app.add_handler(CallbackQueryHandler(clear_link_button, pattern="^clear_link$"))

    # broadcast + send user
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("senduser", senduser_cmd))

    # home buttons
    app.add_handler(CallbackQueryHandler(claim_agent_handler, pattern="^claim_agent$"))
    app.add_handler(CallbackQueryHandler(stats_handler, pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(refer_earn_handler, pattern="^refer_earn$"))

    # referral reward claim button
    app.add_handler(CallbackQueryHandler(ref_show_agent_handler, pattern="^ref_show_agent$"))

    # admin view user/ref buttons
    app.add_handler(CallbackQueryHandler(view_user_handler, pattern="^view_user_"))
    app.add_handler(CallbackQueryHandler(view_ref_handler, pattern="^view_ref_"))

    # noop
    app.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop$"))

    # admin input handler (must be last)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_admin_inputs))

    print("Bot running... ✅")
    app.run_polling()

if __name__ == "__main__":
    main()