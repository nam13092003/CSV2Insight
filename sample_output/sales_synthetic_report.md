# Báo cáo insight dữ liệu: `sales_synthetic.csv`

**8,050 dòng × 14 cột** · Biến mục tiêu: `returned`

## Tóm tắt điều hành

**`unit_price` trung bình khác biệt rõ theo `category`: cao nhất ở `Electronics` (475.8), thấp nhất ở `Office` (42.40) (gấp 11.2 lần); trung bình chung 246.3.**

- Tỉ lệ `returned` khác biệt rõ theo `satisfaction`: cao nhất ở `2` (83.3%), thấp nhất ở `5` (0.3%); trung bình chung 12.4%. _(I04)_
- `quantity` và `discount` tương quan thuận mạnh (Spearman ρ = 0.65): khi `quantity` ≥ 5, `discount` trung bình 0.164, so với 0.0363 khi `quantity` ≤ 2. _(I06)_
- Tổng `revenue` có tính mùa vụ theo tháng: cao nhất vào tháng 12 (cao hơn 46% so với mức xu hướng), thấp nhất vào tháng 9 (-17%). _(I07)_
- `unit_price` và `revenue` tương quan thuận rất mạnh (Spearman ρ = 0.84): khi `unit_price` ≥ 396.5, `revenue` trung bình 2,378, so với 180.4 khi `unit_price` ≤ 50.10. _(I02)_
- Nhóm `category=Furniture` có `revenue` sụt giảm từ 2024-07-08: trung bình mỗi tuần -51% so với giai đoạn trước, trong khi toàn bộ dữ liệu +3%. _(I03)_

**Lưu ý**

- Có 50 dòng trùng lặp hoàn toàn (0.62% dữ liệu) — cần khử trùng trước khi tổng hợp.
- Cột `customer_age` thiếu 15.0% giá trị (1,205/8,050 dòng).
- Cột `country` chỉ có một giá trị duy nhất (`VN`) — không mang thông tin phân tích.

<sub>Tóm tắt tự động (không dùng LLM).</sub>

## Insight nổi bật

1. **[I01]** `unit_price` trung bình khác biệt rõ theo `category`: cao nhất ở `Electronics` (475.8), thấp nhất ở `Office` (42.40) (gấp 11.2 lần); trung bình chung 246.3.  
   <sub>group_diff · score 0.73 · p < 1e-6</sub>
2. **[I04]** Tỉ lệ `returned` khác biệt rõ theo `satisfaction`: cao nhất ở `2` (83.3%), thấp nhất ở `5` (0.3%); trung bình chung 12.4%.  
   <sub>group_diff · score 0.59 · p < 1e-6</sub>
3. **[I06]** `quantity` và `discount` tương quan thuận mạnh (Spearman ρ = 0.65): khi `quantity` ≥ 5, `discount` trung bình 0.164, so với 0.0363 khi `quantity` ≤ 2.  
   <sub>correlation · score 0.52 · p < 1e-6</sub>
4. **[I07]** Tổng `revenue` có tính mùa vụ theo tháng: cao nhất vào tháng 12 (cao hơn 46% so với mức xu hướng), thấp nhất vào tháng 9 (-17%).  
   <sub>seasonality · score 0.51 · p = 2e-05</sub>
5. **[I02]** `unit_price` và `revenue` tương quan thuận rất mạnh (Spearman ρ = 0.84): khi `unit_price` ≥ 396.5, `revenue` trung bình 2,378, so với 180.4 khi `unit_price` ≤ 50.10.  
   <sub>correlation · score 0.67 · p < 1e-6</sub>
6. **[I03]** Nhóm `category=Furniture` có `revenue` sụt giảm từ 2024-07-08: trung bình mỗi tuần -51% so với giai đoạn trước, trong khi toàn bộ dữ liệu +3%.  
   <sub>segment_change · score 0.60 · p = 0.0005</sub>
7. **[I05]** Các yếu tố liên quan mạnh nhất tới `returned` (theo thứ tự): `satisfaction` (η=0.62), `channel` (η=0.17).  
   <sub>drivers · score 0.59</sub>
8. **[I16]** `quantity` tập trung theo `sales_rep`: 6/30 nhóm hàng đầu (Rep_01, Rep_00, Rep_02, Rep_12, Rep_24) tạo ra 49.6% tổng `quantity`.  
   <sub>pareto · score 0.25</sub>
9. **[I09]** Tổng `revenue` bất thường tại 2024-08-26: 221,784 so với mức kỳ vọng khoảng 97,062 (đã tính xu hướng và mùa vụ).  
   <sub>anomaly_period · score 0.35</sub>
10. **[I08]** `quantity` và `revenue` tương quan thuận trung bình (Spearman ρ = 0.48): khi `quantity` ≥ 5, `revenue` trung bình 1,934, so với 436.4 khi `quantity` ≤ 2.  
   <sub>correlation · score 0.38 · p < 1e-6</sub>

## Xu hướng theo thời gian

- **[I03]** Nhóm `category=Furniture` có `revenue` sụt giảm từ 2024-07-08: trung bình mỗi tuần -51% so với giai đoạn trước, trong khi toàn bộ dữ liệu +3%.
- **[I07]** Tổng `revenue` có tính mùa vụ theo tháng: cao nhất vào tháng 12 (cao hơn 46% so với mức xu hướng), thấp nhất vào tháng 9 (-17%).
- **[I09]** Tổng `revenue` bất thường tại 2024-08-26: 221,784 so với mức kỳ vọng khoảng 97,062 (đã tính xu hướng và mùa vụ).
- **[I12]** Nhóm `category=Office` có `revenue` tăng +69% theo đường xu hướng trong kỳ, khác biệt so với toàn bộ dữ liệu (+23%).

