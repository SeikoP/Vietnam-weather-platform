# Cloudflare R2 Và Công Cụ Báo Cáo

Supabase là nguồn chuẩn của automation. Cloudflare R2 cung cấp snapshot CSV/Parquet
chỉ đọc qua HTTP để các công cụ phân tích và báo cáo sử dụng mà không truy vấn trực
tiếp Supabase.

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

Công cụ báo cáo đọc dữ liệu từ `v1/current/analyst/`. `latest.json` và manifest dùng
để kiểm chứng release.

## Cấu Hình

Biến môi trường:

```text
DATABASE_URL
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET_NAME
R2_PUBLIC_BASE_URL
```

Tạo R2 API token `Object Read & Write` giới hạn đúng bucket. Để công cụ báo cáo đọc
dữ liệu, bật public access qua custom domain hoặc endpoint public phù hợp. Cloudflare
xác định `r2.dev` là endpoint development có rate limit, vì vậy không dùng làm nguồn
production lâu dài.

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
liệu báo cáo vì sáu `v1/current/analyst/*.csv` vẫn trỏ nội dung release mới. Rollback
đúng phải:

1. Tạm dừng publisher và các lịch refresh báo cáo.
2. Chọn một release còn được giữ và kiểm tra manifest/object.
3. Khôi phục đủ sáu current CSV từ release đó, giữ đúng metadata/checksum.
4. Cập nhật `latest.json` có điều kiện theo ETag hiện tại.
5. Verify release, current aliases và chạy refresh thử.

Không thực hiện quy trình này bằng thao tác ad-hoc chưa review. Khi dữ liệu nguồn vẫn
đúng, bounded repair/republish thường an toàn hơn rollback.

## Kết Nối Công Cụ Báo Cáo

Mỗi công cụ có thể tải trực tiếp sáu CSV qua HTTP từ đường dẫn:

```text
<R2_PUBLIC_BASE_URL>/v1/current/analyst/<table>.csv
```

Các bảng hiện có:

```text
dim_district
dim_date
dim_hour
fact_weather_daily
fact_weather_hourly
fact_aqi_hourly
```

Công cụ cần hỗ trợ tải CSV qua HTTP, đọc UTF-8, dùng hàng đầu làm header và đặt kiểu
dữ liệu sau khi tải. Nên cấu hình một URL gốc dùng chung thay vì tạo sáu data source
độc lập.

## Ví Dụ Với Power BI

Nguồn public development hiện dùng:

```text
https://pub-74b943718d324227b2990146d782734c.r2.dev
```

Trong Power BI, tạo blank query tên `R2Tables`, mở **Advanced Editor** rồi dán toàn bộ
nội dung `powerbi/r2_tables.pq`. Chọn xác thực `Anonymous` cho URL gốc khi được hỏi.

Tạo sáu query bằng **Reference** từ `R2Tables` và dùng lần lượt các biểu thức:

```powerquery
= R2Tables[dim_district]
= R2Tables[dim_date]
= R2Tables[dim_hour]
= R2Tables[fact_weather_daily]
= R2Tables[fact_weather_hourly]
= R2Tables[fact_aqi_hourly]
```

Đổi tên query theo tên bảng và tắt **Enable load** cho `R2Tables`. Loader chỉ khai báo
URL gốc một lần và dùng `RelativePath`, phù hợp refresh trên Power BI Service. `r2.dev`
là endpoint public có rate limit; dùng cho đồ án hoặc tải cá nhân, không coi là private.

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

Mỗi bảng vẫn là một query/model table, nhưng chỉ cần cấu hình một Web data source.

## Kiểm Tra

- `manifest.json` có đủ sáu table và row count dương.
- Kích thước/SHA-256 của Parquet/CSV khớp manifest.
- Max date của ba fact table đồng nhất và đạt ngày yêu cầu.
- Metadata `release-id`/`sha256` của sáu current CSV khớp release active.
- `v1/latest.json` trỏ tới manifest của release active.
- Công cụ báo cáo tải được cả sáu bảng và quan hệ không tạo many-to-many ngoài ý muốn.
