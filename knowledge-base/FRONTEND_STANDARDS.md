# TÀI LIỆU CHUẨN PRODUCT FRONTEND & UI/UX (`FRONTEND_STANDARDS.md`)
*Tài liệu Huấn luyện & Quy chuẩn Thực thi cho Hệ thống Đa Tác tử SwarmUI (Áp dụng xuyên suốt Quy trình 12 Bước)*

---

## CHƯƠNG 1: QUY CHUẨN TƯ VẤN SẢN PHẨM & KHAI THÁC Ý TƯỞNG NGƯỜI DÙNG KHÔNG CHUYÊN (Dành cho Bước 1 $\rightarrow$ Bước 4)

> [!IMPORTANT]
> **Kỷ luật Chặn Đoán Mò (Zero-Guessing Law):** Khi người dùng đưa ra yêu cầu ban đầu, Agent **tuyệt đối không được tự suy diễn** màu sắc, bố cục hay tính năng. Agent phải đóng vai trò một Giám đốc Sản phẩm & Thiết kế (Product & Design Director) để tư vấn hệ thống trang cần có và đặt câu hỏi khai thác 5 trụ cột thiết kế bằng ngôn ngữ đời thường.

### 1.1. Bản đồ Tư vấn Hệ thống Trang theo Ngành hàng (Dùng ở Bước 2)
Khi người dùng nói muốn làm một trang web (ví dụ: *"Làm web bán hàng"*), Agent phải giải thích rõ một sản phẩm hoàn chỉnh sử dụng được trong thực tế bao gồm những trang nào, và đề xuất người dùng **chọn 1 trang khởi đầu để làm trước (Page-by-Page)**:

| Loại hình Website | Các trang cốt lõi cần tư vấn cho người dùng ở Bước 2 | Trang khuyên làm đầu tiên |
| :--- | :--- | :--- |
| **1. E-Commerce (Web Bán hàng)** | 1. `Landing Page` (Trang chiến dịch/ra mắt sản phẩm chủ lực)<br>2. `Home / Storefront` (Trang chủ trưng bày danh mục)<br>3. `Product Catalog & Filter` (Trang tìm kiếm & lọc sản phẩm)<br>4. `Product Detail Page (PDP)` (Trang chi tiết sản phẩm & chọn phân loại)<br>5. `Cart & Checkout` (Giỏ hàng & Thanh toán)<br>6. `Login / Register & User Profile` (Tài khoản & Lịch sử đơn hàng) | `Landing Page` hoặc `Home / Storefront` |
| **2. SaaS / Web App (Phần mềm dịch vụ)** | 1. `Marketing Landing Page` (Trang giới thiệu giải pháp & bảng giá)<br>2. `Login / Onboarding` (Đăng nhập & Thiết lập ban đầu)<br>3. `Main Dashboard` (Bảng điều khiển trung tâm)<br>4. `Feature Workspace` (Trang thao tác tính năng chính)<br>5. `Settings & Billing` (Cài đặt & Quản lý gói cước) | `Marketing Landing Page` hoặc `Main Dashboard` |
| **3. Booking / Service (Đặt lịch, Dịch vụ, Nhà hàng, Spa)** | 1. `Home / Brand Story` (Trang chủ & Câu chuyện thương hiệu)<br>2. `Service Menu / Catalog` (Danh mục dịch vụ & Bảng giá)<br>3. `Interactive Booking Flow` (Trang chọn ngày giờ & đặt lịch)<br>4. `Login / My Bookings` (Quản lý lịch hẹn cá nhân) | `Home / Brand Story` |
| **4. EdTech / Course (Khóa học trực tuyến)** | 1. `Course Landing Page` (Trang giới thiệu khóa học)<br>2. `Course Directory / Home` (Thư viện khóa học)<br>3. `Learning Room / Video Player` (Trang học tập & bài tập)<br>4. `Login & Student Dashboard` (Tiến độ học tập) | `Course Landing Page` |

---

### 1.2. Ma trận Hỏi đáp 5 Trụ cột & Ánh xạ Ngôn ngữ Đời thường $\rightarrow$ Thông số Kỹ thuật (Dùng ở Bước 3)
Người dùng không có chuyên môn sẽ không hiểu các khái niệm như *"OKLCH Chroma"*, *"Bento Grid"*, hay *"8pt Spatial System"*. Agent bắt buộc phải hỏi bằng **câu hỏi gợi mở đời thường** và tự động biên dịch câu trả lời sang thông số kỹ thuật trong `DESIGN.md`:

