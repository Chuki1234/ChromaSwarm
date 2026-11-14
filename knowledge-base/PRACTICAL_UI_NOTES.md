# Ghi chú nguyên tắc UI — từ *Practical UI* (Adham Dannaway, 2022)

> Đây là **ghi chú tóm tắt viết lại bằng lời của Claude**, không phải bản sao của sách.
> Chỉ giữ các nguyên tắc, con số và lý do có thể áp dụng; không chép văn bản, ví dụ hay hình minh hoạ gốc.
> Sách có bản quyền: muốn đọc chi tiết, hình minh hoạ và ví dụ đầy đủ thì xem bản gốc (practical-ui.com).
>
> Cuối file có phần **Đối chiếu với `FRONTEND_STANDARDS.md`**: chỗ trùng, chỗ thiếu, chỗ mâu thuẫn.

Tinh thần chung của sách: UI tốt phần lớn đến từ một **hệ thống quy tắc logic**, không phải cảm hứng nghệ thuật. Mỗi chi tiết trên giao diện phải có lý do. Các quy tắc là "mặc định an toàn", không phải luật cứng — vẫn nên kiểm chứng bằng usability test.

---

## 1. Nền tảng

### 1.1. Giảm rủi ro khả dụng (usability risk)
- Mỗi quyết định thiết kế nên được cân bằng rủi ro: "có ai đó sẽ gặp khó khăn với chi tiết này không?"
- Rủi ro điển hình: chữ xám nhạt mảnh (khó đọc), icon không có nhãn (khó hiểu, nặng hơn với người suy giảm nhận thức/thị lực), tiêu đề tô màu (bị tưởng là link).
- Thiết kế cho nhóm rộng nhất: thị lực kém, ít rành máy tính, khéo léo tay kém, khả năng nhận thức hạn chế.
- Mức tối thiểu: **WCAG 2.1 AA**.
- Gặp gì mơ hồ thì làm rõ trước, đừng đợi usability test mới phát hiện.

### 1.2. Mỗi chi tiết phải có lý do logic
- UI không chỉ là "làm cho đẹp" mà là thiết kế trải nghiệm: trông thế nào, hoạt động ra sao, vì sao.
- Lý do khách quan giúp ra quyết định nhanh hơn, bảo vệ thiết kế khi thảo luận và góp ý có tính xây dựng ("trông đẹp"/"không thích" không phải là lý do).

### 1.3. Giảm chi phí tương tác (interaction cost)
- Chi phí tương tác = tổng công sức thể chất + tinh thần để xong việc: nhìn, cuộn, tìm, đọc, bấm, chờ, gõ, nghĩ, nhớ.
- Đo được nên tối ưu được. Sản phẩm tập trung làm tốt một việc thường thắng.
- 3 cách hiệu quả nhất:
  1. **Đặt hành động gần thứ nó tác động** + vùng bấm đủ lớn (Định luật Fitts). Vùng an toàn: **≥ 48×48pt**.
  2. **Bớt gây xao nhãng**: banner động, pop-up, hình trang trí không cần thiết.
  3. **Bớt lựa chọn** (Định luật Hick); có thể làm nổi một nhóm nhỏ lựa chọn "gợi ý/phổ biến".
- Ví dụ cách làm: thay dropdown số lượng bằng stepper, đưa nút thêm vào giỏ sát ô số lượng, căn trái nút để người dùng kính lúp màn hình không bỏ sót.

### 1.4. Giảm tải nhận thức (cognitive load)
- Bỏ style, thông tin, quyết định thừa.
- Chia thông tin thành nhóm nhỏ, thể hiện rõ quan hệ.
- Dùng pattern quen thuộc.
- Nhất quán: thứ giống nhau thì trông và hoạt động giống nhau.
- Phân cấp thị giác rõ.
- Bài toán lớn → chia thành bước nhỏ (vd form dài → nhiều bước).

### 1.5. Xây design system (3 bước)
1. **Bộ tuỳ chọn style định sẵn** — màu, chữ, khoảng cách, bóng, bo góc… Giới hạn lựa chọn giúp nhất quán và quyết định nhanh.
   - Màu: mỗi biến thể có **vai trò cố định** (hành động, tiêu đề, chữ phụ, viền đậm, viền nhạt, nền phụ).
   - Chữ: định nghĩa cỡ + độ đậm một lần, dùng lại khắp nơi.
   - Khoảng cách: bộ "cỡ áo" XS–XXL.
   - Bóng: 3 mức (nhỏ / vừa / lớn) cho độ nổi.
   - Bo góc: 3 mức tương ứng phần tử nhỏ / vừa / lớn (ví dụ trong sách: 8 / 16 / 32pt).
2. **Module tái sử dụng** — bắt đầu từ component nhỏ nhất (nút, avatar, ô nhập) → ghép thành component lớn → sắp thành template trang. Gom tất cả thành thư viện component / UI kit.
3. **Hướng dẫn sử dụng** — thứ hay bị quên nhất. Gồm cả quy tắc viết chữ trên giao diện. Ví dụ các quy tắc sách tự đặt: hành động dùng màu primary; viết hoa kiểu câu; căn trái nút; căn trái chữ; tránh nút disabled; đưa ý chính lên đầu câu; ngắn gọn, ngôn ngữ đơn giản.

### 1.6. Khả năng tiếp cận (accessibility)
- Cung cấp trải nghiệm tương đương cho mọi người: mù, thị lực kém, mù màu, suy giảm vận động, suy giảm nhận thức. Ở một số nước là bắt buộc pháp lý.
- Tối thiểu WCAG 2.1 AA; đưa người khuyết tật vào usability test.
- Accessibility tốt = usability tốt cho tất cả: ai cũng có thể bị khuyết tật **tạm thời** (chấn thương) hoặc **theo tình huống** (nắng chói màn hình). Cũng là lý do kinh doanh: bỏ sót họ là mất khách.
- Hai công nghệ hỗ trợ phổ biến cần nhớ khi thiết kế:
  - **Screen reader**: đọc giao diện thành tiếng/chữ nổi; người dùng duyệt bằng bàn phím hoặc vuốt. → Tiêu đề, link, nút phải **hiểu được khi đọc tách khỏi ngữ cảnh**.
  - **Screen magnifier** (kính lúp màn hình): dùng phổ biến hơn screen reader; chỉ thấy một phần nhỏ màn hình mỗi lúc. → Thứ đặt lệch xa (nút căn phải, cột form thứ hai) dễ bị bỏ sót.

### 1.7. Dùng pattern phổ biến (Định luật Jakob)
- Người dùng mang sẵn mô hình tư duy từ sản phẩm khác; dùng pattern quen giảm lỗi, tải nhận thức, chi phí tương tác và tiền test.
- Sáng tạo ở nơi tạo ra giá trị khác biệt của sản phẩm, không phải ở ô nhập liệu.
- Nếu sản phẩm nằm trên nền tảng (iOS/Android) thì theo guideline nền tảng, trừ khi nó test kém hoặc kém tiếp cận.
- Quy ước cơ bản: link có gạch chân; checkbox là ô vuông có dấu tick; ô nhập là hình chữ nhật có nhãn phía trên.

### 1.8. Quy tắc 80/20 (Pareto)
- ~80% người dùng dùng ~20% tính năng; ~80% phàn nàn đến từ ~20% lỗi; ~80% sự chú ý dồn vào ~20% trang.
- Tối ưu cho tác vụ phổ biến trước, đừng sa đà vào edge case hiếm.

### 1.9. Nhớ đến chi phí
- Dùng design system/UI kit có sẵn, bộ icon có sẵn; dùng pattern quen để giảm test.
- Hiểu cách giao diện được code để biết giới hạn kỹ thuật; nói chuyện sớm và thường xuyên với dev. Giải pháp đơn giản thường vừa rẻ vừa dễ dùng.

