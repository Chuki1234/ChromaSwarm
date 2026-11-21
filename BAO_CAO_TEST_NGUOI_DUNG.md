# Báo cáo test như người dùng thật — 21/11/2026

**Cách test:** đóng vai chủ tiệm bánh, gõ prompt bằng lời thường:

> "mình mở tiệm bánh tên Bếp Nhà Mây ở Đà Nẵng, bán bánh mì sourdough với bánh ngọt, muốn có web để khách đặt bánh online"

- **Đi hết B1 → B12 trên Studio:**
  - chọn theo gợi ý;
  - trả lời màu bằng lời thường;
  - điền 4 món kèm giá và phần liên hệ ở B4;
  - duyệt kế hoạch;
  - xem trang ở 1440/1024/375px;
  - bấm thử các nút;
  - góp ý ở B12.
- **Chạy thêm 4 loại tiệm khác** (shop quần áo, quán cà phê, tiệm nail, trung tâm tiếng Nhật) để xem lỗi có lặp lại không.

**Lưu ý:** key OpenRouter đang hết hạn mức (lỗi 402). Vì vậy toàn bộ phần AI (viết chữ, đọc ảnh, mắt AI) không chạy, và trang được dựng hoàn toàn bằng luật. Một số lỗi dưới đây sẽ nhẹ hơn khi có AI, nhưng app phải dùng được cả khi AI hỏng, và người dùng phải được báo.

Kết quả: QA báo đạt 100% cả 4 bài. Nhưng một chủ tiệm bánh nhìn vào trang thì không dùng được.

---

## Mức 1 — Hỏng, người dùng thấy ngay

