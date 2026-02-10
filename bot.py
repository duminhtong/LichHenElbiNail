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

# Chi nhánh
BRANCHES = {
    "rs": "Rạch Sỏi",
    "rg": "Rạch Giá"
}

# Conversation states
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
        """Lấy danh sách lịch hẹn theo ngày và chi nhánh"""
        headers = await self.get_headers()
        
        # Chuẩn hóa ngày nhập vào
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
        
        # Tạo timestamp cho filter (milliseconds)
        date_start = int(date_obj.timestamp() * 1000)
        date_end = int((date_obj + timedelta(days=1)).timestamp() * 1000)
        
        # Thử lấy tất cả records trước (không filter ngày qua API)
        url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{self.base_id}/tables/{self.table_id}/records"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
                params={"page_size": 500}
            )
            data = response.json()
            
            print(f"Lark API Response: {data}")  # Debug log
            
            if data.get("code") != 0:
                print(f"Error: {data}")
                return []
            
            items = data.get("data", {}).get("items", [])
            filtered_items = []
            
            print(f"Total records from Lark: {len(items)}")
            print(f"Looking for date: {date_obj.date()}")
            
            # Filter theo ngày và chi nhánh trong Python
            for item in items:
                fields = item.get("fields", {})
                
                # Lấy ngày hẹn - có thể là timestamp hoặc text
                ngay_hen = fields.get("Ngày hẹn")
                
                print(f"Record fields: {fields}")
                print(f"Ngày hẹn value: {ngay_hen}, type: {type(ngay_hen)}")
                
                if ngay_hen is None:
                    continue
                
                # Xử lý nhiều định dạng ngày
                item_date = None
                
                # Nếu là timestamp (số)
                if isinstance(ngay_hen, (int, float)):
                    item_date = datetime.fromtimestamp(ngay_hen / 1000)
                
                # Nếu là string
                elif isinstance(ngay_hen, str):
                    ngay_hen = ngay_hen.strip()
                    # Thử các định dạng phổ biến
                    for fmt in ["%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d", "%d/%m"]:
                        try:
                            item_date = datetime.strptime(ngay_hen, fmt)
                            if fmt == "%d/%m":
                                item_date = item_date.replace(year=datetime.now().year)
                            break
                        except:
                            continue
                    
                    # Nếu vẫn không parse được, thử tách thủ công
                    if item_date is None and "/" in ngay_hen:
                        try:
                            parts = ngay_hen.split("/")
                            if len(parts) == 3:
                                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                                item_date = datetime(y, m, d)
                            elif len(parts) == 2:
                                d, m = int(parts[0]), int(parts[1])
                                item_date = datetime(datetime.now().year, m, d)
                        except Exception as e:
                            print(f"Manual parse failed: {e}")
                
                # Nếu là dict (Lark Date object)
                elif isinstance(ngay_hen, dict):
                    # Lark có thể trả về dạng {"date": "2025-02-11"} hoặc timestamp
                    if "date" in ngay_hen:
                        try:
                            item_date = datetime.strptime(ngay_hen["date"], "%Y-%m-%d")
                        except:
                            pass
                    elif "timestamp" in ngay_hen:
                        item_date = datetime.fromtimestamp(ngay_hen["timestamp"] / 1000)
                
                if item_date is None:
                    print(f"Cannot parse date: {ngay_hen}")
                    continue
                
                # So sánh ngày (chỉ so sánh ngày, bỏ qua giờ)
                if item_date.date() != date_obj.date():
                    continue
                
                # Filter chi nhánh
                if branch:
                    branch_name = BRANCHES.get(branch.lower(), branch)
                    chi_nhanh = fields.get("Chi nhánh", "")
                    if branch_name not in chi_nhanh and chi_nhanh not in branch_name:
                        continue
                
                filtered_items.append(item)
            
            print(f"Found {len(filtered_items)} appointments for {date_str}")
            return filtered_items
    
    async def add_appointment(self, appointment_data: dict):
        """Thêm lịch hẹn mới"""
        headers = await self.get_headers()
        
        # Chuyển đổi ngày
        try:
            date_obj = datetime.strptime(appointment_data["date"], "%d/%m/%Y")
        except:
            date_obj = datetime.strptime(appointment_data["date"], "%d/%m")
            date_obj = date_obj.replace(year=datetime.now().year)
        
        date_timestamp = int(date_obj.timestamp() * 1000)
        
        fields = {
            "Ngày hẹn": date_timestamp,
            "Giờ hẹn": appointment_data["time"],
            "Chi nhánh": appointment_data["branch"],
            "Tên khách": appointment_data["name"],
            "Trạng thái": "Chờ"
        }
        
        if appointment_data.get("phone"):
            fields["SĐT"] = appointment_data["phone"]
        if appointment_data.get("people"):
            fields["Số người"] = int(appointment_data["people"])
        if appointment_data.get("note"):
            fields["Ghi chú"] = appointment_data["note"]
        
        url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{self.base_id}/tables/{self.table_id}/records"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json={"fields": fields}
            )
            data = response.json()
            
            if data.get("code") == 0:
                return True, data.get("data", {}).get("record", {})
            else:
                return False, data

