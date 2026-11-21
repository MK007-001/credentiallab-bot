import csv
import io
import os
import re
import secrets
import sqlite3
import string
import time
import unicodedata
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "credentiallab.sqlite3")
MAX_PER_HOUR = 10
TEST_DOMAINS = ("example.com", "example.org", "example.net", "example.test")
SPECIALS = "!@#$%&*_-+="

# ---------- Storage ----------

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            amount INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            preview TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_history(user_id: int, kind: str, amount: int, preview: str):
    now = int(time.time())
    with db() as conn:
        recent = conn.execute(
            "SELECT COUNT(*) FROM history WHERE user_id=? AND created_at>=?",
            (user_id, now - 3600),
        ).fetchone()[0]
        if recent >= MAX_PER_HOUR:
            raise ValueError(
                f"Limite atingido: até {MAX_PER_HOUR} gerações por hora."
            )
        conn.execute(
            "INSERT INTO history(user_id,kind,amount,created_at,preview) VALUES(?,?,?,?,?)",
            (user_id, kind, amount, now, preview[:120]),
        )
        conn.commit()


def get_history(user_id: int):
    with db() as conn:
        return conn.execute(
            """SELECT kind, amount, created_at, preview
               FROM history WHERE user_id=?
               ORDER BY id DESC LIMIT 10""",
            (user_id,),
        ).fetchall()


# ---------- Generators ----------

def clean_theme(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9._-]", "", value).strip("._-")
    if not value:
        raise ValueError("Use pelo menos uma letra ou número no tema.")
    return value.lower()[:24]


def generate_test_emails(theme: str, quantity: int, domain: str):
    if domain not in TEST_DOMAINS:
        raise ValueError("Escolha um domínio reservado para testes.")
    if not 1 <= quantity <= 200:
        raise ValueError("A quantidade deve ficar entre 1 e 200.")
    prefix = clean_theme(theme)
    return [f"{prefix}{i:03d}@{domain}" for i in range(1, quantity + 1)]


def make_password():
    # Gera uma senha aleatória independente; não transforma senhas existentes.
    alphabet = string.ascii_letters + string.digits + SPECIALS
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(20))
        if (
            any(c.islower() for c in value)
            and any(c.isupper() for c in value)
            and any(c.isdigit() for c in value)
            and any(c in SPECIALS for c in value)
        ):
            return value


def generate_test_passwords(quantity: int):
    if not 1 <= quantity <= 200:
        raise ValueError("A quantidade deve ficar entre 1 e 200.")
    return [make_password() for _ in range(quantity)]


def make_file(rows, kind: str, fmt: str):
    stream = io.StringIO()
    if fmt == "csv":
        writer = csv.writer(stream)
        writer.writerow(["tipo", "valor"])
        for item in rows:
            writer.writerow([kind, item])
        filename = f"credentiallab_{kind}.csv"
    else:
        stream.write("\n".join(rows))
        filename = f"credentiallab_{kind}.txt"

    data = io.BytesIO(stream.getvalue().encode("utf-8"))
    data.name = filename
    data.seek(0)
    return data


# ---------- Telegram UI ----------

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📧 E-mails fictícios", callback_data="emails")],
        [InlineKeyboardButton("🔐 Senhas aleatórias de teste", callback_data="passwords")],
        [
            InlineKeyboardButton("🕘 Histórico", callback_data="history"),
            InlineKeyboardButton("⚙️ Configurações", callback_data="settings"),
        ],
        [InlineKeyboardButton("❓ Ajuda", callback_data="help")],
    ])


