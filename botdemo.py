import telebot
import websocket
import json
import threading
import os
import uuid
import time
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from collections import deque
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import numpy as np

BOT_ID = "demo" + str(uuid.uuid4())[:8]

HISTORY_FILE = f"history_{BOT_ID}.json"
KEYS_FILE = f"keys_{BOT_ID}.json"
ADMINS_FILE = f"admins_{BOT_ID}.json"
BANNED_USERS_FILE = f"banned_users_{BOT_ID}.json"
BANNED_GROUPS_FILE = f"banned_groups_{BOT_ID}.json"
USERS_FILE = f"users_{BOT_ID}.json"
GROUPS_FILE = f"groups_{BOT_ID}.json"

BOT_TOKEN = "7843749093:AAGJg531Vb1GvBBGMfXSZBwP3S80iJwfEjc"
ADMIN_ID = 6020088518

bot = TeleBot(BOT_TOKEN)

WS_URL = "ws://163.61.110.10:8000/game_sunwin/ws?id=duy914c&key=dduy1514"

history = deque(maxlen=1000)
predictions = {}
subscribed_chats = set()
active_chats = set()
admins = set()
banned_users = set()
banned_groups = set()
users = set()
groups = set()
keys = {}
model = None
label_encoder = LabelEncoder()
scaler = StandardScaler()
MIN_DATA_POINTS = 5
processed_phien = set()

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
    save_json(active_chats, "active_chats.json")

def load_all():
    global admins, banned_users, banned_groups, users, groups, active_chats
    admins = load_json(ADMINS_FILE)
    banned_users = load_json(BANNED_USERS_FILE)
    banned_groups = load_json(BANNED_GROUPS_FILE)
    users = load_json(USERS_FILE)
    groups = load_json(GROUPS_FILE)
    active_chats = load_json("active_chats.json")

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
            for k in keys:
                if "users" not in keys[k]:
                    keys[k]["users"] = {}
                    if keys[k].get("chat_id"):
                        keys[k]["users"][str(keys[k]["chat_id"])] = {
                            "predict_enabled": keys[k].get("predict_enabled", True)
                        }
                    keys[k].pop("chat_id", None)
                    keys[k].pop("predict_enabled", None)
                if "duration" not in keys[k]:
                    keys[k]["duration"] = 3600

def save_keys():
    with open(KEYS_FILE, 'w') as f:
        json.dump(keys, f, ensure_ascii=False, indent=2)

def calculate_features(data):
    features = []
    for i in range(len(data)):
        session = data[i]
        dice_sum = session["Tong"]
        time_diff = (session["timestamp"] - data[i-1]["timestamp"]) if i > 0 else 0
        streak = 1
        j = i - 1
        while j >= 0 and data[j]["Ket_qua"] == session["Ket_qua"]:
            streak += 1
            j -= 1
        tai_count = sum(1 for k in range(max(0, i-10), i+1) if data[k]["Ket_qua"] == "Tài")
        xiu_count = 10 - tai_count if i >= 10 else i - tai_count
        feature = [
            session["Xuc_xac_1"],
            session["Xuc_xac_2"],
            session["Xuc_xac_3"],
            dice_sum,
            time_diff,
            streak,
            tai_count,
            xiu_count
        ]
        features.append(feature)
    return features

def train_model():
    global model
    if len(history) < MIN_DATA_POINTS:
        return False
    data = list(history)
    X = calculate_features(data)
    y = label_encoder.fit_transform([item["Ket_qua"] for item in data])
    X = scaler.fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=200, max_depth=10, min_samples_split=5, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Model accuracy: {accuracy:.2f}")
    return True

def predict_taixiu():
    if len(history) < MIN_DATA_POINTS or model is None:
        return None, 0
    data = list(history)
    X = calculate_features(data)
    X = scaler.transform([X[-1]])
    pred = model.predict(X)
    prob = model.predict_proba(X)[0][pred[0]] * 100
    prediction = label_encoder.inverse_transform(pred)[0]
    return prediction, round(prob, 1)

