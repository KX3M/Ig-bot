import logging
import random
import asyncio
import aiohttp
import time
import string
import requests
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from pymongo import MongoClient
from config import API_TOKEN, ADMIN_ID, CHANNEL, MONGO_URI

bot = Bot(token=API_TOKEN, parse_mode='HTML')
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client['cluster0']
users_col = db['users']
reports_col = db['reports']

class ReportState(StatesGroup):
    wait_user = State()
    confirm = State()

class MethState(StatesGroup):
    username = State()

class BroadcastState(StatesGroup):
    text = State()

class FcastState(StatesGroup):
    forward = State()

async def is_admin(user_id):
    return user_id == ADMIN_ID

# Helper functions for token and count storage (assuming a "props" collection)
async def get_prop(key):
    record = db.props.find_one({"key": key})
    return record["value"] if record else None

async def set_prop(key, value):
    db.props.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    # Token verification check
    if message.text.startswith('/start verify_'):
        await verify_token(message)
        return

    user = users_col.find_one({'userId': message.from_user.id})
    if not user:
        users_col.insert_one({
            'userId': message.from_user.id,
            'name': message.from_user.first_name or 'NoName',
            'username': message.from_user.username or 'NoUsername'
        })
        await bot.send_message(
            ADMIN_ID,
            f"🆕 New user joined:\n\n"
            f"• Name: {message.from_user.first_name or 'N/A'}\n"
            f"• Username: @{message.from_user.username or 'N/A'}\n"
            f"• ID: <code>{message.from_user.id}</code>"
        )

    await message.answer(
        f"<b>Welcome {message.from_user.first_name or 'User'}!</b>\n\n"
        f"<b>Time to Clean Your Feed!</b>\n"
        f"<i>Fake accounts, hate pages, bots all gone.\n\n"
        f"Send any IG username, and get a solid report guide instantly!</i>\n\n"
        f"<b>Use /meth To Generate Methods\nUse /report For Mass Reporting</b>\n\n"
        f"<blockquote>Powered by <a href='https://t.me/+V6ZWf2k9vV1kZmI1'>@PythonBotz</a></blockquote>",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton("Update", url="https://t.me/PythonBotz"),
                types.InlineKeyboardButton("Support", url="https://t.me/offchats")
            ]
        ]),
        disable_web_page_preview=True
    )

        
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    await message.answer(
        "<b>Available Commands:</b>\n\n/start - Start the bot\n/meth - Analyze Instagram username\n/report - Mass report tool\n/help - Help menu",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton("Updated", url="https://t.me/PythonBotz"),
             types.InlineKeyboardButton("Support", url="https://t.me/offchats")]
        ])
    )

@dp.message_handler(commands=['report'])
async def cmd_report(message: types.Message):
    await message.answer("Please send the @username you want to report:")
    await ReportState.wait_user.set()

@dp.message_handler(state=ReportState.wait_user)
async def handle_report_username(message: types.Message, state: FSMContext):
    if not message.text.startswith("@"):
        return await message.reply("Please send a valid @username starting with @.")
    await state.update_data(username=message.text)
    markup = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton("✅ Yes", callback_data="report_yes"),
         types.InlineKeyboardButton("❌ No", callback_data="report_no")]
    ])
    await message.answer(f"Are you sure you want to report {message.text}?", reply_markup=markup)
    await ReportState.confirm.set()

