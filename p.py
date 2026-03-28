import os
import json
import datetime
import random
import time
import threading

import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError

# ------------------------------------------------------------
# 1. Konfigurace a data
# ------------------------------------------------------------
TOKEN = "8514852844:AAFP5pYdkbOFIieo3oGEvhM3sDGJX7yVKKY"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
scheduler = BackgroundScheduler(timezone="UTC")

DATA_FILE = "user_data.json"

# Emoji pro hotové/nehotové kroky
DONE_EMOJI = "💧"      # kapka
NOT_DONE_EMOJI = "🌿"  # list

# Individuální časovače pro každý produkt (v sekundách) – upraveno pro lepší vstřebávání
PRODUCT_TIMERS = {
    "Dove Men+Care Face Wash Oil-Control": 0,          # čištění – ihned další krok
    "Mixa Purifying Lotion": 30,                       # tonikum – 30 s
    "Balea Beauty Expert Peptide Serum": 90,           # sérum – 1,5 min
    "Balea Hautrein Anti-Pickel 24h-Pflege": 90,       # krém – 1,5 min
    "SPF 50": 0,                                       # SPF – ihned
    "Balea 3in1 Reinigung, Peeling & Maske": 240,      # maska – 4 min
    "Balea Peel-Off Maske Aktivkohle": 600,            # peel‑off – 10 min
}

# Produkty a jejich vysvětlení
PRODUCTS = {
    "Dove Men+Care Face Wash Oil-Control": {
        "explanation": "<b>Dove Men+Care Face Wash Oil-Control</b> – obsahuje aktivní uhlí a zinek, které pomáhají regulovat tvorbu mazu a zabraňují ucpávání pórů. Jemně čistí bez vysušování."
    },
    "Mixa Purifying Lotion": {
        "explanation": "<b>Mixa Purifying Lotion</b> – tonikum s kyselinou salicylovou a zinkem. Stahuje póry, zklidňuje podráždění a připravuje pleť na následnou péči."
    },
    "Balea Beauty Expert Peptide Serum": {
        "explanation": "<b>Balea Beauty Expert Peptide Serum</b> – koncentrované sérum s peptidy a kyselinou hyaluronovou. Vyhlazuje jemné linky, podporuje regeneraci a hydratuje."
    },
    "Balea Hautrein Anti-Pickel 24h-Pflege": {
        "explanation": "<b>Balea Hautrein Anti-Pickel 24h-Pflege</b> – krém s kyselinou salicylovou a niacinamidem. Redukuje pupínky, zklidňuje zarudnutí a působí protizánětlivě po celý den."
    },
    "SPF 50": {
        "explanation": "<b>SPF 50</b> – širokospektrální ochrana proti UVA a UVB záření. Zabraňuje předčasnému stárnutí, pigmentovým skvrnám a chrání před slunečním poškozením."
    },
    "Balea 3in1 Reinigung, Peeling & Maske": {
        "explanation": "<b>Balea 3in1 Reinigung, Peeling & Maske</b> – multifunkční produkt s jemnými peelingovými částicemi a jílem. Hloubkově čistí, odstraňuje odumřelé buňky a funguje jako detoxikační maska."
    },
    "Balea Peel-Off Maske Aktivkohle": {
        "explanation": "<b>Balea Peel-Off Maske Aktivkohle</b> – maska s aktivním uhlím, která vytáhne nečistoty z pórů, zmatní pleť a zanechá ji svěží. Používejte max. 2× týdně."
    }
}

MORNING_STEPS = [
    "Dove Men+Care Face Wash Oil-Control",
    "Mixa Purifying Lotion",
    "Balea Beauty Expert Peptide Serum",
    "Balea Hautrein Anti-Pickel 24h-Pflege",
    "SPF 50"
]

EVENING_STEPS = [
    "Dove Men+Care Face Wash Oil-Control",
    "Mixa Purifying Lotion",
    "Balea Beauty Expert Peptide Serum",
    "Balea Hautrein Anti-Pickel 24h-Pflege",
    "Balea 3in1 Reinigung, Peeling & Maske",
    "Balea Peel-Off Maske Aktivkohle"
]

