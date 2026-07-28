# Thiết kế đồng bộ Supabase xuống PostgreSQL local

## Mục tiêu

Tạo một lệnh chạy thủ công để đồng bộ dữ liệu thời tiết và AQI từ Supabase PostgreSQL
xuống một PostgreSQL Docker riêng của dự án. Thành viên sẽ kết nối vào database local
thay vì truy vấn trực tiếp Supabase, qua đó giảm egress và tránh chia sẻ tài khoản
`postgres` của cloud.

Mỗi lần chạy phải đưa local tới trạng thái mới nhất tại thời điểm đó mà không tải lại
toàn bộ lịch sử. Lần chạy đầu tiên trên database local trống bắt buộc tải đầy đủ dữ liệu.

## Phạm vi

### Bao gồm

- PostgreSQL Docker riêng tên `vwdp-postgres`, database `vwdp`, cổng host `5433`.
- Volume riêng để giữ dữ liệu qua các lần khởi động lại container.
- Script Python chạy thủ công từ repository.
- Tự áp dụng Alembic migrations hiện có lên database local trước khi đồng bộ.
- Đồng bộ các bảng:
  - `analyst.dim_district`
  - `analyst.dim_date`
  - `analyst.dim_hour`
  - `analyst.fact_weather_daily`
  - `analyst.fact_weather_hourly`
  - `analyst.fact_aqi_hourly`
- Đồng bộ tăng dần theo watermark local, có lookback mặc định ba ngày.
- Upsert idempotent và báo cáo số dòng đã đọc/ghi theo bảng.
- Chế độ `--full` để dựng lại dữ liệu local khi người vận hành chủ động yêu cầu.
- Kiểm thử unit cho tính watermark, phạm vi lookback, thứ tự bảng và hành vi upsert.

### Không bao gồm

- Không thay đổi ETL cloud hoặc GitHub Actions hiện tại.
- Không tạo lịch chạy tự động.
- Không sửa `.env` hoặc đưa credential vào source control.
- Không dùng chung container `tiki-data-pipeline-postgres-1`.
- Không tự động cấp tài khoản cho từng thành viên trong phiên bản đầu.
- Không xóa dữ liệu cloud sau khi đồng bộ.

## Cấu hình

Script nhận hai URL qua biến môi trường:

- `CLOUD_DATABASE_URL`: URL Supabase chỉ dùng để đọc.
- `LOCAL_DATABASE_URL`: URL PostgreSQL Docker dùng để migrate và ghi dữ liệu.

`.env.example` chỉ ghi placeholder, không chứa credential thật. Khi chạy thủ công,
người vận hành đặt biến môi trường trong PowerShell hoặc sử dụng cơ chế secret cục bộ
ngoài repository.

PostgreSQL local dùng cổng `5433` để không xung đột container Tiki đang chiếm cổng
`5432`.

## Giao diện lệnh

Lệnh mặc định:

```powershell
.venv\Scripts\python.exe scripts\sync_cloud_to_local.py
```

Tùy chọn:

```text
--lookback-days N  Số ngày gần nhất được đọc lại và upsert, mặc định 3.
--batch-size N      Số dòng mỗi batch ghi local, mặc định 1000.
--full              Đọc lại toàn bộ bảng fact; không mặc định và phải chủ động chỉ định.
```

Script từ chối chạy nếu:

- Thiếu một trong hai database URL.
- Cloud URL và local URL trỏ cùng một database.
- `--lookback-days` âm hoặc `--batch-size` không dương.
- Không kết nối được cloud hoặc local.
- Schema cloud không có đủ bảng bắt buộc.

## Kiến trúc

### Docker

`docker-compose.yml` bổ sung service `postgres`:

```text
container_name: vwdp-postgres
image: postgres:17-alpine
host port: 5433
container port: 5432
database: vwdp
volume: vwdp_postgres_data
healthcheck: pg_isready
```

Password local được truyền qua biến môi trường Compose bắt buộc
`VWDP_POSTGRES_PASSWORD`; Compose từ chối khởi động nếu biến chưa được đặt. Không có
password mặc định trong repository.

### Thành phần Python

- `src/sync/cloud_to_local.py`
  - Chứa cấu hình bảng, tính cutoff/watermark, đọc theo batch và upsert.
  - Không đọc trực tiếp biến môi trường và không xử lý CLI để có thể unit test độc lập.
- `scripts/sync_cloud_to_local.py`
  - Parse arguments và biến môi trường.
  - Tạo hai SQLAlchemy engine.
  - Chạy migration local, gọi sync service và in summary.
- `tests/unit/test_cloud_to_local_sync.py`
  - Kiểm tra hành vi thuần và SQL/batch orchestration qua dependency injection.

Không tái sử dụng `SessionLocal`, vì `SessionLocal` chỉ đại diện một `DATABASE_URL`,
trong khi tác vụ này cần hai database đồng thời.

