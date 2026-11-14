# Học từ 10 trang mẫu hiện đại (2026-11-13)

> Ghi chú của Claude. Số liệu đo bằng `playwright_engine/style_dna_scraper.py` (chỉ thống kê tổng hợp:
> màu, font, cỡ chữ, khoảng cách, bo góc, chuyển động — không lấy nội dung, DOM hay ảnh).
> Ảnh chụp để tham khảo nằm ngoài repo, trong `hoc-ui/2-mau-tham-khao/` (không commit: thuộc bản quyền các trang).
> Chỉ học quy luật phong cách; không sao chép bố cục hay nội dung (§2.4 Anti-Cloning).

## 1. Số liệu đo (desktop 1440px)

| Trang | Nền / tối? | Màu nhấn chiếm diện tích | Font | Bo góc trung vị | Phân tách khối | Mật độ | Blur nav |
|---|---|---|---|---|---|---|---|
| Marou (chocolate) | trắng + tím than, sáng | 15% (dải màu thương hiệu) | sans + display condensed IN HOA | 3px | viền | cân bằng | không |
| Blue Bottle (cà phê) | trắng 72% + ngà, sáng | 0% | sans + mono-ish | 2px | viền | thoáng | không |
| Chamberlain (cà phê) | trắng + xám xanh, sáng | 2% | sans + display serif tròn | 15px | viền | thoáng | không |
| Oishii (dâu) | trắng + ngà + đen | 5% | grotesk + serif tiêu đề | 30px | viền | cân bằng | không |
| Aesop (mỹ phẩm) | ngà ấm (L 99.5%, hue 103) | 0% | sans + serif nhân văn | 50px (nút viên thuốc) | viền | thoáng | không |
| Rhode (mỹ phẩm) | trắng 83%, chữ xám nâu | 0% | sans + display đậm | 10px | bóng | cân bằng | có |
| Linear (SaaS) | tối L 14%, bề mặt L 18% | 1% | Inter + mono | 9px | viền 1px | thoáng | có |
| Raycast (app) | tối L 13% | 0% | Inter + mono | 12px | bóng | thoáng | có |
| Framer (tool) | đen thuần | 0% | Inter + mono | 8px | bóng | thoáng | có |
| AirPods (sản phẩm) | xám rất nhạt L 97% + trắng | 0% | SF Pro Text + Display | 28px | viền | thoáng | có |

## 2. Quy luật rút ra

1. **Ảnh thật là nhân vật chính.** 8/10 trang dựng hero và phần lớn trang bằng ảnh chụp sản phẩm/con người cỡ lớn (full-bleed hoặc chiếm ½–⅔ chiều ngang). Không trang nào dùng hình minh hoạ trừu tượng thay ảnh.
2. **Màu nhấn gần như vắng mặt trong khung giao diện.** 9/10 trang có màu nhấn chiếm ≤ 5% diện tích; màu thương hiệu đến từ **ảnh**, không phải từ nút và dải nền. Nút hành động thường là **đen/xám rất tối hoặc trắng** (trên ảnh), không phải màu thương hiệu bão hoà.
3. **Thẻ sản phẩm không khung.** Thương mại (Blue Bottle, Aesop): ảnh sát mép thẻ, không viền, không nền, không padding; dưới ảnh chỉ có tên + mô tả ngắn (+ giá); cả thẻ là vùng bấm, không có nút riêng trên từng thẻ. Các ảnh **cùng một hàng có cùng tỷ lệ** nên mép trên/dưới thẳng hàng.
4. **Phân tách bằng khoảng trắng và dải nền, không bằng hộp.** Các section xen kẽ nền trắng / ngà / tối; hiếm khi bọc nội dung trong card có viền.
5. **Hai họ chữ có tương phản rõ.** 7/10 trang ghép sans cho nội dung với **display/serif có cá tính** cho tiêu đề (condensed in hoa, serif cổ điển, serif tròn). Hai sans gần giống nhau không tạo được tương phản.
6. **Tiêu đề hero rất lớn và chặt.** Hero cỡ ~64–96px, letter-spacing âm, line-height ~1.0–1.1; nội dung thường chỉ 14–18px — chênh lệch lớn tạo cảm giác "biên tập".
7. **Nhãn nhỏ in hoa giãn chữ** (eyebrow) phía trên tiêu đề section ở 5/10 trang.
8. **Bố cục lệch, ảnh tràn mép.** Kiểu biên tập: chữ chiếm ⅓ bên trái, ảnh tràn ra mép phải màn hình; hoặc ảnh lớn bên trái, khối chữ hẹp bên phải.
9. **Bo góc theo phong cách:** F&B thủ công/sang trọng dùng 0–3px; lifestyle hiện đại dùng 15–30px cho ảnh và nút viên thuốc.
10. **Thanh menu mờ kính** (`backdrop-filter`) ở 5/10 trang, luôn có nền đủ đặc để chữ đọc được.
11. **Chi tiết thương mại:** thanh thông báo trên cùng (miễn phí vận chuyển…), dải chữ chạy ngang, thanh mua hàng dính đáy có giá + nút (AirPods).
12. **Giao diện tối (tech):** nền L 13–14%, bề mặt L 17–20%, chữ phụ L 65–70%, viền 1px — khớp với preset Precision Tech hiện có.