### 1.10. Nhất quán
- Trong sản phẩm: thứ giống nhau phải trông và hoạt động giống nhau (component, template, style, ngôn từ).
- Với sản phẩm khác: theo quy ước phổ biến để người dùng không phải học lại.

---

## 2. Ít mà chất (Less is more)

- **Bỏ thông tin thừa**: mỗi phần tử thêm vào đều tranh sự chú ý. Xoá phần lặp lại (vd tên khoá học lặp ở mọi chương → đưa thành tiêu đề nhóm), bỏ từ thừa và câu dẫn, hé lộ dần phần ít quan trọng.
- **Bỏ style thừa**: đường kẻ, màu, nền, animation chỉ để trang trí. Đặc biệt nguy hiểm khi style trang trí bị hiểu nhầm là có ý nghĩa (màu khác nhau cho từng dòng danh sách, tiêu đề xanh gạch chân dù không phải link, icon trang trí trông như nút).
- **Trend phai nhanh**: càng nhiều hiệu ứng thời thượng, giao diện càng chóng cũ. Glassmorphism và neumorphism khó tạo phân cấp thị giác và khó đạt tương phản → dễ vi phạm accessibility.
- **Không phải link nào cũng cần gạch chân**: menu điều hướng, card, tab đã có tín hiệu tương tác riêng (khung nổi, ảnh + chữ trong hộp…) nên có thể bỏ kiểu link truyền thống. Link nằm trong đoạn văn thì vẫn giữ màu + gạch chân.
- **Hé lộ dần (progressive disclosure)**: chỉ hiện thứ cần cho tác vụ hiện tại; ai cần thêm thì mở ra. Tăng nhẹ chi phí tương tác nhưng giảm mạnh tải nhận thức. Nhãn của phần mở rộng phải **mô tả nội dung**, đừng ghi chung chung "Xem thêm". Ví dụ: ô số điện thoại chỉ hiện khi người dùng tick "nhận thông báo qua SMS".
- **Tối giản ≠ đơn giản**: giao diện tối giản có thể mơ hồ — icon không nhãn, trạng thái được chọn quá mờ, hành động quan trọng bị giấu, icon tương phản thấp. Đơn giản hoá không chỉ là cắt bỏ; đừng cắt thông tin then chốt.
- **Thiết kế cho màn hình nhỏ nhất trước**: không gian chật buộc phải ưu tiên; tránh xu hướng "nhà to thì nhồi đồ" trên màn hình lớn.
- **Chia nhỏ lựa chọn** (Hick) — 4 cách:
  1. Bỏ bớt lựa chọn (mỗi trường form/mục menu phải "xứng đáng có mặt").
  2. Nhóm/phân loại lựa chọn (danh mục bài viết theo chủ đề).
  3. Chia thành nhiều bước (form nhiều bước, menu nhiều cấp).
  4. Gợi ý lựa chọn (mục phổ biến, gợi ý từ khoá tìm kiếm).

---

## 3. Màu sắc

### 3.1. Độ tương phản (WCAG 2.1 AA)
- Tỷ lệ từ 1:1 đến 21:1.
- **3:1** — chữ lớn (≥ 18px **đậm**, hoặc ≥ 24px thường) và **thành phần giao diện** (viền ô nhập, radio, checkbox, hình dạng nút, icon mang nghĩa). Phần tử thuần trang trí không cần đạt.
- **4.5:1** — chữ nhỏ (≤ 18px).
- Lỗi hay gặp: icon đóng < 3:1, chữ phụ < 4.5:1, viền ô tìm kiếm < 3:1, placeholder < 4.5:1, nền nút với chữ trắng < 4.5:1, chữ link < 4.5:1.

### 3.2. APCA (nằm trong bản nháp WCAG 3)
- Khắc phục điểm yếu WCAG 2: có trường hợp chữ trắng trên nền cam dễ đọc hơn nhưng WCAG 2 đánh trượt, chữ đen lại đạt; APCA cho kết quả khớp cảm nhận thật.
- Đo bằng số **Lc** (không phải tỷ lệ), phụ thuộc cỡ + độ đậm chữ; **thứ tự chữ/nền có ý nghĩa** (chữ trắng trên nền xanh có thể đạt trong khi chữ xanh trên nền trắng thì trượt).
- Đặc biệt tốt hơn cho **giao diện tối** (WCAG 2 có thể cho đạt những cặp màu tối khó đọc).
- Ngưỡng tham khảo:
  - **90** — khuyến nghị cho body text (từ 14px thường)
  - **75** — tối thiểu cho body text (từ 18px thường)
  - **60** — tối thiểu cho chữ khác (từ 24px thường hoặc 16px đậm)
  - **45** — tối thiểu cho chữ lớn (từ 36px thường hoặc 24px đậm) và thành phần giao diện
  - **30** — sàn tuyệt đối cho chữ kiểu placeholder, chữ nút disabled
  - **15** — tối thiểu cho phần tử không phải chữ
- Khuyến nghị: dự án cá nhân dùng APCA; dự án thương mại cần tuân thủ pháp lý thì vẫn theo WCAG 2 cho tới khi WCAG 3 ra mắt — lý tưởng là **đạt cả hai**.

### 3.3. Không dựa vào màu đơn thuần
- Mù màu (chủ yếu ở nam; phổ biến nhất là lẫn đỏ–xanh lá; một số không thấy màu nào).
- Lỗi form: ngoài màu đỏ, thêm **icon + viền dày hơn + nền tô nhẹ**.
- Link trong đoạn văn: thêm **gạch chân**.

### 3.4. Màu hệ thống (trạng thái)
- Thường cần 3: **đỏ** (lỗi, cần xử lý gấp), **hổ phách/amber** (cảnh báo, hành động có rủi ro), **xanh lá** (thành công).
- Luôn kèm tín hiệu phụ (icon).
- Màu hệ thống dùng cho chữ → ≥ 4.5:1; chỉ dùng cho icon/thành phần → ≥ 3:1.

### 3.5. Dùng màu để phân cấp thị giác
- **Độ bão hoà**: phần quan trọng (link, nút) dùng màu bão hoà hơn.
- **Hue**: một số hue tự nhiên nổi hơn (đỏ rất nổi → dành cho lỗi khẩn).
- **Tương phản**: tiêu đề đậm/tối hơn body.

### 3.6. Giao diện sáng / tối
- **Sáng**: an toàn nhất, quen thuộc, dễ đọc, hợp số đông.
- **Tối**: cảm giác kịch tính, mạnh, sang; bằng chứng về "đỡ mỏi mắt" còn mâu thuẫn, và chi tiết tối có thể khó thấy dưới nắng → càng phải chú ý tương phản.
- Kết hợp vùng sáng + vùng tối trong cùng giao diện giúp cân bằng, tạo nhóm và phân cấp.

### 3.7. Đen trắng làm nền móng
- Đen–trắng (kể cả các sắc xám) cho vẻ vượt thời gian và làm nổi nội dung.
- **Thiết kế bằng đen trắng trước**, tập trung vào khoảng cách, kích thước, bố cục, tương phản; thêm màu sau.
- Tỷ lệ đen/trắng thể hiện tính cách: nhiều trắng → đơn giản, cổ điển; nhiều đen → kịch tính, sang trọng.
- **Tránh đen tuyền trên trắng** (chênh độ sáng quá lớn → mỏi mắt); dùng xám rất tối.
- Có thể **pha chút màu thương hiệu vào đen/trắng/xám** để tạo khác biệt mà vẫn giữ lợi ích đen trắng.

