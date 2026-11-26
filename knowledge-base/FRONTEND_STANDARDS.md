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
  * *Thân thiện, gần gũi, đời sống (Warm Organic)* $\rightarrow$ Font chữ nét tròn mềm (`DM Sans`, `Outfit`), bo góc lớn (`16px–24px`), nút bấm dạng viên thuốc (`9999px`), đổ bóng khuếch tán mềm mại. *(Khi nút đã là viên thuốc, badge/tag phải khác nút bằng cách khác: không dùng màu nhấn, dùng màu trạng thái hoặc nền nhạt, cỡ nhỏ hơn — xem §6.6.)*
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
  * Xác định kích thước chữ cơ sở (`Base Font Size`: `16px` cho giới trẻ/công nghệ, `18px` nếu tệp khách hàng lớn tuổi hoặc đọc nhiều chữ). **Bất kể persona, đoạn văn dài (bài viết, mô tả sản phẩm, chính sách) luôn dùng tối thiểu `18px`**; `16px` chỉ dành cho trang ít chữ, giao diện nhiều thông tin (dashboard) và chữ phụ.
  * Xác định duy nhất **1 Primary CTA** nổi bật nhất trên mỗi khung nhìn (Viewport) để dẫn hướng mắt người dùng.

---

### 1.3. Quy chuẩn Thu thập Assets & Ảnh/Link Tham khảo (Dùng ở Bước 4)
1. **Checklist Assets hỏi người dùng:** Logo (SVG/PNG), ảnh sản phẩm thực tế, Slogan/thông điệp chính, bảng giá/danh sách sản phẩm mẫu. *(Nếu người dùng chưa có sẵn ảnh sản phẩm, Agent ghi chú rõ trong `PRODUCT.md` để dùng ảnh chất lượng cao đúng chủ đề từ Unsplash/Pexels hoặc tạo bằng công cụ hình ảnh, tuyệt đối không để khung xám trống rỗng. Thực thi: `developer/photos.py` chọn bộ ảnh Unsplash license miễn phí theo chủ đề từ lời người dùng — đã kiểm tra bằng mắt — và luôn có ảnh dự phòng tông trung tính khi mất mạng).*
2. **Quy tắc Vàng khi người dùng gửi Ảnh chụp màn hình (Screenshot Reference):**
   - **Bắt buộc khuyến nghị gửi kèm URL:** *"Bạn có thể gửi kèm thêm đường dẫn (Link URL) của trang web trong bức ảnh này không? Khi có cả Ảnh + Link, mình sẽ dùng Playwright đọc được chính xác 100% phông chữ, thông số lề và hiệu ứng mượt mà của họ để chắt lọc vào thiết kế riêng cho bạn!"*
   - **Cam kết Chống Sao chép (Anti-Cloning Rule):** Chỉ trích xuất *Triết lý Thiết kế & Thông số Thẩm mỹ* (xem Mục 2.4), tuyệt đối không sao chép nguyên xi bố cục và nội dung của ảnh.
   - **Ngoại lệ duy nhất: Clone mode** (người dùng chọn ở Bước 1). Quy tắc chống sao chép ở trên chỉ áp dụng cho **Creative mode**. Ở Clone mode, model được phép dựng lại trang mẫu y hệt theo mức người dùng cho phép — xem Mục 2.5.

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
     - **Sàn tương phản bắt buộc cho mọi tầng chữ:** chữ $\le 18\text{px}$ (kể cả `--text-muted` dùng cho chú thích, placeholder ô tìm kiếm) phải đạt **WCAG $\ge 4.5:1$** trên nền nó nằm; chữ body dài nên đạt **APCA $L_c \ge 75$**. Một tầng chữ không đạt 4.5:1 chỉ được dùng cho chữ lớn ($\ge 24\text{px}$ thường hoặc $\ge 18\text{px}$ đậm, sàn **3:1**). Đo trên nền tham chiếu: `--text-muted` Light cần $L \le 55\%$, Warm Paper $L \le 54\%$ để đạt 4.5:1 ($L = 58\%$ chỉ đạt khoảng 4.1:1). Không bao giờ dùng chữ xám nhạt "cho mềm mắt".
     - Đường viền **trang trí** (`--border-subtle`): $L = 90\%$ (Light mode) / $L = 24\%$ (Dark mode) — chỉ đủ để mắt cảm nhận ranh giới mà không gây rối. Chỉ dùng cho đường phân cách, khung card, những thứ bỏ đi vẫn không ảnh hưởng thao tác.
     - Đường viền **thành phần** (`--border-strong`): bắt buộc **WCAG $\ge 3:1$** với nền — dùng cho viền ô nhập, select, textarea, checkbox, radio, toggle, stepper, viền nút secondary. Tham chiếu: Light $L \le 65\%$, Warm Paper $L \le 64\%$, Dark $L \ge 48\%$. Ô nhập có viền mờ là lỗi UI phổ biến nhất: thiếu viền, người dùng không biết đó là chỗ để gõ.
   - **10% — Màu Điểm nhấn & Hành động (Primary Accent & CTA):**
     - Chỉ dành riêng cho **phần tử tương tác**: nút kêu gọi hành động chính (`Primary CTA`), link, viền/chữ nút secondary, trạng thái đang chọn (`Active`) của tab/bộ lọc. Màu nhấn dạy người dùng "màu này là bấm được", nên **không tô màu nhấn cho tiêu đề, con số hay icon không bấm được** (dễ bị tưởng là link) — làm nổi chúng bằng kích thước, độ đậm và `--text-primary`.
     - **Màu hành động (`--action`)**: mọi nút, link, viền nút phụ dùng chung một token. Preset *Hiện đại* và *Cá tính* đặt `--action` = màu nhấn thương hiệu; preset *Sang trọng* và *Ấm áp* đặt `--action` = gần đen (`--text-primary`) — giao diện trung tính, màu sắc đến từ ảnh (9/10 trang mẫu hiện đại để màu nhấn chiếm ≤ 5% diện tích, xem `MODERN_UI_REFERENCES.md`). Dải nền lớn (dải CTA, banner) dùng màu trung tính, không dùng màu nhấn; tổng diện tích nền màu bão hoà ≤ 10% trang.
     - Nếu thương hiệu có nhiều màu: chỉ **1 màu** (màu có tương phản cao nhất với nền) được dùng cho tương tác; các màu còn lại chỉ dùng tiết chế cho trang trí (nền phụ, minh hoạ).
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
   - Tỷ lệ lớn trên mobile làm tiêu đề xuống dòng quá nhiều → **mobile dùng tỷ lệ nhỏ hơn** desktop.
   - Tiêu đề hero (`display`) trên desktop tối thiểu **72px**, `letter-spacing` khoảng `-0.03em`, `line-height` khoảng `1.05` (trang mẫu hiện đại dùng 64–96px).
   - Làm tròn mọi cỡ chữ về số nguyên; không tạo cấp chữ không dùng tới.
