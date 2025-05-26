import telebot
import websocket
import json
import threading
import os
import uuid
import time
from telebot import TeleBot
from collections import deque
import random
from datetime import datetime, timedelta

# ==== PHÂN BIỆT FILE LƯU TRỮ ĐỘC LẠ CHO BOT NÀY ====
BOT_ID = "demo" + str(uuid.uuid4())[:8]  # Ví dụ: taixiu_8e3a4c6b

HISTORY_FILE = f"history_{BOT_ID}.json"
KEYS_FILE = f"keys_{BOT_ID}.json"
ADMINS_FILE = f"admins_{BOT_ID}.json"
BANNED_USERS_FILE = f"banned_users_{BOT_ID}.json"
BANNED_GROUPS_FILE = f"banned_groups_{BOT_ID}.json"
USERS_FILE = f"users_{BOT_ID}.json"
GROUPS_FILE = f"groups_{BOT_ID}.json"

# Bot token và admin_id (bạn cần điền đúng)
BOT_TOKEN = "7843749093:AAGJg531Vb1GvBBGMfXSZBwP3S80iJwfEjc"
ADMIN_ID = 6020088518  # Thay bằng ID admin của bạn

bot = TeleBot(BOT_TOKEN)

# WebSocket URL (thay bằng URL thực tế của server tài xỉu)
WS_URL = "ws://163.61.110.10:8000/game_sunwin/ws?id=duy914c&key=dduy1514"

# Lưu trữ dữ liệu
history = deque(maxlen=100)
predictions = {}
subscribed_chats = set()
admins = set()
banned_users = set()
banned_groups = set()
users = set()
groups = set()
keys = {}

def save_json(obj, fname):
    with open(fname, "w") as f:
        if isinstance(obj, set):
            json.dump(list(obj), f)
        else:
            json.dump(obj, f, ensure_ascii=False, indent=2)

def load_json(fname):
    if os.path.exists(fname):
        with open(fname) as f:
            try:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
                return data
            except Exception:
                return set()
    return set()

def save_all():
    save_json(admins, ADMINS_FILE)
    save_json(banned_users, BANNED_USERS_FILE)
    save_json(banned_groups, BANNED_GROUPS_FILE)
    save_json(users, USERS_FILE)
    save_json(groups, GROUPS_FILE)

def load_all():
    global admins, banned_users, banned_groups, users, groups
    admins = load_json(ADMINS_FILE)
    banned_users = load_json(BANNED_USERS_FILE)
    banned_groups = load_json(BANNED_GROUPS_FILE)
    users = load_json(USERS_FILE)
    groups = load_json(GROUPS_FILE)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            data = json.load(f)
            for item in data:
                history.append(item)

def save_history():
    with open(HISTORY_FILE, 'w') as f:
        json.dump(list(history), f, ensure_ascii=False, indent=2)

def load_keys():
    global keys
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, 'r') as f:
            keys = json.load(f)

def save_keys():
    with open(KEYS_FILE, 'w') as f:
        json.dump(keys, f, ensure_ascii=False, indent=2)

def predict_taixiu():
    if len(history) < 3:
        win_rate = random.randint(65, 90)
        return ("Tài" if random.choice([True, False]) else "Xỉu", win_rate)
    last_three = [item["Ket_qua"] for item in list(history)[-3:]]
    if all(x == "Tài" for x in last_three):
        return ("Xỉu", 90)
    elif all(x == "Xỉu" for x in last_three):
        return ("Tài", 90)
    prediction = "Tài" if random.choice([True, False]) else "Xỉu"
    win_rate = random.randint(65, 90)
    return (prediction, win_rate)

