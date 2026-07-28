# Metabase self-host với Tailscale và ngrok

Metabase chạy trong Docker và đọc warehouse PostgreSQL local bằng role
`metabase_reader`. Thành viên làm dashboard qua Tailscale; ngrok chỉ chia sẻ dashboard
đã bật public link.

## Chuẩn bị biến môi trường

Chạy trong PowerShell riêng tư tại thư mục dự án:

```powershell
$env:VWDP_POSTGRES_PASSWORD = Read-Host "Local PostgreSQL password"
$env:LOCAL_DATABASE_URL = Read-Host "Local PostgreSQL URL"
$env:METABASE_DB_PASSWORD = Read-Host "Metabase DB password"
$env:METABASE_ENCRYPTION_SECRET_KEY = Read-Host "Metabase encryption key"
$env:METABASE_WAREHOUSE_PASSWORD = Read-Host "Warehouse reader password"
$env:METABASE_ADMIN_EMAIL = "admin@example.com"
$env:METABASE_ADMIN_PASSWORD = Read-Host "Metabase admin password"
$env:METABASE_ADMIN_FIRST_NAME = "VWDP"
$env:METABASE_ADMIN_LAST_NAME = "Admin"
$env:METABASE_SITE_URL = "http://localhost:3000"
```

`Read-Host` ở đây trả về chuỗi dùng trong environment của process hiện tại. Không chạy
trên terminal đang được ghi hình/chia sẻ. Dự án không lưu các secret này.

Tạo encryption key base64 ngẫu nhiên bằng .NET rồi gán trực tiếp, không in ra màn hình:

```powershell
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$env:METABASE_ENCRYPTION_SECRET_KEY = [Convert]::ToBase64String($bytes)
```

## Khởi động và thiết lập

```powershell
docker compose up -d postgres metabase-db metabase metabase-public-gateway
docker compose ps postgres metabase-db metabase metabase-public-gateway
.venv\Scripts\python.exe scripts\setup_metabase.py
```

Metabase local: `http://localhost:3000`.

## Thành viên làm dashboard qua Tailscale

Đăng nhập Tailscale tương tác một lần:

```powershell
tailscale up
```

Sau đó:

```powershell
scripts\start_metabase_tailnet.ps1
tailscale serve status
```

Mời thành viên vào tailnet và tạo tài khoản Metabase riêng cho từng người. Không chia
sẻ tài khoản admin.

## Chia sẻ dashboard công khai qua ngrok

Trong Metabase, mở dashboard, chọn Sharing và tạo public link. Chỉ lấy phần path dạng
`/public/dashboard/{dashboard-uuid}`.

```powershell
$env:NGROK_AUTHTOKEN = Read-Host "ngrok authtoken"
$env:NGROK_DOMAIN = "assigned-domain.ngrok-free.app"
$env:METABASE_PUBLIC_DASHBOARD_PATH = "/public/dashboard/123e4567-e89b-12d3-a456-426614174000"
scripts\start_public_dashboard_tunnel.ps1
```

Terminal ngrok phải được giữ mở. Ai có URL đều xem được dashboard. Thu hồi truy cập
bằng cách xóa public link trong Metabase. Endpoint ngrok không chuyển tiếp root, login,
admin hoặc private API của Metabase.

## Cập nhật dữ liệu thủ công

Sau khi đặt URL cloud đã rotate:

```powershell
$env:CLOUD_DATABASE_URL = Read-Host "Rotated cloud PostgreSQL URL"
.venv\Scripts\python.exe scripts\sync_cloud_to_local.py
```

Không có lịch chạy nền. Dashboard hiển thị dữ liệu của lần sync thành công gần nhất.