### 3.8. Một màu thương hiệu, gắn với tương tác
- Nhiều thương hiệu mạnh dùng **1 màu riêng + đen trắng**.
- Tâm lý học màu sắc **không phổ quát** (văn hoá, trải nghiệm cá nhân, mù màu, màu xung quanh, sắc độ khác nhau đều thay đổi cảm nhận) → chỉ coi là gợi ý lỏng. Chọn màu thì: test với người dùng, ưu tiên màu dễ nhận diện, cẩn thận với màu mang nghĩa mạnh (đỏ).
- **Màu thương hiệu = màu hành động**: áp vào link, nút để dạy người dùng "màu này là bấm được". Tránh dùng màu này cho phần tử **không** tương tác (vd tiêu đề tô màu dễ bị tưởng link).
- Màu thương hiệu phải đạt **≥ 4.5:1** với nền chính (sáng hoặc tối). Không đạt thì làm tối/sáng nó một chút.
- **Nhiều màu thương hiệu**: màu tương phản cao nhất dành cho tương tác; các màu khác chỉ dùng **tiết chế cho trang trí** (nền, viền, minh hoạ). Không dùng hơn 1 màu cho phần tử tương tác.

### 3.9. Bảng màu đơn sắc (monochromatic) với vai trò cố định
- Các biến thể của **1 màu thương hiệu** (đổi saturation + brightness) thay vì xám trung tính → nhìn liền mạch, màu có chức năng, ít màu → ít tải nhận thức, thương hiệu rõ.
- Sách dùng hệ **HSB** (Hue 0–360, Saturation 0–100, Brightness 0–100) để tạo biến thể cho dễ.
- Đa số trường hợp chỉ cần **1 màu thương hiệu + 5 biến thể**. Trạng thái hover nên dùng thay đổi opacity thay vì thêm màu mới.

**Bảng màu sáng** (ví dụ trong sách dùng hue 230):

| Vai trò | Dùng cho | Ràng buộc tương phản (so với biến thể nhạt nhất) | HSB ví dụ |
|---|---|---|---|
| Primary | Hành động: link, nút | ≥ 4.5:1 | 230, 70, 80 |
| Darkest | Chữ chính: tiêu đề, body, nhãn | ≥ 4.5:1 | 230, 60, 20 |
| Dark | Chữ phụ | ≥ 4.5:1 | 230, 30, 45 |
| Medium | Viền **không trang trí** (ô nhập…) | ≥ 3:1 | 230, 20, 66 |
| Light | Viền trang trí (tách khối) | không bắt buộc | 230, 10, 95 |
| Lightest | Nền phụ | mọi chữ/thành phần trên nó phải đạt AA | 230, 2, 98 |
| White | Nền chính | như trên | 0, 0, 100 |

Cách tạo: Darkest = giảm mạnh brightness, tăng saturation (vì rất tối); mỗi biến thể tiếp theo tăng brightness + giảm saturation dần. **Kiểm thử bảng màu trên một màn hình thật có đủ mọi biến thể.**

- Muốn trung tính hơn: giữ Primary, các biến thể còn lại đặt saturation = 0.
- **Màu thương hiệu mang nghĩa hệ thống** (đỏ/xanh lá/amber): dùng biến thể Darkest cho link/nút, hoặc dùng xanh dương cho tương tác, để tránh xung đột nghĩa.
- **Màu thương hiệu quá sáng** (vd vàng): làm tối nhẹ nếu còn nhận diện được; hoặc thêm text-shadow cho chữ trắng; hoặc dùng **Darkest cho chữ trên nút**, cho link và tương tác khác, và **thêm viền** cho nút để hình dạng đạt 3:1; hoặc chuyển sang giao diện tối.

**Bảng màu tối** (ví dụ trong sách dùng hue 166):

| Vai trò | Dùng cho | Ràng buộc (so với biến thể Dark — nền phụ) | HSB ví dụ |
|---|---|---|---|
| Primary | Hành động | ≥ 4.5:1 | 166, 50, 90 |
| White | Tiêu đề | ≥ 4.5:1 | 0, 0, 100 |
| Lightest | Chữ phụ | ≥ 4.5:1 | 166, 4, 80 |
| Light | Viền không trang trí | ≥ 3:1 | 166, 6, 65 |
| Medium | Viền trang trí | không bắt buộc | 166, 8, 33 |
| Dark | Nền phụ | mọi chữ/thành phần trên nó đạt AA | 166, 10, 23 |
| Darkest | Nền chính | như trên | 166, 12, 15 |

- Logic đảo ngược bảng sáng; trắng cho tiêu đề vì tương phản cao nhất trên nền tối.
- **Màu thương hiệu quá tối** trên nền tối: làm sáng nhẹ; hoặc dùng **trắng** cho chữ nút/link, và thêm viền (biến thể Light) cho nút để đạt 3:1.

### 3.10. Nhiệt độ màu của ảnh
- Mẹo, không phải quy tắc: bảng màu lạnh → chọn/chỉnh ảnh trang trí sang tông lạnh; bảng màu ấm → ảnh ấm. Không áp dụng cho ảnh sản phẩm (cần màu thật).

---

## 4. Bố cục & khoảng cách

### 4.1. Nhóm các phần tử liên quan (4 cách, có thể kết hợp)
1. **Chung vùng chứa (common region)** — viền, bóng, nền. Tín hiệu nhóm **mạnh nhất**, hay dùng cho khung chính (header, sidebar…), card, dialog. Lấn át được cả khoảng cách. Nhưng **đừng bọc mọi nhóm bằng container** → rối.
2. **Gần nhau (proximity)** — liên quan thì đặt gần, không liên quan thì giãn xa. Thay container bằng khoảng cách thường gọn hơn.
3. **Giống nhau (similarity)** — cùng kích thước, hình dạng, màu → được hiểu là cùng nhóm. Làm một phần tử hơi khác để làm nổi nó (vd gói giá "phổ biến nhất": lớn hơn, viền khác màu, nút đặc, có badge).
   - Hệ quả: **thứ trông giống nhau sẽ bị kỳ vọng hoạt động giống nhau**. Icon trông như nút phụ sẽ bị tưởng bấm được; badge "đã xác minh" trông như nút primary sẽ gây nhầm → đổi hình dạng (bo tròn hơn), màu (không dùng màu hành động; dùng màu trạng thái), nền nhạt hơn.
4. **Thẳng hàng liên tục (continuity)** — phần tử xếp trên một đường liền được hiểu là liên quan (danh sách). Phá vỡ đường liền để báo hết nhóm hoặc làm nổi một mục.
- Khi một nhóm đã được thể hiện bằng nhiều cách (gần + giống + thẳng hàng), có thể bỏ container ngoài cùng mà vẫn rõ nhóm.

### 4.2. Phân cấp thị giác
- Thứ quan trọng hơn trông nổi hơn → quét nhanh, biết nhìn vào đâu, trông có trật tự.
- 6 công cụ: **kích thước**, **màu** (sáng/đậm/ấm/tương phản cao hơn), **tương phản** (style khác biệt), **khoảng trắng** bao quanh nhiều hơn, **vị trí** (trên cùng / đầu hàng), **độ sâu** (nổi lên gần người dùng hơn).
- Quy trình sửa phân cấp cho một màn hình:
  1. Gom thông tin thành nhóm; sắp xếp trong mỗi nhóm theo mức quan trọng.
  2. Sắp xếp các nhóm theo mức quan trọng (quan trọng lên trên).
  3. Chỉnh style từng phần tử: tiêu đề chính to + đậm + màu Darkest; thông tin phụ nhỏ hơn, thường, màu Dark; dùng icon quen thuộc khi giúp quét nhanh.
  4. CTA chính: nút primary; trên mobile có thể **dính đáy màn hình + bóng** để luôn thấy và trong tầm ngón cái; đặt thông tin đáng nhớ (vd giá) cạnh CTA ở cuối (hiệu ứng vị trí nối tiếp: nhớ tốt mục đầu và cuối).
  5. Cặp nhãn–giá trị ngắn: icon + nhãn; icon dạng viền (outline) màu Medium để bớt nổi; chữ màu Dark.
  6. Bỏ nhãn hiển nhiên (vd nhãn "Mô tả" trên đoạn mô tả).