## Phân khúc & yếu tố ảnh hưởng

- **[I01]** `unit_price` trung bình khác biệt rõ theo `category`: cao nhất ở `Electronics` (475.8), thấp nhất ở `Office` (42.40) (gấp 11.2 lần); trung bình chung 246.3.
- **[I04]** Tỉ lệ `returned` khác biệt rõ theo `satisfaction`: cao nhất ở `2` (83.3%), thấp nhất ở `5` (0.3%); trung bình chung 12.4%.
- **[I05]** Các yếu tố liên quan mạnh nhất tới `returned` (theo thứ tự): `satisfaction` (η=0.62), `channel` (η=0.17).
- **[I11]** `Electronics` đóng góp lớn nhất vào `revenue`: 58.8% tổng (với 29.6% số dòng), tiếp theo là `Furniture` (31.2%).
- **[I16]** `quantity` tập trung theo `sales_rep`: 6/30 nhóm hàng đầu (Rep_01, Rep_00, Rep_02, Rep_12, Rep_24) tạo ra 49.6% tổng `quantity`.
- **[I17]** `revenue` trung bình khác biệt rõ theo `category`: cao nhất ở `Electronics` (2,230), thấp nhất ở `Office` (226.5) (gấp 9.8 lần); trung bình chung 1,122.
- **[I18]** `revenue` tập trung theo `sales_rep`: 6/30 nhóm hàng đầu (Rep_01, Rep_00, Rep_02, Rep_24, Rep_12) tạo ra 48.8% tổng `revenue`.
- **[I19]** Tỉ lệ `returned` khác biệt rõ theo `channel`: cao nhất ở `Online` (18.2%), thấp nhất ở `Store` (6.2%) (gấp 2.9 lần); trung bình chung 12.4%.
- **[I20]** `West` đóng góp lớn nhất vào `revenue`: 42.1% tổng (với 40.4% số dòng), tiếp theo là `North` (17.8%).
- **[I24]** `West` đóng góp lớn nhất vào `quantity`: 40.0% tổng (với 40.4% số dòng), tiếp theo là `South` (17.7%).

## Quan hệ giữa các biến

- **[I02]** `unit_price` và `revenue` tương quan thuận rất mạnh (Spearman ρ = 0.84): khi `unit_price` ≥ 396.5, `revenue` trung bình 2,378, so với 180.4 khi `unit_price` ≤ 50.10.
- **[I06]** `quantity` và `discount` tương quan thuận mạnh (Spearman ρ = 0.65): khi `quantity` ≥ 5, `discount` trung bình 0.164, so với 0.0363 khi `quantity` ≤ 2.
- **[I08]** `quantity` và `revenue` tương quan thuận trung bình (Spearman ρ = 0.48): khi `quantity` ≥ 5, `revenue` trung bình 1,934, so với 436.4 khi `quantity` ≤ 2.

## Phân phối & ngoại lai

- **[I13]** Phân phối `quantity` lệch phải mạnh (độ lệch 24.14): trung bình 4.30 nhưng trung vị chỉ 3 — nên dùng trung vị khi báo cáo.
- **[I14]** Phân phối `revenue` lệch phải mạnh (độ lệch 29.32): trung bình 1,122 nhưng trung vị chỉ 516.3 — nên dùng trung vị khi báo cáo.
- **[I15]** `quantity` có 12 giá trị ngoại lai cực đoan (0.15%), trong khoảng 156–288 so với trung vị 3; riêng nhóm này chiếm 8.1% tổng `quantity`.
- **[I22]** `revenue` tập trung cao: 10% dòng lớn nhất chiếm 43.6% tổng giá trị (Gini 0.61).
- **[I25]** `region` bị chi phối bởi `West` với 40.4% số dòng (trong 5 nhóm).

## Chất lượng & cấu trúc dữ liệu

- **[I10]** Có 50 dòng trùng lặp hoàn toàn (0.62% dữ liệu) — cần khử trùng trước khi tổng hợp.
- **[I21]** Cột `customer_age` thiếu 15.0% giá trị (1,205/8,050 dòng).
- **[I23]** Cột `country` chỉ có một giá trị duy nhất (`VN`) — không mang thông tin phân tích.

## Vai trò các cột

| Cột | Vai trò | Thiếu | Số giá trị khác nhau |
|---|---|---|---|
| `order_id` | id | 0.0% | 8000 |
| `order_date` | datetime | 0.0% | 731 |
| `region` | dimension | 0.0% | 5 |
| `channel` | dimension | 0.0% | 3 |
| `category` | dimension | 0.0% | 4 |
| `sales_rep` | dimension | 0.0% | 30 |
| `unit_price` | measure (mean) | 0.0% | 7036 |
| `quantity` | measure (sum) | 0.0% | 28 |
| `discount` | measure (mean) | 0.0% | 6 |
| `revenue` | measure (sum) | 0.0% | 7784 |
| `customer_age` | measure (mean) | 15.0% | 59 |
| `satisfaction` | measure (mean) | 0.0% | 5 |
| `returned` | binary (mean) | 0.0% | 2 |
| `country` | constant | 0.0% | 1 |

## Phương pháp

Insight được tìm bằng kiểm định thống kê (ANOVA/Kruskal theo hạng, Spearman, Cramér's V, Mann-Kendall, mô hình điểm gãy có hiệu chỉnh sup-F, tách mùa vụ), lọc theo mức ý nghĩa p < 0.001 và ngưỡng độ lớn hiệu ứng, loại bỏ quan hệ hiển nhiên (cột trùng, cột suy ra, phân cấp), rồi xếp hạng theo: trọng số loại × độ lớn hiệu ứng × phạm vi ảnh hưởng, có đa dạng hoá.