3. **Độ đậm (Font Weight):** Mỗi họ phông chỉ dùng **2 độ đậm**: `400` (regular) cho chữ thường và `700` (bold) cho tiêu đề/nhấn mạnh — được thay `700` bằng `600` nếu bold quá nặng. Độ đậm cực mảnh (`100–300`) hoặc cực dày (`800–900`) chỉ dùng cho tiêu đề cỡ lớn, không bao giờ cho chữ $\le 18\text{px}$.
4. **Nhịp dòng theo cỡ chữ:** Cỡ chữ càng lớn thì `line-height` càng nhỏ (body `1.5–1.65`, tiêu đề `1.1–1.3`) để khoảng hở thực tế giữa các dòng đều nhau. Typeface đậm hoặc "trông to" cần `line-height` cao hơn trong khoảng cho phép.
5. **Căn chữ:** Đoạn văn dài **căn trái**; cấm `text-align: justify` (tạo "dòng sông" khoảng trắng, khó đọc với người dyslexia). Chữ khác cỡ nằm cùng một hàng (giá + đơn vị "/tháng", số liệu + nhãn) **căn theo baseline** (`align-items: baseline`), không căn giữa theo chiều dọc.
6. **Chữ in hoa:** Chỉ dùng cho **nhãn ngắn** (eyebrow, badge) — luôn kèm cỡ nhỏ (`12–14px`), đậm, `letter-spacing: 0.08em–0.15em`. Không in hoa tiêu đề hay câu dài.
7. **Phông chữ:** Mặc định an toàn là **1 họ sans serif** cho toàn bộ chữ; họ thứ hai (nếu preset có) chỉ dùng cho tiêu đề. Phông phải có x-height cao, đủ 2 độ đậm ở mục 3, và **có bộ ký tự tiếng Việt**.

### 2.3. Hệ Lưới Không gian 8pt & Định luật Khoảng cách (Margins & Spatial Rhythm)
1. **Hệ cơ số 8 (8pt Spatial Grid):**
   - Mọi giá trị `margin`, `padding`, `gap`, chiều cao nút bấm đều phải nằm trong dãy số chuẩn:
     $$\mathcal{S} = \{4\text{px}, 8\text{px}, 12\text{px}, 16\text{px}, 24\text{px}, 32\text{px}, 48\text{px}, 64\text{px}, 80\text{px}, 96\text{px}, 128\text{px}\}$$
   - **Cấm tuyệt đối** các con số lẻ tùy tiện kiểu `padding: 13px 27px` hay `margin-bottom: 19px`.
2. **Định luật Khoảng cách Trong $\le$ Khoảng cách Ngoài (Law of Proximity in Margins):**
   - Trong bất kỳ khối (Card / Section) nào, khoảng cách giữa các phần tử có liên quan bên trong ($d_{\text{internal}}$) **bắt buộc phải nhỏ hơn** khoảng cách từ nội dung ra mép viền thẻ ($d_{\text{padding}}$), và nhỏ hơn khoảng cách giữa các Section với nhau ($d_{\text{section-margin}}$):
     $$d_{\text{inline-elements}} (8\text{px}–12\text{px}) < d_{\text{card-padding}} (24\text{px}–32\text{px}) < d_{\text{section-gap}} (64\text{px}–128\text{px})$$