- **Squint test**: nheo mắt / lùi xa / zoom nhỏ / làm mờ bản thiết kế — vẫn phải thấy phần quan trọng nhất và đoán được màn hình để làm gì.

### 4.3. Độ sâu
- Bóng nâng phần tử lên các tầng; tầng cao hơn = gần hơn = nổi hơn, và trông bấm được hơn. Vd header nổi trên feed; nút chính nổi cao nhất.
- **3 mức bóng định sẵn** (nhỏ / vừa / lớn): bóng nhỏ + sắc = nhô nhẹ; bóng lớn + mềm = nổi cao. Ánh sáng từ **trên xuống**. Màu bóng nên lấy từ biến thể Darkest thay vì đen.
- **Màu cũng tạo độ sâu**: màu sáng trông nổi hơn màu tối → card trắng trên nền xám trông nổi mà không cần bóng.

### 4.4. Box model & đơn vị
- Margin (ngoài viền) / border / padding (trong viền) / nội dung. Giao diện = các hình chữ nhật lồng nhau.
- Thiết kế ở **@1x bằng point (pt)**: 1pt = 1px ở @1x, = 4px vật lý (2×2) ở @2x, = 9px (3×3) ở @3x.

### 4.5. Thang khoảng cách định sẵn
- Bộ cỡ áo theo bội số 8: **XS 8 · S 16 · M 24 · L 32 · XL 48 · XXL 80** (pt). Giao diện chi tiết có thể dùng bước 4.
- Vì sao 8: nhiều kích thước màn hình chia hết cho 8, linh hoạt hơn 10. Hệ quả là mọi thứ khớp lưới 8pt.
- Giống thang chữ: **bước càng lớn càng giãn nhanh** để tỷ lệ cân với phần tử lớn.
- Lợi ích: ít biến thể → gọn hơn, nhất quán hơn, thiết kế nhanh hơn.

### 4.6. Khoảng cách theo mức độ liên quan
- Liên quan chặt → khoảng nhỏ; không liên quan → khoảng lớn.
- Cách áp dụng: coi giao diện là hình chữ nhật lồng nhau; **bắt đầu từ khoảng nhỏ nhất ở trong cùng, tăng dần khi đi ra ngoài**. Dùng một cỡ duy nhất cho mọi chỗ → trông chật và khó hiểu.
- Ví dụ quy tắc khoảng cách nên tự đặt: padding card = M (24); khoảng cách giữa cột = L (32); padding dọc mỗi section website = XXL (80); chữ trong card = XS (8).

### 4.7. Hào phóng khoảng trắng
- Thêm khoảng trắng là cách nhanh nhất để giao diện tốt hơn. Khoảng trắng không nhất thiết màu trắng (có thể là màu, hoạ tiết, ảnh).
- Chật → khó thấy nhóm và phân cấp. Khi phân vân, chọn cỡ lớn hơn một bậc. Kiểm bằng squint test.

### 4.8. Lưới 12 cột
- Gồm **cột** (rộng linh hoạt theo %), **gutter** (khe giữa cột, cố định, rỗng, hẹp hơn cột), **margin** (lề trái/phải).
- Chỉ **khung chính** cần khớp cột; phần tử nhỏ bên trong dùng thang khoảng cách.
- Desktop 12 cột → mobile 4 cột (vd 3 card × 4 cột trên desktop xếp chồng trên mobile).
- Gutter lớn hơn trên màn hình lớn: ví dụ **32pt desktop → 16pt mobile**.
- Margin lớn hơn trên màn hình lớn: ví dụ **80pt desktop → 16pt mobile**.
- 12 vì đủ linh hoạt, không phức tạp, khớp đa số framework front-end.

### 4.9. Căn chỉnh
- **Căn trái** dễ đọc nhất (mắt có mép trái cố định để quay về). Khi đặt icon cạnh chữ, giữ **mép trái thẳng** (icon nằm trên chữ hoặc chữ thẳng hàng nhau), đừng để icon phá mép.
- Căn giữa dùng được cho **khối chữ ngắn**, không dùng cho đoạn dài.
- Chữ khác cỡ trên cùng một hàng → **căn theo baseline**, không căn giữa theo chiều dọc (vd "/tháng" phải dính baseline với con số giá).
- **Hạn chế số kiểu căn** trong một component/section; trộn trái/giữa/phải khiến mắt chạy zic-zac. Nếu nội dung rất ngắn, căn giữa toàn bộ cũng được — khi đó cho nút full-width để cả người thuận tay trái lẫn phải dễ bấm bằng một tay.

### 4.10. Hành động đặt gần (Fitts)
- Vùng bấm ≥ 48×48pt; hành động gần nơi người dùng vừa thao tác.
- Ví dụ menu trượt ra từ góc trái trên: đặt nút đóng **ở đúng chỗ nút mở**, đưa danh sách lên trên, căn trái, mục to hơn, có viền để báo vùng bấm lớn.
- Mỗi lần tiết kiệm nhỏ cộng dồn, nhất là với thao tác lặp lại.

### 4.11. Nội dung quan trọng phải nhìn thấy
- Người dùng không dùng thứ họ không thấy. Giấu sau menu là rủi ro; còn chỗ thì để hiển thị.
- Phải giấu vì thiếu chỗ thì làm cho **khám phá được** (vd để lộ mép card tiếp theo trong carousel ngang).

### 4.12. Giao diện "không vỡ"
- Thiết kế cả cho số lớn, chữ dài, edge case. Ưu tiên component co giãn/xuống dòng hoặc giảm cỡ chữ thay vì cắt bớt.
- Buộc phải cắt thì đừng cắt mất phần phân biệt — cân nhắc **cắt ở giữa** thay vì cuối (để các mục có đầu giống nhau vẫn phân biệt được).

### 4.13. Quy tắc một phần ba cho ảnh
- Chia ảnh 3×3; đặt chủ thể vào 1 trong 4 giao điểm thay vì chính giữa → tự nhiên, có chuyển động. Đặc biệt hiệu quả với ảnh hành động; đường chân trời khớp đường ngang của lưới.

---

## 5. Typography

### 5.1. Một typeface sans serif
- 5 nhóm: **serif** (truyền thống, trang trọng; một số đọc được ở cỡ nhỏ), **sans serif** (hiện đại, rất dễ đọc ở mọi cỡ, trung tính), **script** (viết tay; chỉ dùng cỡ lớn), **display** (trang trí, nhiều cá tính; chỉ dùng cỡ lớn), **monospace** (mọi ký tự rộng bằng nhau; hợp với code và **so sánh số**).
- Mặc định an toàn: **một sans serif duy nhất** vì: dễ đọc (legibility), trung tính (hợp mọi thương hiệu, nội dung là trọng tâm, ít chọn sai), đơn giản (ít chi tiết gây xao nhãng). Nhiều typeface → rối và tăng tải nhận thức.
- Chọn sans serif: chọn font phổ biến đã được kiểm chứng; có nhiều độ đậm (thường chất lượng hơn); **x-height cao** và giãn chữ rộng (đọc tốt ở cỡ nhỏ); xem font của các công ty thiết kế tốt; **hỗ trợ đủ ngôn ngữ cần dùng**; có tính năng OpenType. Phân vân → dùng **system font** của nền tảng (đã kiểm chứng, tải nhanh).

### 5.2. Typeface thứ hai chỉ cho tiêu đề
- Khi đã vững, thêm cá tính bằng font thứ hai **chỉ cho tiêu đề** (không phải lo đọc ở cỡ nhỏ).
- Cảm xúc thường gặp (chủ quan, chỉ là gợi ý): sans serif → trung tính/tối giản/hiện đại; serif → truyền thống/lâu đời/cổ điển; sans serif bo tròn → vui/mềm/tinh nghịch; script tự do → cá nhân/thủ công; script trang trọng → trang nhã/nữ tính; sans serif mảnh → thời thượng/hiện đại/sang trọng.

