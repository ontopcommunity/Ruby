import ast
import asyncio
import contextlib
import html
import json
import os
import re
import sys
import traceback
import logging
from logging import getLogger
from urllib.parse import quote

import aiohttp
import httpx
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from gtts import gTTS
from PIL import Image
from pyrogram import Client, filters
from pyrogram.errors import (
    ChatAdminRequired,
    MessageTooLong,
    QueryIdInvalid,
    UserNotParticipant,
)
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from pyrogram.enums import ParseMode

from tiensiteo import BOT_USERNAME, app
from tiensiteo.core.decorator.errors import capture_err
from tiensiteo.helper.http import fetch
from tiensiteo.helper.tools import gen_trans_image, rentry
from tiensiteo.vars import COMMAND_HANDLER
from utils import extract_user, get_file_id

LOGGER = getLogger("TienSiTeo")

__MODULE__ = "TínhNăngKhác"
__HELP__ = """
<blockquote>/carbon [văn bản hoặc trả lời văn bản hoặc chú thích] - Tạo đoạn mã đẹp trên Carbon từ văn bản

/rmbg [trả lời hình ảnh] - Xóa nền của ảnh
  
(/tr, /trans, /translate) [mã ngôn ngữ] - Dịch văn bản bằng Google Translate 
 
/tts - Chuyển đổi văn bản thành giọng nói  

/imdb [truy vấn] - Tìm thông tin phim từ IMDB.com  

/readqr [trả lời ảnh] - Đọc mã QR từ ảnh  

/createqr [văn bản] - Chuyển đổi văn bản thành mã QR  

/laythongtin - Lấy thông tin người dùng với ảnh và mô tả đầy đủ nếu người dùng đã thiết lập ảnh hồ sơ  

/layid - Lấy ID người dùng đơn giản

/taonut nội dung (tên_nút_1)[url_1] (tên_nút_2)[url_2] - Tạo tin nhắn với nội dung và các nút inline. Định dạng: *đậm*, _nghiêng_, __gạch dưới__, `mã`, {text}[url] cho link

/thoitiet [tỉnh/thành phố] - Xem thông tin và dự báo thời tiết</blockquote>
"""


def remove_html_tags(text):
    """Remove html tags from a string"""

    clean = re.compile("<.*?>")
    return re.sub(clean, "", text)

API_KEY = "23nfCEipDijgVv6SH14oktJe"

def check_filename(filroid):
    if os.path.exists(filroid):
        no = 1
        while True:
            ult = "{0}_{2}{1}".format(*os.path.splitext(filroid) + (no,))
            if os.path.exists(ult):
                no += 1
            else:
                return ult
    return filroid

async def RemoveBG(input_file_name):
    headers = {"X-API-Key": API_KEY}
    url = "https://api.remove.bg/v1.0/removebg"
    try:
        with open(input_file_name, "rb") as img_file:
            files = {"image_file": img_file}
            r = await fetch.post(url, headers=headers, files=files)
            # Kiểm tra xem phản hồi có phải là JSON (lỗi) hay không
            try:
                # Nếu phản hồi là JSON, giả định rằng đây là lỗi
                error_data = r.json()
                return False, error_data
            except ValueError:
                # Nếu không phải JSON, giả định rằng đây là dữ liệu ảnh
                name = check_filename("alpha.png")
                with open(name, "wb") as f:
                    f.write(r.content)
                return True, name
    except Exception as e:
        return False, {"errors": [{"title": "Processing Error", "detail": str(e)}]}