PEEL_OFF_INDEX = 5  # Balea Peel-Off Maske Aktivkohle

# ------------------------------------------------------------
# 2. Správa uživatelských dat
# ------------------------------------------------------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_data = load_data()

def get_user(user_id):
    uid = str(user_id)
    if uid not in user_data:
        user_data[uid] = {
            "morning": [False] * len(MORNING_STEPS),
            "evening": [False] * len(EVENING_STEPS),
            "last_peel_off": None,
            "history": {},
            "morning_msg_id": None,
            "evening_msg_id": None,
            "ai_msg_id": None,
            "ai_chat_id": None,
            "countdown_msg_id": None
        }
        save_data(user_data)
    return user_data[uid]

def update_user(user_id, data):
    uid = str(user_id)
    user_data[uid].update(data)
    save_data(user_data)

def update_history_for_day(user_id, date):
    uid = str(user_id)
    u = get_user(user_id)
    morning_done = sum(u["morning"])
    evening_done = sum(u["evening"])
    total = morning_done + evening_done
    date_str = date.isoformat()
    u["history"][date_str] = total
    save_data(user_data)

def calculate_streak_and_average(user_id):
    u = get_user(user_id)
    history = u["history"]
    if not history:
        return 0, 0.0
    sorted_dates = sorted(history.keys(), reverse=True)
    streak = 0
    for date_str in sorted_dates:
        if history[date_str] > 0:
            streak += 1
        else:
            break
    last_7 = []
    for date_str in sorted_dates[:7]:
        last_7.append(history[date_str])
    avg = sum(last_7) / len(last_7) if last_7 else 0.0
    return streak, avg

# ------------------------------------------------------------
# 3. Správa odpočtů (countdown) – samostatná zpráva, spolehlivé ukončení
# ------------------------------------------------------------
active_countdowns = {}  # user_id -> {"end_time": float, "job_id": str, "msg_id": int}

def delete_countdown_message(user_id, chat_id):
    """Smaže zprávu s odpočtem, pokud existuje."""
    u = get_user(user_id)
    msg_id = u.get("countdown_msg_id")
    if msg_id:
        try:
            bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
        update_user(user_id, {"countdown_msg_id": None})

def update_countdown_message(user_id, chat_id, end_time):
    """Upraví nebo pošle zprávu s odpočtem."""
    remaining = end_time - time.time()
    if remaining <= 0:
        # Čas vypršel – ukončíme odpočet
        finish_countdown(user_id, chat_id)
        return

    minutes = int(remaining // 60)
    seconds = int(remaining % 60)
    time_str = f"{minutes}:{seconds:02d}" if minutes > 0 else f"{seconds} s"
    text = f"⏳ <b>Další krok za {time_str}</b>"

    u = get_user(user_id)
    msg_id = u.get("countdown_msg_id")
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, parse_mode="HTML")
        except Exception:
            # Pokud editace selže, pošleme novou
            msg = bot.send_message(chat_id, text, parse_mode="HTML")
            update_user(user_id, {"countdown_msg_id": msg.message_id})
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML")
        update_user(user_id, {"countdown_msg_id": msg.message_id})

def finish_countdown(user_id, chat_id):
    """Ukončí odpočet, smaže zprávu a pošle upozornění."""
    if user_id in active_countdowns:
        job_id = active_countdowns[user_id].get("job_id")
        if job_id:
            try:
                scheduler.remove_job(job_id)
            except JobLookupError:
                pass
        del active_countdowns[user_id]

    delete_countdown_message(user_id, chat_id)
    bot.send_message(chat_id, "⏰ <b>Čas na další krok!</b>", parse_mode="HTML")

def start_countdown(user_id, chat_id, duration_seconds):
    """Spustí odpočet v samostatné zprávě."""
    # Zrušíme předchozí odpočet
    cancel_countdown(user_id, chat_id)

    if duration_seconds <= 0:
        # Pokud je čas 0, rovnou pošleme upozornění
        bot.send_message(chat_id, "⏰ <b>Čas na další krok!</b>", parse_mode="HTML")
        return

    end_time = time.time() + duration_seconds

    # Naplánujeme periodickou aktualizaci každých 10 sekund
    job = scheduler.add_job(
        update_countdown_message,
        'interval',
        seconds=10,
        args=[user_id, chat_id, end_time],
        id=f"countdown_{user_id}"
    )

    active_countdowns[user_id] = {
        "end_time": end_time,
        "job_id": job.id
    }

    # Okamžitě zobrazíme první odpočet
    update_countdown_message(user_id, chat_id, end_time)

