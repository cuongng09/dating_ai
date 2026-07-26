# Ru Tim — Trợ lý hẹn hò chạy local với Ollama 💬

Một web app nhỏ chạy hoàn toàn trên máy bạn: giao diện chat + backend Python gọi
tới model AI cục bộ qua **Ollama**. Không có API key, không gửi dữ liệu ra ngoài
internet (ngoại trừ chính máy bạn nói chuyện với Ollama trên localhost).

## 1. Cài Ollama và tải model

1. Tải Ollama tại https://ollama.com (có bản Windows/macOS/Linux).
2. Mở terminal, tải một model (khuyên dùng model tiếng Việt tốt, nhẹ):
   ```bash
   ollama pull llama3.1        # cân bằng, ~4.7GB
   # hoặc nhẹ hơn:
   ollama pull qwen2.5:7b
   # hoặc mạnh hơn nếu máy khoẻ:
   ollama pull llama3.1:70b
   ```
3. Đảm bảo Ollama đang chạy nền (thường tự chạy sau khi cài; nếu chưa: `ollama serve`).

## 2. Cài đặt ứng dụng

```bash
cd dating-ai
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Chạy ứng dụng

```bash
python3 server.py
```

Mở trình duyệt tại: **http://localhost:5050**

(Muốn đổi model mặc định hoặc cổng: `DEFAULT_MODEL=qwen2.5:7b PORT=5050 python3 server.py`)

## Chức năng

**Chức năng chính — hỗ trợ chat hẹn hò**, với 6 chế độ chọn ở thanh bên:

| Chế độ | Mô tả |
|---|---|
| Cố vấn hẹn hò | Trò chuyện, xin lời khuyên cho tình huống thực tế |
| Luyện tập hội thoại | AI đóng vai nhân vật giả định để bạn luyện nhắn tin làm quen |
| Chỉnh sửa tin nhắn | Dán tin nhắn nháp, AI gợi ý viết lại tự nhiên/cuốn hút hơn |
| Câu mở đầu | Gợi ý icebreaker dựa trên thông tin profile đối phương |
| Viết bio hẹn hò | Xây dựng bio hồ sơ hẹn hò (Tinder, Bumble...) |
| Lên kế hoạch hẹn hò | Gợi ý địa điểm/lịch trình theo ngân sách, sở thích |

**Chức năng phụ (đã thêm cho đủ):**
- Lưu & quản lý nhiều cuộc trò chuyện (lịch sử lưu file JSON cục bộ tại `data/threads/`)
- Đổi tên tự động theo tin nhắn đầu tiên, xoá cuộc trò chuyện
- Xuất cuộc trò chuyện ra file `.txt`
- Chọn model Ollama đang có sẵn trên máy, điều chỉnh độ sáng tạo (temperature)
- Phản hồi dạng streaming (chữ chạy dần như đang gõ)
- Giao diện tối, tự thiết kế riêng, không cần internet để dùng (trừ tải font/Ollama lần đầu)

## Lưu ý an toàn & đạo đức
- Chế độ "Luyện tập hội thoại" luôn nói rõ đây là nhân vật hư cấu để luyện tập,
  không phải người thật.
- App không hỗ trợ tạo nội dung lừa dối, mạo danh người khác, hay thao túng tâm lý đối phương —
  các system prompt đã được thiết kế để giữ giọng điệu tôn trọng, trung thực.
- Đây là công cụ hỗ trợ giao tiếp, không thay thế phán đoán hay sự an toàn cá nhân của bạn khi
  gặp gỡ người mới (luôn ưu tiên gặp ở nơi công cộng, báo người thân/bạn bè).

## Cấu trúc thư mục

```
dating-ai/
├── server.py           # Backend Flask (API + gọi Ollama)
├── requirements.txt
├── static/
│   └── index.html      # Toàn bộ giao diện (HTML/CSS/JS)
└── data/threads/        # Lịch sử trò chuyện (tự tạo khi chạy)
```

## Tuỳ biến thêm
- Muốn thêm chế độ mới: sửa dict `MODES` trong `server.py`, thêm 1 mục `label`, `subtitle`, `system`.
- Muốn đổi giao diện: sửa `static/index.html` (biến màu ở đầu file `:root{...}`).

## 4. Chạy dưới dạng dịch vụ systemd trên Linux
Tạo file dịch vụ:

```bash
sudo nano /etc/systemd/system/Dating-AI.service
```

Nội dung mẫu:

```ini
[Unit]
Description=Dating AI Server (Flask)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/cwng/Documents/GitHub/dating-ai
ExecStart=/usr/bin/python3 /home/cwng/Documents/GitHub/dating-ai/server.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Thay `USERNAME` bằng tên người dùng và cập nhật đường dẫn phù hợp.

Kích hoạt dịch vụ:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot.service
sudo systemctl start telegram-bot.service
sudo systemctl status telegram-bot.service
```