@app.on_message(filters.command("rmbg", COMMAND_HANDLER))
@capture_err
async def rmbg(c: Client, m: Message):
    if not m.reply_to_message:
        return await m.reply("Vui lòng trả lời một ảnh để xóa nền.")
    
    if not m.reply_to_message.photo:
        return await m.reply("Vui lòng trả lời một ảnh để xóa nền.")

    rmbg_msg = await m.reply("Đang xử lý...")
    photo = await m.reply_to_message.download()

    try:
        success, result = await RemoveBG(photo)
        os.remove(photo)
        
        if not success:
            error = result.get("errors", [{}])[0]
            title = error.get("title", "Unknown Error")
            details = error.get("detail", "")
            return await rmbg_msg.edit(f"Lỗi: {title}\n{details}")
        
        await m.reply_photo(
            photo=result,
            caption=f"Ảnh đã xóa nền bởi @{BOT_USERNAME}",
            quote=True
        )
        await m.reply_document(
            document=result,
            caption=f"Tệp ảnh đã xóa nền bởi @{BOT_USERNAME}",
            quote=True
        )
        await rmbg_msg.delete()
        os.remove(result)
    
    except Exception as e:
        await rmbg_msg.edit(f"Lỗi: {str(e)}")
        if os.path.exists(photo):
            os.remove(photo)

@app.on_cmd("carbon")
async def carbon_make(self: Client, ctx: Message):
    if ctx.reply_to_message and ctx.reply_to_message.text:
        text = ctx.reply_to_message.text
    elif ctx.reply_to_message and ctx.reply_to_message.caption:
        text = ctx.reply_to_message.caption
    elif len(ctx.command) > 1:
        text = ctx.input
    else:
        return await ctx.reply(
            "Vui lòng trả lời văn bản để tạo carbon hoặc thêm văn bản sau lệnh."
        )
    json_data = {
        "code": text,
        "backgroundColor": "#1F816D",
    }
    with contextlib.redirect_stdout(sys.stderr):
        try:
            response = await fetch.post(
                "https://carbon.yasirapi.eu.org/api/cook", json=json_data, timeout=20
            )
        except httpx.HTTPError as exc:
            return await ctx.reply_msg(f"HTTP Exception for {exc.request.url} - {exc}")
    if response.status_code != 200:
        return await ctx.reply_photo(
            f"https://http.cat/{response.status_code}",
            caption="<b>🤧 Carbon API ERROR</b>",
        )
    fname = (
        f"carbonBY_{ctx.from_user.id if ctx.from_user else ctx.sender_chat.title}.png"
    )
    with open(fname, "wb") as e:
        e.write(response.content)
    await ctx.reply_photo(fname, caption=f"Generated by @{self.me.username}")
    os.remove(fname)


@app.on_message(filters.command("readqr", COMMAND_HANDLER))
async def readqr(c, m):
    if not m.reply_to_message:
        return await m.reply("Vui lòng trả lời ảnh có chứa Mã QR hợp lệ.")
    if not m.reply_to_message.photo:
        return await m.reply("Vui lòng trả lời ảnh có chứa Mã QR hợp lệ.")
    foto = await m.reply_to_message.download()
    myfile = {"file": (foto, open(foto, "rb"), "application/octet-stream")}
    url = "http://api.qrserver.com/v1/read-qr-code/"
    r = await fetch.post(url, files=myfile)
    os.remove(foto)
    if res := r.json()[0]["symbol"][0]["data"] is None:
        return await m.reply_msg(res)
    await m.reply_msg(
        f"<b>QR Code Reader by @{c.me.username}:</b> <code>{r.json()[0]['symbol'][0]['data']}</code>",
        quote=True,
    )


@app.on_message(filters.command("createqr", COMMAND_HANDLER))
async def makeqr(c, m):
    if m.reply_to_message and m.reply_to_message.text:
        teks = m.reply_to_message.text
    elif len(m.command) > 1:
        teks = m.text.split(None, 1)[1]
    else:
        return await m.reply(
            "Vui lòng thêm văn bản sau lệnh để chuyển đổi văn bản -> Mã QR."
        )
    url = f"https://api.qrserver.com/v1/create-qr-code/?data={quote(teks)}&size=300x300"
    await m.reply_photo(
        url, caption=f"<b>QR Code Maker by @{c.me.username}</b>", quote=True
    )