#### Trụ cột 1: CHỦ ĐỀ & CẢM XÚC THƯƠNG HIỆU (Theme & Brand Vibe)
* **Cách hỏi người dùng:** *"Khi khách hàng mở trang web này lên, bạn muốn họ có cảm giác gì đầu tiên? (Ví dụ: Sang trọng & tĩnh lặng như bước vào showroom cao cấp; Hiện đại & sắc sảo như sản phẩm công nghệ; Thân thiện & ấm áp; hay Năng động & phá cách?)"*
* **Bảng ánh xạ sang Kỹ thuật (Model tự dịch):**
  * *Sang trọng, cao cấp (Editorial Luxury)* $\rightarrow$ Font chữ tiêu đề có chân (Serif độ tương phản cao như `Playfair Display` / `Instrument Serif`), góc vuông hoặc bo cực nhẹ (`0px–4px`), đường viền mảnh `1px`, chuyển động chậm mượt (`600ms cubic-bezier(0.16, 1, 0.3, 1)`).
  * *Hiện đại, công nghệ, chuẩn xác (Precision Tech)* $\rightarrow$ Font chữ không chân geometric/grotesque (`Inter`, `Plus Jakarta Sans`, `Geist`), kèm font Monospace cho con số/nhãn phụ, bo góc tiêu chuẩn (`8px–12px`), viền tinh tế có độ trong suốt (`border: 1px solid rgba(...)`).
  * *Thân thiện, gần gũi, đời sống (Warm Organic)* $\rightarrow$ Font chữ nét tròn mềm (`DM Sans`, `Outfit`), bo góc lớn (`16px–24px`), nút bấm dạng viên thuốc (`9999px`), đổ bóng khuếch tán mềm mại.
  * *Cá tính, táo bạo (Neo-Brutalist / Bold)* $\rightarrow$ Tiêu đề cỡ cực lớn, viền đậm rõ nét (`2px solid`), độ tương phản màu sắc mạnh, đổ bóng cứng không nhòe (`4px 4px 0px`).

#### Trụ cột 2: BỐ CỤC TRÌNH BÀY (Layout Architecture)
* **Cách hỏi người dùng:** *"Bạn muốn cách sắp xếp nội dung trên trang đi theo hướng nào: (A) Tập trung vào hình ảnh sản phẩm cỡ lớn làm nhân vật chính, ít chữ; (B) Kể chuyện dẫn dắt từng bước từ vấn đề đến giải pháp; hay (C) Hiển thị danh mục nhiều sản phẩm/thông tin ngay lập tức để khách dễ chọn?"*
* **Bảng ánh xạ sang Kỹ thuật:**
  * *Phương án A (Visual-First Showcase)* $\rightarrow$ Hero tràn viền hoặc chia tỷ lệ vàng `7:5`, lưới bất đối xứng (Asymmetric Editorial Grid), ưu tiên tỷ lệ khung hình ảnh lớn (`16:10`, `4:5`).
  * *Phương án B (Narrative Storytelling)* $\rightarrow$ Luồng đọc chữ Z (Z-Pattern), xen kẽ giữa khối tiêu đề lệch trái và khối minh họa tương tác bên phải, có thanh tiến trình hoặc hiệu ứng cuộn theo chương.
  * *Phương án C (High-Utility Catalog)* $\rightarrow$ Luồng đọc chữ F (F-Pattern), thanh lọc (Filter/Search) cố định thông minh, lưới sản phẩm `4 cột` (Desktop) / `2 cột` (Mobile) với mật độ thông tin tối ưu.

#### Trụ cột 3: BẢNG MÀU KHOA HỌC (Color Palette)
* **Cách hỏi người dùng:** *"Thương hiệu của bạn đã có màu chủ đạo chưa? Bạn thích trang web mang tông Sáng trong trẻo (Light), Sáng ấm dịu mắt (Warm Paper), hay Tối sang trọng (Dark Mode)?"*
* **Quy tắc xử lý của Model:** Lấy màu chủ đạo của người dùng làm hạt giống (Seed Color), sau đó áp dụng công thức toán học **OKLCH 60-30-10** ở Chương 2 để sinh toàn bộ dải màu (tuyệt đối không dùng nguyên màu thuần `#FF0000` hay `#0000FF` gây chói mắt).

#### Trụ cột 4: KHOẢNG CÁCH & ĐỘ THOÁNG (Margins & Spatial Density)
* **Cách hỏi người dùng:** *"Bạn muốn các mục trên trang nằm thoáng đãng, cách xa nhau để tạo cảm giác thư thái cao cấp, hay xếp gọn gàng gần nhau để khách xem được nhiều thông tin cùng lúc mà không phải cuộn trang nhiều?"*
* **Bảng ánh xạ sang Kỹ thuật:**
  * *Thoáng đãng (Airy / Luxury)* $\rightarrow$ Section Padding dọc `96px–128px`, Container Margin hai bên rộng (Max-width `1200px–1280px`), Grid Gap `32px–48px`, Tỷ lệ khoảng trắng (Whitespace) $\ge 45\%$.
  * *Cân bằng tiêu chuẩn (Balanced Product)* $\rightarrow$ Section Padding dọc `64px–80px`, Container Max-width `1360px`, Grid Gap `24px`, Tỷ lệ khoảng trắng $35\%–40\%$.
  * *Cô đọng thông tin (High-Density / Dashboard / E-com lớn)* $\rightarrow$ Section Padding dọc `40px–56px`, Container Max-width `1440px`, Grid Gap `16px`, ưu tiên phân tách bằng đường kẻ mảnh `1px`.

