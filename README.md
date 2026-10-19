# CSV2Insight

**Tự động tìm insight từ một bảng CSV bất kỳ — có kiểm chứng thống kê, không bịa số.**

Đưa vào một file CSV → nhận lại báo cáo gồm các phát hiện quan trọng nhất (xu hướng, mùa vụ, điểm gãy, khác biệt giữa
các nhóm, tương quan, ngoại lai, vấn đề chất lượng dữ liệu…). Mỗi phát hiện đều có kiểm định thống kê đi kèm, cùng một
đoạn tóm tắt điều hành do LLM nhỏ (≤ 8B tham số) viết lại từ chính các con số đã kiểm chứng.

👉 **Xem output mẫu:** [báo cáo Markdown](sample_output/sales_synthetic_report.md) ·
[báo cáo HTML có biểu đồ](https://htmlpreview.github.io/?https://github.com/nam13092003/CSV2Insight/blob/main/sample_output/sales_synthetic_report.html) ·
[JSON](sample_output/sales_synthetic_insights.json)

---

## Chạy nhanh (3 bước)

**1. Tải code và cài thư viện** (cần Python ≥ 3.9; chỉ dùng `pandas` và `numpy`)

```bash
git clone https://github.com/nam13092003/CSV2Insight.git
cd CSV2Insight
pip install -r requirements.txt
```

**2. Chạy trên dữ liệu mẫu**

```bash
python insight.py examples/sales_synthetic.csv --no-llm
```

**3. Mở báo cáo**

```bash
# Windows
start insight_output\sales_synthetic_report.html
# macOS
open insight_output/sales_synthetic_report.html
# Linux
xdg-open insight_output/sales_synthetic_report.html
```

Xong! Trong thư mục `insight_output/` sẽ có 3 file:

| File | Dùng để |
|---|---|
| `<tên>_report.html` | Xem trên trình duyệt: tóm tắt, top insight kèm biểu đồ, toàn bộ insight theo nhóm |
| `<tên>_report.md` | Dán vào tài liệu / GitHub / Notion |
| `<tên>_insights.json` | Đưa vào hệ thống khác (mỗi insight có loại, cột, độ mạnh, p‑value, số liệu) |

## Chạy với dữ liệu của bạn

```bash
python insight.py du_lieu_cua_ban.csv --no-llm
```

Tuỳ chọn hay dùng:

```bash
python insight.py data.csv --target churn                       # phân tích yếu tố ảnh hưởng tới cột mục tiêu
python insight.py data.csv --context "Dữ liệu bán hàng 2024"    # bối cảnh cho phần tóm tắt LLM
python insight.py data.csv --lang en --top 15 --out bao_cao/    # tiếng Anh, 15 insight, thư mục output khác
```


## Cách hoạt động

Để LLM nhỏ tự đọc bảng rồi nói insight thì nó hay tính sai và bịa số. Vì vậy CSV2Insight để **thống kê tìm insight, LLM chỉ diễn đạt**
(theo hướng QuickInsights / Top‑K Insights của Microsoft Research):

```
CSV → Nhận diện cột → Khai phá insight → Loại quan hệ hiển nhiên → Xếp hạng → (LLM ≤8B viết tóm tắt) → Kiểm tra số → HTML/MD/JSON
```

1. **Nhận diện cột** (`profile.py`): tự đoán dấu phân cách/encoding; nhận ngày (cả `dd/mm/yyyy`, cặp year+month), số dạng chuỗi
   (`1,234 ₫`, `45%`), cột ID, văn bản, nhị phân; phân biệt chỉ số cộng dồn (doanh thu → sum) và chỉ số trung bình (giá → mean).
2. **Khai phá insight** (`miners.py`):
   - Thời gian: xu hướng (Mann‑Kendall), mùa vụ theo tháng/thứ, điểm gãy (hiệu chỉnh sup‑F), kỳ bất thường, phân khúc đi ngược xu hướng.
   - Phân khúc: khác biệt giữa nhóm (ANOVA, η², Cohen's h), đóng góp, Pareto, yếu tố ảnh hưởng tới biến mục tiêu.
   - Quan hệ: tương quan Spearman, liên hệ giữa biến phân loại (Cramér's V).
   - Phân phối & chất lượng: ngoại lai, lệch, dữ liệu thiếu (kể cả thiếu có hệ thống), trùng dòng, cột hằng.
3. **Loại quan hệ hiển nhiên**: cột trùng thông tin, cột suy ra từ cột khác, quan hệ phân cấp, chỉ số là tích của chỉ số khác.
4. **Xếp hạng**: trọng số loại × độ lớn hiệu ứng × phạm vi ảnh hưởng, có đa dạng hoá top‑k.
5. **LLM (tuỳ chọn)** viết headline, ý chính, khuyến nghị, lưu ý. Mọi con số LLM viết ra được đối chiếu với kết quả thống kê:
   sai → bắt viết lại → vẫn sai thì xoá câu đó. Lỗi mạng/model → model dự phòng → tóm tắt tự động.