@app.on_message(filters.command(["tr", "trans", "translate"], COMMAND_HANDLER))
@capture_err
async def translate(_, message):
    if message.reply_to_message and (
        message.reply_to_message.text or message.reply_to_message.caption
    ):
        target_lang = "vi" if len(message.command) == 1 else message.text.split()[1]
        text = message.reply_to_message.text or message.reply_to_message.caption
    else:
        if len(message.command) < 3:
            return await message.reply_msg(
                "Cung cấp mã ngôn ngữ hợp lệ.\n[Xem các tùy chọn](https://tgraph.yasirweb.eu.org/Lang-Codes-11-08).\n<b>Sử dụng:</b> <code>/tr vi</code>",
            )
        target_lang = message.text.split(None, 2)[1]
        text = message.text.split(None, 2)[2]
    msg = await message.reply_msg("Đang dịch...")
    try:
        my_translator = GoogleTranslator(source="auto", target=target_lang)
        result = my_translator.translate(text=text)
        await msg.edit_msg(
            f"💠 <b>Bản dịch {my_translator.source} -> {my_translator.target}</b>\n——————————————————\n<blockquote expandable>{result}</blockquote>\n<b>Dịch bởi Tiến sĩ Tèo</b>"
        )
    except MessageTooLong:
        url = await rentry(result)
        await msg.edit_msg(
            f"<b>Bản dịch của bạn được dán vào Rentry vì có văn bản dài:</b>\n{url}"
        )
    except Exception as err:
        await msg.edit_msg(f"Oppss, Lỗi: <code>{str(err)}</code>")


@app.on_message(filters.command(["tts"], COMMAND_HANDLER))
@capture_err
async def tts_convert(_, message):
    if message.reply_to_message and (
        message.reply_to_message.text or message.reply_to_message.caption
    ):
        if len(message.text.split()) == 1:
            target_lang = "vi"
        else:
            target_lang = message.text.split()[1]
        text = message.reply_to_message.text or message.reply_to_message.caption
    else:
        if len(message.text.split()) <= 2:
            await message.reply_text(
                "Cung cấp Mã ngôn ngữ hợp lệ.\n[Tùy chọn có sẵn](https://telegra.ph/Lang-Codes-11-08).\n*Cách sử dụng:* /tts vi [văn bản]",
            )
            return
        target_lang = message.text.split(None, 2)[1]
        text = message.text.split(None, 2)[2]
    msg = await message.reply("Đang chuyển đổi sang giọng nói...")
    fname = f"TTS_by_{message.from_user.id if message.from_user else message.sender_chat.title}.mp3"
    try:
        tts = gTTS(text, lang=target_lang)
        tts.save(fname)
    except ValueError as err:
        await msg.edit(f"Error: <code>{str(err)}</code>")
        return
    await msg.delete()
    await msg.reply_audio(fname)
    if os.path.exists(fname):
        os.remove(fname)


@app.on_message(filters.command(["layid"], COMMAND_HANDLER))
async def showid(_, message):
    chat_type = message.chat.type.value
    if chat_type == "private":
        user_id = message.chat.id
        first = message.from_user.first_name
        last = message.from_user.last_name or ""
        username = message.from_user.username
        dc_id = message.from_user.dc_id or ""
        await message.reply_text(
            f"<b>➲ Họ:</b> {first}\n<b>➲ Tên:</b> {last}\n<b>➲ Tên người dùng:</b> {username}\n<b>➲ Telegram ID:</b> <code>{user_id}</code>\n<b>➲ TT Dữ liệu:</b> <code>{dc_id}</code>",
            quote=True,
        )

    elif chat_type in ["group", "supergroup"]:
        _id = ""
        _id += "<b>➲ ID Nhóm</b>: " f"<code>{message.chat.id}</code>\n"
        if message.reply_to_message:
            _id += (
                "<b>➲ ID Người dùng</b>: "
                f"<code>{message.from_user.id if message.from_user else 'Anonymous'}</code>\n"
                "<b>➲ ID người dùng đã trả lời</b>: "
                f"<code>{message.reply_to_message.from_user.id if message.reply_to_message.from_user else 'Anonymous'}</code>\n"
            )
            file_info = get_file_id(message.reply_to_message)
        else:
            _id += (
                "<b>➲ ID Người dùng</b>: "
                f"<code>{message.from_user.id if message.from_user else 'Anonymous'}</code>\n"
            )
            file_info = get_file_id(message)
        if file_info:
            _id += (
                f"<b>{file_info.message_type}</b>: "
                f"<code>{file_info.file_id}</code>\n"
            )
        await message.reply_text(_id, quote=True)