### 2.4. Giải thuật Học Đặc trưng Thiết kế từ Ảnh + URL (Chống Sao chép 100% — Creative mode, Dùng ở Bước 5)
Khi nhận được **Ảnh chụp màn hình** (và **Link URL** do người dùng gửi kèm), Agent thực hiện bộ lọc **Tách Bố cục – Giữ Triết lý (Style-Structure Decoupling)**:

| Thành phần ĐƯỢC PHÉP học và đưa vào `DESIGN.md` (Style DNA) | Thành phần BỊ CẤM SAO CHÉP tuyệt đối (Anti-Cloning) |
| :--- | :--- |
| 1. **Mối quan hệ màu sắc:** Độ chênh lệch sáng tối giữa nền và thẻ, cách dùng màu nhấn (tiết chế hay rực rỡ), nhiệt độ màu (ấm hay lạnh).<br>2. **Cấu trúc Typography:** Sự tương phản giữa độ dày tiêu đề và chữ nội dung, cách viết hoa nhãn nhỏ (`uppercase tracking-widest`).<br>3. **Xử lý bề mặt (Surface Treatment):** Cách bo góc (`0px`, `8px`, hay `24px`), cách phân tách khối (dùng đường kẻ `1px` mờ, dùng khoảng trắng lớn, hay dùng đổ bóng nhiều lớp).<br>4. **Nhịp điệu chuyển động (nếu có URL):** Tốc độ hover, hiệu ứng lướt chữ hoặc làm mờ kính (`backdrop-filter`). | 1. **Cây cấu trúc DOM & Thứ tự khối y hệt trang mẫu** (Không được bê nguyên khung HTML của trang mẫu sang).<br>2. **Văn bản, câu chữ, tên thương hiệu, logo và hình ảnh gốc** bên trong ảnh chụp màn hình.<br>3. **Số lượng và vị trí chính xác từng nút bấm** nếu nó không phục vụ đúng mục đích (`Scope`) mà người dùng đã trả lời ở Bước 3. |

> [!NOTE]
> Bảng trên là luật của **Creative mode**. Ở **Clone mode**, các thành phần trong cột "Bị cấm" được mở khóa theo Mục 2.5.

### 2.5. Clone mode — Dựng lại y hệt trang mẫu (Ngoại lệ của Mục 2.4, Dùng ở Bước 1 → Bước 6)
Người dùng chọn **Clone mode** và gửi URL. Clone mặc định đọc đầy đủ bố cục, văn bản, thương hiệu, logo, hình ảnh và hiệu ứng của trang mẫu; không có bước xác nhận sở hữu hay lọc nội dung theo quyền sở hữu.

Quy tắc bắt buộc:
1. Sketch phải bao phủ toàn bộ trang từ header tới footer, đo đủ component trong mỗi section, kể cả phần tử chuyển động hoặc có `aria-hidden` nhưng vẫn được vẽ trên màn hình.
2. Với animation lặp, giữ vị trí đã đo trong khung cắt, hướng và chu kỳ; thể hiện các component chuyển động trong sketch. Vùng chưa đọc được phải đánh dấu rõ, không coi khung ảnh nền lớn là đã đọc đủ nội dung bên trên.
3. Clone mode **vẫn qua đủ các cổng chặn**: duyệt kế hoạch ở Bước 7, chuẩn màu – chữ – lưới 8pt ở Chương 2, và 4 bài kiểm thử của Cursor Lớn Nhất ở Chương 5. Trang dựng lại phải đạt chuẩn như một trang Creative.
4. Section nào trang mẫu có mà hệ thống chưa dựng được, model dựng bằng kiểu gần nhất và ghi rõ trong `PLAN.md`.

### 2.5b. Kho bố cục Hero & Nhịp Section
1. **Hero chọn theo Trụ cột 2 (và 1)**, không dùng một kiểu cho mọi trang:
   - *Nhiều sản phẩm (Catalog)* → chia đôi `7:5`, gọn để sản phẩm xuất hiện sớm.
   - *Kể chuyện (Narrative)* → **kiểu tạp chí**: tiêu đề rất lớn trải ngang, mô tả + nút trên một hàng, ảnh rộng `21:9` bên dưới.
   - *Hình ảnh lớn (Visual-first)* → **ảnh tràn màn hình** có lớp phủ tối và chữ trên ảnh (Sang trọng, Ấm áp, Cá tính); hoặc **sản phẩm đặt giữa** trên tấm nền dịu (Hiện đại).
2. **Nhịp nền:** các section nội dung sau hero xen kẽ nền thường / nền tô nhạt (`--bg-surface`); dải CTA cuối dùng nền tối trung tính.
3. **Hàng kể chuyện (Z):** ảnh luôn chiếm cột rộng, tỷ lệ ảnh đổi giữa các hàng (`3:2` ↔ `4:5`) để không lặp.
4. **Ảnh trong một trang:** mỗi section lấy ảnh nối tiếp section trước, không bắt đầu lại từ ảnh đầu; hạn chế lặp ảnh ở gần nhau.