def domains_keyboard():
    buttons = [
        [InlineKeyboardButton(f"@{d}", callback_data=f"domain:{d}")]
        for d in TEST_DOMAINS
    ]
    buttons.append([InlineKeyboardButton("⬅️ Menu", callback_data="home")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.effective_message.reply_text(
        "🧪 CREDENTIALLAB\n\n"
        "Gerador de dados sintéticos para desenvolvimento e testes autorizados.\n"
        "Escolha uma ferramenta:",
        reply_markup=main_keyboard(),
    )


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    # Preserve the pending email settings when the user chooses a domain.
    if not action.startswith("domain:"):
        context.user_data.clear()

    if action == "home":
        await query.message.reply_text("Menu principal:", reply_markup=main_keyboard())

    elif action == "emails":
        context.user_data["mode"] = "email_theme"
        await query.message.reply_text(
            "Digite um tema para identificar os endereços fictícios.\n"
            "Exemplo: projetoqa"
        )

    elif action == "passwords":
        context.user_data["mode"] = "password_quantity"
        await query.message.reply_text(
            "Quantas senhas aleatórias de teste deseja gerar? (1 a 200)"
        )

    elif action == "history":
        rows = get_history(update.effective_user.id)
        if not rows:
            msg = "Ainda não há gerações no seu histórico."
        else:
            lines = ["🕘 Últimas gerações:"]
            for kind, amount, created, preview in rows:
                stamp = datetime.fromtimestamp(created, timezone.utc).strftime("%d/%m %H:%M UTC")
                lines.append(f"• {stamp} — {kind}: {amount} item(ns) — {preview}")
            msg = "\n".join(lines)
        await query.message.reply_text(msg, reply_markup=main_keyboard())

    elif action == "settings":
        await query.message.reply_text(
            "⚙️ Configurações atuais\n"
            "• Idioma: português (Brasil)\n"
            "• Limite: 200 itens por geração\n"
            f"• Limite de uso: {MAX_PER_HOUR} gerações por hora\n"
            "• Domínios: somente domínios reservados para testes.",
            reply_markup=main_keyboard(),
        )

    elif action == "help":
        await query.message.reply_text(
            "❓ Ajuda\n\n"
            "E-mails: escolha um tema, quantidade e domínio reservado.\n"
            "Senhas: são aleatórias e independentes, próprias para ambientes de teste.\n"
            "Os endereços não representam caixas postais reais e não são verificados.\n"
            "Comandos: /start e /cancel.",
            reply_markup=main_keyboard(),
        )

    elif action.startswith("domain:"):
        domain = action.split(":", 1)[1]
        theme = context.user_data.get("email_theme")
        quantity = context.user_data.get("email_quantity")
        # State is restored from a dedicated pending object because callbacks clear
        # the conversation mode only when a new top-level action is selected.
        pending = context.user_data.get("pending_email")
        if not pending:
            await query.message.reply_text(
                "A sessão expirou. Comece novamente com /start.",
                reply_markup=main_keyboard(),
            )
            return
        try:
            values = generate_test_emails(pending["theme"], pending["quantity"], domain)
            save_history(update.effective_user.id, "emails", len(values), values[0])
            await query.message.reply_document(
                document=make_file(values, "emails", "txt"),
                caption=f"📧 {len(values)} endereços sintéticos gerados em @{domain}.",
            )
            await query.message.reply_document(
                document=make_file(values, "emails", "csv"),
                caption="Versão CSV.",
            )
            await query.message.reply_text("O que deseja fazer agora?", reply_markup=main_keyboard())
        except ValueError as exc:
            await query.message.reply_text(str(exc), reply_markup=main_keyboard())


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    text = (update.effective_message.text or "").strip()

    if mode == "email_theme":
        try:
            theme = clean_theme(text)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        context.user_data["email_theme"] = theme
        context.user_data["mode"] = "email_quantity"
        await update.effective_message.reply_text("Quantos endereços deseja? (1 a 200)")
        return

    if mode == "email_quantity":
        if not text.isdigit() or not 1 <= int(text) <= 200:
            await update.effective_message.reply_text("Digite um número inteiro entre 1 e 200.")
            return
        context.user_data["email_quantity"] = int(text)
        context.user_data["pending_email"] = {
            "theme": context.user_data["email_theme"],
            "quantity": int(text),
        }
        context.user_data["mode"] = None
        await update.effective_message.reply_text(
            "Escolha um domínio reservado para testes:",
            reply_markup=domains_keyboard(),
        )
        return

    if mode == "password_quantity":
        if not text.isdigit() or not 1 <= int(text) <= 200:
            await update.effective_message.reply_text("Digite um número inteiro entre 1 e 200.")
            return
        try:
            values = generate_test_passwords(int(text))
            save_history(update.effective_user.id, "senhas-teste", len(values), "senha aleatória")
            await update.effective_message.reply_document(
                document=make_file(values, "senhas_teste", "txt"),
                caption=f"🔐 {len(values)} senhas aleatórias de teste.",
            )
            await update.effective_message.reply_document(
                document=make_file(values, "senhas_teste", "csv"),
                caption="Versão CSV.",
            )
            context.user_data.clear()
            await update.effective_message.reply_text("O que deseja fazer agora?", reply_markup=main_keyboard())
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
        return

    await update.effective_message.reply_text(
        "Use os botões do menu ou envie /start.",
        reply_markup=main_keyboard(),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.effective_message.reply_text(
        "Operação cancelada.",
        reply_markup=main_keyboard(),
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    # Não registra tokens nem conteúdo sensível em logs públicos.
    print(f"Erro no processamento: {type(context.error).__name__}")


def main():
    if not TOKEN:
        raise RuntimeError("Defina TELEGRAM_BOT_TOKEN nas variáveis de ambiente.")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(error_handler)

    # Render Web Service: Telegram chama o webhook quando chegam atualizações.
    port = int(os.getenv("PORT", "10000"))
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    webhook_path = os.getenv("WEBHOOK_PATH", "credentiallab-webhook")
    webhook_secret = os.getenv("WEBHOOK_SECRET")

    if render_url:
        if not webhook_secret:
            raise RuntimeError("Defina WEBHOOK_SECRET nas variáveis de ambiente.")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=webhook_path,
            webhook_url=f"{render_url}/{webhook_path}",
            secret_token=webhook_secret,
            drop_pending_updates=True,
        )
    else:
        # Execução local para testes.
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
