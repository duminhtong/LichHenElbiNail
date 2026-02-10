import os
import asyncio
import httpx
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ============== CẤU HÌNH ==============
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8353404370:AAE8llS0H1SYvbQWMMr5g8QApDVZr9PjBUI")
LARK_APP_ID = os.getenv("LARK_APP_ID", "cli_a900530757b81ed0")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET", "EbhapkJ5kCK3ITEdSqv0igWiTTorBO2d")
LARK_BASE_ID = os.getenv("LARK_BASE_ID", "CaGqbAAZOa8hcDs7aYJlmR3cg0b")
LARK_TABLE_ID = os.getenv("LARK_TABLE_ID", "tblMjyHrFu553lEg")

BRANCHES = {
    "rs": "Rạch Sỏi",
    "rg": "Rạch Giá"
}

BOOK_DATE, BOOK_TIME, BOOK_BRANCH, BOOK_NAME, BOOK_PHONE, BOOK_PEOPLE, BOOK_NOTE, BOOK_CONFIRM = range(8)

# ============== LARK API ==============
class LarkAPI:
    def __init__(self):
        self.app_id = LARK_APP_ID
        self.app_secret = LARK_APP_SECRET
        self.base_id = LARK_BASE_ID
        self.table_id = LARK_TABLE_ID
        self.access_token = None
        self.token_expires = None
    
    async def get_access_token(self):
        if self.access_token and self.token_expires and datetime.now() < self.token_expires:
            return self.access_token
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret}
            )
            data = response.json()
            if data.get("code") == 0:
                self.access_token = data["tenant_access_token"]
                self.token_expires = datetime.now() + timedelta(seconds=data.get("expire", 7200) - 300)
                return self.access_token
            return None
    
    async def get_headers(self):
        token = await self.get_access_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    async def get_appointments(self, date_str: str, branch: str = None):
        headers = await self.get_headers()
        try:
            if "/" in date_str:
                parts = date_str.split("/")
                day = int(parts[0])
                month = int(parts[1])
                year = int(parts[2]) if len(parts) > 2 else datetime.now().year
                date_obj = datetime(year, month, day)
            else:
                date_obj = datetime.strptime(date_str, "%d-%m-%Y")
        except:
            return []
        
        url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{self.base_id}/tables/{self.table_id}/records"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params={"page_size": 500})
            data = response.json()
            if data.get("code") != 0: return []
            
            items = data.get("data", {}).get("items", [])
            filtered_items = []
            for item in items:
                fields = item.get("fields", {})
                ngay_hen = fields.get("Ngày hẹn")
                if not ngay_hen: continue
                
                # SỬA LỖI MÚI GIỜ: Cộng 7 tiếng cho đúng giờ VN
                item_date = datetime.fromtimestamp((ngay_hen / 1000) + (7 * 3600))
                
                if item_date.date() == date_obj.date():
                    if branch:
                        branch_name = BRANCHES.get(branch.lower(), branch)
                        chi_nhanh = str(fields.get("Chi nhánh", ""))
                        if branch_name.lower() not in chi_nhanh.lower():
                            continue
                    filtered_items.append(item)
            return filtered_items

    async def add_appointment(self, data: dict):
        headers = await self.get_headers()
        try:
            # Chuẩn hóa ngày về 00:00 GMT+7
            d = datetime.strptime(data["date"], "%d/%m/%Y" if "/" in data["date"] else "%d-%m-%Y")
            d = d.replace(hour=0, minute=0, second=0, microsecond=0)
            # Lark lưu UTC, nên 00:00 VN = 17:00 ngày hôm trước UTC
            ts = int((d - timedelta(hours=7)).timestamp() * 1000)
            
            fields = {
                "Ngày hẹn": ts,
                "Giờ hẹn": data["time"],
                "Chi nhánh": data["branch"],
                "Tên khách": data["name"],
                "SĐT": data.get("phone", ""),
                "Số người": str(data.get("people", "1")),
                "Ghi chú": data.get("note", ""),
                "Trạng thái": "Chờ"
            }
            url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{self.base_id}/tables/{self.table_id}/records"
            async with httpx.AsyncClient() as client:
                res = await client.post(url, headers=headers, json={"fields": fields})
                return res.json().get("code") == 0
        except:
            return False

lark = LarkAPI()

# ============== HANDLERS ==============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏪 **MANNER NAILBOX**\n\n/check [ngày] [rs/rg] - Xem lịch\n/today - Hôm nay\n/book - Đặt lịch mới", parse_mode="Markdown")

async def check_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Gõ theo cú pháp: `/check 11/2` hoặc `/check 11/2 rs`", parse_mode="Markdown")
        return
    
    date_str = context.args[0]
    branch = context.args[1] if len(context.args) > 1 else None
    msg = await update.message.reply_text(f"⏳ Đang kiểm tra lịch ngày {date_str}...")
    
    appointments = await lark.get_appointments(date_str, branch)
    
    if not appointments:
        await msg.edit_text(f"📅 **Lịch ngày {date_str}:**\n✅ Trống, chưa có khách đặt.", parse_mode="Markdown")
        return

    # Sắp xếp theo giờ hẹn
    appointments.sort(key=lambda x: x["fields"].get("Giờ hẹn", "00:00"))
    
    res = f"📅 **Lịch ngày {date_str}:**\n"
    for apt in appointments:
        f = apt["fields"]
        res += f"• `{f.get('Giờ hẹn')}`: {f.get('Tên khách')} ({f.get('Chi nhánh')})\n"
    
    await msg.edit_text(res, parse_mode="Markdown")

async def today_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.args = [datetime.now().strftime("%d/%m")]
    await check_schedule(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Đã hủy thao tác.")
    return ConversationHandler.END

# ============== CẤU HÌNH BOT ==============
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_schedule))
    app.add_handler(CommandHandler("today", today_schedule))
    app.add_handler(CommandHandler("cancel", cancel))
    
    print("🤖 Bot Manner Nailbox đang khởi động...")
    app.run_polling()

if __name__ == "__main__":
    main()