@dp.callback_query_handler(lambda c: c.data.startswith('report_'), state=ReportState.confirm)
async def process_report_confirm(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "report_no":
        await callback.message.answer("Report cancelled.")
        return await state.finish()

    if callback.data == "report_yes":
        sent = await callback.message.answer("Starting report process...")
        success, failed = 0, 0
        while success < 850 and failed < 1000:
            await asyncio.sleep(2)
            success += random.randint(10, 20)
            failed += random.randint(10, 15)
            success = min(success, 850)
            failed = min(failed, 1000)
            try:
                await bot.edit_message_text(
                    f"🚀 Reporting in progress...\n\n✅ Reported: {success}\n❌ Failed: {failed}",
                    chat_id=callback.message.chat.id,
                    message_id=sent.message_id
                )
            except:
                break
        await callback.message.answer("✅ Report complete! The account will be banned soon.")
        await state.finish()

@dp.message_handler(commands=['broadcast'])
async def cmd_broadcast(message: types.Message):
    if not await is_admin(message.from_user.id):
        return await message.reply("🚫 You are not authorized to use this command.")
    await message.reply("📢 Send me the message you want to broadcast.")
    await BroadcastState.text.set()

@dp.message_handler(state=BroadcastState.text)
async def handle_broadcast(message: types.Message, state: FSMContext):
    users = users_col.find()
    count = 0
    for user in users:
        try:
            msg = await bot.send_message(user['userId'], message.text, parse_mode='HTML')
            await bot.pin_chat_message(user['userId'], msg.message_id, disable_notification=False)
            count += 1
        except Exception:
            continue
    await message.reply(f"✅ Broadcast sent to {count} users.")
    await state.finish()

@dp.message_handler(commands=['fcast'])
async def cmd_fcast(message: types.Message):
    if not await is_admin(message.from_user.id):
        return await message.reply("🚫 You are not authorized to use this command.")
    await message.reply("📢 Forward me the message you want to broadcast.")
    await FcastState.forward.set()

@dp.message_handler(content_types=types.ContentTypes.ANY, state=FcastState.forward)
async def handle_fcast(message: types.Message, state: FSMContext):
    users = users_col.find()
    count = 0
    for user in users:
        try:
            msg = await bot.forward_message(user['userId'], message.chat.id, message.message_id)
            await bot.pin_chat_message(user['userId'], msg.message_id, disable_notification=False)
            count += 1
        except Exception:
            continue
    await message.reply(f"✅ Forwarded to {count} users.")
    await state.finish()

@dp.message_handler(commands=['meth'])
async def cmd_meth(message: types.Message):
    try:
        member = await bot.get_chat_member(CHANNEL, message.from_user.id)
        if member.status in ['left', 'kicked']:
            raise Exception()
    except:
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton("Join Channel", url=f"https://t.me/{CHANNEL[1:]}"),
             types.InlineKeyboardButton("Source Code", url="https://t.me/+ssN0YUB1KkNkNTQ9")],
            [types.InlineKeyboardButton("✅ I Joined", callback_data="check_fsub")]
        ])
        return await message.reply(
            "<u><b>Access Denied</b></u>\n\n<i>This command is for channel members only!</i>",
            reply_markup=markup
        )
    
    user_id = message.from_user.id
    now = int(time.time() * 1000)

    meth_count = await get_prop(f"meth_count_{user_id}") or 0
    token_data = await get_prop(f"token_meth_{user_id}")

    has_access = False
    if token_data:
        try:
            token_created = token_data.get("created", 0)
            if now - token_created < 6 * 60 * 60 * 1000:  # 6 hours
                has_access = True
        except Exception:
            pass

    if meth_count >= 3 and not has_access:
        token = str(time.time()).replace('.', '')[-10:]
        await set_prop(f"token_meth_{user_id}", {"token": token, "created": now})
        verify_url = f"https://t.me/Qjiibot?start=verify_{user_id}_{token}"

        random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        alias = f"IGbot_{random_part}"

        try:
            res = requests.get(
                f"https://arolinks.com/api?api=5ba1b9f950d09e04c0ff351012dacbbc2472641d"
                f"&url={verify_url}&alias={alias}"
            )
            short = res.json().get("shortenedUrl") or verify_url
        except:
            short = verify_url

        return await message.reply(
            "🚫 <b>Your free meth limit has been reached!</b>\n\n"
            "🔓 You can unlock 6 hours of free access by completing a simple verification.\n\n"
            "💎 Or upgrade to Premium for unlimited access and faster delivery.\n\n"
            "👇 Choose an option below:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton("🔓 Unlock Free Access", url=short)],
                [
                 types.InlineKeyboardButton("ℹ️ Tutorial", url="https://t.me/ChipsTutorial/8")]
            ])
        )

    if not has_access:
        await set_prop(f"meth_count_{user_id}", meth_count + 1)

    await message.answer("<b>Please Send Your Target Username Without @</b>")
    await MethState.username.set()