def on_message(ws, message):
    data = json.loads(message)
    if all(key in data for key in ["Phien", "Xuc_xac_1", "Xuc_xac_2", "Xuc_xac_3", "Tong", "Ket_qua"]):
        for chat_id in subscribed_chats:
            if chat_id not in predictions:
                predictions[chat_id] = []
            if predictions[chat_id] and predictions[chat_id][-1]["Phien"] == data["Phien"] - 1:
                last_pred = predictions[chat_id][-1]
                result = "🏆 Chiến thắng" if last_pred["Prediction"] == data["Ket_qua"] else "😢 Thua"
                prediction, win_rate = predict_taixiu()
                predictions[chat_id].append({"Phien": data["Phien"], "Prediction": prediction, "Actual": None})
                bot.send_message(
                    chat_id,
                    f"🎲 Phiên: {data['Phien'] + 1}\n"
                    f"🔔 Mọi người hãy chọn: {prediction}\n"
                    f"📈 Tỷ lệ win: {win_rate}%"
                )
                time.sleep(5)
                bot.send_message(
                    chat_id,
                    f"🎰 Phiên: {last_pred['Phien']}\n"
                    f"📣 Kết quả\n"
                    f"🎲 Xúc xắc: {data['Xuc_xac_1']}️⃣ {data['Xuc_xac_2']}️⃣ {data['Xuc_xac_3']}️⃣\n"
                    f"🔢 Tổng: {data['Tong']}\n"
                    f"🏆 Kết quả: {data['Ket_qua']}\n"
                    f"{result}"
                )
        for key, info in list(keys.items()):
            if info["uses"] <= 0 or info["expiry"] < time.time():
                del keys[key]
                save_keys()
                continue
            info["uses"] -= 1
            chat_id = info["chat_id"]
            prediction, win_rate = predict_taixiu()
            try:
                bot.send_message(
                    chat_id,
                    f"🔒 Tín hiệu riêng (Key: {key})\n"
                    f"🎲 Phiên: {data['Phien'] + 1}\n"
                    f"🔔 Mọi người hãy chọn: {prediction}\n"
                    f"📈 Tỷ lệ win: {win_rate}%"
                )
                bot.send_message(
                    chat_id,
                    f"🔒 Tín hiệu riêng (Key: {key})\n"
                    f"🎰 Phiên: {data['Phien']}\n"
                    f"📣 Kết quả\n"
                    f"🎲 Xúc xắc: {data['Xuc_xac_1']}️⃣ {data['Xuc_xac_2']}️⃣ {data['Xuc_xac_3']}️⃣\n"
                    f"🔢 Tổng: {data['Tong']}\n"
                    f"🏆 Kết quả: {data['Ket_qua']}\n"
                    f"{'🏆 Chiến thắng' if prediction == data['Ket_qua'] else '😢 Thua'}"
                )
            except Exception:
                pass
        history.append(data)
        save_history()