### 5.3. Chỉ dùng regular + bold
- Nhiều độ đậm → nhiễu, khó dùng nhất quán. Bold cho tiêu đề, regular cho chữ nhỏ còn lại. Bold quá nặng thì dùng semibold thay.
- Độ đậm quá mảnh/quá dày chỉ dùng cho tiêu đề/chữ lớn.

### 5.4. Thang chữ (type scale)
- Chọn cỡ body làm gốc, nhân liên tiếp với một tỷ lệ:
  1.067 Minor Second · 1.125 Major Second · 1.200 Minor Third · **1.250 Major Third** · 1.333 Perfect Fourth · 1.414 Augmented Fourth · 1.500 Perfect Fifth · 1.618 Golden Ratio.
- Ví dụ trong sách (gốc 18px, tỷ lệ 1.25, làm tròn): H1 44 · H2 36 · H3 28 · H4 22 (bold) · Body 18 · Small 15 (regular).
- **Tỷ lệ nhỏ** cho app phức tạp, công cụ, dashboard; **tỷ lệ lớn** cho website marketing.
- Tỷ lệ lớn trên mobile dễ làm tiêu đề xuống dòng nhiều → **đổi sang tỷ lệ nhỏ hơn trên mobile**.
- Làm tròn số thập phân. Không tạo text style không dùng tới.

### 5.5. Kích thước, line-height, độ dài dòng
- **Body text dài ≥ 18px** (đa số typeface) — màn hình ngày càng lớn và nét, người đọc ở khoảng một sải tay.
- **Line-height body ≥ 1.5**, thường 1.5–2. Dòng dài hơn, typeface đậm/nặng hơn, typeface "trông to" hơn → cần line-height cao hơn.
- **Cỡ chữ càng lớn, line-height càng nhỏ** (vd tiêu đề 24px ~1.3, body 18px ~1.6) để khoảng hở giữa các dòng đều nhau.
- **Độ dài dòng 40–80 ký tự** (kể cả dấu cách). Quá dài khó tìm đầu dòng; quá ngắn mắt phải quay lại liên tục. Không cần trải chữ hết chiều ngang trang.

### 5.6. Căn chữ
- Căn trái cho chữ dài (đọc theo mẫu chữ F).
- **Không căn giữa** chữ dài (đầu dòng thay đổi liên tục).
- **Không căn đều hai bên (justify)**: khoảng cách chữ/từ không đều, tạo "dòng sông" khoảng trắng, đặc biệt khó với người dyslexia.

### 5.7. Giảm letter-spacing cho chữ lớn
- Font "text" được thiết kế với khoảng cách rộng cho cỡ nhỏ; khi phóng to thì nên siết lại, càng to siết càng nhiều. Font "display" thường đã siết sẵn.

### 5.8. Chữ trên ảnh
- Phải đạt 4.5:1 (chữ nhỏ) / 3:1 (chữ lớn).
- Cách làm: **gradient tuyến tính** (vd màu Darkest 90% opacity ở đáy → 0% ở giữa ảnh) + text-shadow; **lớp phủ đặc bán trong suốt** (vd Darkest 50%) + text-shadow; **làm mờ nền** kết hợp lớp phủ; **nền đặc sau chữ** (kiểu phụ đề video — chữ trắng trên nền Darkest).

### 5.9. Màu chữ
- Tránh **xám nhạt** (không đạt 4.5:1) và tránh **đen tuyền trên trắng** (mỏi mắt). Dùng xám đậm đạt chuẩn.

---

## 6. Viết chữ giao diện (copywriting)

- **Ngắn gọn**: từ nào bỏ được mà không mất thông tin hay hại usability thì bỏ.
  - Bỏ từ đệm vô nghĩa (kiểu "thật ra", "về cơ bản", "thực sự", "khá").
  - Bỏ mạo từ/từ nối ngắn khi có thể (trong tiếng Anh: a/an/the).
  - Bỏ câu dẫn kiểu "Bạn có muốn…", "Để…", "Bạn có chắc…", "Có…".
  - Ưu tiên từ ngắn; câu **dưới 20 từ**.
- **Viết hoa kiểu câu (sentence case)**: chỉ viết hoa chữ đầu và danh từ riêng. Title Case khó đọc hơn (chữ hoa ở mỗi từ làm gián đoạn việc quét) và quy tắc không thống nhất.
- **Ngôn ngữ đơn giản, đời thường**: như đang giải thích cho học sinh lớp 6 chưa biết chủ đề; tránh thuật ngữ chuyên ngành, tiếng lóng; từ ngắn và đơn giản; giọng tự nhiên.
- **Đưa ý chính lên đầu (front-loading)**: người dùng quét từ trái sang phải, xuống dưới. Đưa lợi ích/thông tin then chốt lên đầu tiêu đề, danh sách, link (vd con số giảm giá trước, điều kiện sau).
- **Kim tự tháp ngược**: quan trọng nhất trước (thường nằm trong tiêu đề, đủ để phần lớn người dùng hành động) → thông tin hỗ trợ → chi tiết nền (có thể chuyển sang màn hình khác).
- **Hạn chế viết tắt/từ viết tắt**: bắt người đọc phải nghĩ. Nếu dùng thì giải thích lần đầu; tốt nhất viết đầy đủ (vd nhãn form "Số căn hộ" thay vì "Số CH").
- **Hạn chế CHỮ IN HOA**: chữ in hoa mất hình dạng từ nên phải đọc từng chữ cái. Ngoại lệ: **nhãn ngắn** để phân biệt — in hoa + **đậm + cỡ nhỏ + tăng letter-spacing**.
- **Chia nội dung bằng tiêu đề mô tả + gạch đầu dòng**. Tiêu đề phải **nói ra ý chính** (không chỉ là nhãn chung chung), vì nhiều người chỉ quét tiêu đề và người dùng screen reader hay nghe danh sách tiêu đề để nhảy tới.
- **Không dùng "của tôi" trên nhãn form** (giao diện đang "nói chuyện" với người dùng nên "email của tôi" dễ hiểu nhầm). "Của bạn" rõ hơn nhưng thường thừa → chỉ ghi "Email". Dù chọn gì thì nhất quán.
- **Từ vựng nhất quán**: một khái niệm, một từ (nút "Thêm vào giỏ" thì đừng gọi giỏ là "túi"; đừng trộn Đăng ký/Đăng nhập với Sign up/Register/Log in/Sign in, Xoá/Gỡ, Xuất bản/Đăng…).
- **Dùng chữ số** thay vì viết bằng chữ (dễ quét, nhanh hiểu, đúng kỳ vọng, ngắn hơn). Định dạng nhất quán, **có dấu phân cách hàng nghìn**. Số rất lớn → kết hợp số + chữ (vd "1 tỷ").
- **Tránh dấu chấm câu cuối** nếu đoạn chữ không phải câu đầy đủ có dấu phẩy. Các phần tử cạnh nhau phải dùng dấu chấm nhất quán.
- **Độ dài chữ tương đương** giữa các khối nằm cùng hàng (vd 3 cột tính năng) để mọi thứ thẳng hàng.
- **Link phải mô tả đích đến**: tránh "Tìm hiểu thêm", "Đọc thêm", "Bấm vào đây" (khó quét, vô nghĩa khi screen reader đọc danh sách link, nhiều link cùng chữ bị tưởng cùng đích). Dùng tên trang đích; hoặc biến chính tiêu đề thành link. "Bấm" còn sai với người dùng bàn phím/giọng nói/cảm ứng.

---

## 7. Form