### 2.5c. Lưới Bố cục 12 Cột (Layout Grid)
1. **Cột:** `12` cột trên Desktop/Laptop ($\ge 1024\text{px}$), `8` cột trên Tablet, `4` cột trên Mobile ($< 768\text{px}$). Cột rộng linh hoạt theo `%`/`fr`. Chỉ **khung chính** (khối nội dung, card, cột ảnh) phải khớp cột; phần tử nhỏ bên trong dùng thang khoảng cách §2.3.
2. **Gutter (khe giữa cột):** cố định, luôn để trống, hẹp hơn cột — `32px` Desktop → `24px` Tablet → `16px` Mobile (Pillar 4 *Cô đọng* được dùng `16px` ở mọi kích thước).
3. **Lề ngoài (Container Margin):** lớn dần theo màn hình — tối thiểu `16px` Mobile (khớp Bài test 3), `32px` Tablet, `48px–80px` Desktop; nội dung không bao giờ chạm mép màn hình.
4. Ví dụ quy đổi: 3 card × `col-span-4` trên Desktop → xếp chồng `col-span-4` (toàn bộ 4 cột) trên Mobile.

### 2.6. Độ sâu, Đổ bóng & Bo góc (Elevation & Radius)
1. **Phân cấp bằng độ sâu:** phần tử càng quan trọng hoặc càng "nổi" (header dính, thanh CTA dính đáy, dropdown, modal) càng ở tầng cao. Ưu tiên tạo độ sâu bằng **chênh lệch nền** (bề mặt sáng hơn nằm trên nền tối hơn trông nổi lên mà không cần bóng) — khớp Anti-slop #5.
2. **Đúng 3 mức bóng** (`--shadow-sm`, `--shadow-md`, `--shadow-lg`): bóng nhỏ + sắc để nhô nhẹ; bóng lớn + mềm cho tầng cao. Ánh sáng luôn **từ trên xuống** (offset-y dương). Màu bóng lấy từ sắc độ của `--text-primary` với opacity thấp, không dùng đen thuần.
3. **Đúng 3 mức bo góc** (`--radius-sm`, `--radius-md`, `--radius-lg`) cho phần tử nhỏ / vừa / lớn, lấy theo preset Trụ cột 1. Các phần tử **cùng chức năng phải cùng bo góc** (nút primary và secondary không được khác hình dạng).
4. **Chất liệu bề mặt (Surface)** — trục riêng, hỏi ngay sau Trụ cột 1, không tính vào Clarity Score, mặc định *Phẳng*. Chất liệu quyết định cách vẽ thẻ, nút, thanh menu, bóng và bo góc (ghi đè bo góc của preset), còn màu, font và nhịp vẫn theo Trụ cột 1:
   - *Phẳng*: bề mặt riêng của preset (đường viền mảnh, bóng nhẹ).
   - *Kính mờ (Liquid Glass)*: lớp nền trong suốt có `backdrop-filter`, **nền sau chữ đục ≥ 72%**, viền mảnh + vệt sáng mép trên, bóng rộng và mềm; trang có 2–3 vầng sáng màu thương hiệu ≤ 12% trên một lớp cố định (không đặt gradient lên `body`, để QA vẫn đo được tương phản). Có `prefers-reduced-transparency` và trình duyệt không hỗ trợ blur → nền đặc. Bo góc 12/24/32, nút viên thuốc.
   - *Đất sét (Claymorphism)*: khối không viền, bóng ngoài mềm + bóng trong (sáng ở mép trên, tối ở mép dưới); ô nhập **lõm xuống** nhưng vẫn giữ viền ≥ 3:1. Bo góc 16/32/48.
   - *Viền đậm (Neo-brutalism)*: viền 2px màu chữ, bóng lệch cứng `4px 4px 0` không mờ, góc vuông; di chuột thì nhấc lên, nhấn thì ép xuống. Trên dải tối và trên ảnh, viền/bóng đổi sang màu nền.
   - **Không đưa vào:** Neumorphism (nút cùng màu nền, viền < 3:1, trượt WCAG 1.4.11) và nền gradient cực quang (Anti-slop #1).

### 2.7. Quy tắc Sử dụng Màu (Color Usage Rules)
1. **Không bao giờ dùng màu đơn thuần để truyền đạt ý nghĩa** (người mù màu không phân biệt được):
   - Link nằm trong đoạn văn: màu nhấn **+ gạch chân**. Menu điều hướng, tab, card đã có tín hiệu tương tác riêng thì được bỏ gạch chân.
   - Ô nhập bị lỗi: viền đỏ **+ icon cảnh báo + viền dày hơn + thông báo bằng chữ**.
   - Trạng thái (đã duyệt / chờ / từ chối): màu **+ icon hoặc nhãn chữ**.
2. **Màu trạng thái (Semantic):** `danger` (đỏ — lỗi, hành động phá huỷ), `warning` (hổ phách — cảnh báo rủi ro), `success` (xanh lá — hoàn tất). Dùng cho chữ thì đạt $\ge 4.5:1$; chỉ dùng cho icon/viền thì $\ge 3:1$.
3. **Màu thương hiệu xung đột nghĩa:** nếu màu seed là đỏ/xanh lá/hổ phách (dễ bị đọc là lỗi/thành công/cảnh báo), dùng sắc độ rất tối của màu đó (gần `--text-primary`) hoặc xanh dương cho phần tử tương tác.
4. **Màu thương hiệu quá sáng** (vàng, xanh nhạt): được làm tối nhẹ nếu vẫn nhận diện được thương hiệu; nếu không, dùng `--text-primary` cho chữ trên nút và cho link, và thêm viền `--border-strong` cho nút. **Màu thương hiệu quá tối trên nền tối:** ngược lại, dùng chữ trắng và thêm viền.
5. **Thiết kế bằng thang xám trước:** khoảng cách, kích thước, phân cấp phải đúng khi chưa có màu; màu chỉ thêm vào nơi mang ý nghĩa (tương tác, trạng thái).
6. **Kiểm tra bảng màu trong ngữ cảnh:** mọi token màu phải được xem cùng nhau trên một màn hình thật (tiêu đề, chữ phụ, viền ô nhập, viền trang trí, nút, nền phụ) trước khi khoá `DESIGN.md`.

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
| **7** | **Nút bấm (Buttons) lơ lửng không có phân cấp:** Đặt 2–3 nút đậm màu cạnh nhau khiến người dùng không biết bấm vào đâu. | Tuân thủ **3 mức nút** (§6.2): tối đa **1 Primary** mỗi khung nhìn (nền đặc màu nhấn); nút phụ (`Secondary`) nền trong suốt, **viền + chữ màu nhấn, viền đạt $\ge 3:1$** (không dùng viền/nền xám nhạt — trông như nút bị vô hiệu hoá); nút ít quan trọng (`Tertiary`) dạng liên kết **có gạch chân** (được thêm mũi tên dịch chuyển khi di chuột `hover:translate-x-1`, nhưng mũi tên không thay cho gạch chân). |
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
- **Kiểm tra khả năng hiển thị & Vùng chạm:** Chiều cao và chiều rộng vùng bấm trên Mobile phải đạt $\ge 48\text{px}$ (khớp lưới 8pt; sàn tuyệt đối $44\text{px}$ theo khuyến nghị WCAG), hai vùng bấm nằm cạnh nhau trên cùng một hàng cách nhau $\ge 8\text{px}$ (danh sách hàng full-width xếp dọc như accordion, menu dọc được phép chỉ cách nhau bằng đường kẻ), không bị phần tử khác che khuất (`elementFromPoint` trả về đúng nút đó). Phần tử nhìn nhỏ (icon, link trong menu) được mở rộng vùng bấm bằng padding thay vì phóng to hình.
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
- Xác nhận các quy chuẩn thành phần & chữ (Chương 6, 7) đo được từ DOM:
  - Viền `input`, `select`, `textarea`, checkbox, radio đạt $\ge 3:1$ với nền (§2.1 `--border-strong`).
  - Không có `input` chỉ dùng `placeholder` mà không có nhãn hiển thị; dấu `*` bắt buộc không tô đỏ (§6.1).
  - Link trong đoạn văn (`p a`, `li a`) có gạch chân (§2.7).
  - Mỗi khung nhìn tối đa 1 nút Primary; không có nút mang thuộc tính `disabled` mà không có dòng giải thích bên cạnh (§6.2, §6.4).
  - Chữ của link/nút không thuộc danh sách chữ chung chung bị cấm (§7.2).
  - Đoạn văn dài (`p`, `li`, `dd`, `blockquote` từ **200 ký tự** trở lên): `font-size` $\ge 18\text{px}$, `line-height` $\ge 1.5$, không `text-align: justify` (căn giữa đã thuộc Anti-slop #3); mỗi họ phông dùng tối đa 2 `font-weight` (§2.2).
  - Thẻ (`[data-swarm-role=card]`) cùng một hàng có ảnh cao lệch nhau ≤ 8px (§6.6); nền màu bão hoà chiếm ≤ 10% diện tích trang (§2.1).
  - Số từ **5 chữ số** trở lên có dấu phân cách hàng nghìn (§7.1; số 4 chữ số không được kiểm tự động để tránh nhầm với năm).

### Chấm điểm thẩm mỹ (sau khi 4 bài test đạt)
Bài test chứng minh trang **không sai**; độ **đẹp** được chấm riêng bằng model đọc ảnh (`qa/critic.py`):
- Chụp màn hình đầu và toàn trang desktop (cắt từng đoạn), cộng màn hình đầu trên điện thoại, trên một tab sạch không có overlay của AI.
- 8 tiêu chí 1–10: phân cấp, bố cục/nhịp, khoảng trắng, chữ, ảnh, màu, độ hoàn thiện, độ hiện đại. Điểm tổng do code tính theo trọng số, không lấy từ model.
- Thang neo: 9–10 ngang trang mẫu (Aesop, Apple, Linear) · 7–8 chuyên nghiệp · 5–6 template · ≤ 4 nghiệp dư.
- Kết quả ghi vào `CRITIQUE.md` và hiển thị ở Studio; **không chặn** việc bàn giao. Không có model đọc ảnh thì bỏ qua.

> [!TIP]
> **Tiêu chuẩn Chuyển nhượng ở Bước 12:** Chỉ khi cả 4 Bài Test của **Cursor Lớn Nhất** đều hiển thị tích xanh (`100% PASSED`), hệ thống mới bật thông báo bàn giao để người dùng trực tiếp cầm chuột trải nghiệm, sau đó chọn **Upgrade trang hiện tại** hoặc **Chuyển sang Build trang tiếp theo** trong `PRODUCT.md`.

---

## CHƯƠNG 6: QUY CHUẨN THÀNH PHẦN TƯƠNG TÁC (Dành cho Bước 6, 9, 11)

> [!IMPORTANT]
> Ưu tiên **mẫu thành phần quen thuộc** (người dùng đã biết cách dùng từ các trang khác). Chỉ sáng tạo ở phần tạo ra khác biệt cho sản phẩm; ô nhập, nút, checkbox luôn giữ hình dạng nhận diện được. Mọi chi tiết phải có lý do; khi phân vân, chọn phương án ít rủi ro cho người thị lực kém, vận động kém, hoặc ít rành công nghệ.

### 6.1. Form
1. **Bố cục:**
   - Form xếp **một cột**. Chỉ các ô ngắn có liên quan chặt (ngày hết hạn + CVC, ngày + tháng) được đặt cạnh nhau trong cùng chiều rộng cột.
   - **Nhãn đặt phía trên ô nhập**, không đặt bên trái. Khoảng cách nhãn → ô (`4px–8px`) phải nhỏ rõ rệt so với khoảng cách giữa hai trường (`24px–32px`).
   - Radio và checkbox **xếp dọc**, mỗi lựa chọn một dòng.
   - Chiều rộng ô **khớp độ dài dữ liệu dự kiến** (mã bưu chính, CVC, số lượng dùng ô ngắn), không kéo mọi ô full-width.
2. **Số trường:** Chỉ hỏi thông tin **thật sự cần** cho việc đặt hàng/đăng ký. Thông tin nhạy cảm phải kèm lý do vì sao cần.
3. **Bắt buộc / tuỳ chọn:**
   - Đánh dấu **cả hai**: trường bắt buộc có dấu `*` (màu chữ thường, **không tô đỏ** — đỏ là lỗi) kèm một dòng giải thích ở đầu form; trường tuỳ chọn ghi "(không bắt buộc)".
   - Ưu tiên thay trường tuỳ chọn bằng **opt-in**: checkbox "Nhận thông báo qua SMS", tick mới hiện ô số điện thoại (bắt buộc).
   - Được bỏ đánh dấu với form ngắn quen thuộc (đăng nhập, ô đăng ký nhận tin duy nhất).
4. **Nhãn, gợi ý, placeholder:**
   - Mọi ô nhập luôn có **nhãn hiển thị** ngắn gọn; không ghi "của tôi"/"của bạn" ("Email", không phải "Email của bạn").
   - Gợi ý định dạng (hint) đặt **dưới nhãn, trên ô** — phía dưới ô dễ bị bàn phím ảo và menu autofill che. Gợi ý cần thiết thì luôn hiển thị, không giấu trong tooltip.
   - **Không dùng placeholder thay nhãn** (biến mất khi gõ, trông như đã điền, thường không đủ tương phản). Ngoại lệ duy nhất: ô tìm kiếm đơn — placeholder đạt $\ge 4.5:1$ và có `aria-label`.
   - Bỏ động từ thừa: "Email", không phải "Nhập email của bạn tại đây".
5. **Chọn đúng điều khiển:**
   - $\le 10$ lựa chọn → **radio** (luôn thấy, một lần bấm) thay vì dropdown.
   - Danh sách dài người dùng biết mình cần gì (tỉnh/thành, quốc gia) → **autocomplete**, tối đa ~10 gợi ý, làm đậm phần khác nhau giữa các gợi ý.
   - Số nhỏ (số lượng, số khách) → **stepper `−` / `+`** xếp ngang, mỗi nút $\ge 48\text{px}$; không dùng mũi tên lên/xuống.
   - Bật/tắt có hiệu lực **sau khi bấm gửi** → **checkbox**; có hiệu lực **ngay lập tức** → **toggle**. Nhãn mô tả điều xảy ra khi bật, phát biểu **khẳng định** ("Cho phép cập nhật tự động", không phải "Không cho phép…").
6. **Form dài:** chia **nhiều bước** (mỗi bước một nhóm câu liên quan, câu dễ trước), hiện tiến độ ("Bước 2/3"), cho xem lại và sửa trước khi xác nhận, sau đó báo rõ điều gì xảy ra tiếp theo. Không chia bước được thì nhóm trường dưới các tiêu đề.
7. **Kiểm tra & lỗi:**
   - Kiểm tra **khi bấm gửi**, không báo lỗi khi người dùng mới gõ ký tự đầu. Ngoại lệ được kiểm tra khi gõ: độ mạnh mật khẩu, giới hạn ký tự, tên người dùng còn trống.
   - Khi gửi lỗi: hiện **khối tóm tắt lỗi ở đầu form** (mỗi lỗi là link nhảy tới ô tương ứng) và thông báo lỗi **phía trên ô** bị lỗi, luôn kèm icon.
   - Câu báo lỗi nói **chuyện gì xảy ra và cách sửa**, không đổ lỗi người dùng, không "Oops"/"Xin lỗi", không thuật ngữ kỹ thuật ("Nhập số điện thoại gồm 10 chữ số", không phải "Dữ liệu không hợp lệ").

### 6.2. Ba mức nút (Button Hierarchy)
| Mức | Hình thức | Dùng khi |
| :--- | :--- | :--- |
| **Primary** | Nền đặc màu hành động (`--action`), chữ `--action-fg` ($\ge 4.5:1$), bo góc `--radius-md` | Hành động quan trọng nhất — **tối đa 1 nút mỗi khung nhìn** |
| **Secondary** | Nền trong suốt, viền + chữ màu hành động (`--action-ink`), viền $\ge 3:1$, **cùng bo góc với Primary** | Hành động phụ, hoặc nhiều hành động ngang hàng (cùng mức nổi để không thiên vị) |
| **Tertiary** | Chữ màu hành động **có gạch chân**, không nền, không viền | Hành động ít quan trọng nhất, hành động lặp lại trong danh sách, hành động phá huỷ |

- Phân cấp giữa các mức phải thấy được **khi bỏ màu đi** (nền đặc ↔ viền ↔ gạch chân), không chỉ khác màu.
- Không có hành động nổi bật duy nhất → không dùng Primary. Danh sách "Theo dõi"/"Thêm" lặp lại ở mỗi dòng → Secondary hoặc Tertiary.
- Vùng bấm $\ge 48\text{px}$, khoảng cách giữa hai nút $\ge 8\text{px}$ (khuyến nghị `16px`).
- **Chữ trên nút = động từ + danh từ** ("Thêm vào giỏ", "Lưu địa chỉ", "Xoá đánh giá"), hiểu được khi đọc tách khỏi ngữ cảnh. Cấm "OK", "Có", "Gửi" trơ trọi khi có thể nói rõ hơn.
- Icon đi kèm chữ: cùng độ dày nét và kích thước tương đương chữ; icon to/đậm hơn thì giảm tương phản icon (dùng `--text-secondary`).

### 6.3. Căn chỉnh & Thứ tự nút
- **Căn trái, sắp từ quan trọng nhất → ít quan trọng nhất** (trái sang phải), áp dụng cho form, card, dialog (nhất quán toàn trang).
- **Mobile:** xếp chồng từ trên xuống theo cùng thứ tự, **full-width**.
- **Form nhiều bước:** nút tiến (Primary) căn trái ở cuối form; nút "Quay lại" là **Tertiary ở góc trái phía trên** form, không đặt cạnh nút tiến (tránh bấm nhầm mất dữ liệu).
- **Ngoại lệ:** form một ô (tìm kiếm, đăng ký nhận tin) — nút nằm **bên phải, dính liền ô nhập**.
- CTA chính của trang chi tiết trên mobile được phép **dính đáy màn hình** (kèm `--shadow-md`) để luôn trong tầm ngón cái; đặt thông tin quyết định (giá) cạnh CTA.

### 6.4. Nút bị vô hiệu hoá (Disabled)
Mặc định **không dùng nút `disabled`** (không giải thích vì sao bấm không được, tương phản thấp, không focus được bằng bàn phím). Thay bằng, theo thứ tự ưu tiên:
1. Để nút **luôn bấm được** và kiểm tra khi gửi (§6.1.7).
2. **Bỏ hẳn** hành động chưa khả dụng và nói lý do bằng chữ.
3. Giữ nút bình thường kèm **icon khoá** + giải thích cách mở khoá (hợp với tính năng trả phí).
4. Buộc phải dùng `disabled`: kèm **dòng giải thích ngay cạnh nút** và vẫn cho focus bằng bàn phím (`aria-disabled` thay vì `disabled`).

### 6.5. Hành động phá huỷ (Destructive Actions)
Mức ma sát tăng theo lượng dữ liệu có thể mất:
| Mức | Cách làm |
| :--- | :--- |
| **Ban đầu** | Hành động phá huỷ ở dạng **Tertiary**, đặt xa hành động chính, **không tô đỏ** (đỏ làm nó nổi hơn). |
| **Nhẹ** (mất ít) | Hỏi xác nhận bằng dialog; nút xác nhận ghi rõ hành động ("Xoá khỏi giỏ"). |
| **Vừa** | Như trên + nút xác nhận màu `danger` và/hoặc icon cảnh báo; nói rõ không khôi phục được. |
| **Nặng** (xoá tài khoản, xoá toàn bộ dữ liệu) | Như trên + checkbox "Tôi xác nhận…" phải tick mới bấm được. |

**Tốt hơn ma sát là hoàn tác:** nếu khôi phục được, thực hiện ngay và hiện thông báo kèm nút "Hoàn tác" / "Khôi phục".

### 6.6. Hiển thị, Nhóm & Tính nhất quán
- **Thứ trông giống nhau phải hoạt động giống nhau.** Phần tử không bấm được (badge, tag, icon thông số) không được trông như nút: không dùng màu nhấn, không viền màu nhấn, badge dùng màu trạng thái hoặc nền nhạt.
- **Thẻ sản phẩm không khung:** ảnh sát mép thẻ, tên + giá bên dưới, không nền, không viền, không padding; cả thẻ là vùng bấm. Thẻ nằm cùng một hàng phải có **ảnh cao bằng nhau** (lệch ≤ 8px) dù thẻ chiếm số cột khác nhau — nếu không, mép thẻ lởm chởm ("méo").
- **Nhóm bằng ít container nhất có thể:** ưu tiên khoảng cách (§2.3), sự giống nhau và thẳng hàng; chỉ bọc khung/thẻ khi các cách kia chưa đủ rõ.
- **Thứ quan trọng phải nhìn thấy:** không giấu điều hướng chính sau menu hamburger trên desktop; nội dung cuộn ngang (carousel) phải **lộ mép thẻ kế tiếp**.
- **Hé lộ dần (progressive disclosure):** chi tiết phụ đặt trong accordion/tab với **nhãn mô tả nội dung** ("Chính sách đổi trả 30 ngày"), không dùng "Xem thêm".
- **Giao diện không vỡ:** component phải chịu được chữ dài, số lớn, danh sách rỗng và rất dài. Ưu tiên xuống dòng; buộc phải cắt chữ thì không cắt mất phần phân biệt các mục (cân nhắc cắt ở giữa).
- **Kiểm tra bằng Squint Test:** làm mờ/thu nhỏ trang — vẫn phải nhận ra phần quan trọng nhất và trang dùng để làm gì.

---

## CHƯƠNG 7: QUY CHUẨN VIẾT CHỮ TRÊN GIAO DIỆN (Dành cho Bước 9 & 11)

Bổ sung cho Anti-slop #6. Áp dụng cho tiêu đề, nút, nhãn, thông báo — tiếng Việt và tiếng Anh.

### 7.1. Câu chữ
1. **Ngắn gọn:** từ nào bỏ được mà không mất thông tin thì bỏ. Bỏ từ đệm ("thực sự", "về cơ bản", "khá là") và câu dẫn ("Bạn có muốn…", "Để có thể…", "Bạn có chắc chắn…"). Câu dưới 20 từ.
2. **Ngôn ngữ đời thường:** như đang giải thích cho người chưa biết gì về chủ đề; không thuật ngữ chuyên ngành, không tiếng lóng.
3. **Ý chính lên đầu (front-load):** lợi ích/con số then chốt đặt đầu tiêu đề, link, gạch đầu dòng ("Giảm 30% khi đăng ký hôm nay", không phải "Đăng ký hôm nay để được giảm 30%"). Đoạn dài theo **kim tự tháp ngược**: điều quan trọng nhất → chi tiết hỗ trợ → thông tin nền.
4. **Viết hoa kiểu câu (sentence case):** chỉ viết hoa chữ đầu và danh từ riêng ("Thêm vào giỏ hàng", không phải "Thêm Vào Giỏ Hàng"). Không IN HOA câu dài (§2.2 mục 6).
5. **Hạn chế viết tắt:** viết đầy đủ ("Số căn hộ", không phải "Số CH"); nếu phải dùng thì giải thích ở lần xuất hiện đầu.
6. **Con số:** viết bằng chữ số, có dấu phân cách hàng nghìn theo ngôn ngữ trang (`1.250.000₫` tiếng Việt, `1,250` tiếng Anh). Số rất lớn kết hợp chữ ("1,2 triệu lượt mua").
7. **Dấu chấm câu:** nhãn, tiêu đề, gạch đầu dòng ngắn **không** chấm cuối. Các khối cạnh nhau dùng dấu câu nhất quán.
8. **Độ dài tương đương:** các khối chữ nằm cùng hàng (3 cột tính năng) có độ dài gần nhau để thẳng hàng.

### 7.2. Tiêu đề, link & nút
- **Tiêu đề phải nói ra ý chính**, không chỉ là nhãn chung ("Giao hàng miễn phí toàn quốc" thay vì "Vận chuyển") — người dùng quét tiêu đề, và người dùng trình đọc màn hình duyệt theo danh sách tiêu đề.
- **Link mô tả đích đến** (tên trang hoặc nội dung sẽ thấy). **Cấm** chữ link/nút chung chung: "Xem thêm", "Tìm hiểu thêm", "Đọc thêm", "Bấm vào đây", "Click here", "Learn more", "Read more", "OK". Nhiều thẻ cùng loại → biến chính tiêu đề thẻ thành link.
- Chữ trên nút theo §6.2 (động từ + danh từ).

### 7.3. Từ vựng nhất quán
- **Một khái niệm, một từ** trên toàn sản phẩm: chọn một và giữ nguyên — "Giỏ hàng" (không lẫn "Túi"), "Đăng nhập"/"Đăng ký" (không lẫn "Sign in"/"Register"), "Xoá" (không lẫn "Gỡ"), "Thanh toán" (không lẫn "Checkout").
- Chữ trên nút khớp với tên của thứ nó mở ra (nút "Thêm vào giỏ" → trang tiêu đề "Giỏ hàng").