## 3. Chẩn đoán trang ChromaSwarm hiện tại (phiên `s-mwelf6yd`, landing "Máy tình")

Ảnh: `hoc-ui/1-loi-hien-tai/hien-tai-*.png`.

| # | Vấn đề | Mức độ | Nguyên nhân trong code |
|---|---|---|---|
| 1 | **Thanh menu ánh hồng**, lệch với nền kem | Lỗi | `color-mix(in oklch, var(--bg-primary) 85%, transparent)`: `transparent` không có hue nên kết quả có hue `none` → hiển thị hồng. Cùng lỗi ở `.modal-scrim` và quy tắc heal `sticky-legibility` của QA. |
| 2 | **Ảnh giả** (gradient + hình tròn + vạch) ở mọi khối → trông "AI làm", không sản phẩm | Nặng nhất | `developer/nextjs.py: art_component` |
| 3 | **Thẻ bento méo**: ảnh 16:9 cạnh ảnh 1:1 → thẻ cùng hàng cao thấp khác nhau, mép không thẳng | Nặng | `_bento`: tỷ lệ ảnh theo vị trí, không theo hàng |
| 4 | **Card lồng card**: thẻ có nền + viền + padding, ảnh bên trong lại bo góc riêng; mỗi thẻ thêm 1 nút "Xem nhanh" viền xanh → 4 nút giống hệt | Vừa | `.card`, `_bento`, `_grid4` |
| 5 | **Lạm dụng màu nhấn**: nút chính, 4 nút phụ, link, dải CTA nền xanh đặc, ảnh giả cũng xanh → cả trang xanh, giống app hơn là cửa hàng | Vừa | `.btn-ghost` dùng `accent-ink`, `.s-band` nền `accent`, `art_component` dùng accent |
| 6 | **Khoảng trống rỗng**: section cách 128px nhưng nội dung thưa; chữ ở các hàng Z quá nhỏ so với tiêu đề | Vừa | `--section-y` theo preset Airy áp đều; `_z_rows` dùng `t-body` |
| 7 | **Hai font tiêu đề/nội dung gần giống nhau** (Geist / Inter) → thiếu tương phản | Nhẹ | preset Precision Tech |
| 8 | **Tiêu đề section chung chung** ("Nổi bật", "Câu hỏi thường gặp"), không có eyebrow | Nhẹ | `_bento`, `_accordion` |
| 9 | **Mobile: nút "Menu" viền xanh to** trên header | Nhẹ | `_nav` |

## 4. Đề xuất thay đổi — đã thực hiện 2026-11-13 (người dùng chọn ảnh Unsplash)

