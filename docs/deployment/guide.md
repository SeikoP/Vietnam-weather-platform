# Triển Khai

1. Sử dụng Supabase project `gaudwyopkcpfhtmccvgb`.
2. Thêm secret `DATABASE_URL` bằng Session Pooler:
   `postgresql+psycopg://postgres.gaudwyopkcpfhtmccvgb:<password>@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres`.
3. Chạy `poetry run alembic upgrade head`.
4. Chạy `poetry run python scripts/seed_provinces.py`.
5. Cấu hình GitHub Actions secrets nếu dùng workflow.