#### Trụ cột 5: PHẠM VI & ĐỐI TƯỢNG NGƯỜI DÙNG (Scope & Target Persona)
* **Cách hỏi người dùng:** *"Khách hàng chính vào trang này là ai (độ tuổi, thói quen dùng điện thoại hay máy tính nhiều hơn)? Và hành động QUAN TRỌNG NHẤT bạn muốn họ bấm vào trước khi rời trang là gì (Ví dụ: Mua ngay, Đặt lịch tư vấn, hay Đăng ký dùng thử)?"*
* **Bảng ánh xạ sang Kỹ thuật:**
  * Xác định kích thước chữ cơ sở (`Base Font Size`: `16px` cho giới trẻ/công nghệ, `18px` nếu tệp khách hàng lớn tuổi hoặc đọc nhiều chữ).
  * Xác định duy nhất **1 Primary CTA** nổi bật nhất trên mỗi khung nhìn (Viewport) để dẫn hướng mắt người dùng.

---

### 1.3. Quy chuẩn Thu thập Assets & Ảnh/Link Tham khảo (Dùng ở Bước 4)
1. **Checklist Assets hỏi người dùng:** Logo (SVG/PNG), ảnh sản phẩm thực tế, Slogan/thông điệp chính, bảng giá/danh sách sản phẩm mẫu. *(Nếu người dùng chưa có sẵn ảnh sản phẩm, Agent ghi chú rõ trong `PRODUCT.md` để dùng ảnh chất lượng cao đúng chủ đề từ Unsplash/Pexels hoặc tạo bằng công cụ hình ảnh, tuyệt đối không để khung xám trống rỗng).*
2. **Quy tắc Vàng khi người dùng gửi Ảnh chụp màn hình (Screenshot Reference):**
   - **Bắt buộc khuyến nghị gửi kèm URL:** *"Bạn có thể gửi kèm thêm đường dẫn (Link URL) của trang web trong bức ảnh này không? Khi có cả Ảnh + Link, mình sẽ dùng Playwright đọc được chính xác 100% phông chữ, thông số lề và hiệu ứng mượt mà của họ để chắt lọc vào thiết kế riêng cho bạn!"*
   - **Cam kết Chống Sao chép (Anti-Cloning Rule):** Chỉ trích xuất *Triết lý Thiết kế & Thông số Thẩm mỹ* (xem Mục 2.4), tuyệt đối không sao chép nguyên xi bố cục và nội dung của ảnh.

---

## CHƯƠNG 2: HỆ THỐNG TOÁN HỌC CỦA THIẾT KẾ CHUẨN PRODUCT (Dành cho Bước 5 & Bước 8)

Để giao diện nhìn **chuẩn Product chuyên nghiệp** và không bao giờ bị nhận ra là "do AI làm", mọi thông số trong `DESIGN.md` phải tuân thủ 4 định luật toán học dưới đây:

### 2.1. Khoa học Phối màu trong Không gian OKLCH & Quy tắc 60-30-10
Các model AI thông thường chọn màu trong hệ RGB/HEX dẫn đến màu sắc bị chói (oversaturated) hoặc xỉn đục. Hệ thống SwarmUI bắt buộc tính toán màu trong không gian cảm nhận thị giác đồng đều **OKLCH** $\text{oklch}(L, C, H)$ (trong đó $L \in [0, 100\%]$ là Độ sáng cảm nhận, $C \in [0, 0.4]$ là Độ bão hòa màu, $H \in [0, 360^\circ]$ là Góc sắc độ):