@app.on_message(filters.command(["laythongtin"], COMMAND_HANDLER))
async def who_is(client, message):
    # https://github.com/SpEcHiDe/PyroGramBot/blob/master/pyrobot/plugins/admemes/whois.py#L19
    if message.sender_chat:
        return await message.reply_msg("Kênh không được hỗ trợ..")
    status_message = await message.reply_text("`Đang lấy thông tin người dùng...`")
    await status_message.edit("`Xử lý thông tin người dùng...`")
    from_user = None
    from_user_id, _ = extract_user(message)
    try:
        from_user = await client.get_users(from_user_id)
    except Exception as error:
        return await status_message.edit(str(error))
    if from_user is None:
        return await status_message.edit("Không có user_id/tin nhắn hợp lệ nào được chỉ định")
    message_out_str = ""
    username = f"@{from_user.username}" or "<b>Không có tên người dùng</b>"
    dc_id = from_user.dc_id or "<i>[Người dùng không có ảnh hồ sơ]</i>"
    bio = (await client.get_chat(from_user.id)).bio
    count_pic = await client.get_chat_photos_count(from_user.id)
    message_out_str += f"<b>🔸 Họ:</b> {from_user.first_name}\n"
    if last_name := from_user.last_name:
        message_out_str += f"<b>🔹 Tên:</b> {last_name}\n"
    message_out_str += f"<b>🆔 ID:</b> <code>{from_user.id}</code>\n"
    message_out_str += f"<b>✴️ Tên người dùng:</b> {username}\n"
    message_out_str += f"<b>💠 TT Dữ liệu:</b> <code>{dc_id}</code>\n"
    if bio:
        message_out_str += f"<b>👨🏿‍💻 Bio:</b> <code>{bio}</code>\n"
    message_out_str += f"<b>📸 Ảnh:</b> {count_pic}\n"
    message_out_str += f"<b>🧐 Hạn chế:</b> {from_user.is_restricted}\n"
    message_out_str += f"<b>✅ Đã xác minh:</b> {from_user.is_verified}\n"
    message_out_str += f"<b>🌐 Liên kết trang cá nhân:</b> <a href='tg://user?id={from_user.id}'><b>Bấm vào đây</b></a>\n"
    if message.chat.type.value in (("supergroup", "channel")):
        with contextlib.suppress(UserNotParticipant, ChatAdminRequired):
            chat_member_p = await message.chat.get_member(from_user.id)
            joined_date = chat_member_p.joined_date
            message_out_str += (
                "<b>➲Đã tham gia cuộc trò chuyện này vào:</b> <code>" f"{joined_date}" "</code>\n"
            )
    if chat_photo := from_user.photo:
        local_user_photo = await client.download_media(message=chat_photo.big_file_id)
        buttons = [
            [
                InlineKeyboardButton(
                    "🔐 Đóng", callback_data=f"close#{message.from_user.id}"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_photo(
            photo=local_user_photo,
            quote=True,
            reply_markup=reply_markup,
            caption=message_out_str,
            disable_notification=True,
        )
        os.remove(local_user_photo)
    else:
        buttons = [
            [
                InlineKeyboardButton(
                    "🔐 Đóng", callback_data=f"close#{message.from_user.id}"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(
            text=message_out_str,
            reply_markup=reply_markup,
            quote=True,
            disable_notification=True,
        )
    await status_message.delete_msg()


@app.on_callback_query(filters.regex("^close"))
async def close_callback(_, query: CallbackQuery):
    _, userid = query.data.split("#")
    if query.from_user.id != int(userid):
        with contextlib.suppress(QueryIdInvalid):
            return await query.answer("⚠️ Truy cập bị từ chối!", True)
    with contextlib.redirect_stdout(Exception):
        await query.answer("Tin nhắn này sẽ xóa sau 5 giây.")
        await asyncio.sleep(5)
        await query.message.delete_msg()
        #await query.message.reply_to_message.delete_msg()

        
@app.on_message(filters.command(["thuid"], COMMAND_HANDLER))
async def thuid_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Vui lòng cung cấp ID người dùng.")
        return

    user_id = message.command[1]

    profile_link = f"tg://user?id={user_id}"
    text = (
        f"Nhấn vào link sau để xem profile của id bạn vừa yêu cẩu: {profile_link}\n\n"
        "⚠️ Link sẽ không bấm được nếu ID bị sai / không tồn tại / bị xoá."
    )

    await message.reply_text(text, disable_web_page_preview=True)

@app.on_message(filters.command("taonut", COMMAND_HANDLER))
@capture_err
async def create_buttons(c: Client, m: Message):
    suggestion_text = (
        "Vui lòng cung cấp nội dung và ít nhất một nút.\n\n"
        "<code>/taonut *Xin* _chào_ {anh em}[https://dabeecao.org] (Về tôi)[https://dabeecao.org]</code>\n\n"
        "Định dạng: <code>*đậm*, _nghiêng_, __gạch dưới__, `mã`, {text}[url] cho link</code>"
    )
    
    if len(m.text.split()) < 2:
        return await m.reply(suggestion_text)

    # Lấy nội dung và phần chứa nút
    text = m.text[len("/taonut "):].strip()
    
    # Tìm tất cả các nút theo pattern (tên)[url]
    button_pattern = r'\((.*?)\)\[(.*?)\]'
    buttons = re.findall(button_pattern, text)
    
    if not buttons:
        return await m.reply(
            "Không tìm thấy nút nào. Vui lòng dùng định dạng: (tên_nút)[url]\n\n" + suggestion_text
        )

    # Lấy nội dung chính (loại bỏ phần nút)
    content = re.sub(button_pattern, '', text).strip()
    
    # Kiểm tra nếu không có nội dung (chỉ có nút)
    if not content and buttons:
        return await m.reply(
            "Vui lòng thêm nội dung kèm theo nút.\n\n" + suggestion_text,
            parse_mode=ParseMode.HTML
        )

    if not content:
        content = " "  # Đảm bảo có nội dung để gửi tin nhắn

    # Chuyển đổi cú pháp định dạng sang HTML
    # Link: {text}[url] -> <a href="url">text</a>
    content = re.sub(r'\{(.*?)\}\[(.*?)\]', r'<a href="\2">\1</a>', content)
    # Đậm: *text* -> <b>text</b>
    content = re.sub(r'\*(.*?)\*', r'<b>\1</b>', content)
    # Nghiêng: _text_ -> <i>text</i>
    content = re.sub(r'_(.*?)_', r'<i>\1</i>', content)
    # Gạch dưới: __text__ -> <u>text</u>
    content = re.sub(r'__(.*?)__', r'<u>\1</u>', content)
    # Mã: `text` -> <code>text</code>
    content = re.sub(r'`(.*?)`', r'<code>\1</code>', content)

    # Tạo danh sách các nút inline
    inline_buttons = []
    current_row = []
    
    for button_name, button_url in buttons:
        button = InlineKeyboardButton(text=button_name.strip(), url=button_url.strip())
        current_row.append(button)
        
        # Nếu có 2 nút trong một hàng thì xuống hàng mới
        if len(current_row) == 2:
            inline_buttons.append(current_row)
            current_row = []
    
    # Thêm hàng cuối nếu còn nút
    if current_row:
        inline_buttons.append(current_row)

    # Tạo markup cho các nút
    reply_markup = InlineKeyboardMarkup(inline_buttons)

    # Gửi tin nhắn với nội dung và các nút, bật chế độ parse HTML
    await m.reply(
        content,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,  # Dùng HTML để hỗ trợ định dạng
        quote=True
    )