# Báo cáo insight dữ liệu: `air_quality_dataset.csv`

**500 dòng × 10 cột**

## Tóm tắt điều hành

**`NO2` và `CO2` tương quan thuận rất mạnh (Spearman ρ = 0.84): khi `NO2` ≥ 63.82, `CO2` trung bình 502.3, so với 390.8 khi `NO2` ≤ 17.45.**

- `PM2.5` và `SO2` tương quan thuận mạnh (Spearman ρ = 0.71): khi `PM2.5` ≥ 73.82, `SO2` trung bình 19.87, so với 6.53 khi `PM2.5` ≤ 36.37. _(I06)_
- `NOx` và `CO` tương quan thuận mạnh (Spearman ρ = 0.67): khi `NOx` ≥ 134.7, `CO` trung bình 2.86, so với 1.49 khi `NOx` ≤ 35.46. _(I10)_

<sub>Tóm tắt tự động (không dùng LLM).</sub>

## Insight nổi bật

1. **[I01]** `NO2` và `CO2` tương quan thuận rất mạnh (Spearman ρ = 0.84): khi `NO2` ≥ 63.82, `CO2` trung bình 502.3, so với 390.8 khi `NO2` ≤ 17.45.  
   <sub>correlation · score 0.67 · p < 1e-6</sub>
2. **[I06]** `PM2.5` và `SO2` tương quan thuận mạnh (Spearman ρ = 0.71): khi `PM2.5` ≥ 73.82, `SO2` trung bình 19.87, so với 6.53 khi `PM2.5` ≤ 36.37.  
   <sub>correlation · score 0.57 · p < 1e-6</sub>
3. **[I10]** `NOx` và `CO` tương quan thuận mạnh (Spearman ρ = 0.67): khi `NOx` ≥ 134.7, `CO` trung bình 2.86, so với 1.49 khi `NOx` ≤ 35.46.  
   <sub>correlation · score 0.54 · p < 1e-6</sub>

## Quan hệ giữa các biến

