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
            else:
                raise Exception(f"Lark Auth Error: {data}")
    
    async def get_headers(self):
        token = await self.get_access_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    async def get_appointments(self, date_str: str, branch: str = None):
        headers = await self.get_headers()
        
        try:
            if "/" in date_str:
                parts = date_str.split("/")
                if len(parts) == 2:
                    day, month = parts
                    year = datetime.now().year
                else:
                    day, month, year = parts
                date_obj = datetime(int(year), int(month), int(day))
            else:
                date_obj = datetime.strptime(date_str, "%d-%m-%Y")
        except Exception as e:
            print(f"Date parse error: {e}")
            return []
        
        url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{self.base_id}/tables/{self.table_id}/records"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params={"page_size": 500})
            data = response.json()
            
            if data.get("code") != 0:
                return []
            
            items = data.get("data", {}).get("items", [])
            filtered_items = []
            
            for item in items:
                fields = item.get("fields", {})
                ngay_hen = fields.get("Ngày hẹn")
                
                if ngay_hen is None:
                    continue
                
                item_date = None
                # KHẮC PHỤC MÚI GIỜ: Cộng 7 tiếng cho đúng giờ VN
                if isinstance(ngay_hen, (int, float)):
                    item_date = datetime.fromtimestamp((ngay_hen / 1000) + (7 * 3600))
                
                elif isinstance(ngay_hen, str):
                    for fmt in ["%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d"]:
                        try:
                            item_date = datetime.strptime(ngay_hen, fmt)
                            break
                        except:
                            continue
                
                if item_date is None or item_date.date() != date_obj.date():
                    continue
                
                if branch:
                    branch_name = BRANCHES.get(branch.lower(), branch)
                    chi_nhanh = str(fields.get("Chi nhánh", "")) # Sửa lỗi kiểu dữ liệu chi nhánh
                    if branch_name not in chi_nhanh and chi_nhanh not in branch_name:
                        continue
                
                filtered_items.append(item)
            
            return filtered_items
    
    async def add_appointment(self, appointment_data: dict):
        headers = await self.get_headers()
        try:
            try:
                date_obj = datetime.strptime(appointment_data["date"], "%d/%m/%Y")
            except:
                date_obj = datetime.strptime(appointment_data["date"], "%d/%m")
                date_obj = date_obj.replace(year=datetime.now().year)
            
            # Chuẩn hóa về 00:00:00 của ngày đó
            date_obj = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            date_timestamp = int(date_obj.timestamp() * 1000)
            
            fields = {
                "Ngày hẹn": date_timestamp,
                "Giờ hẹn": appointment_data["time"],
                "Chi nhánh": appointment_data["branch"],
                "Tên khách": appointment_data["name"],
                "Trạng thái": "Chờ"
            }
            
            if appointment_data.get("phone"): fields["SĐT"] = appointment_data["phone"]
            if appointment_data.get("note"): fields["Ghi chú"] = appointment_data["note"]
            
            url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{self.base_id}/tables/{self.table_id}/records"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json={"fields": fields})
                data = response.json()
                return (True, data.get("data", {}).get("record", {})) if data.get("code") == 0 else (False, data)
        except Exception as e:
            return False, str(e)

lark = LarkAPI()

# ============== BOT COMMANDS (Giữ nguyên logic của bạn) ==============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = "🏪 **NAIL SALON BOT**\n\n/check [ngày] [rs/rg] - Xem lịch\n/today - Hôm nay\n/book - Đặt lịch"
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def check_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Nhập ngày! VD: `/check 11/2`", parse_mode="Markdown")
        return
    
    date_str = args[0]
    branch = args[1] if len(args) > 1 else None
    await update.message.reply_text("⏳ Đang tra cứu...")
    
    appointments = await lark.get_appointments(date_str, branch)
    
    header = f"📅 **Lịch ngày {date_str}**\n\n"
    if not appointments:
        await update.message.reply_text(header + "✅ Trống!", parse_mode="Markdown")
        return

    res = header
    for apt in appointments:
        f = apt.get("fields", {})
        res += f"• {f.get('Giờ hẹn')} - {f.get('Tên khách')} ({f.get('Chi nhánh')})\n"
    
    await update.message.reply_text(res, parse_mode="Markdown")

async def today_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.args = [datetime.now().strftime("%d/%m")]
    await check_schedule(update, context)

# ... (Các hàm book_start, book_date_callback, v.v. giữ nguyên từ file gốc của bạn) ...
# Lưu ý: Do giới hạn độ dài, tôi tập trung sửa các phần gây lỗi. 
# Hãy copy các hàm conversation còn lại từ file cũ của bạn vào dưới đây.

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check_schedule))
    application.add_handler(CommandHandler("today", today_schedule))
    print("🤖 Bot đang chạy...")
    application.run_polling()

if __name__ == "__main__":
    main()