def check_data_sufficiency(chat_id):
    missing = MIN_DATA_POINTS - len(history)
    if missing > 0:
        bot.send_message(chat_id, f"⚠️ Chưa đủ dữ liệu để dự đoán! Cần thêm {missing} dữ liệu.")
        return False
    if len(history) == MIN_DATA_POINTS:
        if train_model():
            bot.send_message(chat_id, "✅ Đã đủ dữ liệu! Bắt đầu dự đoán từ phiên tiếp theo.")
        else:
            bot.send_message(chat_id, "❌ Lỗi khi huấn luyện mô hình!")
            return False
    return True

def on_message(ws, message):
    try:
        data = json.loads(message)
        required_keys = ["Phien", "Xuc_xac_1", "Xuc_xac_2", "Xuc_xac_3", "Tong", "Ket_qua"]
        if not all(key in data for key in required_keys):
            print(f"Invalid data received: {data}")
            return

        phien = data["Phien"]
        if phien in processed_phien:
            print(f"Phien {phien} already processed, skipping...")
            return
        processed_phien.add(phien)

        data["timestamp"] = time.time()
        history.append(data)
        save_history()
        train_model()

        # Lưu dự đoán cho phiên tiếp theo trước
        prediction, win_rate = predict_taixiu()
        for chat_id in subscribed_chats.copy():
            if chat_id in banned_groups or chat_id not in active_chats:
                continue
            if chat_id not in predictions:
                predictions[chat_id] = []
            if not check_data_sufficiency(chat_id):
                continue

            try:
                analysis_msg = bot.send_message(chat_id, "🤖 Bot đang phân tích ...")
            except Exception as e:
                print(f"Failed to send analysis message to {chat_id}: {e}")
                subscribed_chats.remove(chat_id)
                continue

            if prediction:
                predictions[chat_id].append({"Phien": data["Phien"] + 1, "Prediction": prediction, "WinRate": win_rate, "Actual": None})
                try:
                    bot.send_message(
                        chat_id,
                        f"🎲 Phiên: {data['Phien'] + 1}\n"
                        f"🔔 Dự đoán: {prediction}\n"
                        f"📈 Xác suất: {win_rate}%"
                    )
                except Exception as e:
                    print(f"Failed to send prediction to {chat_id}: {e}")
                    subscribed_chats.remove(chat_id)
                    continue

            time.sleep(1)
            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=analysis_msg.message_id,
                    text="⏳ Vui lòng chờ kết quả ..."
                )
            except Exception as e:
                print(f"Failed to send waiting message to {chat_id}: {e}")
                continue

            # Lấy dự đoán của phiên trước (data["Phien"]) để so sánh với kết quả thực tế
            current_pred = next((p for p in predictions[chat_id] if p["Phien"] == data["Phien"]), None)
            if current_pred:
                current_pred["Actual"] = data["Ket_qua"]
                result = "🏆 Chiến thắng" if current_pred["Prediction"] == data["Ket_qua"] else "😢 Thua"
                try:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=analysis_msg.message_id,
                        text=(
                            f"🎰 Phiên: {data['Phien']}\n"
                            f"📣 Kết quả\n"
                            f"🎲 Xúc xắc: {data['Xuc_xac_1']}️⃣ {data['Xuc_xac_2']}️⃣ {data['Xuc_xac_3']}️⃣\n"
                            f"🔢 Tổng: {data['Tong']}\n"
                            f"🏆 Kết quả: {data['Ket_qua']}\n"
                            f"📌 Dự đoán: {current_pred['Prediction']} ({result})"
                        )
                    )
                except Exception as e:
                    print(f"Failed to send result to {chat_id}: {e}")

        for key, info in list(keys.items()):
            if info["uses"] <= 0 or (info.get("expiry") and info["expiry"] < time.time()):
                del keys[key]
                save_keys()
                try:
                    bot.send_message(ADMIN_ID, f"Key {key} đã hết hạn hoặc hết lượt sử dụng.")
                except Exception:
                    pass
                continue
            for chat_id, user_info in info["users"].items():
                if not user_info["predict_enabled"] or int(chat_id) not in active_chats:
                    continue
                if not check_data_sufficiency(int(chat_id)):
                    continue
                try:
                    analysis_msg = bot.send_message(
                        int(chat_id),
                        "🤖 Bot đang phân tích ..."
                    )
                    if prediction:
                        predictions[int(chat_id)] = predictions.get(int(chat_id), [])
                        predictions[int(chat_id)].append({"Phien": data["Phien"] + 1, "Prediction": prediction, "WinRate": win_rate, "Actual": None})
                        bot.send_message(
                            int(chat_id),
                            f"🎲 Phiên: {data['Phien'] + 1}\n"
                            f"🔔 Dự đoán: {prediction}\n"
                            f"📈 Xác suất: {win_rate}%"
                        )
                    time.sleep(1)
                    bot.edit_message_text(
                        chat_id=int(chat_id),
                        message_id=analysis_msg.message_id,
                        text="⏳ Vui lòng chờ kết quả ..."
                    )
                    current_pred = next((p for p in predictions[int(chat_id)] if p["Phien"] == data["Phien"]), None)
                    if current_pred:
                        current_pred["Actual"] = data["Ket_qua"]
                        result = "🏆 Chiến thắng" if current_pred["Prediction"] == data["Ket_qua"] else "😢 Thua"
                        bot.edit_message_text(
                            chat_id=int(chat_id),
                            message_id=analysis_msg.message_id,
                            text=(
                                f"🎰 Phiên: {data['Phien']}\n"
                                f"📣 Kết quả\n"
                                f"🎲 Xúc xắc: {data['Xuc_xac_1']}️⃣ {data['Xuc_xac_2']}️⃣ {data['Xuc_xac_3']}️⃣\n"
                                f"🔢 Tổng: {data['Tong']}\n"
                                f"🏆 Kết quả: {data['Ket_qua']}\n"
                                f"📌 Dự đoán: {current_pred['Prediction']} ({result})"
                            )
                        )
                except Exception as e:
                    print(f"Failed to send private signal to {chat_id}: {e}")

    except json.JSONDecodeError:
        print(f"Failed to decode message: {message}")