lark = LarkAPI()

# ============== BOT COMMANDS ==============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /start"""
    welcome_text = """
🏪 **NAIL SALON BOT** 🏪

Chào mừng bạn! Bot giúp quản lý lịch hẹn Nail Salon.

📋 **DANH SÁCH LỆNH:**

🔍 **Tra cứu lịch:**
• `/check [ngày] [chi nhánh]` - Xem lịch
  VD: `/check 20/2 rs` hoặc `/check 20/2 rg`
  
• `/today` - Lịch hôm nay (cả 2 chi nhánh)
• `/tomorrow` - Lịch ngày mai

📝 **Đặt lịch:**
• `/book` - Đặt lịch mới (bot hướng dẫn từng bước)

⚡ **Đặt nhanh:**
• `/quick [ngày] [giờ] [chi nhánh] [tên] [sđt]`
  VD: `/quick 20/2 10h30 rs Chị Lan 0901234567`

**Chi nhánh:**
• `rs` = Rạch Sỏi
• `rg` = Rạch Giá
"""
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def check_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /check - Tra cứu lịch hẹn"""
    args = context.args
    
    if len(args) < 1:
        await update.message.reply_text("❌ Vui lòng nhập ngày!\nVD: `/check 20/2 rs`", parse_mode="Markdown")
        return
    
    date_str = args[0]
    branch = args[1] if len(args) > 1 else None
    
    # Validate date format
    try:
        if "/" not in date_str:
            await update.message.reply_text("❌ Định dạng ngày không đúng!\nVD: `20/2` hoặc `20/02/2025`", parse_mode="Markdown")
            return
    except:
        pass
    
    await update.message.reply_text("⏳ Đang tra cứu...")
    
    appointments = await lark.get_appointments(date_str, branch)
    
    # Format response
    if branch:
        branch_name = BRANCHES.get(branch.lower(), branch)
        header = f"📅 **Lịch ngày {date_str} - {branch_name}**\n\n"
    else:
        header = f"📅 **Lịch ngày {date_str} - Cả 2 chi nhánh**\n\n"
    
    if not appointments:
        response = header + "✅ Chưa có lịch hẹn nào. Còn trống!"
    else:
        # Group by branch and sort by time
        rs_appointments = []
        rg_appointments = []
        
        for apt in appointments:
            fields = apt.get("fields", {})
            branch_field = fields.get("Chi nhánh", "")
            
            time_str = fields.get("Giờ hẹn", "N/A")
            name = fields.get("Tên khách", "N/A")
            phone = fields.get("SĐT", "")
            people = fields.get("Số người", 1)
            note = fields.get("Ghi chú", "")
            status = fields.get("Trạng thái", "Chờ")
            
            status_icon = "⏳" if status == "Chờ" else "✅" if status == "Đã đến" else "❌"
            
            line = f"{status_icon} **{time_str}** - {name}"
            if people and people > 1:
                line += f" ({people} người)"
            if phone:
                line += f" | {phone}"
            if note:
                line += f"\n   📝 {note}"
            
            if "Rạch Sỏi" in branch_field:
                rs_appointments.append((time_str, line))
            else:
                rg_appointments.append((time_str, line))
        
        # Sort by time
        rs_appointments.sort(key=lambda x: x[0])
        rg_appointments.sort(key=lambda x: x[0])
        
        response = header
        
        if not branch or branch.lower() == "rs":
            response += f"🏪 **CHI NHÁNH RẠCH SỎI** ({len(rs_appointments)} khách)\n"
            if rs_appointments:
                for _, line in rs_appointments:
                    response += f"{line}\n"
            else:
                response += "✅ Còn trống\n"
            response += "\n"
        
        if not branch or branch.lower() == "rg":
            response += f"🏪 **CHI NHÁNH RẠCH GIÁ** ({len(rg_appointments)} khách)\n"
            if rg_appointments:
                for _, line in rg_appointments:
                    response += f"{line}\n"
            else:
                response += "✅ Còn trống\n"
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def today_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /today - Xem lịch hôm nay"""
    context.args = [datetime.now().strftime("%d/%m/%Y")]
    await check_schedule(update, context)

