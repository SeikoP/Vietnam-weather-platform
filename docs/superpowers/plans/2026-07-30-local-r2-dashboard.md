# Local R2 Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chạy dashboard Streamlit local bằng dữ liệu CSV public trên R2 mà không
kết nối Supabase hoặc đọc credential từ `.env`.

**Architecture:** `dashboard/Dashboard.py` là file local bị Git ignore. Dashboard
dùng URL R2 public cố định, tải ba bảng `dim_district`, `dim_hour` và
`fact_aqi_hourly`, rồi merge theo khóa của warehouse trước khi giữ nguyên phần tính
AQI và giao diện.

**Tech Stack:** Python 3.13, Streamlit, pandas, Plotly, statsmodels, Cloudflare R2.

## Global Constraints

- Không thay đổi quyền public read-only hiện tại của dữ liệu R2.
- Không dùng `.env`, Supabase hoặc database credential trong dashboard.
- Không đưa `dashboard/Dashboard.py` vào Git.
- Không xóa hoặc thay đổi dữ liệu Supabase.

---

### Task 1: Di chuyển và loại dashboard khỏi Git

**Files:**
- Move: `C:\Users\Admin\Downloads\Dashboard.py` -> `dashboard/Dashboard.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: file dashboard local hiện có.
- Produces: dashboard local tại đường dẫn ổn định và bị Git ignore.

- [x] Xác minh source tồn tại và target chưa tồn tại.
- [x] Tạo `dashboard/` và di chuyển file bằng PowerShell.
- [x] Thêm `/dashboard/Dashboard.py`, `/dashboard/.streamlit/` và cache local vào
      `.gitignore`.
- [x] Chạy `git check-ignore -v dashboard/Dashboard.py`.

### Task 2: Thay Supabase bằng CSV public R2

**Files:**
- Modify local ignored file: `dashboard/Dashboard.py`

**Interfaces:**
- Consumes:
  `https://pub-74b943718d324227b2990146d782734c.r2.dev/v1/current/analyst/`.
- Produces: `load_data() -> pd.DataFrame` với cùng các cột mà dashboard hiện dùng.

- [x] Bỏ import SQLAlchemy, `DATABASE_URL` và `get_engine()`.
- [x] Tải ba CSV bằng `pd.read_csv`.
- [x] Merge fact với dimensions bằng `hour_key` và `district_id`.
- [x] Parse `observed_at` đã có offset Việt Nam, sort theo quận và thời gian.
- [x] Giữ nguyên logic Nowcast, AQI, forecast và UI.

### Task 3: Cài dependency và chạy thử

**Files:**
- Modify: `pyproject.toml`
- Modify: `poetry.lock`
- Modify: `docs/r2-reporting.md`

**Interfaces:**
- Consumes: dashboard local đã chuyển sang R2.
- Produces: lệnh chạy local có thể lặp lại.

- [x] Thêm `streamlit`, `plotly` và `statsmodels` vào dependency project.
- [x] Cập nhật tài liệu bằng lệnh
      `streamlit run dashboard/Dashboard.py --server.headless true`.
- [x] Kiểm tra compile và import.
- [x] Khởi động Streamlit, gọi `/_stcore/health`, rồi dừng process.
- [x] Chạy full pytest, Ruff và `git diff --check`.
