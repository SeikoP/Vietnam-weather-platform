# Đồng bộ Supabase về PostgreSQL cục bộ

Luồng này chỉ chạy khi bạn chủ động gọi lệnh. Nó sao chép dữ liệu từ Supabase sang
PostgreSQL riêng của dự án tại `localhost:5433`, không dùng và không thay đổi container
PostgreSQL của dự án Tiki.

## 1. Khởi động PostgreSQL cục bộ

Mở PowerShell tại thư mục dự án:

```powershell
$env:VWDP_POSTGRES_PASSWORD = "<local-secret>"
docker compose up -d postgres
docker compose ps postgres
```

Giữ mật khẩu ngoài Git và không ghi giá trị thật vào `.env.example`.

Nếu volume đã được tạo, đổi `VWDP_POSTGRES_PASSWORD` rồi restart container sẽ không
đổi mật khẩu trong PostgreSQL. Hãy đổi tương tác để mật khẩu không xuất hiện trong
command history:

```powershell
docker exec -it vwdp-postgres psql -U vwdp -d vwdp
```

Tại dấu nhắc `psql`, chạy:

```text
\password vwdp
\q
```

Sau đó cập nhật `VWDP_POSTGRES_PASSWORD` và phần mật khẩu đã URL-encode trong
`LOCAL_DATABASE_URL` ở phiên PowerShell dùng để vận hành. Hãy thực hiện bước này trước
khi cho thành viên kết nối.

## 2. Chạy đồng bộ thủ công

Tài khoản cloud nên là tài khoản chỉ có quyền đọc schema cần đồng bộ.
Nếu mật khẩu chứa ký tự đặc biệt, hãy URL-encode phần mật khẩu trong connection string.

```powershell
$env:CLOUD_DATABASE_URL = "<read-only-supabase-url>"
$env:LOCAL_DATABASE_URL = "postgresql+psycopg://vwdp:<url-encoded-password>@localhost:5433/vwdp"
.venv\Scripts\python.exe scripts\sync_cloud_to_local.py
```

Lần đầu, local chưa có watermark nên lệnh lấy toàn bộ dữ liệu hiện có. Những lần sau,
lệnh lấy toàn bộ khóa mới hơn watermark local, kể cả khi nhiều ngày chưa chạy. Mặc định
không đọc lại dữ liệu cũ để giảm egress. Chỉ đặt `--lookback-days` khi cần kiểm tra lại
các bản ghi có thể bị sửa muộn; đây là cửa sổ đọc lại, không phải giới hạn khoảng trống:

```powershell
.venv\Scripts\python.exe scripts\sync_cloud_to_local.py --lookback-days 7
```

Chỉ dùng `--full` khi thực sự cần tải lại toàn bộ vì tùy chọn này làm tăng egress:

```powershell
.venv\Scripts\python.exe scripts\sync_cloud_to_local.py --full
```

## 3. Kết nối Power BI và thành viên

Power BI kết nối tới:

- Server: `localhost:5433` nếu chạy trên cùng máy.
- Database: `vwdp`.
- Import mode: mỗi lần refresh, Power BI đọc dữ liệu từ local thay vì Supabase.

Với máy thành viên khác, không dùng `localhost`; dùng IP hoặc hostname của máy chạy
Docker, đồng thời chỉ mở cổng `5433` trong mạng nội bộ/VPN cho các máy cần thiết.
Không công khai PostgreSQL trực tiếp ra Internet.

Nên tạo một PostgreSQL role chỉ đọc riêng cho Power BI/thành viên, cấp `CONNECT`,
`USAGE` trên các schema cần xem và `SELECT` trên các bảng tương ứng. Không chia sẻ
tài khoản `vwdp` có quyền ghi.

## 4. Cách hiểu kết quả

Lệnh in số dòng đã đọc và upsert theo từng bảng nhưng không in URL hoặc mật khẩu.
Chỉ bảng hiện tại được rollback nếu lỗi; các bảng đã hoàn tất trước đó vẫn được giữ.
Chạy lại cùng lệnh là an toàn vì dữ liệu được upsert theo khóa duy nhất.