Kết quả: dựng lại cùng câu trả lời (phiên `s-maytinh-moi`) → qua QA lần đầu, không cần vòng sửa;
ảnh trước/sau ở `hoc-ui/1-loi-hien-tai/` (`hien-tai-*` / `sau-khi-sua-*`).
Chưa làm: padding section co theo lượng nội dung (mới giảm riêng dải số liệu); hero ảnh tràn màn hình có lớp phủ chữ.


1. **Sửa lỗi màu menu** (#1): đổi `color-mix(in oklch, …, transparent)` → `in srgb` ở nav, modal scrim và heal QA; thêm kiểm tra QA "nền header lệch hue so với nền trang".
2. **Ảnh** (#2): thay ảnh giả bằng một trong hai: (a) ảnh thật từ kho miễn phí (Unsplash/Pexels, đúng §1.3 của chuẩn) theo ngành hàng; hoặc (b) khung ảnh trung tính có chủ đích (một tông nền, nhãn tỷ lệ) và nhắc người dùng tải ảnh ở B4. *Cần bạn chọn.*
3. **Thẻ sản phẩm không khung + cùng tỷ lệ theo hàng** (#3, #4): ảnh sát mép, tên/giá bên dưới, cả thẻ là link, bỏ nút trên từng thẻ; bento dùng cùng tỷ lệ trong một hàng. Thêm QA "thẻ cùng hàng lệch chiều cao".
4. **Kỷ luật màu nhấn** (#5): nút phụ, dải CTA, ảnh dùng màu trung tính; với preset sang trọng / ấm (editorial-luxury, warm-organic) cho phép **màu hành động = gần đen** (`--text-primary`), màu thương hiệu chỉ ở chi tiết nhỏ. Thêm QA "màu nhấn chiếm > 10% diện tích".
5. **Nhịp & chữ** (#6, #8): eyebrow in hoa nhỏ trên tiêu đề section; tiêu đề mô tả; hàng Z dùng `t-lead`, ảnh tràn mép kiểu biên tập; padding section co theo lượng nội dung.
6. **Ghép font tương phản** (#7): mỗi preset có một font tiêu đề khác loại với font nội dung (serif/display + sans), vẫn bắt buộc có bộ chữ tiếng Việt.
7. **Hero lớn hơn**: cỡ display desktop ~72–88px, tracking −0.03em; có biến thể hero ảnh tràn màn hình + lớp phủ khi có ảnh thật.
8. **Mobile nav** (#9): nút icon ☰ có `aria-label`, không viền màu.

## 5. Con mắt chấm điểm & kho hero (2026-11-14)

Chấm bằng `uv run python -m chromaswarm.qa.critic` (model đọc ảnh, thang 1–10):

| Trang | Điểm | Ghi chú |
|---|---:|---|
| Linear | 9.1 | trang mẫu |
| Chamberlain Coffee | 8.1 | trang mẫu |
| **ChromaSwarm — cà phê** (Sang trọng + Hình ảnh lớn → hero ảnh tràn màn hình) | **8.46** | |
| ChromaSwarm — tai nghe (Hiện đại + Hình ảnh lớn → hero đặt giữa) | 7.46 | |
| ChromaSwarm — máy tính, sau đợt sửa 1 (hero chia đôi) | 7.4 | |
| ChromaSwarm — máy tính (Kể chuyện → hero tạp chí) | 7.34 | lỗi chính tả "máy tình" từ lời người dùng bị chấm trừ |
| ChromaSwarm — máy tính, bản gốc | 5.8 | ảnh giả |

Aesop và Blue Bottle chặn trình duyệt headless nên không chấm được (critic chỉ thấy trang xác minh).
Nhận xét lặp lại của critic cho thấy giới hạn tiếp theo: **ảnh stock chung chung** (cần ảnh thật của người dùng),
**nội dung mẫu** (tiêu đề công thức "…, làm đúng từ chi tiết nhỏ nhất"), footer quá đơn giản.