### 7.1. Bố cục
- **Một cột**: giữ đà đi xuống, không phải nghĩ "điền ô nào tiếp", ít bỏ sót (người dùng kính lúp hay bỏ sót cột hai).
- **Nhãn đặt trên ô nhập**, sát ô. Nhãn bên trái → mắt chạy zic-zac, khoảng cách không đều; căn phải nhãn thì mép trái lởm chởm khó quét; lại không vừa mobile.
- **Radio/checkbox xếp dọc**, mỗi lựa chọn một dòng (tách rõ, khó chọn nhầm).
- Lo form dài: chấp nhận vì lợi nhiều hơn hại. Có thể đặt **các ô ngắn liên quan cạnh nhau** trong cùng chiều rộng cột (vd ngày hết hạn + CVC). Dài quá ảnh hưởng tỷ lệ hoàn thành → chia bước.
- **Khoảng cách nhãn–ô phải nhỏ hơn rõ rệt khoảng cách giữa các trường** (để thấy nhãn thuộc ô nào; mắt chỉ cần tập trung một lần).

### 7.2. Số trường và trường tuỳ chọn
- Chỉ hỏi thứ **thật sự cần** để cung cấp dịch vụ; nếu hỏi thông tin nhạy cảm thì nói lý do. Thêm trường = nhiều người bỏ cuộc hơn, nhiều việc hơn, nhiều lỗi hơn, tốn công dev hơn.
- Trường tuỳ chọn: ghi chữ **"(không bắt buộc)"** trên nhãn.
- Tốt hơn nữa: **thay trường tuỳ chọn bằng opt-in** — checkbox "nhận cập nhật qua SMS", tick thì mới hiện ô số điện thoại (bắt buộc).
- **Đánh dấu cả trường bắt buộc lẫn tuỳ chọn** (đặc biệt cho người suy giảm nhận thức; cũng là yêu cầu accessibility cho screen reader). Câu hướng dẫn đầu form kiểu "tất cả bắt buộc trừ khi ghi tuỳ chọn" hay bị bỏ qua.
  - Bắt buộc: dấu `*` (gọn, quen; **không tô đỏ** vì đỏ = lỗi) kèm một dòng giải thích ở đầu form; hoặc chữ "(bắt buộc)" — rõ nhất, không cần hướng dẫn.
  - Có thể không đánh dấu khi: sản phẩm không có trường tuỳ chọn nào; form ngắn quen thuộc (đăng nhập, đăng ký nhận tin 1 ô); mỗi màn hình chỉ một câu hỏi kèm lý do; usability test xác nhận không cần.

### 7.3. Kiểu ô nhập
- **Chiều rộng ô khớp độ dài dữ liệu dự kiến** (mã bưu chính 4–6 số thì ô ngắn), đừng cho mọi ô cùng rộng. Dữ liệu thay đổi độ dài → theo trường hợp phổ biến hoặc dài nhất.
- **Giữ kiểu ô nhập quen thuộc** (hình chữ nhật, nhãn bên ngoài phía trên). Nhãn nằm trong ô khiến ô trông như đã điền. Nếu muốn biến tấu, giữ lại **dấu hiệu nhận diện** (vd vòng tròn bên trái của radio dù đã phóng to vùng bấm).
- **Gợi ý (hint) đặt phía trên ô**, dưới nhãn — người dùng đọc điều kiện trước khi gõ; phía dưới ô dễ bị menu autofill / bàn phím ảo che. Gợi ý quan trọng thì phải luôn hiển thị, đừng giấu trong tooltip.
- **Không dùng placeholder thay nhãn**: biến mất khi gõ (quên ô để làm gì), trông như đã điền sẵn, tương phản gần như luôn không đạt. Tốt nhất **không dùng placeholder**. Bỏ động từ hướng dẫn thừa ("Nhập email tại đây"). Ngoại lệ: ô đơn như ô tìm kiếm — được dùng placeholder nếu tương phản ≥ 4.5:1 và vẫn có nhãn cho screen reader.

### 7.4. Chọn đúng điều khiển
- **≤ ~10 lựa chọn → radio thay dropdown** (dropdown: nhiều thao tác chính xác, khó với người suy giảm vận động, dễ tưởng đã điền, lựa chọn bị giấu). Thiếu chỗ thì dropdown vẫn được.
- **Danh sách dài → autocomplete** (ví dụ quốc gia): hợp khi người dùng biết mình tìm gì. Danh sách lạ phải duyệt → tách thành nhiều trường (vd ngành → nghề). Giữ ~10 gợi ý trở xuống; **làm đậm phần khác nhau giữa các gợi ý** thay vì phần người dùng đã gõ.
- **Số nhỏ → stepper** thay dropdown: nút ≥ 48×48pt, **xếp ngang** (cách xa nhau hơn), dùng **+/−** (không dùng mũi tên/chevron, dễ lẫn với dropdown/accordion). Không hợp cho thay đổi số lớn.
- **Hai trạng thái bật/tắt (mặc định tắt)**:
  - **Checkbox**: có hiệu lực **sau khi bấm nút gửi**; nhãn mô tả điều xảy ra khi tick.
  - **Toggle**: có hiệu lực **ngay lập tức**; nhãn mô tả điều xảy ra khi bật.
- **Checkbox phát biểu khẳng định**: mẹo kiểm tra — thay dấu tick bằng "Có, …"; nếu câu thành phủ định kép/khó hiểu thì viết lại.

### 7.5. Form dài
- **Chia bước**: báo trước mất bao lâu và cần chuẩn bị gì; nhóm các câu liên quan thành ít bước (30 câu → 6 bước × 5 câu, không phải 30 bước); câu dễ trước, khó sau (thắng sớm); **hiển thị tiến độ** (càng gần đích càng có động lực); cho xem lại và sửa trước khi xác nhận; sau đó báo đã xong và điều gì xảy ra tiếp.
- Không chia bước được → **nhóm trường liên quan dưới tiêu đề**.

### 7.6. Viền và lỗi
- **Viền ô nhập ≥ 3:1** — lỗi UI phổ biến nhất. Áp dụng cho mọi phần tử không thuần trang trí: nút, toggle, stepper, checkbox, radio.
- **Thông báo lỗi**: nói chuyện gì xảy ra, vì sao, cách khắc phục. Không đổ lỗi người dùng; tích cực, giúp đỡ. Bỏ "vui lòng", "xin lỗi", "ối". Không nói như máy, không thuật ngữ kỹ thuật. Tiêu đề và nút phải tự giải thích (vd tiêu đề "Thanh toán không thành công" + nút "Cập nhật thông tin thanh toán" thay vì "Đã có lỗi" + "OK").
- **Kiểm tra khi bấm gửi, không kiểm tra ngay khi gõ** (báo lỗi sau một ký tự rất phiền).
  - Đầu form: **danh sách tóm tắt lỗi**, mỗi mục là link nhảy tới ô lỗi.
  - Thông báo lỗi **phía trên ô** (không bị autofill/bàn phím che).
  - Màu đỏ **kèm icon**.
  - Ngoại lệ nên kiểm tra khi gõ: độ mạnh mật khẩu, giới hạn ký tự, tên người dùng còn trống không.

---

## 8. Nút bấm

### 8.1. Ba mức nút
- **Primary**: chữ nhật bo góc, **nền đặc màu hành động**, chữ trắng — hành động quan trọng nhất.
- **Secondary**: **không nền, viền + chữ màu hành động**, bo góc. Tránh nền đặc màu khác (xung đột với primary, nhất là với người mù màu); tránh nền/viền xám nhạt (trông như disabled).
- **Tertiary**: trông như link — **chữ màu hành động có gạch chân** (để người mù màu biết bấm được).
- Có thể thêm cỡ nhỏ/lớn tuỳ độ phức tạp.

