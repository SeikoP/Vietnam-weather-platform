# Thiết Kế Hợp Nhất Tài Liệu

## Mục tiêu

Rà soát mã nguồn, cấu hình và test hiện tại; hợp nhất tài liệu vận hành còn sáu file để đọc
nhanh nhưng vẫn đủ thông tin triển khai, vận hành và phân tích dữ liệu.

## Phạm vi

- Cập nhật `README.md` và tài liệu hiện hành trong `docs/`.
- Giữ nguyên `AGENTS.md` và `docs/superpowers/*` ngoài spec này vì đây là quy tắc và hồ sơ
  lịch sử.
- Không thay đổi mã nguồn, schema, workflow hoặc bí mật môi trường.
- Xóa mười tài liệu hiện hành cũ sau khi toàn bộ nội dung cần thiết đã được chuyển sang cấu
  trúc mới.

## Cấu trúc đích

1. `README.md`: mục tiêu, luồng dữ liệu, quick start, lệnh chính và mục lục.
2. `docs/architecture.md`: kiến trúc, cấu trúc mã nguồn và API routes.
3. `docs/data-model.md`: sáu bảng `analyst`, bốn bảng `monitoring`, khóa và quan hệ.
4. `docs/etl.md`: CLI, khoảng ngày, GitHub Actions, demo và manual catch-up.
5. `docs/deployment.md`: cấu hình, Supabase, migration, seed, Docker và đồng bộ local.
6. `docs/r2-powerbi.md`: bootstrap, publish, repair, verify R2 và mô hình Power BI.

## Nguyên tắc nội dung

- Viết tiếng Việt ngắn gọn; giữ nguyên lệnh, tên file, biến môi trường và identifier bằng
  tiếng Anh.
- Mỗi thông tin vận hành chỉ có một nơi giải thích chính; các file khác dùng liên kết.
- Chỉ mô tả hành vi được chứng minh bởi mã nguồn, cấu hình hoặc test hiện tại.
- Không ghi credential thật, số liệu snapshot dễ lỗi thời hoặc quy trình chưa có công cụ hỗ
  trợ.
- Phân biệt rõ luồng scheduled, manual, local và hành vi chỉ dành cho recovery.

## Các điểm phải sửa

- Incremental mặc định xử lý một ngày đã hoàn tất gần nhất, không phải ba ngày.
- Preset GitHub Actions dùng nhãn tiếng Việt hiện có trong workflow.
- Power BI đọc CSV từ `v1/current/analyst/`; hourly và AQI liên kết `dim_hour` bằng
  `hour_key`.
- API middleware hiện ghi structured log; bảng `monitoring.api_requests` chưa được route ghi
  trực tiếp.
- Publisher cập nhật cả release, sáu CSV alias và `v1/latest.json`, đồng thời chỉ giữ ba
  release đủ điều kiện gần nhất.
- Không mô tả đổi riêng `v1/latest.json` là rollback hoàn chỉnh vì thao tác đó không cập nhật
  CSV alias.
- `--lookback-days 0` của cloud-to-local sync phải giữ nguyên nghĩa: lấy mọi khóa mới hơn
  watermark, không bỏ qua khoảng trống do nhiều ngày chưa chạy.

## Kiểm chứng

- Chạy toàn bộ pytest và Ruff bằng `.venv` nếu Poetry không có trên `PATH`.
- Chạy `git diff --check`.
- Kiểm tra liên kết Markdown nội bộ và bảo đảm README chỉ dẫn tới năm tài liệu hiện hành.
- Đối chiếu các lệnh được ghi với `--help`, `pyproject.toml`, `.env.example`, workflow và
  Docker Compose.
- Rà soát diff để bảo đảm không sửa `AGENTS.md`, `.env`, mã nguồn hoặc thay đổi sẵn có trong
  `.codebase-memory/*`.
