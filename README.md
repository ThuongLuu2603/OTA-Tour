# ✈️ OTA Tour Market Dashboard

Web app phân tích thị trường tour du lịch Việt Nam, xây dựng bằng **Streamlit** và **Plotly**.  
Dữ liệu đọc trực tiếp từ Google Sheets (public) — không cần API key.

---

## Tính năng

| Tab | Nội dung |
|-----|----------|
| 📊 **Tổng Quan** | KPI cards · Số SP theo thị trường · Thị phần công ty · Scatter giá × thời gian · Phân khúc giá |
| 💰 **Phân Tích Giá** | Histogram phân phối · Box plot & Violin theo thị trường · Box plot theo tuyến · Price Heatmap (Công ty × Tuyến) · Bảng thống kê |
| 🗺️ **Thị Trường** | Treemap thị trường → công ty · Stacked bar phân khúc · Cơ cấu thời gian chuyến · Giá TB theo công ty × thị trường · Bubble chart |
| 🏢 **Đối Thủ** | Profile công ty · Định vị giá vs giá TB tuyến · Bảng so sánh · Danh sách sản phẩm |
| 📅 **Lịch KH** | Calendar heatmap 120 ngày · Lịch theo tháng × thị trường · Ngày trong tuần · Danh sách chuyến sắp tới |
| 📋 **Dữ Liệu** | Bảng đầy đủ với link clickable · Export CSV & Excel |

**Sidebar filters:** Thị trường · Công ty · Tuyến · Điểm khởi hành · Loại lịch · Khoảng giá

---

## Cài đặt & Chạy local

### Yêu cầu
- Python 3.9 trở lên
- pip

### Bước 1 — Clone / tải về
```bash
git clone https://github.com/<your-username>/ota-tour-dashboard.git
cd ota-tour-dashboard
```

### Bước 2 — Cài thư viện
```bash
pip install -r requirements.txt
```

### Bước 3 — Chạy app
```bash
streamlit run streamlit_app.py
```

Mở trình duyệt tại `http://localhost:8501`

---

## Deploy lên Streamlit Cloud (miễn phí)

### Bước 1 — Tạo GitHub repo
1. Vào [github.com](https://github.com) → **New repository**
2. Đặt tên: `ota-tour-dashboard` (public hoặc private đều được)
3. Push code lên:

```bash
git init
git add .
git commit -m "Initial commit: OTA Tour Dashboard"
git remote add origin https://github.com/<your-username>/ota-tour-dashboard.git
git push -u origin main
```

### Bước 2 — Deploy trên Streamlit Cloud
1. Vào [share.streamlit.io](https://share.streamlit.io) (đăng nhập bằng GitHub)
2. Click **New app**
3. Chọn repo `ota-tour-dashboard` → branch `main` → file `streamlit_app.py`
4. Click **Deploy!**

App sẽ có URL dạng:  
`https://<your-username>-ota-tour-dashboard-streamlit-app-xxxx.streamlit.app`

> **Lưu ý:** Streamlit Cloud free tier cho phép 1 app public, tự động deploy lại khi push code mới lên GitHub.

---

## Cấu trúc dự án

```
ota-dashboard/
├── streamlit_app.py       # App chính (single-file, multi-tab)
├── requirements.txt       # Python dependencies
├── .streamlit/
│   └── config.toml        # Theme màu navy #003580, layout wide
└── README.md
```

---

## Thay đổi data source

Mở `streamlit_app.py`, sửa 2 biến ở đầu file:

```python
SHEET_ID = "1sI34D88zsmSrN7Jf9fS3jh4aUvaep-blxnBR1CGq9eM"  # ID Google Sheet
GID = "1729132868"  # GID của sheet tab cụ thể
```

Lấy GID từ URL Google Sheet: `...#gid=1729132868`

> **Yêu cầu:** Google Sheet phải được set **"Anyone with the link → Viewer"**  
> (Chia sẻ → Bất kỳ ai có đường liên kết → Người xem)

---

## Cấu trúc Google Sheet

App kỳ vọng sheet "Tổng Hợp Tour" có các cột theo thứ tự:

| Cột | Tên | Mô tả |
|-----|-----|-------|
| 0 | Tên Công Ty | Tên công ty (forward-fill khi để trống) |
| 1 | Thị trường | Vùng miền (Bắc Trung Bộ, v.v.) |
| 2 | Tuyến tour | Tên tuyến |
| 3 | Tên Tour | Tên tour đầy đủ |
| 4 | Lịch trình | Mô tả lịch trình |
| 5 | Điểm khởi hành | Nơi xuất phát |
| 6 | Thời gian | Số ngày (0.5 ngày, 3N2D, v.v.) |
| 7 | Giá | Giá VND (format: 1.050.000) |
| 8 | Lịch khởi hành | Ngày KH hoặc Hàng ngày/tuần |
| 23 | Link | URL đầy đủ đến trang tour |

---

## Dependencies

```
streamlit>=1.35.0
pandas>=2.0.0
plotly>=5.18.0
openpyxl>=3.1.0
numpy>=1.24.0
```
