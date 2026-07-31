# Cloudflare R2 Và Power BI

Supabase là nguồn chuẩn của automation. R2 cung cấp release CSV/Parquet chỉ đọc;
Power BI không query trực tiếp Supabase nên tránh egress lặp từ các lần refresh.

## Luồng Release

Mỗi release chứa đủ sáu bảng `analyst`:

```text
v1/releases/<release-id>/analyst/<table>.parquet
v1/releases/<release-id>/analyst/<table>.csv
v1/releases/<release-id>/manifest.json
```

Publisher upload và kiểm tra kích thước/SHA-256 của 12 data object, ghi manifest,
sao chép sáu CSV sang alias ổn định rồi mới cập nhật pointer:

```text
v1/current/analyst/<table>.csv
v1/latest.json
```

Power BI đọc `v1/current`; `latest.json` và manifest dùng để kiểm chứng release.

## Cấu Hình

Biến môi trường local:

```text
LOCAL_DATABASE_URL
DATABASE_URL
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET_NAME
R2_PUBLIC_BASE_URL
```

Tạo R2 API token `Object Read & Write` giới hạn đúng bucket. Bucket có thể private
khi bootstrap; để Power BI đọc CSV, bật public access qua custom domain. Cloudflare
xác định `r2.dev` là endpoint development có rate limit, vì vậy không dùng làm nguồn
production lâu dài.

## Bootstrap Lịch Sử

Trước tiên đồng bộ các khoảng còn thiếu về PostgreSQL local:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\sync_cloud_to_local.py --lookback-days 0
```

Kiểm tra row count/min-max date, sau đó tạo release đầu tiên:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\bootstrap_r2_history.py `
  --result-json .tmp\r2-bootstrap-result.json
```

Bootstrap đọc từ `LOCAL_DATABASE_URL`; publisher hằng ngày đọc từ `DATABASE_URL`.

## Publish Hằng Ngày

Scheduled GitHub Actions chỉ publish sau khi cả daily, hourly và AQI collector thành
công. Publisher đọc watermark của manifest hiện tại, lấy mọi ngày còn thiếu đến hôm
qua theo `Asia/Ho_Chi_Minh`, ghép với snapshot hiện tại rồi kích hoạt release mới.

Chạy thủ công khi ETL đã thành công nhưng job R2 lỗi:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\publish_r2_release.py `
  --result-json .tmp\r2-publish-result.json
```

Nếu warehouse không có ngày publish yêu cầu hoặc max date của ba fact table khác
nhau, publisher dừng trước khi kích hoạt release.

## Repair Và Verify

Ưu tiên script catch-up để sửa đủ ba fact table, publish bounded range và verify:

```powershell
.\scripts\run_manual_catchup.ps1 `
  -StartDate 2026-07-28 -EndDate 2026-07-28
```

Nếu dữ liệu Supabase đã được sửa đầy đủ, có thể republish trực tiếp một khoảng:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\publish_r2_release.py `
  --start-date 2026-07-28 --end-date 2026-07-28 --force-republish
```

`--force-republish` chỉ hợp lệ với bounded range. Xác minh release active và sáu
alias mà không ghi object:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\publish_r2_release.py --verify-only
```

## Retention Và Rollback

Sau khi kích hoạt, publisher giữ ba release đủ điều kiện gần nhất: release active và
hai release trước. Release mới hơn nhưng chưa active không bị xóa bởi lần prune đó.

Repository hiện chưa có rollback CLI. Đổi riêng `v1/latest.json` không rollback dữ
liệu Power BI vì sáu `v1/current/analyst/*.csv` vẫn trỏ nội dung release mới. Rollback
đúng phải:

1. Tạm dừng publisher và Power BI refresh.
2. Chọn một release còn được giữ và kiểm tra manifest/object.
3. Khôi phục đủ sáu current CSV từ release đó, giữ đúng metadata/checksum.
4. Cập nhật `latest.json` có điều kiện theo ETag hiện tại.
5. Verify release, current aliases và chạy refresh thử.

Không thực hiện quy trình này bằng thao tác ad-hoc chưa review. Khi dữ liệu nguồn vẫn
đúng, bounded repair/republish thường an toàn hơn rollback.

## Power BI

Tạo parameter text `R2BaseUrl` trỏ tới custom domain, không có dấu `/` cuối. Tạo một
blank query `LoadR2Table`:

```powerquery
(tableName as text) as table =>
let
    Source = Csv.Document(
        Web.Contents(
            R2BaseUrl,
            [RelativePath = "v1/current/analyst/" & tableName & ".csv"]
        ),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Result = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    Result
```

Tạo sáu query gọi function:

```powerquery
= LoadR2Table("dim_district")
= LoadR2Table("dim_date")
= LoadR2Table("dim_hour")
= LoadR2Table("fact_weather_daily")
= LoadR2Table("fact_weather_hourly")
= LoadR2Table("fact_aqi_hourly")
```

Đặt kiểu dữ liệu rồi tạo quan hệ:

```text
fact_weather_daily.date_key -> dim_date.date_key
fact_weather_hourly.hour_key -> dim_hour.hour_key
fact_aqi_hourly.hour_key -> dim_hour.hour_key
dim_hour.date_key -> dim_date.date_key
fact_weather_daily.district_id -> dim_district.district_id
fact_weather_hourly.district_id -> dim_district.district_id
fact_aqi_hourly.district_id -> dim_district.district_id
```

Mỗi bảng là một query/model table, nhưng chỉ cần cấu hình một Web data source qua
`R2BaseUrl` và function dùng chung.

## Kiểm Tra

- `manifest.json` có đủ sáu table và row count dương.
- Kích thước/SHA-256 của Parquet/CSV khớp manifest.
- Max date của ba fact table đồng nhất và đạt ngày yêu cầu.
- Metadata `release-id`/`sha256` của sáu current CSV khớp release active.
- `v1/latest.json` trỏ tới manifest của release active.
- Power BI refresh được cả sáu query và quan hệ không tạo many-to-many ngoài ý muốn.