1. **Quy tắc Phân bổ Tỷ lệ Diện tích 60 - 30 - 10:**
   - **60% — Màu Nền & Bề mặt (Dominant Surfaces):**
     - Không bao giờ dùng trắng tinh `#FFFFFF` đi với đen tuyền `#000000` trên diện rộng vì gây mỏi mắt.
     - *Light Mode chuẩn Product:* Pha một chút sắc độ (Hue $H$) của màu thương hiệu vào màu nền với độ bão hòa cực thấp ($C \in [0.003, 0.012]$):
       - Nền chính (`--bg-primary`): $\text{oklch}(98.5\%\ 0.005\ H_{\text{brand}})$
       - Nền thẻ/khối phụ (`--bg-surface`): $\text{oklch}(96\%\ 0.008\ H_{\text{brand}})$ hoặc `#FFFFFF` nổi trên nền `97%`.
     - *Dark Mode chuẩn Product:* Không dùng `#000000` phẳng lì; dùng độ sâu phân lớp theo độ cao (Elevation):
       - Nền sâu nhất (`--bg-primary`): $\text{oklch}(13\%\ 0.01\ H_{\text{brand}})$
       - Bề mặt thẻ nổi (`--bg-elevated`): $\text{oklch}(18\%\ 0.015\ H_{\text{brand}})$ kèm đường viền sáng mảnh ở cạnh trên (`border-top: 1px solid rgba(255,255,255,0.08)`).
   - **30% — Màu Cấu trúc, Chữ & Đường viền (Secondary / Structural & Typography):**
     - Phân cấp độ tương phản chữ thành 3 tầng rõ rệt (pha nhẹ sắc độ thương hiệu $C \approx 0.015$ để chữ hòa quyện với nền):
       - `--text-primary` (Tiêu đề & Nội dung chính): $L = 15\%$ (Light mode) / $L = 96\%$ (Dark mode).
       - `--text-secondary` (Mô tả phụ): $L = 42\%$ (Light mode) / $L = 72\%$ (Dark mode).
       - `--text-muted` (Chú thích nhỏ, Placeholder): $L = 58\%$ (Light mode) / $L = 52\%$ (Dark mode).
     - Đường viền (`--border-subtle`): $L = 90\%$ (Light mode) / $L = 24\%$ (Dark mode) — chỉ đủ để mắt cảm nhận ranh giới mà không gây rối.
   - **10% — Màu Điểm nhấn & Hành động (Primary Accent & CTA):**
     - Chỉ dành riêng cho nút kêu gọi hành động chính (`Primary CTA`), trạng thái đang chọn (`Active`), và con số/biểu tượng quan trọng nhất.
     - Độ bão hòa cao ($C \in [0.16, 0.26]$) nhưng độ sáng $L$ phải đảm bảo độ tương phản chữ trên nút đạt chuẩn **WCAG AA ($\ge 4.5:1$)** hoặc **APCA $L_c \ge 60$**.

### 2.2. Toán học Phân cấp Chữ (Modular Typography Scale)
1. **Quy tắc Kết hợp Phông chữ (Font Pairing Law):**
   - Tối đa **2 họ phông chữ** trên toàn trang (hoặc 3 nếu tính thêm `Monospace` cho mã số/giá tiền/nhãn kỹ thuật):
     - `Font Heading`: Tạo cá tính thương hiệu (`letter-spacing: -0.02em` đến `-0.035em` cho cỡ chữ lớn $> 32\text{px}$, `line-height: 1.1` đến `1.2`).
     - `Font Body`: Ưu tiên độ dễ đọc tuyệt đối (`line-height: 1.5` đến `1.65`, độ dài mỗi dòng văn bản bắt buộc nằm trong khoảng **`45ch` đến `72ch`** — không bao giờ để 1 dòng chữ dài tràn hết màn hình `1440px`).
2. **Tỷ lệ Phóng Chữ (Typographic Scale Ratio $r$):**
   - Kích thước chữ ở các cấp bậc $S_n = S_0 \times r^n$ (với $S_0 = 16\text{px}$):
     - Giao diện nhiều thông tin (Dashboard / E-commerce): Dùng tỷ lệ *Major Second ($r = 1.125$)* hoặc *Minor Third ($r = 1.200$)*.
     - Giao diện Landing Page / Thương hiệu: Dùng tỷ lệ *Major Third ($r = 1.250$)* hoặc *Perfect Fourth ($r = 1.333$)*.
   - Sử dụng hàm `clamp(min, preferred, max)` cho tiêu đề lớn để tự động co giãn mượt mà từ Mobile lên Desktop.

### 2.3. Hệ Lưới Không gian 8pt & Định luật Khoảng cách (Margins & Spatial Rhythm)
1. **Hệ cơ số 8 (8pt Spatial Grid):**
   - Mọi giá trị `margin`, `padding`, `gap`, chiều cao nút bấm đều phải nằm trong dãy số chuẩn:
     $$\mathcal{S} = \{4\text{px}, 8\text{px}, 12\text{px}, 16\text{px}, 24\text{px}, 32\text{px}, 48\text{px}, 64\text{px}, 80\text{px}, 96\text{px}, 128\text{px}\}$$
   - **Cấm tuyệt đối** các con số lẻ tùy tiện kiểu `padding: 13px 27px` hay `margin-bottom: 19px`.