def on_error(ws, error):
    print(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed")

def on_open(ws):
    print("WebSocket connected")

def run_websocket():
    while True:
        ws = websocket.WebSocketApp(WS_URL,
                                    on_open=on_open,
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close)
        ws.run_forever()
        print("Reconnecting WebSocket...")
        time.sleep(5)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        if call.data.startswith("copy_key:"):
            key = call.data.split(":")[1]
            if key in keys:
                bot.answer_callback_query(call.id, key, show_alert=True)
            else:
                bot.answer_callback_query(call.id, "Key không tồn tại!", show_alert=True)
        elif call.data.startswith("enable_predict:"):
            key = call.data.split(":")[1]
            if not key or key not in keys:
                bot.answer_callback_query(call.id, "Key không hợp lệ hoặc đã hết hạn!", show_alert=True)
                return
            chat_id = str(call.from_user.id)
            if chat_id not in keys[key]["users"]:
                bot.answer_callback_query(call.id, "Bạn không có quyền điều khiển key này!", show_alert=True)
                return
            keys[key]["users"][chat_id]["predict_enabled"] = True
            save_keys()
            bot.answer_callback_query(call.id, "Đã bật dự đoán!")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=call.message.text,
                reply_markup=create_predict_buttons(key, chat_id)
            )
            if not check_data_sufficiency(int(chat_id)):
                return
            bot.send_message(int(chat_id), "✅ Dự đoán đã được bật và sẽ bắt đầu khi đủ dữ liệu.")
        elif call.data.startswith("disable_predict:"):
            key = call.data.split(":")[1]
            if not key or key not in keys:
                bot.answer_callback_query(call.id, "Key không hợp lệ hoặc đã hết hạn!", show_alert=True)
                return
            chat_id = str(call.from_user.id)
            if chat_id not in keys[key]["users"]:
                bot.answer_callback_query(call.id, "Bạn không có quyền điều khiển key này!", show_alert=True)
                return
            keys[key]["users"][chat_id]["predict_enabled"] = False
            save_keys()
            bot.answer_callback_query(call.id, "Đã tắt dự đoán!")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=call.message.text,
                reply_markup=create_predict_buttons(key, chat_id)
            )
    except Exception as e:
        print(f"Error in callback_query: {e}")
        bot.answer_callback_query(call.id, "Lỗi khi xử lý nút, vui lòng thử lại!", show_alert=True)