def cancel_countdown(user_id, chat_id):
    """Zruší běžící odpočet a smaže jeho zprávu."""
    if user_id in active_countdowns:
        job_id = active_countdowns[user_id].get("job_id")
        if job_id:
            try:
                scheduler.remove_job(job_id)
            except JobLookupError:
                pass
        del active_countdowns[user_id]
    delete_countdown_message(user_id, chat_id)

# ------------------------------------------------------------
# 4. Klávesnice a pomocné funkce
# ------------------------------------------------------------
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton("🌅 Ranní rutina"),
        KeyboardButton("🌙 Večerní rutina"),
        KeyboardButton("♨️ Spustit páru"),
        KeyboardButton("📊 Pokrok"),
        KeyboardButton("❌ Zrušit vše")
    ]
    keyboard.add(*buttons)
    return keyboard

def get_routine_inline_keyboard(routine_type, steps_done):
    markup = InlineKeyboardMarkup(row_width=1)
    steps = MORNING_STEPS if routine_type == "ranni" else EVENING_STEPS
    for i, step in enumerate(steps):
        status = f"{DONE_EMOJI} " if steps_done[i] else f"{NOT_DONE_EMOJI} "
        callback_data = f"toggle:{routine_type}:{i}"
        markup.add(InlineKeyboardButton(f"{status}{step}", callback_data=callback_data))
    return markup

def format_routine_message(routine_type, steps_done):
    steps = MORNING_STEPS if routine_type == "ranni" else EVENING_STEPS
    if routine_type == "ranni":
        header = "🌅 Ranní rutina – klikni pro označení/odznačení:"
    else:
        header = "🌙 Večerní rutina – klikni pro označení/odznačení:"

    lines = [header]
    for i, step in enumerate(steps):
        mark = DONE_EMOJI if steps_done[i] else NOT_DONE_EMOJI
        lines.append(f"{mark} {step}")
    return "\n".join(lines)

def get_product_explanation(product_name):
    return PRODUCTS.get(product_name, {}).get("explanation", "")

def get_smart_ai_feedback(total_done, total_possible):
    percent = total_done / total_possible if total_possible else 0
    if percent == 1.0:
        templates = [
            "🎉 Fantastický výkon! Dokončili jste vše. Vaše pleť vám děkuje!",
            "🌟 Perfektní! Jste vzorný pečovatel. Takto se pleť rychle zlepšuje.",
            "💪 Mistrovský výkon! Všechny kroky hotové. Udržujte si toto tempo."
        ]
    elif percent >= 0.8:
        templates = [
            "👍 Skvělá práce, už jste skoro hotovi! Zbývá už jen pár kroků.",
            "🚀 Výborně, jste na dobré cestě. Doplňte poslední kroky a bude to dokonalé.",
            "🌞 Těsně před cílem! Doplňte zbývající produkty a pleť zazáří."
        ]
    elif percent >= 0.5:
        templates = [
            "💪 Držte se, půlka je za vámi. Každý krok se počítá!",
            "🧴 Dobrá práce. Zkuste přidat ještě pár kroků pro maximální účinek.",
            "🌿 Hezký pokrok. Pleť už cítí vaši péči."
        ]
    elif percent >= 0.2:
        templates = [
            "🌱 Každý krok je důležitý. Dnes máte pěkný základ, můžete přidat další.",
            "📈 Začátek je vždycky těžký, ale už jste se rozjeli!",
            "💧 I malá péče se počítá. Zkuste zítra přidat jeden krok navíc."
        ]
    else:
        templates = [
            "🌟 Začněte s prvními kroky. I jedno umytí obličeje dělá rozdíl.",
            "🕊️ Nebojte se začít. Zkuste dnes alespoň základní péči.",
            "🌙 Malé krůčky vedou k velké změně. Vezměte to hezky postupně."
        ]
    base = random.choice(templates)
    if random.random() < 0.3 and total_done < total_possible:
        advice = "\n💡 <i>Tip:</i> Pokud nemáte čas, stačí čistění a hydratace. Hlavní je pravidelnost."
        base += advice
    return base

