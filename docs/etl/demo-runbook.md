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

| Input | Giá trị demo |
| --- | --- |
| `run_type` | `incremental-daily` |
| `demo_mode` | `true` |
| `district_ids` | `1,2` |
| `request_delay_seconds` | `0` |

## Câu Hỏi

1. Run type nào nên schedule?
2. Demo này tạo bao nhiêu API request?
3. Khi gặp `429`, nên retry hay dừng?