- **[I01]** `NO2` và `CO2` tương quan thuận rất mạnh (Spearman ρ = 0.84): khi `NO2` ≥ 63.82, `CO2` trung bình 502.3, so với 390.8 khi `NO2` ≤ 17.45.
- **[I02]** `NOx` và `NO2` tương quan thuận rất mạnh (Spearman ρ = 0.82): khi `NOx` ≥ 134.7, `NO2` trung bình 69.58, so với 15.27 khi `NOx` ≤ 35.46.
- **[I03]** `NOx` và `CO2` tương quan thuận rất mạnh (Spearman ρ = 0.81): khi `NOx` ≥ 134.7, `CO2` trung bình 495.9, so với 390.1 khi `NOx` ≤ 35.46.
- **[I04]** `CO` và `CO2` tương quan thuận mạnh (Spearman ρ = 0.74): khi `CO` ≥ 2.73, `CO2` trung bình 496.9, so với 396.8 khi `CO` ≤ 1.54.
- **[I05]** `NO2` và `CO` tương quan thuận mạnh (Spearman ρ = 0.71): khi `NO2` ≥ 63.82, `CO` trung bình 3.02, so với 1.51 khi `NO2` ≤ 17.45.
- **[I06]** `PM2.5` và `SO2` tương quan thuận mạnh (Spearman ρ = 0.71): khi `PM2.5` ≥ 73.82, `SO2` trung bình 19.87, so với 6.53 khi `PM2.5` ≤ 36.37.
- **[I07]** `PM10` và `SO2` tương quan thuận mạnh (Spearman ρ = 0.70): khi `PM10` ≥ 110.3, `SO2` trung bình 20.00, so với 6.62 khi `PM10` ≤ 61.12.
- **[I08]** `SO2` và `CH4` tương quan thuận mạnh (Spearman ρ = 0.68): khi `SO2` ≥ 17.12, `CH4` trung bình 2.56, so với 1.87 khi `SO2` ≤ 5.98.
- **[I09]** `SO2` và `VOCs` tương quan thuận mạnh (Spearman ρ = 0.67): khi `SO2` ≥ 17.12, `VOCs` trung bình 155.0, so với 85.46 khi `SO2` ≤ 5.98.
- **[I10]** `NOx` và `CO` tương quan thuận mạnh (Spearman ρ = 0.67): khi `NOx` ≥ 134.7, `CO` trung bình 2.86, so với 1.49 khi `NOx` ≤ 35.46.
- **[I11]** `PM10` và `CH4` tương quan thuận mạnh (Spearman ρ = 0.65): khi `PM10` ≥ 110.3, `CH4` trung bình 2.53, so với 1.88 khi `PM10` ≤ 61.12.
- **[I12]** `PM2.5` và `CH4` tương quan thuận mạnh (Spearman ρ = 0.65): khi `PM2.5` ≥ 73.82, `CH4` trung bình 2.53, so với 1.89 khi `PM2.5` ≤ 36.37.
- **[I13]** `PM2.5` và `PM10` tương quan thuận mạnh (Spearman ρ = 0.63): khi `PM2.5` ≥ 73.82, `PM10` trung bình 116.9, so với 66.20 khi `PM2.5` ≤ 36.37.
- **[I14]** `PM10` và `VOCs` tương quan thuận mạnh (Spearman ρ = 0.63): khi `PM10` ≥ 110.3, `VOCs` trung bình 150.6, so với 86.43 khi `PM10` ≤ 61.12.
- **[I15]** `PM2.5` và `VOCs` tương quan thuận mạnh (Spearman ρ = 0.61): khi `PM2.5` ≥ 73.82, `VOCs` trung bình 151.0, so với 88.99 khi `PM2.5` ≤ 36.37.
- **[I16]** `CO2` và `Temperature` tương quan thuận mạnh (Spearman ρ = 0.60): khi `CO2` ≥ 491.0, `Temperature` trung bình 32.93, so với 28.43 khi `CO2` ≤ 397.4.
- **[I17]** `VOCs` và `CH4` tương quan thuận trung bình (Spearman ρ = 0.60): khi `VOCs` ≥ 140.6, `CH4` trung bình 2.50, so với 1.90 khi `VOCs` ≤ 81.52.
- **[I18]** `PM2.5` và `CO2` tương quan thuận trung bình (Spearman ρ = 0.58): khi `PM2.5` ≥ 73.82, `CO2` trung bình 501.2, so với 409.5 khi `PM2.5` ≤ 36.37.
- **[I19]** `NO2` và `Temperature` tương quan thuận trung bình (Spearman ρ = 0.57): khi `NO2` ≥ 63.82, `Temperature` trung bình 32.67, so với 28.72 khi `NO2` ≤ 17.45.
- **[I20]** `NOx` và `Temperature` tương quan thuận trung bình (Spearman ρ = 0.56): khi `NOx` ≥ 134.7, `Temperature` trung bình 32.56, so với 28.68 khi `NOx` ≤ 35.46.
- **[I21]** `PM10` và `CO2` tương quan thuận trung bình (Spearman ρ = 0.56): khi `PM10` ≥ 110.3, `CO2` trung bình 500.8, so với 410.4 khi `PM10` ≤ 61.12.
- **[I22]** `SO2` và `CO2` tương quan thuận trung bình (Spearman ρ = 0.54): khi `SO2` ≥ 17.12, `CO2` trung bình 502.9, so với 413.2 khi `SO2` ≤ 5.98.
- **[I23]** `PM10` và `NO2` tương quan thuận trung bình (Spearman ρ = 0.53): khi `PM10` ≥ 110.3, `NO2` trung bình 69.51, so với 30.60 khi `PM10` ≤ 61.12.
- **[I24]** `PM2.5` và `NO2` tương quan thuận trung bình (Spearman ρ = 0.52): khi `PM2.5` ≥ 73.82, `NO2` trung bình 70.66, so với 31.69 khi `PM2.5` ≤ 36.37.
- **[I25]** `PM10` và `CO` tương quan thuận trung bình (Spearman ρ = 0.51): khi `PM10` ≥ 110.3, `CO` trung bình 2.94, so với 1.81 khi `PM10` ≤ 61.12.
- **[I26]** `CO2` và `CH4` tương quan thuận trung bình (Spearman ρ = 0.51): khi `CO2` ≥ 491.0, `CH4` trung bình 2.53, so với 1.98 khi `CO2` ≤ 397.4.
- **[I27]** `VOCs` và `CO2` tương quan thuận trung bình (Spearman ρ = 0.51): khi `VOCs` ≥ 140.6, `CO2` trung bình 495.5, so với 412.6 khi `VOCs` ≤ 81.52.
- **[I28]** `NO2` và `SO2` tương quan thuận trung bình (Spearman ρ = 0.50): khi `NO2` ≥ 63.82, `SO2` trung bình 20.39, so với 8.10 khi `NO2` ≤ 17.45.
- **[I29]** `PM2.5` và `CO` tương quan thuận trung bình (Spearman ρ = 0.50): khi `PM2.5` ≥ 73.82, `CO` trung bình 2.96, so với 1.84 khi `PM2.5` ≤ 36.37.
- **[I30]** `SO2` và `CO` tương quan thuận trung bình (Spearman ρ = 0.50): khi `SO2` ≥ 17.12, `CO` trung bình 3.00, so với 1.90 khi `SO2` ≤ 5.98.
- **[I31]** `CO` và `Temperature` tương quan thuận trung bình (Spearman ρ = 0.50): khi `CO` ≥ 2.73, `Temperature` trung bình 32.42, so với 28.86 khi `CO` ≤ 1.54.
- **[I32]** `NO2` và `CH4` tương quan thuận trung bình (Spearman ρ = 0.49): khi `NO2` ≥ 63.82, `CH4` trung bình 2.54, so với 1.97 khi `NO2` ≤ 17.45.
- **[I33]** `SO2` và `Temperature` tương quan thuận trung bình (Spearman ρ = 0.48): khi `SO2` ≥ 17.12, `Temperature` trung bình 32.89, so với 29.49 khi `SO2` ≤ 5.98.
- **[I34]** `PM10` và `NOx` tương quan thuận trung bình (Spearman ρ = 0.47): khi `PM10` ≥ 110.3, `NOx` trung bình 141.5, so với 73.79 khi `PM10` ≤ 61.12.
- **[I35]** `PM2.5` và `NOx` tương quan thuận trung bình (Spearman ρ = 0.47): khi `PM2.5` ≥ 73.82, `NOx` trung bình 142.8, so với 73.22 khi `PM2.5` ≤ 36.37.
- **[I36]** `PM2.5` và `Temperature` tương quan thuận trung bình (Spearman ρ = 0.45): khi `PM2.5` ≥ 73.82, `Temperature` trung bình 32.66, so với 29.59 khi `PM2.5` ≤ 36.37.
- **[I37]** `NOx` và `SO2` tương quan thuận trung bình (Spearman ρ = 0.45): khi `NOx` ≥ 134.7, `SO2` trung bình 18.60, so với 7.99 khi `NOx` ≤ 35.46.
- **[I38]** `CO` và `CH4` tương quan thuận trung bình (Spearman ρ = 0.44): khi `CO` ≥ 2.73, `CH4` trung bình 2.46, so với 1.96 khi `CO` ≤ 1.54.
- **[I39]** `PM10` và `Temperature` tương quan thuận trung bình (Spearman ρ = 0.43): khi `PM10` ≥ 110.3, `Temperature` trung bình 32.61, so với 29.47 khi `PM10` ≤ 61.12.
- **[I40]** `NOx` và `VOCs` tương quan thuận trung bình (Spearman ρ = 0.43): khi `NOx` ≥ 134.7, `VOCs` trung bình 147.4, so với 98.29 khi `NOx` ≤ 35.46.
- **[I41]** `CH4` và `Temperature` tương quan thuận trung bình (Spearman ρ = 0.43): khi `CH4` ≥ 2.39, `Temperature` trung bình 32.71, so với 29.57 khi `CH4` ≤ 1.84.
- **[I42]** `NO2` và `VOCs` tương quan thuận trung bình (Spearman ρ = 0.43): khi `NO2` ≥ 63.82, `VOCs` trung bình 149.9, so với 101.4 khi `NO2` ≤ 17.45.
- **[I43]** `VOCs` và `CO` tương quan thuận trung bình (Spearman ρ = 0.42): khi `VOCs` ≥ 140.6, `CO` trung bình 2.83, so với 1.90 khi `VOCs` ≤ 81.52.
- **[I44]** `NOx` và `CH4` tương quan thuận trung bình (Spearman ρ = 0.42): khi `NOx` ≥ 134.7, `CH4` trung bình 2.45, so với 1.99 khi `NOx` ≤ 35.46.
- **[I45]** `VOCs` và `Temperature` tương quan thuận trung bình (Spearman ρ = 0.41): khi `VOCs` ≥ 140.6, `Temperature` trung bình 32.54, so với 29.67 khi `VOCs` ≤ 81.52.

