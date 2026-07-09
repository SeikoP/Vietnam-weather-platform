# Runbook Demo ETL

## Kịch Bản

1. Mở sơ đồ kiến trúc.
2. Chạy ETL cho 1-2 quận/huyện.
3. Xem `monitoring.etl_runs` và `monitoring.etl_logs`.
4. Gọi API hoặc mở Power BI.

## Lệnh

```powershell
poetry run vwdp-etl --run-type incremental-daily --district-id 1 --district-id 2 --request-delay-seconds 0
```

## GitHub Actions

Chọn workflow `Daily ETL`, bấm `Run workflow`, rồi chọn một preset:

| Nhu cầu | `quick_preset` |
| --- | --- |
| Demo daily nhỏ | `demo-daily-2-districts` |
| Demo hourly nhỏ | `demo-hourly-2-districts` |
| Demo AQI nhỏ | `demo-aqi-2-districts` |

Với preset demo, các ô còn lại có thể để mặc định. Workflow sẽ tự giới hạn 2 quận đầu tiên
và đặt `request_delay_seconds=0`.

Nếu muốn tự chọn quận cụ thể, chọn `quick_preset=custom`:

| Input | Giá trị ví dụ |
| --- | --- |
| `run_type` | `incremental-daily` |
| `demo_mode` | `true` |
| `district_ids` | `1,2` |
| `request_delay_seconds` | `0` |

## Câu Hỏi

1. Run type nào nên schedule?
2. Demo này tạo bao nhiêu API request?
3. Khi gặp `429`, nên retry hay dừng?