def update_ai_message(chat_id, user_id, total_done, total_possible):
    """Aktualizuje hlavní AI zprávu (motivace + počet kroků)."""
    u = get_user(user_id)
    feedback = get_smart_ai_feedback(total_done, total_possible)
    text = f"<b>Mini AI:</b> {feedback}\n\n<b>Dnes hotovo:</b> {total_done} kroků"

    if u.get("ai_msg_id") and u.get("ai_chat_id") == chat_id:
        try:
            bot.edit_message_text(text, chat_id, u["ai_msg_id"], parse_mode="HTML")
        except Exception:
            msg = bot.send_message(chat_id, text, parse_mode="HTML")
            u["ai_msg_id"] = msg.message_id
            u["ai_chat_id"] = chat_id
            update_user(user_id, {"ai_msg_id": msg.message_id, "ai_chat_id": chat_id})
    else:
        msg = bot.send_message(chat_id, text, parse_mode="HTML")
        u["ai_msg_id"] = msg.message_id
        u["ai_chat_id"] = chat_id
        update_user(user_id, {"ai_msg_id": msg.message_id, "ai_chat_id": chat_id})

def reset_all_steps(user_id, chat_id):
    u = get_user(user_id)
    u["morning"] = [False] * len(MORNING_STEPS)
    u["evening"] = [False] * len(EVENING_STEPS)
    today = datetime.date.today()
    update_history_for_day(user_id, today)

    if u.get("morning_msg_id"):
        try:
            new_text = format_routine_message("ranni", u["morning"])
            markup = get_routine_inline_keyboard("ranni", u["morning"])
            bot.edit_message_text(new_text, chat_id, u["morning_msg_id"], reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
    if u.get("evening_msg_id"):
        try:
            new_text = format_routine_message("vecerni", u["evening"])
            markup = get_routine_inline_keyboard("vecerni", u["evening"])
            bot.edit_message_text(new_text, chat_id, u["evening_msg_id"], reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass

    total_done = sum(u["morning"]) + sum(u["evening"])
    total_possible = len(MORNING_STEPS) + len(EVENING_STEPS)
    update_ai_message(chat_id, user_id, total_done, total_possible)

    update_user(user_id, {"morning": u["morning"], "evening": u["evening"]})

    # Zrušit případný odpočet
    cancel_countdown(user_id, chat_id)

def show_routine(chat_id, user_id, routine_type):
    u = get_user(user_id)
    steps_done = u["morning"] if routine_type == "ranni" else u["evening"]
    text = format_routine_message(routine_type, steps_done)
    markup = get_routine_inline_keyboard(routine_type, steps_done)

    if routine_type == "ranni" and u.get("morning_msg_id"):
        try:
            bot.edit_message_text(text, chat_id, u["morning_msg_id"], reply_markup=markup, parse_mode="HTML")
        except Exception:
            msg = bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
            update_user(user_id, {"morning_msg_id": msg.message_id})
    elif routine_type == "vecerni" and u.get("evening_msg_id"):
        try:
            bot.edit_message_text(text, chat_id, u["evening_msg_id"], reply_markup=markup, parse_mode="HTML")
        except Exception:
            msg = bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
            update_user(user_id, {"evening_msg_id": msg.message_id})
    else:
        msg = bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
        if routine_type == "ranni":
            update_user(user_id, {"morning_msg_id": msg.message_id})
        else:
            update_user(user_id, {"evening_msg_id": msg.message_id})

def is_routine_complete(user_id, routine_type):
    """Zkontroluje, zda je daná rutina kompletně hotová."""
    u = get_user(user_id)
    if routine_type == "ranni":
        return all(u["morning"])
    else:
        return all(u["evening"])

def send_completion_praise(chat_id, routine_type):
    """Pošle pochvalu za dokončení rutiny."""
    if routine_type == "ranni":
        praises = [
            "🌞 Skvělá práce! Ranní rutina je kompletní. Vaše pleť je připravená na nový den!",
            "✨ Výborně! Máte za sebou ranní péči. Užijte si svěží pleť po celý den.",
            "💪 Paráda! Ranní rutina hotová. Krásný den plný energie!",
            "🧴 Dokonalé! Vaše pleť dnes dostala tu nejlepší péči."
        ]
    else:
        praises = [
            "🌙 Fantastické! Večerní rutina je dokončena. Teď už jen odpočívejte a nechte pleť regenerovat.",
            "✨ Skvělá práce! Večerní péče hotová. Uvidíte zítra tu krásu!",
            "💪 Výborně! Máte za sebou kompletní večerní rutinu. Dobrou noc!",
            "🧴 Dokonalé! Vaše pleť vám děkuje za dnešní péči. Krásně se vyspěte."
        ]
    bot.send_message(chat_id, random.choice(praises), parse_mode="HTML")

# ------------------------------------------------------------
# 5. Handlery
# ------------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "🐾 Vítejte u <b>meowmeow's personal slave bot</b>! 🧴\n\n"
        "Tlačítky dole si zobrazíte rutinu, spustíte páru, zkontrolujete pokrok nebo vše zrušíte.\n"
        "Kliknutím na jednotlivé produkty je označíte jako hotové a dozvíte se, proč jsou prospěšné.\n\n"
        "Po označení kroku se objeví samostatná zpráva s odpočtem do dalšího kroku. "
        "Časy jsou nastaveny podle doby vstřebávání – u některých produktů (maska) je potřeba delší působení.\n\n"
        "⚠️ <b>Upozornění:</b> Nedoporučuje se nanášet produkty příliš rychle za sebou – "
        "mohou se špatně vstřebat nebo vzájemně reagovat (např. kyseliny a peptidy). "
        "Dodržujte prosím doporučené čekací doby.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    text = message.text
    chat_id = message.chat.id
    user_id = message.from_user.id

    if text == "🌅 Ranní rutina":
        show_routine(chat_id, user_id, "ranni")
    elif text == "🌙 Večerní rutina":
        show_routine(chat_id, user_id, "vecerni")
    elif text == "♨️ Spustit páru":
        bot.send_message(
            chat_id,
            "🔥 <b>Horká pára spuštěna!</b> 🌬️\n"
            "Posaďte se nad misku s horkou vodou (přes obličej ručník) na 5–10 minut.\n"
            "Pára otevře póry a připraví pleť na čištění.",
            parse_mode="HTML"
        )
    elif text == "📊 Pokrok":
        u = get_user(user_id)
        today = datetime.date.today()
        update_history_for_day(user_id, today)
        streak, avg = calculate_streak_and_average(user_id)
        today_done = u["history"].get(today.isoformat(), 0)
        pred_7 = avg * 7
        pred_14 = avg * 14
        msg = (
            f"<b>📊 Váš pokrok</b>\n\n"
            f"<b>Dnes hotovo:</b> {today_done} kroků\n"
            f"<b>Streak:</b> {streak} dní v řadě\n"
            f"<b>Průměr za posledních 7 dní:</b> {avg:.1f} kroků/den\n\n"
            f"<b>Odhad za 7 dní:</b> {pred_7:.0f} kroků\n"
            f"<b>Odhad za 14 dní:</b> {pred_14:.0f} kroků\n\n"
            f"💡 <i>Čím vyšší průměr, tím lépe se vaše pleť regeneruje a čistí.</i>"
        )
        bot.send_message(chat_id, msg, parse_mode="HTML")
    elif text == "❌ Zrušit vše":
        reset_all_steps(user_id, chat_id)
        bot.send_message(chat_id, "✅ Všechny dnešní kroky byly zrušeny.", reply_markup=get_main_keyboard())
    else:
        bot.send_message(
            chat_id,
            "Nerozumím. Použijte prosím tlačítka dole. 👇",
            reply_markup=get_main_keyboard()
        )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    data = call.data
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    message_id = call.message.message_id

    if data.startswith("toggle:"):
        _, routine_type, idx_str = data.split(":")
        idx = int(idx_str)
        u = get_user(user_id)

        if routine_type == "ranni":
            steps = MORNING_STEPS
            done_list = u["morning"]
        else:
            steps = EVENING_STEPS
            done_list = u["evening"]

        product_name = steps[idx]
        current_state = done_list[idx]

        # Speciální logika pro peel‑off masku
        if routine_type == "vecerni" and idx == PEEL_OFF_INDEX:
            last_peel = u.get("last_peel_off")
            today = datetime.date.today().isoformat()
            if last_peel:
                last_date = datetime.date.fromisoformat(last_peel)
                if (datetime.date.today() - last_date).days < 3:
                    bot.answer_callback_query(call.id, "❌ Dnes masku vynechte – použijte ji až za 3 dny.", show_alert=True)
                    return
                else:
                    u["last_peel_off"] = today
                    update_user(user_id, {"last_peel_off": today})
            else:
                u["last_peel_off"] = today
                update_user(user_id, {"last_peel_off": today})

        # Přepneme stav
        new_state = not current_state
        done_list[idx] = new_state
        update_user(user_id, {routine_type: done_list})

        # Aktualizujeme historii
        today = datetime.date.today()
        update_history_for_day(user_id, today)

        # Editujeme zprávu s rutinou
        new_text = format_routine_message(routine_type, done_list)
        markup = get_routine_inline_keyboard(routine_type, done_list)
        try:
            bot.edit_message_text(new_text, chat_id, message_id, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass

        # Vysvětlení produktu
        explanation = get_product_explanation(product_name)
        if explanation:
            bot.send_message(chat_id, explanation, parse_mode="HTML")

        # Aktualizujeme hlavní AI zprávu
        total_done = sum(u["morning"]) + sum(u["evening"])
        total_possible = len(MORNING_STEPS) + len(EVENING_STEPS)
        update_ai_message(chat_id, user_id, total_done, total_possible)

        # Rozhodnutí o odpočtu nebo pochvale
        if new_state:
            # Krok byl označen – zjistíme, zda je rutina nyní kompletní
            routine_complete = is_routine_complete(user_id, routine_type)
            if routine_complete:
                # Pokud je rutina hotová, pošleme pochvalu a nespouštíme odpočet
                send_completion_praise(chat_id, routine_type)
                # Zrušíme případný odpočet (např. pokud byl předtím spuštěn)
                cancel_countdown(user_id, chat_id)
            else:
                # Rutina není hotová – spustíme odpočet
                wait_time = PRODUCT_TIMERS.get(product_name, 60)
                start_countdown(user_id, chat_id, wait_time)
        else:
            # Krok byl odznačen – zrušíme odpočet
            cancel_countdown(user_id, chat_id)

        bot.answer_callback_query(call.id)

# ------------------------------------------------------------
# 6. Denní připomínky
# ------------------------------------------------------------
def send_morning_reminder():
    for uid, u in user_data.items():
        if sum(u.get("morning", [])) == 0:
            try:
                bot.send_message(
                    int(uid),
                    "🌅 Dobré ráno! Nezapomeňte na ranní skincare rutinu. Klepněte na 🌅 Ranní rutina a udělejte první krok.",
                    reply_markup=get_main_keyboard()
                )
            except Exception:
                pass

def send_evening_reminder():
    for uid, u in user_data.items():
        if sum(u.get("evening", [])) == 0:
            try:
                bot.send_message(
                    int(uid),
                    "🌙 Večer se blíží. Dopřejte pleti regeneraci a proveďte večerní rutinu. Stačí kliknout na 🌙 Večerní rutina.",
                    reply_markup=get_main_keyboard()
                )
            except Exception:
                pass

scheduler.add_job(send_morning_reminder, 'cron', hour=9, minute=0)
scheduler.add_job(send_evening_reminder, 'cron', hour=21, minute=0)
scheduler.start()

# ------------------------------------------------------------
# 7. Spuštění bota
# ------------------------------------------------------------
if __name__ == "__main__":
    print("Skincare Reminder Bot běží...")
    bot.infinity_polling()