async def tomorrow_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /tomorrow - Xem lịch ngày mai"""
    tomorrow = datetime.now() + timedelta(days=1)
    context.args = [tomorrow.strftime("%d/%m/%Y")]
    await check_schedule(update, context)

async def quick_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /quick - Đặt lịch nhanh"""
    args = context.args
    
    if len(args) < 4:
        await update.message.reply_text(
            "❌ Thiếu thông tin!\n\n"
            "Cú pháp: `/quick [ngày] [giờ] [chi nhánh] [tên] [sđt]`\n"
            "VD: `/quick 20/2 10h30 rs Chị Lan 0901234567`",
            parse_mode="Markdown"
        )
        return
    
    date_str = args[0]
    time_str = args[1]
    branch_code = args[2].lower()
    name = args[3]
    phone = args[4] if len(args) > 4 else ""
    
    # Validate branch
    if branch_code not in BRANCHES:
        await update.message.reply_text("❌ Chi nhánh không hợp lệ! Dùng `rs` (Rạch Sỏi) hoặc `rg` (Rạch Giá)", parse_mode="Markdown")
        return
    
    branch_name = BRANCHES[branch_code]
    
    appointment_data = {
        "date": date_str,
        "time": time_str,
        "branch": branch_name,
        "name": name,
        "phone": phone
    }
    
    await update.message.reply_text("⏳ Đang đặt lịch...")
    
    success, result = await lark.add_appointment(appointment_data)
    
    if success:
        response = f"""
✅ **ĐẶT LỊCH THÀNH CÔNG!**

📅 Ngày: {date_str}
🕐 Giờ: {time_str}
🏪 Chi nhánh: {branch_name}
👤 Khách: {name}
📞 SĐT: {phone or "Không có"}
"""
        await update.message.reply_text(response, parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Lỗi đặt lịch: {result}", parse_mode="Markdown")

# ============== BOOKING CONVERSATION ==============

async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bắt đầu quy trình đặt lịch"""
    keyboard = [
        [InlineKeyboardButton("📅 Hôm nay", callback_data="date_today")],
        [InlineKeyboardButton("📅 Ngày mai", callback_data="date_tomorrow")],
        [InlineKeyboardButton("📅 Nhập ngày khác", callback_data="date_custom")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📝 **ĐẶT LỊCH HẸN MỚI**\n\nBước 1/6: Chọn ngày hẹn:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return BOOK_DATE

async def book_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý chọn ngày"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "date_today":
        context.user_data["date"] = datetime.now().strftime("%d/%m/%Y")
        return await ask_time(query, context)
    elif query.data == "date_tomorrow":
        tomorrow = datetime.now() + timedelta(days=1)
        context.user_data["date"] = tomorrow.strftime("%d/%m/%Y")
        return await ask_time(query, context)
    else:
        await query.edit_message_text("📅 Nhập ngày (VD: 20/2 hoặc 20/02/2025):")
        return BOOK_DATE

async def book_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý nhập ngày bằng text"""
    date_str = update.message.text.strip()
    
    # Validate
    try:
        if "/" not in date_str:
            raise ValueError()
        parts = date_str.split("/")
        if len(parts) == 2:
            date_str = f"{date_str}/{datetime.now().year}"
    except:
        await update.message.reply_text("❌ Định dạng không đúng! Nhập lại (VD: 20/2):")
        return BOOK_DATE
    
    context.user_data["date"] = date_str
    return await ask_time_message(update, context)

async def ask_time(query, context):
    """Hỏi giờ hẹn"""
    await query.edit_message_text(
        f"✅ Ngày: {context.user_data['date']}\n\n"
        "Bước 2/6: Nhập giờ hẹn (VD: 10h30, 14h, 8h15):"
    )
    return BOOK_TIME

async def ask_time_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hỏi giờ hẹn qua message"""
    await update.message.reply_text(
        f"✅ Ngày: {context.user_data['date']}\n\n"
        "Bước 2/6: Nhập giờ hẹn (VD: 10h30, 14h, 8h15):"
    )
    return BOOK_TIME

async def book_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý nhập giờ"""
    time_str = update.message.text.strip()
    context.user_data["time"] = time_str
    
    keyboard = [
        [InlineKeyboardButton("🏪 Rạch Sỏi", callback_data="branch_rs")],
        [InlineKeyboardButton("🏪 Rạch Giá", callback_data="branch_rg")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Ngày: {context.user_data['date']}\n"
        f"✅ Giờ: {time_str}\n\n"
        "Bước 3/6: Chọn chi nhánh:",
        reply_markup=reply_markup
    )
    return BOOK_BRANCH

async def book_branch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý chọn chi nhánh"""
    query = update.callback_query
    await query.answer()
    
    branch_code = query.data.replace("branch_", "")
    context.user_data["branch"] = BRANCHES[branch_code]
    
    await query.edit_message_text(
        f"✅ Ngày: {context.user_data['date']}\n"
        f"✅ Giờ: {context.user_data['time']}\n"
        f"✅ Chi nhánh: {context.user_data['branch']}\n\n"
        "Bước 4/6: Nhập tên khách:"
    )
    return BOOK_NAME

async def book_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý nhập tên"""
    context.user_data["name"] = update.message.text.strip()
    
    keyboard = [[InlineKeyboardButton("⏭ Bỏ qua", callback_data="skip_phone")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Tên: {context.user_data['name']}\n\n"
        "Bước 5/6: Nhập số điện thoại (hoặc bỏ qua):",
        reply_markup=reply_markup
    )
    return BOOK_PHONE

async def book_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý nhập SĐT"""
    context.user_data["phone"] = update.message.text.strip()
    return await ask_people(update, context)

async def book_phone_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bỏ qua SĐT"""
    query = update.callback_query
    await query.answer()
    context.user_data["phone"] = ""
    
    keyboard = [
        [InlineKeyboardButton("1 người", callback_data="people_1")],
        [InlineKeyboardButton("2 người", callback_data="people_2")],
        [InlineKeyboardButton("3+ người", callback_data="people_more")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Bước 6/6: Số người:",
        reply_markup=reply_markup
    )
    return BOOK_PEOPLE

async def ask_people(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hỏi số người"""
    keyboard = [
        [InlineKeyboardButton("1 người", callback_data="people_1")],
        [InlineKeyboardButton("2 người", callback_data="people_2")],
        [InlineKeyboardButton("3+ người", callback_data="people_more")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ SĐT: {context.user_data.get('phone', 'Không có')}\n\n"
        "Bước 6/6: Số người:",
        reply_markup=reply_markup
    )
    return BOOK_PEOPLE

async def book_people(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý chọn số người"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "people_more":
        await query.edit_message_text("Nhập số người:")
        return BOOK_PEOPLE
    
    people = int(query.data.replace("people_", ""))
    context.user_data["people"] = people
    
    return await show_confirm(query, context)

async def book_people_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý nhập số người bằng text"""
    try:
        context.user_data["people"] = int(update.message.text.strip())
    except:
        context.user_data["people"] = 1
    
    return await show_confirm_message(update, context)

async def show_confirm(query, context):
    """Hiển thị xác nhận"""
    data = context.user_data
    
    keyboard = [
        [InlineKeyboardButton("✅ Xác nhận đặt lịch", callback_data="confirm_yes")],
        [InlineKeyboardButton("📝 Thêm ghi chú", callback_data="add_note")],
        [InlineKeyboardButton("❌ Hủy", callback_data="confirm_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📋 **XÁC NHẬN THÔNG TIN**\n\n"
        f"📅 Ngày: {data['date']}\n"
        f"🕐 Giờ: {data['time']}\n"
        f"🏪 Chi nhánh: {data['branch']}\n"
        f"👤 Tên: {data['name']}\n"
        f"📞 SĐT: {data.get('phone') or 'Không có'}\n"
        f"👥 Số người: {data.get('people', 1)}\n"
        f"📝 Ghi chú: {data.get('note') or 'Không có'}\n",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return BOOK_CONFIRM

async def show_confirm_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị xác nhận qua message"""
    data = context.user_data
    
    keyboard = [
        [InlineKeyboardButton("✅ Xác nhận đặt lịch", callback_data="confirm_yes")],
        [InlineKeyboardButton("📝 Thêm ghi chú", callback_data="add_note")],
        [InlineKeyboardButton("❌ Hủy", callback_data="confirm_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📋 **XÁC NHẬN THÔNG TIN**\n\n"
        f"📅 Ngày: {data['date']}\n"
        f"🕐 Giờ: {data['time']}\n"
        f"🏪 Chi nhánh: {data['branch']}\n"
        f"👤 Tên: {data['name']}\n"
        f"📞 SĐT: {data.get('phone') or 'Không có'}\n"
        f"👥 Số người: {data.get('people', 1)}\n"
        f"📝 Ghi chú: {data.get('note') or 'Không có'}\n",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return BOOK_CONFIRM

async def book_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý xác nhận"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_no":
        await query.edit_message_text("❌ Đã hủy đặt lịch.")
        return ConversationHandler.END
    
    if query.data == "add_note":
        await query.edit_message_text("📝 Nhập ghi chú:")
        return BOOK_NOTE
    
    # Confirm booking
    await query.edit_message_text("⏳ Đang đặt lịch...")
    
    data = context.user_data
    appointment_data = {
        "date": data["date"],
        "time": data["time"],
        "branch": data["branch"],
        "name": data["name"],
        "phone": data.get("phone", ""),
        "people": data.get("people", 1),
        "note": data.get("note", "")
    }
    
    success, result = await lark.add_appointment(appointment_data)
    
    if success:
        await query.edit_message_text(
            f"✅ **ĐẶT LỊCH THÀNH CÔNG!**\n\n"
            f"📅 Ngày: {data['date']}\n"
            f"🕐 Giờ: {data['time']}\n"
            f"🏪 Chi nhánh: {data['branch']}\n"
            f"👤 Khách: {data['name']}\n"
            f"📞 SĐT: {data.get('phone') or 'Không có'}\n"
            f"👥 Số người: {data.get('people', 1)}\n"
            f"📝 Ghi chú: {data.get('note') or 'Không có'}",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(f"❌ Lỗi đặt lịch: {result}")
    
    return ConversationHandler.END

async def book_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý nhập ghi chú"""
    context.user_data["note"] = update.message.text.strip()
    return await show_confirm_message(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hủy conversation"""
    await update.message.reply_text("❌ Đã hủy.")
    return ConversationHandler.END

# ============== MAIN ==============

def main():
    """Khởi chạy bot"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Conversation handler cho đặt lịch
    book_handler = ConversationHandler(
        entry_points=[CommandHandler("book", book_start)],
        states={
            BOOK_DATE: [
                CallbackQueryHandler(book_date_callback, pattern="^date_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, book_date_text)
            ],
            BOOK_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, book_time)
            ],
            BOOK_BRANCH: [
                CallbackQueryHandler(book_branch, pattern="^branch_")
            ],
            BOOK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, book_name)
            ],
            BOOK_PHONE: [
                CallbackQueryHandler(book_phone_skip, pattern="^skip_phone$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, book_phone)
            ],
            BOOK_PEOPLE: [
                CallbackQueryHandler(book_people, pattern="^people_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, book_people_text)
            ],
            BOOK_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, book_note)
            ],
            BOOK_CONFIRM: [
                CallbackQueryHandler(book_confirm, pattern="^(confirm_|add_note)")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check_schedule))
    application.add_handler(CommandHandler("today", today_schedule))
    application.add_handler(CommandHandler("tomorrow", tomorrow_schedule))
    application.add_handler(CommandHandler("quick", quick_book))
    application.add_handler(book_handler)
    
    print("🤖 Bot đang chạy...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
