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
| 🔄 **Vietravel** | Quét tour từ travel.com.vn · Lưu vào tab Vietravel trên Google Sheet |
| 🌐 **FindTourGo** | Quét OTA findtourgo.com (Trung Quốc / Nhật Bản / Việt Nam) · Nhiều công ty LH · Lưu tab FindTourGo |

**Sidebar filters:** Thị trường · Công ty · Tuyến · Điểm khởi hành · Loại lịch · Khoảng giá

---

## Quét tour Vietravel (travel.com.vn)

App tự động quét 2 trang:

- https://travel.com.vn/du-lich-viet-nam.aspx (trong nước)
- https://travel.com.vn/du-lich-nuoc-ngoai.aspx (nước ngoài)

Và ghi vào tab **Vietravel** trên Google Sheet:  
`gid=620817544` trong file [OTA Sheet](https://docs.google.com/spreadsheets/d/1sI34D88zsmSrN7Jf9fS3jh4aUvaep-blxnBR1CGq9eM/edit#gid=620817544)

### Cấu hình Google Service Account (bắt buộc để ghi Sheet)

1. Google Cloud Console → bật **Google Sheets API**
2. Tạo Service Account → tải JSON → lưu `credentials.json` cạnh `streamlit_app.py`
3. Chia sẻ Google Sheet cho email Service Account (quyền **Editor**)
4. Streamlit Cloud: copy JSON vào `.streamlit/secrets.toml` (xem `secrets.toml.example`)

### Chạy từ app hoặc CLI

**Trong app:** Tab **🔄 Vietravel** → *Quét thử* hoặc *Quét & Lưu lên Google Sheet*

**CLI:**
```bash
python sync_vietravel.py --preview   # chỉ xem số lượng tour quét được
python sync_vietravel.py             # quét + ghi Sheet
```

---

## Quét tour FindTourGo (OTA)

Nguồn: API FindTourGo — quét **mọi quốc gia** có tour (~30+ nước, ~600+ sản phẩm).

Ghi vào tab **FindTourGo** (`gid=408521834`):  
[Sheet](https://docs.google.com/spreadsheets/d/1sI34D88zsmSrN7Jf9fS3jh4aUvaep-blxnBR1CGq9eM/edit#gid=408521834)

Cột chính: **Công ty lữ hành** (mỗi tour một operator khác nhau), **Nguồn** (thị trường từ tên tour), **Quốc gia** (điểm đến), **Mã tour**, **Link tour** / **Link thô**.

Mặc định khi lưu: **ghi đè toàn bộ tab**. Tick *Merge* nếu muốn giữ tour không trùng mã.

**Trong app:** Tab **🌐 FindTourGo** → *Quét thử* hoặc *Quét & Lưu* (cột Link hiển thị 🔗 Xem như tab Dữ liệu)

**CLI:**
```bash
python sync_findtourgo.py --preview           # xem thống kê
python sync_findtourgo.py                      # quét tất cả quốc gia + ghi Sheet
python sync_findtourgo.py --countries CN JP VN # chỉ một vài quốc gia
python sync_findtourgo.py --merge              # merge theo mã tour
```

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
├── streamlit_app.py       # App chính (multi-tab)
├── vietravel_scraper.py   # Quét travel.com.vn + ghi Google Sheet
├── sync_vietravel.py      # CLI đồng bộ Vietravel
├── requirements.txt
├── credentials.json       # (tự tạo) Google Service Account key
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
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