2. **Định luật Khoảng cách Trong $\le$ Khoảng cách Ngoài (Law of Proximity in Margins):**
   - Trong bất kỳ khối (Card / Section) nào, khoảng cách giữa các phần tử có liên quan bên trong ($d_{\text{internal}}$) **bắt buộc phải nhỏ hơn** khoảng cách từ nội dung ra mép viền thẻ ($d_{\text{padding}}$), và nhỏ hơn khoảng cách giữa các Section với nhau ($d_{\text{section-margin}}$):
     $$d_{\text{inline-elements}} (8\text{px}–12\text{px}) < d_{\text{card-padding}} (24\text{px}–32\text{px}) < d_{\text{section-gap}} (64\text{px}–128\text{px})$$

### 2.4. Giải thuật Học Đặc trưng Thiết kế từ Ảnh + URL (Chống Sao chép 100% — Dùng ở Bước 5)
Khi nhận được **Ảnh chụp màn hình** (và **Link URL** do người dùng gửi kèm), Agent thực hiện bộ lọc **Tách Bố cục – Giữ Triết lý (Style-Structure Decoupling)**:

| Thành phần ĐƯỢC PHÉP học và đưa vào `DESIGN.md` (Style DNA) | Thành phần BỊ CẤM SAO CHÉP tuyệt đối (Anti-Cloning) |
| :--- | :--- |
| 1. **Mối quan hệ màu sắc:** Độ chênh lệch sáng tối giữa nền và thẻ, cách dùng màu nhấn (tiết chế hay rực rỡ), nhiệt độ màu (ấm hay lạnh).<br>2. **Cấu trúc Typography:** Sự tương phản giữa độ dày tiêu đề và chữ nội dung, cách viết hoa nhãn nhỏ (`uppercase tracking-widest`).<br>3. **Xử lý bề mặt (Surface Treatment):** Cách bo góc (`0px`, `8px`, hay `24px`), cách phân tách khối (dùng đường kẻ `1px` mờ, dùng khoảng trắng lớn, hay dùng đổ bóng nhiều lớp).<br>4. **Nhịp điệu chuyển động (nếu có URL):** Tốc độ hover, hiệu ứng lướt chữ hoặc làm mờ kính (`backdrop-filter`). | 1. **Cây cấu trúc DOM & Thứ tự khối y hệt trang mẫu** (Không được bê nguyên khung HTML của trang mẫu sang).<br>2. **Văn bản, câu chữ, tên thương hiệu, logo và hình ảnh gốc** bên trong ảnh chụp màn hình.<br>3. **Số lượng và vị trí chính xác từng nút bấm** nếu nó không phục vụ đúng mục đích (`Scope`) mà người dùng đã trả lời ở Bước 3. |

---

## CHƯƠNG 3: TỪ ĐIỂN CHỐNG "AI SLOP" (ANTI-AI-SLOP BLACKLIST) (Dành cho Bước 5, 8, 9, 11)

> [!WARNING]
> Nếu bất kỳ Agent nào trong Phòng Design (Bước 8) hoặc Phòng Developer (Bước 9) vi phạm 1 trong 10 điều cấm dưới đây, **Cursor Lớn Nhất (Bước 11)** sẽ đánh trượt (`FAIL`) ngay lập tức và yêu cầu làm lại.

