# Vận hành snapshot Cloudflare R2

## Luồng chính

Supabase là nguồn chuẩn của automation. R2 chứa release Parquet/CSV chỉ đọc cho Power
BI. Bootstrap lịch sử đi trực tiếp từ PostgreSQL local; publisher hằng ngày chỉ query
khoảng còn thiếu từ Supabase.

```text
Open-Meteo -> Supabase -> R2 release -> Power BI
PostgreSQL local ------> R2 release đầu tiên
```

Project hiện có 30 quận/huyện Hà Nội và sáu bảng `analyst`.

## Cấu hình Cloudflare

1. Dùng bucket `vwdp`, storage class Standard.
2. Tạo R2 API token `Object Read & Write`, scope đúng bucket.
3. Lưu Account ID, Access Key ID và Secret Access Key vào `.env` local hoặc GitHub
   Secrets/Variables; không ghi vào source code.
4. Bootstrap có thể chạy khi bucket private.
5. Khi kết nối Power BI, bật custom domain cho bucket. `r2.dev` chỉ dùng kiểm thử.

Biến local:

```text
LOCAL_DATABASE_URL
DATABASE_URL
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET_NAME
R2_PUBLIC_BASE_URL
```

Code vẫn đọc `ACCESS_KEY_ID` và `SECRET_ACCESS_KEY` để tương thích môi trường local
cũ. Cấu hình mới nên dùng hai tên có prefix `R2_` để tránh nhầm với dịch vụ khác.

GitHub Secrets:

```text
DATABASE_URL
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
DISCORD_WEBHOOK_URL
```

GitHub Variables:

```text
R2_ACCOUNT_ID
R2_BUCKET_NAME
R2_PUBLIC_BASE_URL
DISCORD_NOTIFICATIONS_ENABLED
```

## Bootstrap lịch sử

Đồng bộ mọi khoảng trống từ Supabase về PostgreSQL local trước, không reread mặc định:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\sync_cloud_to_local.py --lookback-days 0
```

Kiểm tra số dòng:

```powershell
docker exec vwdp-postgres psql -U vwdp -d vwdp -X -c "
SELECT 'dim_district', count(*) FROM analyst.dim_district
UNION ALL SELECT 'dim_date', count(*) FROM analyst.dim_date
UNION ALL SELECT 'dim_hour', count(*) FROM analyst.dim_hour
UNION ALL SELECT 'fact_weather_daily', count(*) FROM analyst.fact_weather_daily
UNION ALL SELECT 'fact_weather_hourly', count(*) FROM analyst.fact_weather_hourly
UNION ALL SELECT 'fact_aqi_hourly', count(*) FROM analyst.fact_aqi_hourly;
"
```

Publish release đầu tiên:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\bootstrap_r2_history.py `
  --result-json .tmp\r2-bootstrap-result.json
```

Xác minh lại mà không ghi object:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\bootstrap_r2_history.py --verify-only
```

## Daily publish và repair

Daily publisher tự lấy từ watermark đến hôm qua theo `Asia/Ho_Chi_Minh`:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\publish_r2_release.py
```

ETL thành công nhưng R2 lỗi: chạy lại đúng lệnh trên, không gọi lại Open-Meteo.

Repair một khoảng đã publish:

```powershell
.\.venv\Scripts\python.exe -m dotenv run -- `
  .\.venv\Scripts\python.exe scripts\publish_r2_release.py `
  --start-date 2026-07-28 --end-date 2026-07-28 --force-republish
```

## Power BI

Publisher duy trì sáu URL CSV ổn định dưới `v1/current/analyst/`. Power BI vẫn cần
sáu query vì warehouse có sáu bảng và quan hệ riêng, nhưng chỉ cấu hình Web source
một lần.

Tạo parameter text `R2BaseUrl`:

```text
https://pub-74b943718d324227b2990146d782734c.r2.dev
```

Tạo một blank query tên `LoadR2Table`, mở Advanced Editor và dán:

```powerquery
(tableName as text) as table =>
let
    Source = Csv.Document(
        Web.Contents(
            R2BaseUrl,
            [
                RelativePath =
                    "v1/current/analyst/" & tableName & ".csv"
            ]
        ),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Result = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    Result
```

Tạo sáu blank query, đặt tên đúng bảng và dùng một dòng tương ứng:

```powerquery
= LoadR2Table("dim_district")
= LoadR2Table("dim_date")
= LoadR2Table("dim_hour")
= LoadR2Table("fact_weather_daily")
= LoadR2Table("fact_weather_hourly")
= LoadR2Table("fact_aqi_hourly")
```

Đây là sáu bảng model nhưng không phải sáu lần thiết lập `Get Data -> Web`. Đặt Power
BI refresh sau GitHub Actions tối thiểu 30 phút. `latest.json` và manifest vẫn dùng
cho kiểm chứng release và rollback, không còn bắt buộc trong Power Query.

## Dashboard Streamlit local

`dashboard/Dashboard.py` là file local được khai báo trong `.gitignore`; file không
được commit vì đây là dashboard thử nghiệm riêng. Dashboard không đọc `.env` và
không kết nối Supabase. Base URL public được khai báo trực tiếp trong file:

```text
https://pub-74b943718d324227b2990146d782734c.r2.dev/v1/current/analyst
```

Dashboard chỉ tải ba file cần cho AQI:

```text
dim_district.csv
dim_hour.csv
fact_aqi_hourly.csv
```

Chạy local:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\Dashboard.py
```

URL public chỉ cung cấp nội dung object. Quyền ghi/xóa vẫn yêu cầu R2 API credential
được lưu trong GitHub Secrets hoặc `.env` local của pipeline; dashboard không sử
dụng các credential đó.

## Rollback

Release là bất biến. Để rollback, thay `v1/latest.json` bằng pointer tới một trong hai
release trước. Không sửa trực tiếp các file trong release. Chỉ xóa release cũ sau khi
release mới đã active và không còn Power BI refresh đang chạy.