### 8.2. Lỗi thiết kế nút hay gặp (tóm lược 9 kiểu sai)
- Nền nút phụ tương phản < 3:1 với nền trang → không thấy hình dạng nút (sửa bằng viền tương phản cao).
- Nút phụ xám nhạt → tưởng disabled.
- Primary và secondary cùng kiểu, chỉ khác màu → phân cấp gãy, người mù màu không phân biệt được, và nếu chênh < 3:1 thì người thị lực kém cũng không phân biệt được.
- Chữ nút phụ < 4.5:1.
- Viền nút tertiary < 3:1.
- Tertiary chỉ khác chữ thường bằng màu (không gạch chân).
- Primary và secondary **khác hình dạng** (bo góc khác nhau) mà không khác chức năng → gây hiểu nhầm.
- Primary và secondary có độ nổi gần nhau → không rõ hành động nào chính.

### 8.3. Quy tắc nút
- Phân cấp rõ, **không chỉ dựa vào màu**.
- Hình dạng nút ≥ **3:1**; chữ nút ≥ **4.5:1**.
- Hai nút cùng kiểu thì chênh nhau ≥ 3:1.
- Vùng bấm ≥ **48×48pt** (khớp lưới 8pt, lớn hơn mức WCAG khuyến nghị 44×44); nút dùng thường xuyên thì làm to hơn.
- Khoảng cách giữa các nút ≥ **8pt** (sách thường dùng **16pt** cho an toàn).
- Phần tử nhỏ: **mở rộng vùng bấm ra ngoài phần nhìn thấy** — nhưng nếu không thể hiện vùng bấm lớn thì người dùng vẫn bấm cẩn thận như với vùng nhỏ.

### 8.4. Dùng đúng mức
- **Một primary cho hành động quan trọng nhất** mỗi màn hình. Không có hành động nổi bật duy nhất → dùng secondary/tertiary. Nhiều primary cạnh nhau = "cái gì cũng quan trọng thì không cái gì quan trọng" (vd danh sách "Theo dõi" mỗi người → secondary hoặc tertiary).
- **Secondary** cho hành động phụ hoặc **nhiều hành động ngang hàng** — hai lựa chọn ngang hàng thì cùng mức nổi để không tạo thiên vị.
- **Tertiary** cho hành động ít quan trọng nhất, khi có **nhiều hành động lặp lại**, hoặc **hành động phá huỷ** cần làm mờ đi.

### 8.5. Tránh nút disabled
- Vấn đề: không giải thích vì sao bấm không được (người dùng kẹt), tương phản thấp, không focus được bằng bàn phím.
- Thay thế:
  - **Để nút bật và kiểm tra khi gửi** → lỗi chỉ ngay chỗ thiếu.
  - **Bỏ hẳn hành động không khả dụng** và nói lý do (vd tài khoản riêng tư: chỉ hiện "Gửi yêu cầu theo dõi" kèm giải thích).
  - **Gắn icon khoá** lên nút thường (vẫn thấy, vẫn đủ tương phản; hợp với tính năng trả phí) + nói lý do và cách mở khoá.
  - Buộc phải dùng disabled: thêm **dòng giải thích cạnh nút** hoặc **tooltip**, và vẫn cho focus bằng bàn phím.

### 8.6. Căn và thứ tự nút
- **Căn trái, sắp từ quan trọng nhất → ít nhất, trái sang phải**: mắt bám mép trái khi đi xuống; nút căn phải dễ bị bỏ sót trên màn hình lớn và với kính lúp; nút được dùng nhiều nhất đặt đầu tiên giảm chi phí tương tác.
- **Mobile**: xếp chồng **trên → dưới theo thứ tự quan trọng**, **full-width** (dùng một tay, cả tay trái lẫn phải).
- **Dialog nhỏ**: hai trường phái (căn phải kiểu macOS thể hiện "tiến tới", căn trái kiểu Windows/web). Tác giả chọn **căn trái để nhất quán** với form; miễn phân cấp đúng thì ảnh hưởng không lớn.
- **Form nhiều bước**: đừng để "Quay lại" ở vị trí nổi bật bên trái và nút chính ở xa bên phải (dễ bấm nhầm mất dữ liệu, xa ô nhập, dễ bị bỏ sót). Giữ nút chính căn trái; đặt **"Quay lại" dạng tertiary ở góc trái trên** (vị trí quen như trình duyệt/breadcrumb, không phải cuộn xuống).
- Ngoại lệ: **form một ô** (tìm kiếm, đăng ký nhận tin) → nút nằm **bên phải, dính vào ô** để tiết kiệm chỗ và thể hiện liên kết.

### 8.7. Chữ trên nút
- **Động từ + danh từ** ("Lưu bài viết", "Xoá tin nhắn", "Sửa bài") — hiểu được khi đọc tách rời; nhiều người nhìn nút trước khi đọc nội dung; screen reader hay nhảy thẳng tới nút. Tránh "OK", "Có".

### 8.8. Cân bằng icon + chữ
- Cùng **độ dày nét** với chữ; cùng **kích thước** tương đương.
- Không khớp được → **giảm tương phản icon** (vd icon màu Medium, chữ màu Dark) để cân lại.

### 8.9. Thêm "ma sát" cho hành động phá huỷ (tăng dần theo mức mất dữ liệu)
- **Ma sát ban đầu**: làm hành động kém nổi (tertiary), đặt xa hơn, hoặc hé lộ dần. **Đừng tô đỏ** ở bước này (đỏ làm nó nổi hơn).
- **Nhẹ** (mất ít): hỏi xác nhận.
- **Vừa**: xác nhận + nút đỏ và/hoặc icon cảnh báo, nói rõ không khôi phục được.
- **Nặng** (mất nhiều, vd xoá tài khoản): thêm checkbox "Tôi xác nhận…" phải tick mới thực hiện được.
- **Tốt hơn cả: cho phép hoàn tác (undo)** — loại bỏ rủi ro thay vì chặn.

---

## 9. Tóm tắt cốt lõi

1. Giữ giao diện đơn giản và quen thuộc để giảm rủi ro khả dụng.
2. Mỗi chi tiết có lý do logic, không chỉ vì "đẹp".
3. Giảm chi phí tương tác và tải nhận thức.
4. Design system: style định sẵn + component tái sử dụng + hướng dẫn sử dụng.
5. Accessibility tốt = usability tốt cho mọi người.

---

## 10. Đối chiếu với `FRONTEND_STANDARDS.md`

Đánh giá dựa trên bản `FRONTEND_STANDARDS.md` hiện có trong `knowledge-base/` (chưa đối chiếu với code engine). Đây là **gợi ý**, chưa sửa gì trong chuẩn hay code.