## Luồng dữ liệu

Thứ tự đồng bộ cố định để giữ toàn vẹn khóa ngoại:

```text
dim_district
→ dim_date
→ dim_hour
→ fact_weather_daily
→ fact_weather_hourly
→ fact_aqi_hourly
```

### Dimension

- `dim_district` nhỏ, được đọc và upsert đầy đủ mỗi lần.
- `dim_date` đọc các `date_key` lớn hơn `max(date_key)` ở local; `--full` đọc toàn bộ.
- `dim_hour` đọc các `hour_key` lớn hơn `max(hour_key)` ở local; lookback bổ sung các
  giờ có `observed_at` từ cutoff trở đi.

### Fact

Watermark được tính riêng theo từng quận:

- Daily: `max(date_key)` theo `district_id`.
- Hourly/AQI: `max(hour_key)` theo `district_id`.

Truy vấn cloud trả dòng khi thỏa ít nhất một điều kiện:

1. Khóa lớn hơn watermark local của quận đó.
2. Thời gian quan sát nằm trong lookback tính từ thời điểm chạy.
3. `--full` được bật.

Lookback không phải lịch chạy. Nếu script chạy ngày 20/08 thì nó lấy toàn bộ dòng mới
tới thời điểm đó và đọc lại dữ liệu từ 17/08 tới 20/08 khi dùng mặc định ba ngày.

### Upsert

Khóa conflict:

- Daily: `(district_id, date_key)`.
- Hourly/AQI: `(district_id, hour_key)`.
- Dimension: primary key tương ứng.

Mọi cột không thuộc khóa được cập nhật bằng giá trị cloud. Chạy lại cùng dữ liệu không
tạo bản ghi trùng.

## Tính nhất quán và phục hồi lỗi

- Kết nối cloud mở transaction read-only.
- Mỗi bảng local được ghi trong một transaction riêng.
- Batch hiện tại rollback nếu lỗi; các bảng đã hoàn tất trước đó được giữ lại.
- Lần chạy tiếp theo tự tiếp tục từ watermark local nên không cần file state riêng.
- Summary chỉ in số dòng và tên bảng, không in URL hoặc credential.
- Không thực hiện delete local khi một dòng biến mất trên cloud.

Thiết kế watermark không tự phát hiện lỗ hổng cũ hơn lookback. Người vận hành dùng
`--full` khi cần đối soát hoặc dựng lại toàn bộ.

## Egress

- Lần đầu local trống tạo egress tương ứng toàn bộ dữ liệu được tải.
- Các lần sau chỉ tạo egress cho dòng mới và lookback ba ngày.
- Không chạy `SELECT *` toàn bảng ở chế độ mặc định.
- Query dimension/fact chỉ chọn đúng các cột thuộc model hiện tại.
- Thành viên đọc local không tạo Supabase egress.

## Bảo mật

- Không ghi cloud/local password vào code, migration, log hoặc tài liệu.
- Không sửa hoặc đọc lại credential từ `.env` trong quá trình triển khai.
- Cloud credential nên thuộc role read-only riêng thay vì `postgres`.
- Database local không mở ra Internet; chỉ mở trong LAN hoặc localhost.
- Tài khoản Power BI/thành viên local chỉ cần `CONNECT`, `USAGE` trên schema
  `analyst`, và `SELECT` trên các bảng phân tích.

## Kiểm thử và xác nhận

### Unit

- Database local trống tạo truy vấn full lần đầu.
- Watermark theo từng quận chỉ lấy khóa mới hơn.
- Lookback đọc lại đúng khoảng ba ngày nhưng không thay đổi lịch chạy.
- `--full` bỏ qua watermark.
- Batch upsert dùng đúng conflict key.
- Thứ tự dimension trước fact.
- URL cloud/local giống nhau bị từ chối.
- Lỗi một batch rollback transaction của bảng đó.

### Integration local

1. Khởi động `vwdp-postgres`.
2. Chạy sync lần đầu với phạm vi kiểm thử nhỏ hoặc database fixture.
3. Ghi nhận row count local.
4. Chạy lại không có dữ liệu cloud mới.
5. Xác nhận không có duplicate và số dòng local không đổi.
6. Thêm fixture cloud mới, chạy lại và xác nhận chỉ dòng mới được chèn.

### Repository

- `pytest`
- `ruff check .`
- Kiểm tra `docker compose config`.
- Kiểm tra migration local tới `head`.

## Tiêu chí hoàn thành

- Một lệnh thủ công dựng/cập nhật database local thành công.
- Lần đầu tải đầy đủ; lần sau chỉ tải dòng mới cộng lookback.
- Có thể chạy lại sau lỗi mà không tạo duplicate.
- Không chạm container/database Tiki.
- Không thay đổi ETL cloud.
- Không làm lộ credential.
- Test và lint liên quan đều pass.