| # | Dấu hiệu "Mùi AI" bị CẤM TUYỆT ĐỐI (AI Slop Pattern) | Giải pháp Chuẩn Product Thay Thế (Professional Product Standard) |
| :--- | :--- | :--- |
| **1** | **Dải màu Gradient Tím – Xanh – Hồng mặc định** (`from-indigo-500 via-purple-500 to-pink-500`) trên chữ tiêu đề hoặc nút bấm. | Sử dụng màu đơn sắc có chiều sâu trong hệ **OKLCH**, hoặc ánh sáng nền khuếch tán cực nhẹ (Subtle Radial Glow độ mờ `< 12%`) đúng tông màu thương hiệu trong `DESIGN.md`. |
| **2** | **Lặp lại liên tục "Hàng 3 Thẻ Card giống hệt nhau"** (Section nào cũng là 1 tiêu đề căn giữa + 3 ô vuông bo góc có icon tròn ở góc trái). | **Đa dạng hóa Nhịp điệu Thị giác (Visual Rhythm):** Kết hợp bố cục 2 cột bất đối xứng (`60/40`), bảng so sánh tương tác (Interactive Tabs/Accordion), danh sách đánh số lớn kiểu tạp chí (Editorial Numbered List), hoặc lưới Bento có kích thước ô khác nhau (`col-span-2` kết hợp `col-span-1`). |
| **3** | **Hội chứng Căn Giữa Toàn Trang (Center-Everything Syndrome):** Mọi tiêu đề, đoạn văn dài 4–5 dòng, và thẻ thông tin đều `text-align: center`. | Chỉ căn giữa khi tiêu đề ngắn đi kèm tối đa 2 dòng mô tả (`< 65ch`). Toàn bộ văn bản dài, danh sách tính năng, thông số sản phẩm **bắt buộc căn trái (`text-left`)** để mắt người đọc có điểm neo cố định. |
| **4** | **Lạm dụng Icon vô nghĩa ở mọi dòng chữ** (Gắn icon tên lửa 🚀, tia sét ⚡, khiên bảo vệ 🛡️ vào mọi tiêu đề nhỏ). | Chỉ dùng Icon khi nó giúp nhận diện chức năng điều hướng hoặc trạng thái. Thay các icon trang trí sáo rỗng bằng **Hình ảnh sản phẩm thật (Assets Bước 4)**, số liệu định lượng rõ ràng, hoặc đồ họa vi mô (Micro-UI Mockup). |
| **5** | **Đổ bóng đen đục và nặng nề** (`shadow-lg`, `shadow-xl` mặc định trên mọi thẻ làm giao diện nhìn bẩn và lỗi thời). | Ưu tiên phân tách bề mặt bằng **Độ chênh lệch màu nền nhẹ** + **Viền mảnh `1px`** (`border-subtle`). Nếu cần đổ bóng (cho Dropdown, Modal, Floating Card), dùng bóng đa lớp có độ trong suốt cực thấp (`opacity: 0.03 - 0.06`) pha sắc độ của nền. |
| **6** | **Nội dung chữ (Copywriting) sáo rỗng kiểu ChatGPT:** Dùng các từ *"Nâng tầm trải nghiệm"*, *"Khám phá tiềm năng vô hạn"*, *"Giải pháp đột phá hàng đầu"* hay dữ liệu giả *"Lorem ipsum"*, *"John Doe"*. | Viết nội dung cụ thể, sắc bén, mang tính thực tế cao dựa trên thông tin ngành hàng và Assets người dùng cung cấp ở Bước 3 & Bước 4 (có giá tiền thật, thông số kỹ thuật cụ thể, tên danh mục thực tế). |
| **7** | **Nút bấm (Buttons) lơ lửng không có phân cấp:** Đặt 2–3 nút đậm màu cạnh nhau khiến người dùng không biết bấm vào đâu. | Tuân thủ quy tắc **1 Primary + 1 Secondary**: Nút chính (`Primary CTA`) dùng màu đặc nổi bật; nút phụ (`Secondary CTA`) dùng nền trong suốt có viền mảnh hoặc dạng liên kết có mũi tên dịch chuyển khi di chuột (`hover:translate-x-1`). |
| **8** | **Hình ảnh bị méo tỷ lệ hoặc không đồng nhất phong cách:** Các khung ảnh sản phẩm cao thấp lộn xộn, chữ đè lên ảnh sáng màu không đọc được. | Khóa tỷ lệ khung hình chuẩn (`aspect-square 1:1`, `aspect-[4/5]` cho thời trang, `aspect-video 16:9` cho công nghệ) với `object-fit: cover`. Nếu đặt chữ trên ảnh, bắt buộc có lớp phủ chuyển sắc tối dần (`scrim gradient`) để đảm bảo độ tương phản chữ. |
| **9** | **Giao diện tĩnh "chết" (Zero Micro-interactions):** Khi di chuột vào nút, thẻ sản phẩm, ô nhập liệu không có bất kỳ phản hồi thị giác nào. | Mọi phần tử tương tác phải có chuyển đổi mượt mà (`transition: all 200ms cubic-bezier(0.22, 1, 0.36, 1)`), trạng thái `hover`, `active` (nhấn xuống nhẹ `scale-[0.98]`), và `focus-visible` rõ ràng. |
| **10** | **Thiếu các Trạng thái Thực tế của Product (Missing Product States):** Trang bán hàng chỉ có ảnh tĩnh, bấm vào giỏ hàng hoặc bộ lọc không có phản ứng gì. | Vì xây dựng trang web **có thể sử dụng được**, Phòng Developer (Bước 9) phải lập trình đầy đủ trạng thái tương tác thực tế cho trang đó (VD: Lọc danh mục hoạt động thật, chọn kích cỡ/màu sắc đổi trạng thái thật, mở ngăn kéo Giỏ hàng / Modal xem nhanh, kiểm tra lỗi form đăng nhập). |

---

## CHƯƠNG 4: KHUÔN MẪU BỘ 3 TÀI LIỆU (`DESIGN.md`, `PRODUCT.md`, `PLAN.md`) & QUY TẮC ĐỒNG BỘ 2 PHÒNG BAN (Dành cho Bước 5 $\rightarrow$ Bước 10)