### 10.1. Đã khớp
- 8pt grid; khoảng cách trong < khoảng cách ngoài (chuẩn §2.3 ≈ sách §4.6). Thang của sách (8/16/24/32/48/80) là tập con của thang chuẩn.
- Thang chữ: tỷ lệ nhỏ cho dashboard/e-commerce, lớn cho landing (chuẩn §2.2 ≈ sách §5.4).
- Line-height body 1.5–1.65; tiêu đề 1.1–1.2; siết letter-spacing cho tiêu đề lớn.
- Độ dài dòng 45–72ch (chặt hơn khoảng 40–80 của sách — vẫn nằm trong).
- Tránh đen tuyền/trắng tinh; pha chút sắc độ thương hiệu vào nền và chữ (chuẩn §2.1 ≈ sách §3.7, §3.9).
- Căn trái chữ dài, chỉ căn giữa chữ ngắn (Anti-slop #3 ≈ sách §4.9, §5.6).
- Một Primary CTA nổi nhất (Trụ cột 5, Anti-slop #7 ≈ sách §8.4).
- Chữ trên ảnh cần scrim gradient (Anti-slop #8 ≈ sách §5.8).
- Không lạm dụng icon trang trí (Anti-slop #4 ≈ sách §2, §1.1).
- Cấm copy sáo rỗng (Anti-slop #6) — sách bổ sung nhiều quy tắc cụ thể hơn (xem 10.2).
- Lề mobile ≥ 16px (Bài test 3 ≈ sách §4.8: margin mobile 16pt).
- Dùng cả WCAG và APCA.

### 10.2. Chuẩn hiện tại còn thiếu (sách có, chuẩn chưa có)
- **Form** — gần như chưa có quy chuẩn: nhãn trên ô, không dùng placeholder thay nhãn, hint phía trên ô, một cột, đánh dấu bắt buộc/tuỳ chọn (`*` không tô đỏ), độ rộng ô theo dữ liệu, radio thay dropdown khi ≤ 10 mục, autocomplete cho danh sách dài, stepper cho số nhỏ, checkbox vs toggle, kiểm tra khi gửi + tóm tắt lỗi ở đầu form + lỗi phía trên ô + icon.
- **Ba mức nút** (primary/secondary/tertiary) với định nghĩa hình thức rõ; tertiary có gạch chân.
- **Tránh nút disabled** và các phương án thay thế.
- **Ma sát cho hành động phá huỷ** + ưu tiên undo.
- **Thứ tự & căn nút**: căn trái, quan trọng trước; mobile xếp chồng full-width; "Quay lại" ở góc trên trong form nhiều bước.
- **Màu thương hiệu chỉ dành cho phần tử tương tác**; tiêu đề không tô màu hành động; nhiều màu thương hiệu thì chỉ 1 màu cho tương tác.
- **Màu thương hiệu mang nghĩa hệ thống** (đỏ/xanh lá/amber) hoặc **quá sáng/quá tối** → quy tắc xử lý (§3.9).
- **Màu trạng thái** đỏ/amber/xanh lá kèm icon; ngưỡng 4.5:1 (chữ) / 3:1 (icon).
- **Không dựa vào màu đơn thuần**: link trong đoạn văn phải gạch chân; lỗi phải có icon.
- **Viền thành phần không trang trí ≥ 3:1** (ô nhập, checkbox, radio, toggle, viền nút secondary).
- **Chỉ dùng regular + bold**.
- **Lưới 12 cột → 4 cột mobile**, gutter 32 → 16.
- **Căn baseline** cho chữ khác cỡ cùng hàng.
- **Copywriting cụ thể**: sentence case, front-load, link mô tả đích (cấm "Xem thêm"/"Bấm vào đây"), nút động từ + danh từ, từ vựng nhất quán, chữ số có dấu phân cách hàng nghìn, hạn chế viết tắt, in hoa chỉ cho nhãn ngắn (đậm + nhỏ + giãn chữ), tiêu đề mô tả, không "của tôi" trên nhãn form, câu < 20 từ.
- **Squint test** và **thiết kế mobile trước**.
- **Giao diện không vỡ**: chữ dài/số lớn phải xuống dòng hoặc co lại, không cắt mất phần phân biệt.
- **Độ sâu bằng màu** (nền sáng hơn trông nổi hơn) và **3 mức bóng**, màu bóng lấy từ biến thể tối nhất.

### 10.3. Chỗ lệch / mâu thuẫn cần cân nhắc

| # | `FRONTEND_STANDARDS.md` | Sách | Ghi chú |
|---|---|---|---|
| 1 | Bài test 1: vùng chạm mobile **≥ 40px** (khuyến nghị 44) | **≥ 48×48pt**, cách nhau ≥ 8pt (thường 16) | Chuẩn hiện tại thấp hơn mức an toàn của sách; 40px còn dưới mức 44 của WCAG khuyến nghị. |
| 2 | Trụ cột 5: base font **16px** cho giới trẻ/công nghệ, 18px nếu đọc nhiều | Body text **dài** ≥ **18px** | Hợp lý nếu 16px chỉ dùng cho trang ít chữ; trang có đoạn văn dài nên dùng 18px bất kể persona. |
| 3 | `--text-muted` L=58% (light) dùng cho chú thích nhỏ, **placeholder** | Tránh chữ xám nhạt; không dùng placeholder thay nhãn; placeholder (nếu có) ≥ 4.5:1 | Đã đo bằng `engines/color.py` (L=58%, C=0.015 trên nền L=98.5%): **WCAG 4.1:1** (trượt 4.5:1 cho chữ nhỏ), **APCA Lc 66.6** (dưới ngưỡng 75 cho body, trên ngưỡng 60). `engines/palette.py` hiện chỉ yêu cầu muted đạt 3:1 / Lc 45 — đủ cho chữ lớn, không đủ cho chú thích nhỏ hay placeholder. |
| 4 | Accent 10% dùng cho CTA, trạng thái active, **"con số/biểu tượng quan trọng nhất"** | Màu thương hiệu **chỉ** cho phần tử tương tác | Con số/icon tô màu hành động có thể bị tưởng bấm được. |
| 5 | Anti-slop #7: nút phụ "nền trong suốt có **viền mảnh**" hoặc link có mũi tên | Secondary: viền + chữ màu hành động, viền ≥ 3:1; tertiary phải gạch chân | "Viền mảnh" dễ thành viền nhạt < 3:1 hoặc trông như disabled; link-mũi-tên thiếu gạch chân thì chỉ dựa vào màu. |
| 6 | Warm Organic: nút **dạng viên thuốc (9999px)** | Badge nên bo tròn hơn nút để phân biệt; primary/secondary không nên khác hình dạng | Nếu nút đã là viên thuốc thì badge cần cách phân biệt khác (màu trạng thái, không dùng màu hành động, nền nhạt). |
| 7 | Anti-slop #5: ưu tiên viền 1px + chênh nền; bóng rất nhẹ | 3 mức bóng; bóng để tạo phân cấp; viền trang trí không cần tương phản, nhưng viền **thành phần** phải ≥ 3:1 | Không mâu thuẫn trực tiếp, nhưng cần phân biệt "viền trang trí" (`--border-subtle` L=90%) với "viền ô nhập/nút" — chuẩn hiện chỉ có một token viền. Sách có 2 vai trò riêng (Medium ≥ 3:1 và Light trang trí). |
| 8 | Trụ cột 1 / §2.2: tiêu đề có thể dùng nhiều độ đậm tuỳ phong cách | Chỉ regular + bold (semibold nếu bold quá nặng) | Chưa có quy định độ đậm trong chuẩn. |
| 9 | Dark mode `--text-primary` L=96% | Tiêu đề dark mode dùng trắng | Tương đương thực tế; chỉ ghi nhận. |
| 10 | Sticky header dùng `backdrop-filter: blur()` | Glassmorphism khó đạt tương phản | Vẫn dùng được nếu nền header đủ đặc để chữ đạt chuẩn. |

### 10.4. Gợi ý quy tắc có thể kiểm tự động ở B11 (chưa triển khai)
Những quy tắc từ sách đo được bằng DOM/`getComputedStyle`, có thể bổ sung vào QA nếu muốn:
- Vùng bấm < 48×48 và khoảng cách giữa các nút < 8px.
- Viền của `input`, `select`, `textarea`, checkbox/radio có tương phản < 3:1 với nền.
- `input` có `placeholder` nhưng không có `label` hiển thị.
- Link trong đoạn văn (`p a`) không có `text-decoration: underline`.
- Nhiều hơn 1 nút primary trong cùng viewport.
- Nút có `disabled`.
- Chữ link/nút là "Xem thêm", "Tìm hiểu thêm", "Bấm vào đây", "OK", "Click here", "Learn more".
- Body text dài (đoạn > N ký tự) có `font-size` < 18px, `line-height` < 1.5, `text-align: center|justify`.
- Dùng quá 2 `font-weight` cho chữ thường + tiêu đề.
- Thông báo lỗi chỉ dựa vào màu (không có icon/role kèm theo).
- Dấu `*` bắt buộc tô màu đỏ.
- Số ≥ 1000 không có dấu phân cách hàng nghìn.