| # | Chỗ | Lỗi | Bằng chứng |
|---|---|---|---|
| 1 | Trang dựng ra | **Chữ mẫu của tiệm nội thất xuất hiện trên mọi trang bán hàng** | Tiệm bánh có "Lắp đặt tại nhà, không tính phí", "2 năm bảo hành", "30 ngày đổi trả", "Chọn vật liệu trước, thiết kế sau". FAQ có "Có lắp đặt tại nhà không?", "Gửi kích thước phòng". Shop quần áo trẻ em cũng bị y hệt. Chữ mẫu ecommerce đang viết cho đồ nội thất, không phải cho "bán hàng" nói chung. |
| 2 | Trang dựng ra | **Nút hành động chính là giả** | Bấm "đặt bánh" chỉ đổi chữ thành "Đã ghi nhận, chúng tôi sẽ liên hệ", trong khi chưa hỏi món, ngày hay số điện thoại. Khách tưởng đã đặt được bánh, chủ tiệm không nhận được gì. |
| 3 | Trang dựng ra | **Không mua được gì** | Không có nút "thêm vào giỏ". "Xem nhanh" chỉ hiện tên món. Giỏ hàng luôn 0. Các link menu (Bộ sưu tập, Câu chuyện, Hỏi đáp, Liên hệ) đều là `#`, bấm không đi đâu. |
| 4 | Lấy tên thương hiệu | **Tên bị cắt hoặc lấy cả câu** | "Bếp Nhà Mây" thành "Bếp Nhà". "quán cà phê Gác Nhỏ muốn web để khách đặt bàn" thành tên "Quán cà phê Gác Nhỏ muốn web để khách". "tiệm nail Hồng Nhung quận 7 đặt lịch…" thành "Tiệm nail Hồng Nhung quận 7 đặt lịch". |
| 5 | Tiêu đề tab và tài liệu | Dùng đoạn đầu prompt thay cho tên | Tab trình duyệt ghi "Mở tiệm bánh tên Bếp Nhà Mây ở Đà Nẵng, bán…". DESIGN.md và PRODUCT.md cũng vậy. |
| 6 | B12 góp ý | **Hiểu sai góp ý hoàn toàn** | Góp ý: "tên tiệm là Bếp Nhà Mây…, bỏ mấy chữ lắp đặt, bảo hành, đổi trả đi, nút đặt bánh cho màu nâu". Hệ thống hiểu thành "Khoảng cách → Gọn, nhiều thông tin", một việc không ai xin; cả 3 yêu cầu thật đều bị bỏ qua. Bộ hiểu góp ý khi không có AI chỉ bắt được vài từ khóa cố định. |
| 7 | Màu | Màu người dùng xin không vào nút | Người dùng xin "nâu như vỏ bánh mì": accent được làm nâu (#7c4a2d), nhưng nút chính lại là "gần đen". DESIGN.md tự mâu thuẫn: §1 ghi "accent chỉ dành cho đặt bánh", §5 ghi "Màu hành động: gần đen". |
| 8 | Studio | **Không báo khi AI hỏng** | Log có hàng chục lỗi 402, nhưng Studio không nói gì. Người dùng tưởng trang do AI viết và đánh giá app "kém thông minh". Hệ thống cũng vẫn gọi model cho từng phần dù lần đầu đã lỗi 402, nên chậm vô ích. |
| 9 | Studio, lúc mở lại | Gõ chữ bị rơi vào phiên cũ | Mở Studio thấy màn hình "Hôm nay bạn muốn làm trang web gì?" kèm "Mất kết nối". Vài giây sau nó tự nhảy về phiên cũ ở B4, và chữ đang gõ ở ô chính rơi vào ô "Slogan" của phiên cũ. |

## Mức 2 — Kém thông minh

| # | Bước | Vấn đề |
|---|---|---|
| 10 | B2 | Danh sách trang là khuôn chung cho mọi shop ("Product Catalog & Filter", "Login / Register & Profile"), lẫn tiếng Anh. Tiệm bánh nhỏ được đề xuất làm "Landing chiến dịch ra mắt" trước, trong khi cái họ cần là menu bánh, đặt bánh và giờ mở cửa. |
| 11 | B3 | Hỏi lại điều đã biết: prompt đã nói "để khách đặt bánh online", B3 vẫn hỏi "hành động quan trọng nhất là gì?". Không gợi ý sẵn câu trả lời hợp với tiệm bánh (ví dụ đánh dấu "Thân thiện & ấm áp" là nên chọn). |
| 12 | B3 | Lựa chọn viết bằng thuật ngữ thiết kế: "Playfair Display · bo góc 2px", "Claymorphism", "Neo-brutalism", "Asymmetric editorial / F-pattern", "section 128px". Không có hình minh họa để chọn bằng mắt. |
| 13 | B4 | Mọi ví dụ trong form vẫn là đồ gỗ ("Bàn gỗ sồi Mộc 120", "12 Lê Lợi, Đà Lạt") dù người dùng là tiệm bánh ở Đà Nẵng. Ví dụ mới chỉ đổi theo 5 loại trang, chưa đổi theo ngành. Form cũng không điền sẵn những gì prompt đã nói (tên tiệm, sourdough, Đà Nẵng). |
| 14 | B7 | PLAN không có phần riêng của tiệm bánh: chọn ngày lấy bánh, giao hay nhận tại tiệm, nút Zalo, giờ mở cửa, bản đồ, món phải đặt trước. Ô cuối trang là "nhận tin qua email", không phải đặt bánh. |
| 15 | B7 | Người dùng chọn "Nhiều sản phẩm ngay lập tức (lưới 4 cột, có lọc)", nhưng kế hoạch dùng bento 4 ô to và không có bộ lọc. |
| 16 | Chữ trên trang | Phần đầu trang chép nguyên câu mô tả khách: "Dành cho dân văn phòng với mấy mẹ bỉm sữa 25-40 tuổi: chất liệu, giá…". Trang đang nói với khách về chính khách, bằng giọng người chủ tiệm tả khách. Tiêu đề "Từng món được kiểm tra trước khi giao" chung chung, không nhắc tới bánh. |
| 17 | Chữ trên trang | Nút "đặt bánh" viết thường chữ đầu, vì lấy nguyên chữ người dùng gõ. Giá lẫn kiểu: "85k", "35k", "280k" cạnh "120.000đ"; nên đưa về một kiểu. |
| 18 | Ảnh | Ảnh đúng chủ đề bánh, nhưng không khớp từng món: "Sourdough nguyên cám" hiện ảnh cupcake sô-cô-la, ảnh phần đầu trang bị lặp lại ở thẻ "Croissant bơ", và ảnh "Bánh kem bắp" lặp lại ở phần "Chọn vật liệu…". |
| 19 | Mục để trống | Khi người dùng không nhập danh sách, trang hiện "Sản phẩm chủ lực", "Phiên bản nhỏ gọn", "Dịch vụ tiêu chuẩn": nhìn là biết chữ giữ chỗ. |
| 20 | QA | QA "đạt 100%" nhưng không bắt được lỗi 1, 2, 3, 4, 7. QA đang kiểm tra kỹ thuật (tương phản, tràn ngang, nút có phản hồi), chưa kiểm tra "trang này có đúng ngành không" và "nút chính có làm đúng việc không". |

## Mức 3 — Nhỏ, sửa nhanh

| # | Chỗ | Vấn đề |
|---|---|---|
| 21 | Studio B4 | Ô ảnh từng món: dòng không có dấu "\|" hiện cả giá trong tên ("Sourdough nguyên cám 85k"). Backend thì tách đúng. |
| 22 | Studio | Dòng tiến độ đầy từ nội bộ: "Master Cursor", "Motion thêm reveal (GSAP / Three.js)", "Design đo Header". |
| 23 | Studio B7 | Kế hoạch hiện dạng markdown thô với bảng OKLCH, APCA, `clamp(...)`. Người không làm thiết kế đọc không nổi; nên có bản tóm tắt 5 dòng bằng lời thường ở trên, còn chi tiết thì thu gọn. |
| 24 | Trang dựng ra | Chữ phần đầu trang bắt đầu từ độ mờ 0 rồi hiện dần. Trên máy chậm, màn hình đầu sẽ trống một lúc (lúc đo khung trình duyệt đang ẩn nên số đo chưa chắc chắn). |
| 25 | Footer | Tiệm bánh có link "Vận chuyển / Đổi trả / Bảo mật / Điều khoản" trỏ `#`, cộng ô đăng ký email. Phần liên hệ thật (địa chỉ, giờ, Zalo) thì nằm chung một dòng nhỏ với ©. |

---

## Đã sửa (21/11)

- **Chữ theo ngành** (lỗi 1, 13, 16, 19 và một phần 17): chữ mẫu giờ đi theo ngành, gồm 11 bộ (tiệm bánh, đồ ăn, thời trang, mỹ phẩm, nội thất, quán cà phê, nhà hàng, nail, tóc, phòng khám, spa); không nhận ra ngành thì dùng chữ chung trung tính.
  - Form B4 có ví dụ đúng ngành.
  - Phần đầu trang không còn chép câu tả khách.
  - Chữ đầu của nút được viết hoa.
  - Người viết chữ (AI) bị trả lại nếu viết chữ của ngành khác.
  - Chưa làm: đưa giá về một kiểu ("85k" / "120.000đ").

- **Nút đặt hàng thật** (lỗi 2, một phần lỗi 3 và lỗi 20):
  - Nút chính, dải cuối trang và "Xem nhanh" mở form đặt hàng thật. Tiệm bánh được hỏi: món, số lượng, ngày giờ nhận, nhận tại tiệm hay giao (kèm địa chỉ), tên, số điện thoại.
  - Thông tin sai được báo ngay dưới từng ô.
  - Đơn lưu vào `data/orders.jsonl` hoặc gửi tới webhook. Không gửi được thì trang nói rõ, và đưa nút Zalo, gọi, nhắn tin lấy từ dòng liên hệ của chủ tiệm.
  - QA có thêm kiểm tra nút chính giả.
  - Chưa làm: link menu `#`, nút thêm vào giỏ.

## Gợi ý thứ tự sửa

1. **Chữ mẫu theo ngành, không theo loại trang.** Tách chữ mẫu "bán hàng" thành nhóm chung trung tính, rồi thêm vài ngành hay gặp: đồ ăn/bánh, thời trang, mỹ phẩm, nội thất, cà phê/nhà hàng, spa/nail. Chữ chung không được nhắc "lắp đặt, bảo hành, vật liệu". *(Sửa lỗi 1, 13, 16, 19.)*
2. **Nút chính phải làm việc thật.** "Đặt bánh/Đặt lịch/Mua" mở form ngắn (món, số lượng, ngày, tên, số điện thoại) có kiểm lỗi, hoặc mở Zalo hay gọi điện bằng số người dùng đã nhập. Có danh sách món thì thêm nút vào giỏ. Link menu phải cuộn tới đúng phần. *(Sửa lỗi 2, 3.)*
3. **Lấy tên thương hiệu đúng khi không có AI:** bắt "tên X", "tiệm X", "quán X", "thương hiệu X" và dừng ở từ chức năng ("ở", "muốn", "bán", "đặt", "quận"). Tiêu đề trang, tab và tài liệu dùng tên này. *(Sửa lỗi 4, 5.)*
4. **B12 hiểu góp ý tốt hơn khi không có AI:** bắt "tên là…", "bỏ chữ…", "màu …"; nếu không hiểu thì hỏi lại, thay vì đoán bừa một thay đổi khác. *(Sửa lỗi 6.)*
5. **Báo người dùng khi AI hỏng,** ví dụ: "Phần AI đang tạm dừng (key hết hạn mức), trang được dựng bằng luật". Sau lỗi 402 đầu tiên thì ngừng gọi model trong phiên đó. *(Sửa lỗi 8.)*
6. **Thêm vào QA:** kiểm tra từ lạc ngành (bảo hành, lắp đặt… trên trang không phải nội thất), nút chính có mở form hay link thật không, và tên thương hiệu có đúng chữ trong prompt không. *(Sửa lỗi 20.)*
7. **Lời thường hơn ở B3 và B7,** kèm gợi ý sẵn theo ngành và bản tóm tắt dễ đọc. *(Sửa lỗi 11, 12, 22, 23.)*

---

# Chức năng còn thiếu ở Creative (đọc code ngày 21/11)

## A. Có giao diện nhưng chưa làm việc thật

| # | Chỗ | Thiếu gì | Code |
|---|---|---|---|
| A1 | Trang thanh toán, trang đặt lịch, trang liên hệ | Nút "Đặt hàng", "Xác nhận đặt lịch", "Gửi lời nhắn" chỉ hiện "Đã đặt / Đã gửi", không gửi đi đâu. Đây là cùng lỗi nút giả đã sửa ở nút chính. | `app_pages.py` dòng 131, 541, 668 |
| A2 | Giỏ hàng | "Thêm vào giỏ" chỉ tăng con số trên trang đó; sang trang khác là mất. Trang giỏ hàng hiện danh sách mẫu, không phải món khách đã chọn. | `nextjs.py` ~782, `app_pages.cart_checkout` |
| A3 | Đăng nhập, tài khoản | Chỉ kiểm tra định dạng email và mật khẩu. Không có tài khoản thật, đăng ký hay quên mật khẩu. Trang "tài khoản" chính là trang đăng nhập, không có lịch sử đơn. Bảng điều khiển và "Lịch hẹn của tôi" là số liệu mẫu cố định. | `nextjs._auth`, `planner.BLUEPRINTS["account"]` |
| A4 | Liên kết | Link menu là `#`. Thẻ sản phẩm không dẫn sang trang chi tiết dù đã dựng. "Xem chi tiết" trỏ `#details`, nhưng chỉ có khi trang có khối câu chuyện. Tên trang trong menu là tiếng Anh ("Product Detail Page"). | `content.nav_links`, `nextjs.py` (12 chỗ `href="#…"`) |
| A5 | Trang liên hệ | Địa chỉ "12 Nguyễn Huệ, Quận 1" và giờ "Thứ 2 – Thứ 7, 8:00 – 18:00" ghi cứng, không lấy dòng liên hệ chủ tiệm nhập ở B4. | `app_pages.contact_form` |
| A6 | Chân trang | Link Vận chuyển, Đổi trả, Bảo mật, Điều khoản trỏ `#`, và không có các trang đó. Không có link mạng xã hội (Facebook, Instagram, TikTok, Zalo) hay bản đồ. | `nextjs._footer` |
| A7 | Chủ tiệm xem đơn | Đơn chỉ nằm trong `data/orders.jsonl`. Không có trang xem đơn và không có email hay Zalo báo cho chủ tiệm khi có đơn mới, trừ khi tự nối webhook. | `order.py` |
| A8 | Thanh toán | Có lựa chọn "Chuyển khoản" và "Ví điện tử" nhưng không hiện số tài khoản hay mã VietQR, cũng không có MoMo. | `app_pages.py` dòng 134 |

## B. Trang web thật cần mà chưa có

- **SEO:** chưa có mô tả trang, ảnh khi chia sẻ link lên Zalo/Facebook, favicon từ logo, `sitemap.xml`, `robots.txt`, trang 404. Tiêu đề tab đang là đoạn đầu prompt.
- **Nút nổi trên điện thoại:** chưa có nút Zalo hoặc gọi nổi, thứ mà web bán hàng ở Việt Nam gần như luôn có.
- **Thống kê lượt xem:** chưa có chỗ gắn mã Google Analytics hay Meta Pixel.
- **Các khối hay cần:** bản đồ và giờ mở cửa, đội ngũ, tin tức hoặc blog, video, đánh giá kèm ảnh.
- **Loại trang web:** mới có 5 loại (bán hàng, phần mềm, đặt lịch, khóa học, portfolio). Công ty dịch vụ (xây dựng, luật, kế toán), khách sạn, sự kiện, bất động sản đều rơi vào "Khác". Loại "Khác" lấy danh sách trang của portfolio nhưng chữ mẫu của bán hàng, nên không khớp nhau. *(`consultant.sitemap_for`, `content.DEFAULTS[OTHER]`)*

## C. Studio và quy trình

- **Không có danh sách dự án.** "Phiên mới" xoá mã phiên khỏi trình duyệt, nên mất đường quay lại dự án cũ. *(`pipeline-console.tsx` dòng 312)*
- **Góp ý chỉ đổi được 5 trụ thiết kế.** Khi không có AI, không sửa được chữ, tên tiệm, ảnh, cũng không thêm, bỏ hay đổi thứ tự các khối. Không sửa chữ trực tiếp trên trang xem trước được. *(`consultant.interpret_feedback`)*
- **Không có lịch sử phiên bản hay nút hoàn tác** khi bản sửa xấu hơn bản trước.
- **Không báo khi AI hỏng** (lỗi 402): người dùng không biết trang đang dựng bằng luật.
- **Khung xem trước không có nút đổi khổ** điện thoại / máy tính bảng / máy tính.

### Đã sửa (21/11): A1, A5 và một phần A8

- **Ba form trang phụ gửi thật:** thanh toán, đặt lịch và liên hệ gửi vào cùng API nhận đơn, kèm mã đơn và kênh dự phòng (Zalo, gọi, nhắn tin, email) khi không gửi được. Mỗi form được kiểm tra lại trên máy chủ.
- **Trang liên hệ dùng thông tin thật:** địa chỉ, giờ, số điện thoại và email lấy từ dòng liên hệ ở B4. Không có thì ẩn mục này, không bịa địa chỉ.
- **Giỏ hàng đọc đúng giá:** đọc được "85k", "1,5tr", "2 triệu", trước đây bị thay bằng giá mẫu 390.000₫.
- **Ô nhập chữ dài** (lời nhắn, ghi chú) dùng font của trang, không còn font máy đánh chữ.
- **Còn lại:**
  - trang Cài đặt (SaaS) vẫn chỉ hiện "Đã lưu";
  - "Chuyển khoản" chưa có số tài khoản hay VietQR;
  - giỏ hàng chưa giữ món giữa các trang.

### Đã sửa (21/11): A2 giỏ hàng

- **Giỏ hàng giữ món giữa các trang:** "Thêm vào giỏ" ở lưới sản phẩm, phần xem nhanh và trang sản phẩm (kèm phân loại) bỏ món vào cùng một giỏ, lưu trong trình duyệt của khách. Mở tab khác vẫn thấy.
- **Icon giỏ trên menu:** hiện số món, từng món kèm giá, tạm tính và nút "Xem giỏ hàng".
- **Trang `/cart` hiện đúng món khách đã chọn:** đổi số lượng, xoá món, gửi đơn xong thì giỏ trống. Không gửi được thì giỏ vẫn giữ nguyên. Giỏ trống thì gợi ý các món có giá kèm nút thêm, không còn món mẫu bịa giá.
- **Chưa có trang giỏ hàng** (mới dựng trang chủ): các nút này mở form đặt hàng cho đúng món đó và icon giỏ bị ẩn, nên khách không bỏ món vào một giỏ không thanh toán được. Dựng xong trang `/cart` thì các trang đã dựng tự chuyển sang giỏ hàng. Món không có giá ("Liên hệ") luôn đi qua form đặt hàng.
- **Sửa thêm:** cột trái của trang giỏ hàng, đặt lịch, liên hệ bị căn giữa theo chiều dọc vì `.split` đè `.align-start`; giờ căn trên.
- **Còn lại:** giá trong giỏ do trình duyệt gửi lên, máy chủ chưa đối chiếu lại với bảng giá của tiệm.

### Đã sửa (21/11): A4 liên kết

- **Menu:**
  - mỗi link đều dẫn tới một chỗ có thật: trang đã dựng (tên ngắn tiếng Việt, ví dụ "Sản phẩm" thay cho "Product Catalog & Filter"), một phần của trang chủ ("Hỏi đáp" → `/#faq`, "Menu bánh" → `/#collection`), form đặt hàng ("Đặt trước" → `#dat-hang`, mở được từ mọi trang), hoặc trang/chân trang liên hệ;
  - từ nào không có chỗ để tới thì bỏ ra khỏi menu, không để link `#`;
  - giỏ hàng, chi tiết sản phẩm và tài khoản không nằm trên menu, vì đã có icon và thẻ sản phẩm dẫn tới;
  - trên điện thoại, bấm link thì menu tự đóng.
- **Thẻ sản phẩm:**
  - ở trang chủ và trang Sản phẩm, thẻ mở trang chi tiết của đúng món đó (`/pdp?sp=…`); trang chi tiết đọc món từ link;
  - danh mục mở trang Sản phẩm đã lọc sẵn (`?dm=…`);
  - link đọc danh sách trang đã dựng lúc chạy (`content/routes.ts`), nên trang dựng trước tự có link sang trang dựng sau.
- **"Xem chi tiết" ở hero và dải cuối trang:**
  - trỏ tới các dòng câu chuyện nếu trang có;
  - nếu không có thì trỏ tới phần ngay sau hero;
  - mỗi phần của trang có `id` để link tới được.
- **Icon tài khoản:** chỉ hiện khi đã có trang tài khoản hoặc đăng nhập.
- **Chân trang shop:**
  - chỉ còn link dẫn tới chỗ có thật: Câu hỏi thường gặp, Đặt hàng, Liên hệ (khi có trang liên hệ);
  - các link chính sách (vận chuyển, đổi trả, bảo mật, điều khoản) tạm bỏ cho tới khi có trang (A6);
  - dòng liên hệ của chủ tiệm hiện ở chân trang.
- **QA có luật mới `dead-link`:** link `#`, hoặc link tới phần mà trang không có, đều bị báo lỗi.
- **Sửa thêm:**
  - danh mục không còn chia xoay vòng: trước đây "Croissant bơ" bị xếp vào "Bánh kem", giờ chỉ xếp khi tên món chứa tên danh mục;
  - tiêu đề trang Sản phẩm đổi thành "Tất cả sản phẩm", không còn luôn ghi danh mục đầu tiên;
  - menu của chế độ Clone bỏ các mục không có địa chỉ.
- **Còn lại:**
  - ô "Sắp xếp" ở trang Sản phẩm chưa sắp xếp thật;
  - các trang chính sách (A6);
  - các dòng danh sách bài viết không còn là link, vì chưa có trang bài viết.

