# Thiết kế xuất bản warehouse lên Cloudflare R2

## Kết luận

Supabase PostgreSQL là nguồn dữ liệu chuẩn của pipeline production. Cloudflare R2 là
lớp phân phối chỉ đọc cho Power BI và member. Dữ liệu lịch sử ban đầu được bootstrap
trực tiếp từ PostgreSQL local; các lần chạy hằng ngày chỉ đọc phần còn thiếu từ
Supabase theo watermark.

Project hiện phục vụ 30 quận/huyện Hà Nội. R2 phản chiếu sáu bảng trong schema
`analyst`; không mở rộng sang 63 tỉnh/thành trong phạm vi này.

## Luồng dữ liệu

```text
Open-Meteo
  -> GitHub Actions ETL
  -> Supabase PostgreSQL
  -> R2 publisher đọc delta theo watermark
  -> merge với Parquet của release hiện tại bằng DuckDB
  -> release mới gồm Parquet + CSV
  -> cập nhật latest.json cuối cùng
  -> Power BI đọc CSV qua custom domain
```

Không dual-write trực tiếp từ extractor vào Supabase và R2. R2 chỉ được publish sau
khi ba ETL scheduled hoàn tất. Nếu R2 lỗi, có thể chạy lại publisher mà không gọi lại
Open-Meteo.

## Object layout

Một bucket chỉ chứa dữ liệu thời tiết có thể công khai:

```text
v1/
  latest.json
  current/
    analyst/
      <table>.csv
  releases/
    <release_id>/
      manifest.json
      analyst/
        dim_district.parquet
        dim_date.parquet
        dim_hour.parquet
        fact_weather_daily.parquet
        fact_weather_hourly.parquet
        fact_aqi_hourly.parquet
        dim_district.csv
        dim_date.csv
        dim_hour.csv
        fact_weather_daily.csv
        fact_weather_hourly.csv
        fact_aqi_hourly.csv
```

`release_id` dùng timestamp UTC có thể sắp xếp, ví dụ `20260729T181500Z`. Manifest
ghi cả UTC và `Asia/Ho_Chi_Minh`. Mỗi release bất biến; `latest.json` là object duy
nhất được thay thế và luôn được upload cuối cùng. Giữ tối thiểu release hiện tại và
hai release trước để rollback.

Sau khi kiểm tra release bất biến, publisher copy sáu CSV sang
`v1/current/analyst/<table>.csv` và xác minh size/checksum. Các alias này là giao diện
ổn định cho Power BI; `latest.json` chỉ được activate sau khi toàn bộ alias thành công.

Không lưu PostgreSQL dump trong bucket public. Backup database là luồng riêng, ngoài
phạm vi publisher Power BI.

## Định dạng

- Parquet là trạng thái chuẩn để GitHub Actions tải về và merge.
- CSV UTF-8 là giao diện ổn định cho Power BI Web connector.
- JSON dùng cho manifest và con trỏ release.
- Null được xuất thành chuỗi trống trong CSV; ngày và timestamp dùng ISO 8601.
- Thứ tự cột lấy từ SQLAlchemy model và không phụ thuộc thứ tự trả về ngẫu nhiên.

## Mapping bảng và khóa

| Bảng | Khóa upsert |
| --- | --- |
| `dim_district` | `district_id` |
| `dim_date` | `date_key` |
| `dim_hour` | `hour_key` |
| `fact_weather_daily` | `district_id, date_key` |
| `fact_weather_hourly` | `district_id, hour_key` |
| `fact_aqi_hourly` | `district_id, hour_key` |

Merge dimension trước fact. Khi source và snapshot có cùng khóa, source thay toàn bộ
giá trị của row cũ. Chạy lại cùng một khoảng ngày phải cho cùng row count và không
tạo duplicate.

## Bootstrap

Bootstrap đọc `LOCAL_DATABASE_URL`, stream toàn bộ sáu bảng từ PostgreSQL local,
ghi Parquet và CSV, kiểm tra row count/PK/FK/checksum rồi upload release đầu tiên.
Chỉ sau khi toàn bộ 12 data object và manifest tồn tại mới ghi `v1/latest.json`.

## Daily publish và repair

Daily publisher đọc `v1/latest.json`. Watermark mặc định là `max_date` của release;
publisher lấy mọi khoảng thiếu từ `watermark + 1` đến ngày đích, không mặc định đọc
lại ba ngày.

Fact hourly và AQI lọc theo `analyst.dim_hour.observed_date`. `dim_hour` lấy cùng
khoảng ngày; hai dimension nhỏ còn lại được đọc toàn bộ để phản ánh thay đổi seed.

Repair dữ liệu đã publish bắt buộc truyền `--start-date`, `--end-date` và
`--force-republish`. Delete không được suy ra từ incremental upsert; một full
bootstrap/reconciliation mới loại bỏ được row đã xóa ở source.

## Tính nguyên tử và lỗi

Publisher upload vào prefix release mới, kiểm tra `head_object`, size, SHA-256 và row
count, sau đó mới thay `latest.json`. Release chưa hoàn tất không được active.

Workflow dùng một concurrency group cho ETL và R2 publisher. Nếu `latest.json` thay
đổi kể từ khi bắt đầu, publisher dừng thay vì ghi đè release của workflow khác.

Failure behavior:

- ETL lỗi: không chạy publisher.
- Publisher lỗi trước activate: Power BI tiếp tục dùng release cũ.
- Activate lỗi: release mới tồn tại nhưng chưa active; retry được.
- Summary/Discord lỗi: không làm thay đổi trạng thái ETL hoặc release.

## GitHub Actions

Workflow có bảy job hiển thị:

1. `validate`
2. `prepare-database`
3. `collect-daily`
4. `collect-hourly`
5. `collect-aqi`
6. `publish-r2`
7. `summary`

R2 download, merge, validate và upload là các step trong cùng `publish-r2` job để
không truyền snapshot lớn qua GitHub artifacts. Manual demo ETL không tự publish R2.
Publisher có thể được chạy thủ công theo khoảng ngày để repair.

## Cấu hình

GitHub Secrets:

- `DATABASE_URL`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `DISCORD_WEBHOOK_URL`

GitHub Variables:

- `R2_ACCOUNT_ID`
- `R2_BUCKET_NAME`
- `R2_PUBLIC_BASE_URL`
- `DISCORD_NOTIFICATIONS_ENABLED`

Local bootstrap dùng thêm `LOCAL_DATABASE_URL`. Không log URL database, access key,
secret key hoặc exception chứa credential.

## Power BI

Power Query dùng hostname cố định từ `R2_PUBLIC_BASE_URL` và `Web.Contents` với
`RelativePath`. Một function chung đọc `v1/current/analyst/<table>.csv`; sáu query
bảng chỉ truyền tên bảng. Scheduled refresh đặt sau workflow ít nhất 30 phút.