### 4.1. Cấu trúc chuẩn của `DESIGN.md` (Sinh ra ở Bước 5)
```markdown
# DESIGN.md — Hiến pháp Thiết kế & Triết lý Thị giác
1. **Triết lý Thiết kế Cốt lõi (Design Philosophy Statement):** (Đúc kết 3 nguyên tắc thẩm mỹ riêng biệt cho dự án này).
2. **Hồ sơ Đặc trưng Học từ Tham khảo (Extracted Style DNA):** (Những quy luật học từ Ảnh/URL của người dùng + Ranh giới chống sao chép).
3. **Hệ thống Màu sắc Khoa học (OKLCH 60-30-10 Token Table):** (Mã màu chính xác cho Background, Surface, Text 3 cấp, Border, Primary Accent, Semantic States).
4. **Hệ thống Chữ (Typography Hierarchy):** (Họ font, Scale Ratio, cỡ chữ từ Display/H1 đến Caption, Line-height, Letter-spacing).
5. **Hệ thống Không gian & Lề (Spatial Grid & Margins):** (Max-width container, Section Padding Desktop/Mobile, Card Padding, Grid Gap, Border Radius, Elevation/Shadow).
6. **Ngôn ngữ Chuyển động & Hiệu ứng 2D/3D (Motion & MCP Specs - B8.1):** (Các đường cong Easing, hiệu ứng cuộn, hoặc yêu cầu 2D/3D cụ thể).
```

### 4.2. Cấu trúc chuẩn của `PRODUCT.md` (Sinh ra ở Bước 6)
```markdown
# PRODUCT.md — Đặc tả Sản phẩm & Hệ thống Trang
1. **Chân dung Người dùng & Mục tiêu Cốt lõi (Scope & Persona):** (Từ câu trả lời Bước 3).
2. **Bản đồ Hệ thống Trang (Full Product Sitemap):** (Danh sách toàn bộ các trang từ Bước 2 và trạng thái: [Đã hoàn thành] / [Đang xây dựng] / [Chờ xây dựng]).
3. **Kho Tài nguyên (User Assets Inventory):** (Đường dẫn Logo, hình ảnh sản phẩm, nội dung chữ, dữ liệu danh mục thu thập ở Bước 4).
4. **Luồng Tương tác Liên trang (Cross-Page Navigation & State Contract):** (Cách trang hiện tại kết nối với các trang tiếp theo).
```

### 4.3. Cấu trúc chuẩn của `PLAN.md` (Sinh ra ở Bước 6, chờ duyệt ở Bước 7)
```markdown
# PLAN.md — Kế hoạch Triển khai Vi mô cho Trang: [Tên Trang Hiện Tại]
1. **Cấu trúc Phân vùng từ Trên xuống Dưới (Section-by-Section Blueprint & Visual Rhythm):** (Mô tả bố cục từng Section sao cho không trùng lặp).
2. **Phân công Nhân sự Vi mô (Micro-Subagent Task Matrix):**
   - **Phòng DESIGN (Playwright Browser - B8):** Nhiệm vụ bố trí khung, căn chỉnh Margins, kiểm tra màu sắc cho từng Cursor; chỉ định rõ phần nào gọi **MCP 2D/3D (B8.1)**.
   - **Phòng DEVELOPER (Next.js / Angular - B9):** Cấu trúc cây Component, quản lý State tương tác, gắn mã định danh `data-swarm-id`.
3. **Danh sách Test Case Bắt buộc cho "Cursor Lớn Nhất" (Master Cursor E2E Checklist - B11):** (Liệt kê từng nút bấm, từng luồng cuộn và các điểm kiểm tra Responsive trên trang này).
```

### 4.4. Giao thức Đồng bộ giữa Phòng Design & Phòng Developer (Bước 8 & Bước 9)
Để đàn Cursor của **Phòng Design** trên trình duyệt Playwright và tiến trình sinh code của **Phòng Developer** (Next.js hoặc Angular) khớp nhau từng milimet:
- Mọi khối Section và phần tử tương tác do Phòng Developer viết code đều phải gắn thuộc tính chuẩn:
  - `data-swarm-section="<section-id>"` (Ví dụ: `data-swarm-section="hero-showcase"`)
  - `data-swarm-id="<element-id>"` (Ví dụ: `data-swarm-id="primary-cta-buy-now"`)
  - `data-swarm-role="<interactive-type>"` (Ví dụ: `button | nav-link | filter-tab | input-field | modal-trigger`)
- Nhờ các thuộc tính này:
  1. Ở **Bước 8**, các Cursor của Phòng Design (`Layout Cursor`, `Color Cursor`, `Typography Cursor`, `Motion MCP Cursor`) biết chính xác tọa độ $(x, y, width, height)$ trên màn hình để bay tới vẽ thước đo và tinh chỉnh trực quan.
  2. Ở **Bước 11**, **Cursor Lớn Nhất (Master QA Cursor)** quét toàn bộ `[data-swarm-role]` để không bỏ sót bất kỳ nút bấm nào khi chạy Test Case.

---

## CHƯƠNG 5: BỘ QUY CHUẨN KIỂM THỬ TỰ ĐỘNG CHO "CURSOR LỚN NHẤT" (Dành cho Bước 11)

