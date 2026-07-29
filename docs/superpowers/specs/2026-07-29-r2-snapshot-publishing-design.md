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

Sau bootstrap, tách workflow hiện tại thành nhiều job để dependency graph trên GitHub
Actions thể hiện rõ từng giai đoạn:

```text
1. Kiểm tra mã nguồn
    |
2. Chuẩn bị database
    |
3. Thu thập daily
    |
4. Thu thập hourly
    |
5. Thu thập AQI
    |
6. Xuất bản R2
    |
7. Tổng hợp kết quả
```

Các job ETL chạy tuần tự để tránh tăng tải Open-Meteo và giữ thứ tự trình bày dễ hiểu.
Mỗi job GitHub-hosted tự checkout và setup runtime; Poetry cache được dùng để giảm thời
gian cài lại dependencies.

Job `publish-r2` chỉ chạy khi ba job thu thập đều thành công. Job này:

- đọc manifest watermark;
- export các ngày chưa publish;
- upload object bất biến theo ngày;
- xác minh row count và checksum;
- cập nhật manifest sau cùng.

Thông thường job chỉ đọc ngày hôm qua. Nếu R2 job lỗi nhiều ngày, watermark giúp lần
chạy tiếp theo catch up các ngày chưa publish mà không đọc lại lịch sử đã xuất bản.

Manual recovery hiện có tiếp tục đồng bộ Supabase xuống PostgreSQL Docker. Giai đoạn 2
sẽ bổ sung lệnh republish một khoảng ngày cụ thể lên R2 khi cần sửa hoặc bù dữ liệu.

### Định nghĩa job

| Job ID | Tên hiển thị | Phụ thuộc | Trách nhiệm |
| --- | --- | --- | --- |
| `validate` | `1. Kiểm tra mã nguồn` | Không | Setup Python/Poetry, lint và test |
| `prepare-database` | `2. Chuẩn bị database` | `validate` | Alembic migration và seed dimensions |
| `collect-daily` | `3. Thu thập thời tiết daily` | `prepare-database` | Chạy `incremental-daily` |
| `collect-hourly` | `4. Thu thập thời tiết hourly` | `collect-daily` | Chạy `incremental-hourly` |
| `collect-aqi` | `5. Thu thập AQI hourly` | `collect-hourly` | Chạy `incremental-aqi-hourly` |
| `publish-r2` | `6. Xuất bản snapshot R2` | Ba job collect | Export và upload dữ liệu chưa publish |
| `summary` | `7. Tổng hợp kết quả` | Tất cả job | Tạo Step Summary và gửi Discord |

Job `summary` dùng `if: always()` để vẫn chạy khi một giai đoạn thất bại. Nó không biến
một workflow thất bại thành thành công; trạng thái tổng thể vẫn phản ánh kết quả các job
bắt buộc.

### Trao đổi metadata giữa các job

Mỗi job ghi output tối thiểu:

- `started_at_utc`;
- `finished_at_utc`;
- `duration_seconds`;
- `run_type`;
- `etl_run_id`;
- `rows_upserted`;
- `rows_skipped`;
- `min_date`;
- `max_date`;
- thông báo lỗi đã được loại bỏ thông tin nhạy cảm.

Job `summary` nhận outputs qua `needs` và có thể truy vấn bổ sung `monitoring.etl_runs`
bằng `etl_run_id`. Không truyền database URL hoặc R2 credentials qua job outputs hay
artifacts.

## Thời gian và GitHub Step Summary

Database và manifest tiếp tục lưu timestamp chuẩn UTC. Khi hiển thị cho người dùng,
workflow chuyển đổi sang múi giờ IANA:

```text
Asia/Ho_Chi_Minh
```

Thời gian hiển thị dùng định dạng:

```text
DD/MM/YYYY HH:mm:ss (UTC+7)
```

Cron GitHub Actions vẫn khai báo bằng UTC. Workflow ghi rõ trong Summary:

```text
Lịch cron: 18:00 UTC
Giờ Việt Nam: 01:00 ngày hôm sau (UTC+7)
```

Không cộng thủ công bảy giờ trong shell hoặc Python. Script report dùng
`zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")` để tránh logic thời gian rải rác.

Step Summary gồm:

1. Trạng thái tổng thể và trigger (`schedule` hoặc `workflow_dispatch`).
2. Bảng tiến trình từng job.
3. Bảng kết quả ETL theo run type.
4. Kết quả publish R2.
5. Khoảng dữ liệu hiện có.
6. Cảnh báo, lỗi và bước recovery đề xuất.

Bảng tiến trình:

| Bước | Trạng thái | Bắt đầu | Kết thúc | Thời lượng |
| --- | --- | --- | --- | --- |
| Kiểm tra mã nguồn | Thành công/Thất bại/Bỏ qua | Giờ Việt Nam | Giờ Việt Nam | Giây/phút |
| Chuẩn bị database | Thành công/Thất bại/Bỏ qua | Giờ Việt Nam | Giờ Việt Nam | Giây/phút |
| Daily | Thành công/Thất bại/Bỏ qua | Giờ Việt Nam | Giờ Việt Nam | Giây/phút |
| Hourly | Thành công/Thất bại/Bỏ qua | Giờ Việt Nam | Giờ Việt Nam | Giây/phút |
| AQI | Thành công/Thất bại/Bỏ qua | Giờ Việt Nam | Giờ Việt Nam | Giây/phút |
| Publish R2 | Thành công/Thất bại/Bỏ qua | Giờ Việt Nam | Giờ Việt Nam | Giây/phút |

Bảng ETL hiển thị `run_type`, `etl_run_id`, số dòng upsert, số dòng bỏ qua và min/max
date. Phần R2 hiển thị bucket, manifest version, số object, tổng byte, row count và
watermark mới nhất nhưng không hiển thị endpoint có chữ ký hoặc credentials.

Nếu một job thất bại, Summary chỉ ra job đầu tiên lỗi và lệnh recovery phù hợp. Ví dụ,
nếu ETL đã hoàn thành nhưng `publish-r2` lỗi, hướng dẫn retry publisher thay vì gọi lại
Open-Meteo.

## Kiểm thử và nghiệm thu

Bootstrap đạt yêu cầu khi:

1. Sync Supabase xuống PostgreSQL Docker thành công.
2. Ba fact table có cùng ngày lớn nhất.
3. Tổng row count trong manifest bằng tổng row count PostgreSQL theo từng bảng.
4. Mọi object có checksum SHA-256 và có thể đọc lại từ R2.
5. `manifest.json` có trạng thái `complete`.
6. Không có credential trong log, manifest hoặc Git diff.
7. Chạy lại bootstrap tạo version mới mà không làm hỏng version đang hoạt động.

Workflow hằng ngày đạt yêu cầu khi:

1. GitHub Actions graph hiển thị bảy job theo đúng dependency.
2. Job sau không chạy khi dependency bắt buộc thất bại, ngoại trừ `summary`.
3. Summary luôn được tạo và mọi thời gian hiển thị theo `Asia/Ho_Chi_Minh`.
4. Duration của từng job được tính từ timestamp UTC, không từ chuỗi đã format.
5. Row count trong Summary khớp `monitoring.etl_runs` và manifest R2.
6. Lỗi R2 không làm mất manifest hoàn chỉnh trước đó.

## Ngoài phạm vi

- Dùng R2 thay Supabase làm database.
- DirectQuery Power BI vào file R2.
- Public bucket hoặc custom domain trong giai đoạn bootstrap.
- R2 Data Catalog, R2 SQL, Iceberg hoặc Worker API.
- Xóa dữ liệu lịch sử khỏi Supabase.