def create_predict_buttons(key, chat_id):
    markup = InlineKeyboardMarkup()
    predict_enabled = keys[key]["users"][chat_id]["predict_enabled"]
    enable_button = InlineKeyboardButton(
        "✅ Bật dự đoán" if not predict_enabled else "🔄 Bật dự đoán (Đang bật)",
        callback_data=f"enable_predict:{key}"
    )
    disable_button = InlineKeyboardButton(
        "⛔ Tắt dự đoán" if predict_enabled else "🔄 Tắt dự đoán (Đang tắt)",
        callback_data=f"disable_predict:{key}"
    )
    markup.add(enable_button, disable_button)
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id in banned_groups or user_id in banned_users:
        bot.send_message(chat_id, "Bot không hoạt động trong nhóm/người dùng này.")
        return
    if chat_id < 0:
        groups.add(chat_id)
    else:
        users.add(user_id)
    save_all()
    subscribed_chats.add(chat_id)
    active_chats.add(chat_id)
    if chat_id not in predictions:
        predictions[chat_id] = []
    bot.send_message(
        chat_id, 
        "🤖 Xin chào! Đây là bot dự đoán tài xỉu tự động.\n"
        "Để sử dụng bot, vui lòng liên hệ admin: t.me/hknamip\n"
        "Để xem các lệnh, hãy dùng /help\n"
        "📌 Dùng /startbot để chạy bot và /stopbot để tắt bot."
    )