Khi trang web hoàn thành ở Bước 10, **Cursor Lớn Nhất (Master QA Cursor)** sẽ xuất hiện trên trình duyệt Playwright và thực hiện tuần tự **4 Bài Kiểm Tra Thực Chiến** dưới đây trước mặt người dùng:

### Bài Test 1: Kiểm tra Thao tác Từng Nút Một (Interactive Element Sweep)
`Master Cursor` di chuyển đường dẫn chuột mượt mà tới từng phần tử tương tác (`button`, `a`, `input`, `[data-swarm-role]`) từ đầu trang xuống cuối trang:
- **Kiểm tra khả năng hiển thị & Vùng chạm:** Chiều cao và chiều rộng vùng bấm trên Mobile phải đạt $\ge 40\text{px}$ (khuyến nghị $44\text{px}$), không bị phần tử khác che khuất (`elementFromPoint` trả về đúng nút đó).
- **Kiểm tra Phản hồi Thị giác (`Hover & Focus`):** Khi `Master Cursor` dừng lại trên nút (`page.hover()`), style của nút phải thay đổi (màu nền, độ sáng, viền hoặc `transform`) so với trạng thái nghỉ.
- **Kiểm tra Hành vi Click (`Click & State Transition`):** Khi `Master Cursor` bấm vào các nút lọc danh mục, chuyển tab, mở giỏ hàng, hoặc gửi form trống, giao diện phải phản hồi đúng logic nghiệp vụ trong `PLAN.md` và không phát sinh bất kỳ lỗi `console.error` hay `uncaught exception` nào trên trình duyệt.

### Bài Test 2: Kiểm tra Cuộn Trang & Bố cục Động (Scroll & Sticky Choreography)
`Master Cursor` thực hiện cuộn trang mượt mà (`smooth scroll`) từ `scrollY = 0` đến kịch đáy trang `document.body.scrollHeight` rồi cuộn ngược lên:
- Kiểm tra thanh điều hướng (`Sticky/Fixed Header`) không đè mất nội dung khi dừng cuộn và có độ tương phản nền rõ ràng (`backdrop-filter: blur()`).
- Kiểm tra các hiệu ứng xuất hiện khi cuộn (Scroll-triggered animations từ Bước 8.1) hoạt động đúng thời điểm, không có phần tử nào bị kẹt ở trạng thái ẩn (`opacity: 0`).
- Kiểm tra tất cả hình ảnh (`<img>`) đã tải thành công (`naturalWidth > 0`), không có ảnh bị lỗi gãy link.

### Bài Test 3: Kiểm tra Đa Màn Hình (4-Breakpoint Responsive Audit)
`Master Cursor` lần lượt thu phóng cửa sổ Playwright qua 4 kích thước tiêu chuẩn:
1. **Desktop Wide (`1440 × 900`)**
2. **Laptop (`1024 × 768`)**
3. **Tablet (`768 × 1024`)**
4. **Mobile (`375 × 812`)**

Tại mỗi kích thước, `Master Cursor` chạy thuật toán kiểm tra DOM trực tiếp:
- **Không tràn khung ngang (Zero Horizontal Overflow):** `document.documentElement.scrollWidth <= document.documentElement.clientWidth`.
- **Không chồng lấn văn bản (Zero Text/Box Collision):** Không có 2 khối chữ hoặc nút bấm cùng tầng bị đè tọa độ (`BoundingBox` giao nhau trái phép).
- **Kiểm tra Lề Ngoài (`Margins`):** Ở màn hình Mobile (`375px`), mọi nội dung văn bản và thẻ phải cách mép màn hình trái/phải tối thiểu `16px–24px` (không bao giờ dính sát mép màn hình `0px` trừ ảnh tràn viền có chủ đích).

### Bài Test 4: Kiểm toán Tuân thủ `DESIGN.md` & Chống "AI Slop" (Aesthetic & Token Audit)
`Master Cursor` đọc `getComputedStyle` trên toàn trang và đối chiếu với `DESIGN.md`:
- Xác nhận phông chữ thực tế đang hiển thị khớp 100% với `DESIGN.md`.
- Xác nhận độ tương phản giữa màu chữ và màu nền tại mọi khối đạt chuẩn đọc hiểu rõ ràng.
- Xác nhận không vi phạm bất kỳ mục nào trong **10 Điều Cấm Chống AI Slop** (Chương 3).

> [!TIP]
> **Tiêu chuẩn Chuyển nhượng ở Bước 12:** Chỉ khi cả 4 Bài Test của **Cursor Lớn Nhất** đều hiển thị tích xanh (`100% PASSED`), hệ thống mới bật thông báo bàn giao để người dùng trực tiếp cầm chuột trải nghiệm, sau đó chọn **Upgrade trang hiện tại** hoặc **Chuyển sang Build trang tiếp theo** trong `PRODUCT.md`.
