# 🏪 HƯỚNG DẪN CÀI ĐẶT NAIL SALON BOT

## 📋 TỔNG QUAN

Bot Telegram giúp bạn:
- ✅ Tra cứu lịch hẹn theo ngày, chi nhánh
- ✅ Đặt lịch hẹn mới (tự động lưu vào Lark Base)
- ✅ Xem lịch hôm nay / ngày mai nhanh chóng

---

## 🚀 CÁCH 1: DEPLOY LÊN RAILWAY (Miễn phí - Khuyên dùng)

### Bước 1: Tạo tài khoản Railway
1. Vào https://railway.app/
2. Đăng ký bằng GitHub (nếu chưa có GitHub thì tạo tại github.com)

### Bước 2: Tạo Project mới
1. Click **"New Project"**
2. Chọn **"Empty Project"**

### Bước 3: Thêm Service
1. Click **"+ New"** → **"GitHub Repo"**
2. Nếu chưa có repo, chọn **"Empty Service"** → **"Deploy from GitHub"**

### Bước 4: Upload code
**Cách A - Qua GitHub:**
1. Tạo repo mới trên GitHub
2. Upload 4 file: `bot.py`, `requirements.txt`, `Dockerfile`, `.env`
3. Kết nối repo với Railway

**Cách B - Deploy trực tiếp:**
1. Trong Railway, chọn **"Deploy from local files"**
2. Upload thư mục chứa các file

### Bước 5: Cấu hình Environment Variables
Trong Railway → Service → **Variables**, thêm:

```
TELEGRAM_TOKEN = 8353404370:AAE8llS0H1SYvbQWMMr5g8QApDVZr9PjBUI
LARK_APP_ID = cli_a900530757b81ed0
LARK_APP_SECRET = EbhapkJ5kCK3ITEdSqv0igWiTTorBO2d
LARK_BASE_ID = CaGqbAAZOa8hcDs7aYJlmR3cg0b
LARK_TABLE_ID = tblMjyHrFu553lEg
```

### Bước 6: Deploy
1. Click **"Deploy"**
2. Chờ 1-2 phút để build
3. Kiểm tra Logs xem có lỗi không

### Bước 7: Test Bot
1. Mở Telegram, tìm bot của bạn
2. Gửi `/start` để kiểm tra

---

## 💻 CÁCH 2: CHẠY TRÊN MÁY TÍNH CÁ NHÂN

### Yêu cầu:
- Python 3.9 trở lên
- Máy tính bật 24/7 (hoặc khi nào cần dùng bot)

### Bước 1: Cài đặt Python
Tải từ https://python.org/downloads/

### Bước 2: Tạo thư mục và copy files
```bash
mkdir nail_salon_bot
cd nail_salon_bot
# Copy 4 file vào thư mục này
```

### Bước 3: Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### Bước 4: Chạy bot
```bash
python bot.py
```

Bot sẽ hiện: `🤖 Bot đang chạy...`

---

## 📱 CÁCH SỬ DỤNG BOT

### Các lệnh chính:

| Lệnh | Mô tả | Ví dụ |
|------|-------|-------|
| `/start` | Xem hướng dẫn | `/start` |
| `/check` | Tra cứu lịch | `/check 20/2 rs` |
| `/today` | Lịch hôm nay | `/today` |
| `/tomorrow` | Lịch ngày mai | `/tomorrow` |
| `/book` | Đặt lịch (có hướng dẫn) | `/book` |
| `/quick` | Đặt lịch nhanh | `/quick 20/2 10h30 rs Chị Lan 0901234567` |

### Mã chi nhánh:
- `rs` = Rạch Sỏi
- `rg` = Rạch Giá

### Ví dụ sử dụng:

**1. Tra cứu lịch ngày 20/2 chi nhánh Rạch Sỏi:**
```
/check 20/2 rs
```

**2. Tra cứu lịch ngày 20/2 cả 2 chi nhánh:**
```
/check 20/2
```

**3. Đặt lịch nhanh:**
```
/quick 20/2 10h30 rs Chị Lan 0901234567
```

**4. Đặt lịch có hướng dẫn:**
```
/book
```
Bot sẽ hỏi từng bước: Ngày → Giờ → Chi nhánh → Tên → SĐT → Số người → Xác nhận

---

## 🔧 CẤU HÌNH LARK BASE

### Cấu trúc bảng "Lịch hẹn":

| Tên cột | Loại | Ghi chú |
|---------|------|---------|
| Ngày hẹn | Date | Bắt buộc |
| Giờ hẹn | Text | VD: 10h30 |
| Chi nhánh | Single Select | "Rạch Sỏi", "Rạch Giá" |
| Tên khách | Text | Bắt buộc |
| SĐT | Text | |
| Số người | Number | Mặc định 1 |
| Dịch vụ | Multi Select | Tùy chỉnh |
| Ghi chú | Text | |
| Trạng thái | Single Select | "Chờ", "Đã đến", "Hủy" |

### Cấp quyền cho Lark App:
1. Vào https://open.larksuite.com/
2. Chọn App đã tạo
3. **Permissions & Scopes** → Thêm:
   - `bitable:app`
   - `bitable:app:readonly`
4. **Version Management** → Publish

---

## ⚠️ BẢO MẬT

**QUAN TRỌNG:** Sau khi hệ thống hoạt động, hãy đổi:

1. **Telegram Bot Token:**
   - Vào @BotFather → `/mybots` → Chọn bot → **API Token** → **Revoke**
   - Copy token mới, cập nhật vào Railway/code

2. **Lark App Secret:**
   - Vào Lark Developer Console → App → **Credentials**
   - Click **Reset** App Secret
   - Copy secret mới, cập nhật vào Railway/code

---

## ❓ XỬ LÝ LỖI THƯỜNG GẶP

### 1. Bot không phản hồi
- Kiểm tra bot đang chạy (xem Logs trên Railway)
- Kiểm tra Telegram Token đúng chưa

### 2. Lỗi "Lark Auth Error"
- Kiểm tra App ID và App Secret
- Đảm bảo đã Publish App trên Lark Developer Console
- Kiểm tra đã cấp quyền `bitable:app`

### 3. Không lưu được lịch hẹn
- Kiểm tra Base ID và Table ID
- Đảm bảo tên các cột trong Lark Base đúng chính tả
- Kiểm tra App có quyền ghi vào Base

### 4. Lọc theo ngày không đúng
- Đảm bảo cột "Ngày hẹn" là kiểu Date
- Định dạng ngày nhập: dd/mm hoặc dd/mm/yyyy

---

## 📞 HỖ TRỢ

Nếu gặp vấn đề, hãy:
1. Chụp ảnh màn hình lỗi
2. Copy logs từ Railway
3. Gửi cho người hỗ trợ kỹ thuật

---

**Chúc bạn sử dụng thành công! 🎉**