## Vai trò các cột

| Cột | Vai trò | Thiếu | Số giá trị khác nhau |
|---|---|---|---|
| `PM2.5` | measure (mean) | 0.0% | 500 |
| `PM10` | measure (mean) | 0.0% | 500 |
| `NOx` | measure (mean) | 0.0% | 500 |
| `NO2` | measure (mean) | 0.0% | 500 |
| `SO2` | measure (mean) | 0.0% | 500 |
| `VOCs` | measure (mean) | 0.0% | 500 |
| `CO` | measure (mean) | 0.0% | 500 |
| `CO2` | measure (mean) | 0.0% | 500 |
| `CH4` | measure (mean) | 0.0% | 500 |
| `Temperature` | measure (mean) | 0.0% | 500 |

## Phương pháp

Insight được tìm bằng kiểm định thống kê (ANOVA/Kruskal theo hạng, Spearman, Cramér's V, Mann-Kendall, mô hình điểm gãy có hiệu chỉnh sup-F, tách mùa vụ), lọc theo mức ý nghĩa p < 0.001 và ngưỡng độ lớn hiệu ứng, loại bỏ quan hệ hiển nhiên (cột trùng, cột suy ra, phân cấp), rồi xếp hạng theo: trọng số loại × độ lớn hiệu ứng × phạm vi ảnh hưởng, có đa dạng hoá.
