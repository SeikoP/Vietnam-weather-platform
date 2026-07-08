# Triển Khai

1. Tạo Supabase project.
2. Thêm secret `DATABASE_URL`.
3. Chạy `poetry run alembic upgrade head`.
4. Chạy `poetry run python scripts/seed_provinces.py`.
5. Cấu hình GitHub Actions secrets nếu dùng workflow.