@bot.message_handler(commands=['startbot'])
def startbot_cmd(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id in banned_groups or user_id in banned_users:
        bot.reply_to(message, "Bot không hoạt động trong nhóm/người dùng này.")
        return
    if chat_id not in subscribed_chats:
        bot.reply_to(message, "Vui lòng dùng /start trước!")
        return
    active_chats.add(chat_id)
    save_all()
    bot.reply_to(message, "✅ Bot đã được kích hoạt!")

@bot.message_handler(commands=['stopbot'])
def stopbot_cmd(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id in banned_groups or user_id in banned_users:
        bot.reply_to(message, "Bot không hoạt động trong nhóm/người dùng này.")
        return
    if chat_id not in subscribed_chats:
        bot.reply_to(message, "Vui lòng dùng /start trước!")
        return
    active_chats.discard(chat_id)
    save_all()
    bot.reply_to(message, "⛔ Bot đã được tắt!")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    user_id = message.from_user.id
    if user_id in admins or user_id == ADMIN_ID:
        bot.reply_to(message,
            "📜 Danh sách lệnh:\n"
            "/start - Khởi động bot\n"
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
            "/startbot - Chạy bot\n"
            "/stopbot - Tắt bot\n"
        )
    else:
        bot.reply_to(message,
            "📜 Danh sách lệnh:\n"
            "/start - Khởi động bot\n"
            "/help - Xem hướng dẫn\n"
            "/key <key> - Nhập key để nhận tín hiệu riêng\n"
            "/lichsu <số_ván> - Xem lịch sử X ván gần nhất\n"
            "/startbot - Chạy bot\n"
            "/stopbot - Tắt bot\n"
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
            if keys[key]["uses"] <= 0:
                bot.reply_to(message, "Key này đã hết lượt sử dụng!")
                return
            chat_id_str = str(user_id)
            if chat_id_str in keys[key]["users"]:
                bot.reply_to(message, "Bạn đã kích hoạt key này trước đó!")
                return
            keys[key]["uses"] -= 1
            if not keys[key].get("expiry"):
                keys[key]["expiry"] = time.time() + keys[key]["duration"]
            keys[key]["users"][chat_id_str] = {"predict_enabled": True}
            save_keys()
            seconds_left = int(keys[key]['expiry'] - time.time())
            if seconds_left < 0: seconds_left = 0
            expire_time = datetime.fromtimestamp(keys[key]['expiry'])
            expire_str = expire_time.strftime("%H:%M:%S %d-%m-%Y")
            bot.reply_to(
                message,
                f"✅ Key {key} đã được kích hoạt!\n"
                f"⏰ Thời gian còn lại: {str(timedelta(seconds=seconds_left))} (hết hạn lúc: {expire_str})\n"
                f"📌 Sử dụng các nút dưới đây để bật/tắt dự đoán riêng:",
                reply_markup=create_predict_buttons(key, chat_id_str)
            )
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
            check_data_sufficiency(chat_id)
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
            "uses": uses,
            "duration": duration,
            "expiry": None,
            "users": {}
        }
        save_keys()
        markup = InlineKeyboardMarkup()
        copy_button = InlineKeyboardButton("📋 Sao chép key", callback_data=f"copy_key:{key}")
        markup.add(copy_button)
        bot.reply_to(
            message,
            f"🔑 Key mới đã được tạo!\nKey: `{key}`\n🔄 Số người có thể nhập: {uses}\n⏰ Thời gian hiệu lực: {duration} giây",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception:
        bot.reply_to(message, "Cú pháp: /taokey <số_người> <thời_gian_giây>")

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
        expiry_str = "Chưa kích hoạt" if not v.get("expiry") else f"{int(v['expiry']-time.time())}s"
        msg += f"Key: {k} | Số người còn lại: {v['uses']} | Hết hạn: {expiry_str}\n"
        msg += "Người dùng:\n"
        for chat_id, user_info in v["users"].items():
            msg += f"  - ID: {chat_id} | Dự đoán: {'Bật' if user_info['predict_enabled'] else 'Tắt'}\n"
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
    if not content:
        bot.reply_to(message, "Vui lòng nhập nội dung thông báo!")
        return
    sent_messages = []
    for uid in users:
        try:
            msg = bot.send_message(uid, f"📢 Thông báo admin: {content}")
            sent_messages.append((uid, msg.message_id))
        except Exception:
            pass
    for gid in groups:
        try:
            msg = bot.send_message(gid, f"📢 Thông báo admin: {content}")
            sent_messages.append((gid, msg.message_id))
        except Exception:
            pass
    bot.reply_to(message, "Đã gửi thông báo.")
    return sent_messages

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
    try:
        bot.send_message(uid, f"📢 Thông báo riêng admin: {content}")
        bot.reply_to(message, f"Đã gửi cho {uid}")
    except Exception:
        bot.reply_to(message, "Không thể gửi thông báo cho user này.")

@bot.message_handler(commands=['xoatb'])
def xoatb_cmd(message):
    if not (message.from_user.id in admins or message.from_user.id == ADMIN_ID):
        bot.reply_to(message, "Bạn không có quyền sử dụng lệnh này.")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "Bạn cần reply vào thông báo cần xoá.")
        return
    content = message.reply_to_message.text
    if not content.startswith("📢 Thông báo admin:"):
        bot.reply_to(message, "Vui lòng reply vào một thông báo admin!")
        return
    deleted_count = 0
    for uid in users:
        try:
            for msg_id in range(message.reply_to_message.message_id - 100, message.reply_to_message.message_id + 100):
                bot.delete_message(uid, msg_id)
                deleted_count += 1
        except Exception:
            pass
    for gid in groups:
        try:
            for msg_id in range(message.reply_to_message.message_id - 100, message.reply_to_message.message_id + 100):
                bot.delete_message(gid, msg_id)
                deleted_count += 1
        except Exception:
            pass
    bot.reply_to(message, f"Đã xoá {deleted_count} thông báo tương ứng.")

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

load_history()
load_keys()
load_all()
websocket_thread = threading.Thread(target=run_websocket)
websocket_thread.start()

bot.infinity_polling()
