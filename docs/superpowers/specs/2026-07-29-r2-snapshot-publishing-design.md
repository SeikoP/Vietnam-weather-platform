# Thiết kế xuất bản snapshot dữ liệu lên Cloudflare R2

## Mục tiêu

Giảm Supabase egress khi thành viên và Power BI đọc dữ liệu bằng cách giữ Supabase
PostgreSQL làm nguồn dữ liệu chuẩn, đồng thời xuất bản bản sao chỉ đọc dưới dạng file
tĩnh trên Cloudflare R2.

Thiết kế gồm hai giai đoạn:

1. Bootstrap toàn bộ lịch sử hiện có từ PostgreSQL Docker `vwdp-postgres` lên R2.
2. Bổ sung job GitHub Actions để xuất bản dữ liệu mới sau mỗi cron ETL thành công.

## Kiến trúc

```text
Open-Meteo
    |
    v
Python ETL
    |
    v
Supabase PostgreSQL (system of record)
    |
    +--> PostgreSQL Docker local (recovery/manual sync)
    |
    +--> Cloudflare R2 (read-only BI snapshots)
              |
              +--> Power BI
              +--> Thành viên
```

Supabase chịu trách nhiệm upsert, ràng buộc quan hệ, API và monitoring. R2 chỉ là lớp
phân phối dữ liệu đã commit, không thay thế database và không nhận chỉnh sửa trực tiếp.

## Phạm vi giai đoạn 1

Giai đoạn đầu chỉ thực hiện:

- xác minh PostgreSQL Docker đã đồng bộ với Supabase;
- tạo bucket R2 riêng cho snapshot;
- export sáu bảng `analyst` từ PostgreSQL Docker;
- upload dữ liệu lịch sử lên R2;
- kiểm tra row count, khoảng thời gian và checksum;
- publish `manifest.json` sau khi tất cả object hợp lệ.

Giai đoạn đầu không sửa workflow cron, không đổi Power BI connection và không xóa dữ
liệu khỏi Supabase hoặc PostgreSQL Docker.

## Nguồn bootstrap

Nguồn bootstrap là PostgreSQL Docker:

- container: `vwdp-postgres`;
- endpoint local: `localhost:5433`;
- database: `vwdp`;
- schema: `analyst`.

Trước khi export, chạy script hiện có:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\sync_cloud_to_local.py --lookback-days 1
```

Bootstrap chỉ được tiếp tục khi ba fact table có cùng `max(observed_date)`.

## Dataset được xuất bản

Giữ nguyên star schema hiện tại:

- `dim_district`;
- `dim_date`;
- `dim_hour`;
- `fact_weather_daily`;
- `fact_weather_hourly`;
- `fact_aqi_hourly`.

CSV được chọn làm định dạng phục vụ Power BI qua Web connector. Các dimension nhỏ được
xuất thành một file. `dim_hour` và ba fact table được chia theo tháng để tránh một
object quá lớn và chuẩn bị cho cơ chế incremental sau này.

## Bố cục object R2

```text
v1/
  dimensions/
    dim_district.csv
    dim_date.csv
  history/
    dim_hour/year=2026/month=07/data.csv
    fact_weather_daily/year=2026/month=07/data.csv
    fact_weather_hourly/year=2026/month=07/data.csv
    fact_aqi_hourly/year=2026/month=07/data.csv
  manifests/
    bootstrap-20260729T151500Z.json
  manifest.json
```

Các object dữ liệu được upload trước. `v1/manifest.json` chỉ được cập nhật sau khi mọi
file đã upload và xác minh thành công. Power BI chỉ đọc manifest hiện hành.

## Manifest

Manifest chứa:

- schema version;
- thời điểm tạo theo UTC;
- nguồn dữ liệu;
- ngày nhỏ nhất và lớn nhất;
- danh sách object;
- table name và partition;
- row count;
- kích thước byte;
- SHA-256 checksum;
- trạng thái `complete`.

Manifest không chứa database URL, R2 credentials hoặc thông tin bí mật khác.

## Cấu hình R2

Bucket mặc định:

```text
vwdp-snapshots
```

Giai đoạn bootstrap giữ bucket private. R2 API token chỉ có quyền `Object Read & Write`
trên bucket này.

Biến môi trường:

```text
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET_NAME
```

GitHub Actions về sau lưu access key và secret key trong GitHub Secrets; account ID và
bucket name lưu trong GitHub Variables.

## Thành phần code dự kiến

- `src/export/r2_snapshot.py`: truy vấn, partition, serialize, checksum và manifest.
- `scripts/bootstrap_r2_history.py`: CLI bootstrap từ PostgreSQL local.
- `tests/unit/test_r2_snapshot.py`: kiểm tra partition, row count, checksum và manifest.
- `docs/r2-snapshots.md`: hướng dẫn vận hành bằng tiếng Việt.
- `pyproject.toml`: thêm `boto3` làm S3-compatible client.

Exporter dùng SQLAlchemy streaming để không nạp toàn bộ hai fact table hourly vào RAM.
Mỗi partition được ghi vào thư mục tạm riêng và xóa sau khi upload thành công.

## Xử lý lỗi

- Lỗi query PostgreSQL: dừng trước khi upload partition đó.
- Lỗi upload: không cập nhật `manifest.json`; snapshot trước vẫn hợp lệ.
- Row count hoặc checksum không khớp: đánh dấu bootstrap thất bại và giữ object dưới
  manifest timestamp để điều tra.
- Chạy lại: upload vào manifest timestamp mới; không ghi đè snapshot hoàn chỉnh cũ.
- Không tự xóa object lỗi trong lần triển khai đầu; cleanup là thao tác vận hành riêng.

## Giai đoạn 2: publish hằng ngày

Sau bootstrap, thêm job `publish-r2` phụ thuộc job ETL:

```text
ETL commit Supabase
    |
    v
publish-r2
    |
    +--> đọc manifest watermark
    +--> export các ngày chưa publish
    +--> upload object bất biến theo ngày
    +--> cập nhật manifest sau cùng
```

Thông thường job chỉ đọc ngày hôm qua. Nếu R2 job lỗi nhiều ngày, watermark giúp job
tiếp theo catch up các ngày chưa publish mà không đọc lại lịch sử đã xuất bản.

Manual recovery hiện có tiếp tục đồng bộ Supabase xuống PostgreSQL Docker. Giai đoạn 2
sẽ bổ sung lệnh republish một khoảng ngày cụ thể lên R2 khi cần sửa hoặc bù dữ liệu.

## Kiểm thử và nghiệm thu

Bootstrap đạt yêu cầu khi:

1. Sync Supabase xuống PostgreSQL Docker thành công.
2. Ba fact table có cùng ngày lớn nhất.
3. Tổng row count trong manifest bằng tổng row count PostgreSQL theo từng bảng.
4. Mọi object có checksum SHA-256 và có thể đọc lại từ R2.
5. `manifest.json` có trạng thái `complete`.
6. Không có credential trong log, manifest hoặc Git diff.
7. Chạy lại bootstrap tạo version mới mà không làm hỏng version đang hoạt động.

## Ngoài phạm vi

- Dùng R2 thay Supabase làm database.
- DirectQuery Power BI vào file R2.
- Public bucket hoặc custom domain trong giai đoạn bootstrap.
- R2 Data Catalog, R2 SQL, Iceberg hoặc Worker API.
- Xóa dữ liệu lịch sử khỏi Supabase.