def on_error(ws, error):
    print(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed")

def on_open(ws):
    print("WebSocket connected")

def run_websocket():
    ws = websocket.WebSocketApp(WS_URL,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()

# ========== CÁC LỆNH BOT ==========

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    users.add(user_id)
    groups.add(chat_id)
    save_all()
    subscribed_chats.add(chat_id)
    if chat_id not in predictions:
        predictions[chat_id] = []
    bot.send_message(chat_id, 
        "🤖 Xin chào! Đây là bot dự đoán tài xỉu tự động.\n"
        "Để sử dụng bot, vui lòng liên hệ admin: t.me/hknamip\n"
        "Để xem các lệnh, hãy dùng /help"
    )

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(message,
        "📜 Danh sách lệnh:\n"
        "/help - Xem hướng dẫn\n"
        "/taokey <lượt> <thời_gian> - Tạo key mới (admin)\n"
        "/key <key> - Nhập key để nhận tín hiệu riêng\n"
        "/lichsu <số_ván> - Xem lịch sử X ván gần nhất\n"
        "/ban - Reply vào user cần ban (admin)\n"
        "/unban - Reply vào user cần unban (admin)\n"
        "/listban - Danh sách user bị ban (admin)\n"
        "/themadmin <id> - Thêm admin phụ (admin gốc)\n"
        "/xoaadmin <id> - Xoá admin phụ (admin gốc)\n"
        "/listkey - Danh sách key (admin)\n"
        "/list - Danh sách user đã dùng bot (admin)\n"
        "/listnhom - Danh sách nhóm bot hoạt động (admin)\n"
        "/bannhom <id> - Ban nhóm không cho chạy bot\n"
        "/listbannhom - Danh sách nhóm bị ban (admin)\n"
        "/tb <nội_dung> - Gửi thông báo tới tất cả user/nhóm (admin)\n"
        "/tbrieng - Reply vào user & nhập nội dung (admin)\n"
        "/xoatb - Reply vào thông báo cần xoá (admin)\n"
        "/xoakey <key> - Xoá key khỏi hệ thống (admin)\n"
    )

@bot.message_handler(commands=['lichsu'])
def lichsu_cmd(message):
    chat_id = message.chat.id
    args = message.text.split()
    so_van = 5
    if len(args) > 1 and args[1].isdigit():
        so_van = int(args[1])
    if len(history) == 0:
        bot.send_message(chat_id, "⚠️ Chưa có lịch sử phiên nào!")
        return
    recent_history = list(history)[-so_van:]
    msg = f"📜 Lịch sử {so_van} phiên gần nhất:\n"
    for session in recent_history:
        msg += (f"🎰 Phiên: {session['Phien']}\n"
                f"🎲 Xúc xắc: {session['Xuc_xac_1']}️⃣ {session['Xuc_xac_2']}️⃣ {session['Xuc_xac_3']}️⃣\n"
                f"🔢 Tổng: {session['Tong']}\n"
                f"🏆 Kết quả: {session['Ket_qua']}\n\n")
    bot.send_message(chat_id, msg)

@bot.message_handler(commands=['key'])
def key_cmd(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    if user_id in banned_users:
        bot.reply_to(message, "Bạn đã bị cấm sử dụng bot.")
        return
    try:
        key = message.text.split()[1]
        if key in keys:
            # Key chưa ai dùng hoặc user này là người đã dùng key này
            if keys[key]["chat_id"] is None or keys[key]["chat_id"] == user_id:
                keys[key]["chat_id"] = user_id
                save_keys()
                seconds_left = int(keys[key]['expiry'] - time.time())
                if seconds_left < 0: seconds_left = 0
                expire_time = datetime.fromtimestamp(keys[key]['expiry'])
                expire_str = expire_time.strftime("%H:%M:%S %d-%m-%Y")
                # User KHÔNG thấy số lượt
                bot.reply_to(
                    message,
                    f"✅ Key {key} đã được kích hoạt!\n"
                    f"⏰ Thời gian còn lại: {str(timedelta(seconds=seconds_left))} (hết hạn lúc: {expire_str})"
                )
                # Admin có số lượt
                admin_notify = (
                    f"🔔 User: {user_name} (ID: {user_id}) vừa nhập key: {key}\n"
                    f"Thời hạn còn lại: {str(timedelta(seconds=seconds_left))} (hết hạn lúc: {expire_str})\n"
                    f"Số lượt còn lại: {keys[key]['uses']}\n"
                    f"Chat ID: {chat_id}"
                )
                try:
                    bot.send_message(ADMIN_ID, admin_notify)
                except Exception:
                    pass
            else:
                bot.reply_to(message, "Key này đã được sử dụng bởi người khác!")
        else:
            bot.reply_to(message, "Key không hợp lệ!")
    except Exception:
        bot.reply_to(message, "Vui lòng nhập đúng cú pháp: /key <key>")

@bot.message_handler(commands=['taokey'])
def taokey_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    try:
        _, uses, duration = message.text.split()
        uses = int(uses)
        duration = int(duration)
        key = str(uuid.uuid4())[:8]
        keys[key] = {
            "chat_id": None,
            "uses": uses,
            "expiry": time.time() + duration
        }
        save_keys()
        bot.reply_to(message, f"🔑 Key mới đã được tạo!\nKey: {key}\n🔄 Số lượt: {uses}\n⏰ Thời gian: {duration} giây")
    except Exception:
        bot.reply_to(message, "Cú pháp: /taokey <số_lượt> <thời_gian_giây>")

@bot.message_handler(commands=['ban'])
def ban_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "Bạn cần reply vào tin nhắn của người muốn ban.")
        return
    user_id = message.reply_to_message.from_user.id
    if user_id == ADMIN_ID:
        bot.reply_to(message, "Không thể ban admin gốc.")
        return
    banned_users.add(user_id)
    save_json(banned_users, BANNED_USERS_FILE)
    bot.reply_to(message, f"Đã ban user {user_id} khỏi bot.")

@bot.message_handler(commands=['unban'])
def unban_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "Bạn cần reply vào tin nhắn của người muốn unban.")
        return
    user_id = message.reply_to_message.from_user.id
    if user_id in banned_users:
        banned_users.remove(user_id)
        save_json(banned_users, BANNED_USERS_FILE)
        bot.reply_to(message, f"Đã mở ban cho user {user_id}.")
    else:
        bot.reply_to(message, "User này không bị ban.")

@bot.message_handler(commands=['listban'])
def listban_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    if not banned_users:
        bot.reply_to(message, "Không có user nào bị ban.")
    else:
        msg = "Danh sách user bị ban:\n"
        msg += "\n".join(str(uid) for uid in banned_users)
        bot.reply_to(message, msg)

@bot.message_handler(commands=['themadmin'])
def themadmin_cmd(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "Chỉ admin gốc mới được thêm admin.")
        return
    try:
        _, uid = message.text.split()
        uid = int(uid)
        admins.add(uid)
        save_json(admins, ADMINS_FILE)
        bot.reply_to(message, f"Đã thêm admin {uid}")
    except Exception:
        bot.reply_to(message, "Cú pháp: /themadmin <id>")

@bot.message_handler(commands=['xoaadmin'])
def xoaadmin_cmd(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "Chỉ admin gốc mới được xoá admin.")
        return
    try:
        _, uid = message.text.split()
        uid = int(uid)
        if uid in admins:
            admins.remove(uid)
            save_json(admins, ADMINS_FILE)
            bot.reply_to(message, f"Đã xoá admin {uid}")
        else:
            bot.reply_to(message, "ID này không phải admin phụ.")
    except Exception:
        bot.reply_to(message, "Cú pháp: /xoaadmin <id>")

@bot.message_handler(commands=['listkey'])
def listkey_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    msg = "Danh sách key:\n"
    for k, v in keys.items():
        msg += f"Key: {k} | User: {v['chat_id']} | Lượt: {v['uses']} | Expiry: {int(v['expiry']-time.time())}s\n"
    bot.reply_to(message, msg or "Không có key nào.")

@bot.message_handler(commands=['list'])
def list_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    msg = "Danh sách user đã dùng bot:\n" + "\n".join(str(u) for u in users)
    bot.reply_to(message, msg)

@bot.message_handler(commands=['listnhom'])
def listnhom_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    msg = "Danh sách nhóm đã dùng bot:\n" + "\n".join(str(g) for g in groups)
    bot.reply_to(message, msg)

@bot.message_handler(commands=['bannhom'])
def bannhom_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    try:
        _, gid = message.text.split()
        gid = int(gid)
        banned_groups.add(gid)
        save_json(banned_groups, BANNED_GROUPS_FILE)
        bot.reply_to(message, f"Đã ban nhóm {gid}")
    except Exception:
        bot.reply_to(message, "Cú pháp: /bannhom <id>")

@bot.message_handler(commands=['listbannhom'])
def listbannhom_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    msg = "Danh sách nhóm bị ban:\n" + "\n".join(str(g) for g in banned_groups)
    bot.reply_to(message, msg)

@bot.message_handler(commands=['tb'])
def tb_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    content = message.text.partition(' ')[2]
    for uid in users:
        try:
            bot.send_message(uid, f"📢 Thông báo admin: {content}")
        except Exception: pass
    for gid in groups:
        try:
            bot.send_message(gid, f"📢 Thông báo admin: {content}")
        except Exception: pass
    bot.reply_to(message, "Đã gửi thông báo.")

@bot.message_handler(commands=['tbrieng'])
def tbrieng_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "Bạn cần reply vào tin nhắn của người muốn gửi.")
        return
    content = message.text.partition(' ')[2]
    uid = message.reply_to_message.from_user.id
    bot.send_message(uid, f"📢 Thông báo riêng admin: {content}")
    bot.reply_to(message, f"Đã gửi cho {uid}")

@bot.message_handler(commands=['xoatb'])
def xoatb_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    if message.reply_to_message:
        try:
            bot.delete_message(message.reply_to_message.chat.id, message.reply_to_message.message_id)
            bot.reply_to(message, "Đã xoá thông báo.")
        except Exception:
            bot.reply_to(message, "Không thể xoá tin nhắn.")

@bot.message_handler(commands=['xoakey'])
def xoakey_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    try:
        _, key = message.text.split()
        if key in keys:
            del keys[key]
            save_keys()
            bot.reply_to(message, "Đã xoá key.")
        else:
            bot.reply_to(message, "Key không tồn tại.")
    except Exception:
        bot.reply_to(message, "Cú pháp: /xoakey <key>")

# ===== Khởi động =====
load_history()
load_keys()
load_all()
websocket_thread = threading.Thread(target=run_websocket)
websocket_thread.start()

bot.infinity_polling()