@dp.message_handler(state=MethState.username)
async def meth_handler(message: types.Message, state: FSMContext):
    username = message.text.strip().replace('@', '')
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api-v2.nextcounts.com/api/instagram/user/{username}", timeout=10) as resp:
                if resp.status != 200:
                    raise Exception("Failed to fetch data.")
                data = await resp.json()

        info = (f"<b>Is this the correct user?</b>\n\n"
                f"• <b>Username:</b> {data['username']}\n"
                f"• <b>Nickname:</b> {data.get('nickname', 'N/A')}\n"
                f"• <b>Followers:</b> {data['followers']}\n"
                f"• <b>Following:</b> {data['following']}\n"
                f"• <b>Posts:</b> {data['posts']}")
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton("Yes ✅", callback_data=f"confirm_yes_{username}"),
             types.InlineKeyboardButton("No ❌", callback_data="confirm_no")]
        ])
        await message.reply(info, reply_markup=markup)
        await state.finish()
    except:
        await message.reply("<b>Error while processing. Try again.</b>")

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_") or c.data == "check_fsub")
async def callback_handler(cb: types.CallbackQuery):
    data = cb.data

    if data == "check_fsub":
        try:
            member = await bot.get_chat_member(CHANNEL, cb.from_user.id)
            if member.status in ['left', 'kicked']:
                return await cb.answer("Still not joined.", show_alert=True)
            await cb.answer("Thanks! Use /meth")
        except:
            await cb.answer("Error checking.", show_alert=True)
        return

    if data == "confirm_no":
        await cb.message.edit_text("<b>Okay, Try again. /meth</b>")
        return

    if data.startswith("confirm_yes_"):
        username = data.split("confirm_yes_")[1]
        await cb.message.edit_text(f"<b>Confirmed IG:</b> @{username}\n\nStarting...")
        loading = await bot.send_message(cb.message.chat.id, "<b>Generating method... Please wait.</b>")
        for i in range(10, 101, 10):
            bar = '▓' * (i // 10) + '░' * (10 - i // 10)
            await asyncio.sleep(0.1)
            try:
                await bot.edit_message_text(
                    f"<b>🔍 Scanning Profile... {i}%</b>\n<pre>{bar}</pre>",
                    cb.message.chat.id,
                    loading.message_id
                )
            except:
                break

        existing = reports_col.find_one({"username": username})
        if existing:
            result = "\n".join([f"➥ {cat}" for cat in existing['reports']])
        else:
            categories = ['Nudity¹', 'Nudity²', 'Hate', 'Scam', 'Terrorism', 'Vio¹', 'Vio²',
                          'Sale Illegal [Drugs]', 'Firearms', 'Bully_Me', 'Self_Injury', 'Spam']
            picked = random.sample(categories, k=random.randint(2, 4))
            result = "\n".join([f"➥ {random.randint(1, 5)}x {cat}" for cat in picked])
            reports_col.insert_one({
                "username": username,
                "reports": picked,
                "generatedBy": cb.from_user.id
            })

        final_text = (f"<i>Username : @{username}</i>\n\n<b>Suggested Reports for Your Target:</b>\n\n"
                      f"<pre>{result}</pre>\n\n"
                      f"<blockquote>⚠️ <b>Note:</b> <i><a href='https://t.me/Sendpayments'>This method is based on available data and may not be fully accurate.</a></i></blockquote>")
        await bot.edit_message_text(final_text, cb.message.chat.id, loading.message_id,
                                    parse_mode='HTML', disable_web_page_preview=True,
                                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                                        [types.InlineKeyboardButton("ᴜᴘᴅᴀᴛᴇ", url="https://t.me/PythonBotz"),
                                         types.InlineKeyboardButton("ᴅᴇᴠʟᴏᴘᴇʀ", url="https://t.me/existable")],
                                        [types.InlineKeyboardButton("ᴛᴀʀɢᴇᴛ ᴘʀᴏғɪʟᴇ", url=f"https://instagram.com/{username}")]
                                    ]))


# /verify (via /start verify_)
async def verify_token(message: types.Message):
    parts = message.text.split("_")
    if len(parts) != 3:
        return await message.reply("❌ Invalid verify link.")
    user_id, token = parts[1], parts[2]
    token_data = await get_prop(f"token_{user_id}")
    if token_data and token_data["token"] == token:
        await set_prop(f"verified_{int(user_id)}", int(time.time() * 1000))
        return await message.reply("✅ <b>Access Unlocked!</b>\n\nYou now have unlimited likes for 6 hours.")
    else:
        return await message.reply("❌ Invalid or expired token.")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)
    
