"""Sample copy per industry, inside a domain.

The domain (ecommerce, booking…) says which page parts a site needs; it does not say what the
business sells. Sample copy written for one shop (furniture: "lắp đặt tại nhà", "2 năm bảo hành",
"gửi kích thước phòng") read as nonsense on a bakery or a kids' clothes shop. Here the prompt picks
an industry pack (keywords, no LLM needed); a pack overrides the domain's neutral samples: facts,
list, categories, FAQ, story, quotes, hero and closing lines, and the B4 form's examples.

No pack matches → the domain's neutral samples, which mention nothing industry-specific.
`stray()` lists words of one industry found in copy for another (copywriter check, tests).
"""

from __future__ import annotations

import re

from chromaswarm.state_machine.pipeline_state import Domain

_SHOP = (Domain.ECOMMERCE, Domain.OTHER)


def _p(*words: str) -> re.Pattern:
    return re.compile(r"(?<!\w)(?:" + "|".join(words) + r")(?!\w)", re.I)


# ------------------------------------------------------------------ packs
# Keys a pack may set (all optional): nav, facts, items [(name, note, price, tag)], categories, faqs,
# story, quotes, headline, subhead, closing, features, tabs, form {offer, different, items, numbers,
# reviews, faqs, contact} (B4 placeholders).

BAKERY = dict(
    label="tiệm bánh",
    order=dict(item_label="Bánh", when="Ngày nhận bánh", time=True),
    nav=["Menu bánh", "Đặt trước", "Hỏi đáp", "Liên hệ"],
    facts=[("Mỗi sáng", "mẻ bánh mới ra lò"), ("Đặt trước", "bánh kem từ 1 ngày"),
           ("Nội thành", "giao trong ngày"), ("2–3 ngày", "dùng ngon nhất, không chất bảo quản")],
    items=[("Sourdough nguyên cám", "Lên men chậm 24 giờ", "85.000₫", "Bán chạy"),
           ("Bánh mì hoa cúc", "Bơ lạt, nướng mỗi sáng", "120.000₫", ""),
           ("Croissant bơ", "Nhiều lớp, vỏ giòn", "35.000₫", ""),
           ("Bánh kem bắp", "Đặt trước 1 ngày", "280.000₫", "")],
    categories=["Bánh mì", "Bánh ngọt", "Bánh kem", "Hộp quà"],
    faqs=[("Đặt bánh kem trước bao lâu?", "Trước ít nhất 1 ngày; mẫu vẽ riêng nên đặt trước 2–3 ngày."),
          ("Tiệm có giao tận nơi không?", "Có, giao nội thành trong ngày; phí báo trước khi giao."),
          ("Bánh để được bao lâu?", "Bánh mì ngon nhất trong 2–3 ngày; bánh kem giữ lạnh, dùng trong ngày."),
          ("Có viết chữ lên bánh kem không?", "Có, ghi lời chúc khi đặt, tiệm viết miễn phí."),
          ("Thanh toán thế nào?", "Tiền mặt, chuyển khoản hoặc ví điện tử khi nhận bánh.")],
    story=[("Nướng mỗi sáng", "Bánh mì ra lò từ sớm, hết mẻ là hết, không bán bánh để qua đêm."),
           ("Bột lên men chậm", "Sourdough ủ 24 giờ cho vỏ giòn, ruột dai và dễ tiêu hơn."),
           ("Bánh kem làm theo đơn", "Mỗi chiếc làm riêng theo cỡ, vị và lời chúc bạn ghi khi đặt."),
           ("Giao trong ngày", "Đơn trước 15h được giao trong buổi chiều ở nội thành."),
           ("Ghi rõ thành phần", "Mỗi loại ghi bột, bơ, đường và chất gây dị ứng nếu có."),
           ("Hộp quà cho dịp lễ", "Hộp bánh gói sẵn cho Trung thu, Tết và sinh nhật.")],
    quotes=["Sourdough vỏ giòn, ruột mềm, để hai ngày vẫn ngon.",
            "Đặt bánh kem sinh nhật, giao đúng giờ, chữ viết đẹp."],
    headline="Bánh nướng mỗi sáng, đặt trước để giữ phần",
    subhead="chọn bánh, chọn giờ nhận, tiệm xác nhận lại qua tin nhắn.",
    closing="Bánh kem cần đặt trước một ngày để tiệm làm kịp đúng ý bạn.",
    tabs=[("Mô tả", "Hương vị, cỡ bánh và cách dùng ngon nhất."), ("Thành phần", "Bột, bơ, đường và chất gây dị ứng."),
          ("Nhận bánh", "Giờ nhận tại tiệm, phí và khung giờ giao.")],
    form=dict(offer="Bán gì, ở đâu — bánh mì sourdough và bánh ngọt nướng mỗi sáng ở Hải Châu, Đà Nẵng",
              different="Lên men 24 giờ | sourdough không men công nghiệp\nKhông chất bảo quản | bánh ra lò trong ngày",
              items="Sourdough nguyên cám | 85.000₫ | lên men 24 giờ\nBánh kem bắp | 280.000₫ | đặt trước 1 ngày",
              numbers="300 | ổ bánh mỗi sáng\n4,9/5 | 210 đánh giá trên Google Maps",
              reviews="Sourdough vỏ giòn, để hai ngày vẫn ngon | Chị Thảo, Sơn Trà",
              faqs="Đặt bánh kem trước bao lâu? | Ít nhất 1 ngày",
              contact="45 Lê Đình Dương, Đà Nẵng · 6h30–20h · Zalo 0905 111 222"),
)

FOOD = dict(
    label="đồ ăn, thực phẩm",
    order=dict(item_label="Món"),
    nav=["Sản phẩm", "Cách dùng", "Hỏi đáp", "Liên hệ"],
    facts=[("Hạn dùng", "ghi trên từng gói"), ("Hút chân không", "giữ hương vị khi giao xa"),
           ("2–4 ngày", "giao toàn quốc"), ("Mua sỉ", "giá riêng từ 10 phần")],
    items=[("Gói dùng thử", "Phần nhỏ để nếm trước", "89.000₫", "Nên thử"),
           ("Gói gia đình", "Đủ dùng cho 4 người", "249.000₫", ""),
           ("Hộp quà", "Đóng hộp, kèm thiệp", "390.000₫", ""),
           ("Combo hai món", "Giá tốt hơn mua lẻ", "319.000₫", "")],
    categories=["Bán chạy", "Gói nhỏ", "Hộp quà", "Combo"],
    faqs=[("Bảo quản thế nào?", "Nơi khô mát; sau khi mở gói nên dùng trong thời gian ghi trên bao bì."),
          ("Giao tỉnh có bị hỏng không?", "Hàng được hút chân không và đóng thùng, giao 2–4 ngày."),
          ("Có hóa đơn và nguồn gốc không?", "Có, thông tin nơi sản xuất in trên từng gói."),
          ("Mua làm quà được không?", "Được, có hộp quà và thiệp viết tay theo yêu cầu."),
          ("Thanh toán thế nào?", "Chuyển khoản hoặc thanh toán khi nhận hàng.")],
    story=[("Biết rõ nơi làm ra", "Mỗi sản phẩm ghi nơi sản xuất và ngày đóng gói."),
           ("Đóng gói để đi xa", "Hút chân không, chèn kỹ, giao tỉnh vẫn giữ được hương vị."),
           ("Ít mà ngon", "Danh sách gọn, chỉ giữ những món khách quay lại mua."),
           ("Có gói dùng thử", "Nếm phần nhỏ trước khi mua gói lớn."),
           ("Quà biếu gói sẵn", "Hộp quà kèm thiệp cho dịp lễ, Tết."),
           ("Hỏi trước khi mua", "Nhắn tin để được tư vấn khẩu vị và số lượng.")],
    quotes=["Đóng gói kỹ, giao ra tỉnh vẫn thơm như mới.", "Mua gói dùng thử trước, giờ đặt gói gia đình mỗi tháng."],
    headline="Món ngon đóng gói cẩn thận, giao tận nhà",
    subhead="ghi rõ nơi làm, hạn dùng và cách bảo quản ở từng sản phẩm.",
    closing="Chưa biết chọn món nào? Bắt đầu bằng gói dùng thử.",
    tabs=[("Mô tả", "Hương vị và cách dùng."), ("Thành phần", "Nguyên liệu, nơi sản xuất, hạn dùng."),
          ("Giao hàng", "Thời gian giao và cách đóng gói.")],
    form=dict(offer="Bán gì, cho ai — cà phê rang mộc từ Cầu Đất, giao cho người pha tại nhà",
              different="Rang theo mẻ nhỏ | rang trong tuần, ghi ngày rang trên túi\nHút chân không | giữ mùi khi giao xa",
              items="Cà phê rang mộc 250g | 120.000₫ | vị đậm, hậu ngọt\nTrà ô long 100g | 150.000₫ | Bảo Lộc",
              numbers="2.000 | túi đã bán năm 2025\n4,8/5 | 150 đánh giá trên Shopee",
              reviews="Cà phê thơm, giao nhanh, gói kỹ | Anh Minh, Hà Nội",
              faqs="Bảo quản thế nào? | Nơi khô mát, dùng trong 30 ngày sau khi mở",
              contact="Shopee: caphemoc · Zalo 0909 123 456"),
)

FASHION = dict(
    label="thời trang",
    nav=["Mới về", "Bán chạy", "Bảng size", "Liên hệ"],
    facts=[("7 ngày", "đổi size miễn phí"), ("Kiểm hàng", "trước khi trả tiền"),
           ("2–4 ngày", "giao toàn quốc"), ("Bảng size", "số đo cm ở từng mẫu")],
    items=[("Áo thun cotton dày", "Form rộng, không xù", "249.000₫", "Mới"),
           ("Quần ống rộng", "Vải đứng form, có túi sâu", "389.000₫", ""),
           ("Váy midi", "Dài qua gối, có lót", "459.000₫", ""),
           ("Túi canvas", "Đựng vừa laptop 14 inch", "199.000₫", "")],
    categories=["Áo", "Quần", "Váy", "Phụ kiện"],
    faqs=[("Chọn size thế nào?", "Mỗi mẫu có bảng số đo cm; nhắn chiều cao, cân nặng để được gợi ý."),
          ("Đổi size được không?", "Đổi miễn phí trong 7 ngày nếu chưa giặt và còn tem."),
          ("Vải có bị co sau khi giặt không?", "Vải đã xử lý co; giặt nước lạnh, phơi trong bóng râm."),
          ("Bao lâu thì nhận được hàng?", "Nội thành 1–2 ngày, tỉnh khác 2–4 ngày."),
          ("Thanh toán thế nào?", "Thanh toán khi nhận hàng, chuyển khoản hoặc ví điện tử.")],
    story=[("Ảnh chụp hàng thật", "Mỗi mẫu có ảnh mặc thật dưới ánh sáng tự nhiên, không chỉnh màu."),
           ("Số đo rõ ràng", "Bảng size ghi số đo cm của từng mẫu, không chỉ S, M, L."),
           ("Chất vải dày dặn", "Vải được chọn để mặc nhiều lần vẫn giữ form."),
           ("Đổi size dễ dàng", "Đổi miễn phí trong 7 ngày nếu chưa vừa."),
           ("Kiểm hàng khi nhận", "Mở gói xem hàng trước khi trả tiền."),
           ("Mẫu mới mỗi tuần", "Hàng mới lên vào thứ sáu, số lượng ít.")],
    quotes=["Áo đúng màu như ảnh, vải dày, mặc rất mát.", "Hỏi size được tư vấn kỹ, mặc vừa ngay lần đầu."],
    headline="Đồ mặc hằng ngày, chọn đúng size ngay lần đầu",
    subhead="mỗi mẫu có ảnh mặc thật, số đo cm và chất vải ghi rõ.",
    closing="Phân vân giữa hai size? Nhắn chiều cao và cân nặng, cửa hàng chọn giúp bạn.",
    tabs=[("Mô tả", "Kiểu dáng và cách phối."), ("Chất vải", "Thành phần vải và cách giặt."),
          ("Đổi size", "Thời gian đổi, điều kiện và phí giao.")],
    form=dict(offer="Bán gì, cho ai — quần áo basic cho sinh viên, form rộng, giá dưới 400k",
              different="Vải cotton 250gsm | dày, không xù sau nhiều lần giặt\nĐổi size 7 ngày | miễn phí",
              items="Áo thun basic | 199.000₫ | 6 màu\nQuần ống rộng | 359.000₫ | kaki",
              numbers="5.000 | đơn đã giao năm 2025\n4,9/5 | 1.200 đánh giá trên Shopee",
              reviews="Áo dày, đúng màu, mặc rất mát | Linh, Thủ Đức",
              faqs="Chọn size thế nào? | Nhắn chiều cao, cân nặng để được gợi ý",
              contact="Instagram @be.mon · Zalo 0909 123 456"),
)

BEAUTY = dict(
    label="mỹ phẩm",
    nav=["Sản phẩm", "Theo loại da", "Hỏi đáp", "Liên hệ"],
    facts=[("Hạn dùng", "ghi rõ trên từng sản phẩm"), ("Mẫu thử", "trước khi mua cỡ lớn"),
           ("Nguồn gốc", "giấy tờ nhập hàng xem được khi hỏi"), ("2–4 ngày", "giao toàn quốc")],
    items=[("Sữa rửa mặt dịu nhẹ", "Cho da nhạy cảm", "189.000₫", "Bán chạy"),
           ("Serum phục hồi", "Dùng buổi tối", "329.000₫", ""),
           ("Kem chống nắng", "Không bết, không vệt trắng", "279.000₫", ""),
           ("Son dưỡng", "Không màu, dùng hằng ngày", "99.000₫", "")],
    categories=["Làm sạch", "Dưỡng da", "Chống nắng", "Trang điểm"],
    faqs=[("Da nhạy cảm dùng được không?", "Nên thử mẫu nhỏ ở vùng cằm 2–3 ngày trước khi dùng cả mặt."),
          ("Hàng có chính hãng không?", "Có, cửa hàng gửi giấy tờ nhập hàng khi bạn hỏi."),
          ("Hạn dùng còn bao lâu?", "Hạn dùng ghi ở từng sản phẩm; hàng gửi đi còn ít nhất 12 tháng."),
          ("Đổi được không nếu không hợp?", "Đổi trong 7 ngày với sản phẩm chưa mở nắp."),
          ("Thanh toán thế nào?", "Chuyển khoản hoặc thanh toán khi nhận hàng.")],
    story=[("Chọn theo loại da", "Mỗi sản phẩm ghi rõ hợp da dầu, da khô hay da nhạy cảm."),
           ("Thành phần ghi đủ", "Bảng thành phần đầy đủ, chụp từ bao bì thật."),
           ("Thử trước, mua sau", "Có mẫu nhỏ cho những món dễ kén da."),
           ("Hạn dùng còn dài", "Hàng gửi đi còn ít nhất 12 tháng sử dụng."),
           ("Tư vấn theo da", "Gửi ảnh da và thói quen chăm sóc để được gợi ý quy trình."),
           ("Đổi nếu chưa mở", "Đổi trong 7 ngày với sản phẩm còn nguyên seal.")],
    quotes=["Da nhạy cảm dùng không bị kích ứng, tư vấn rất kỹ.", "Hàng có hạn dùng dài, gói cẩn thận."],
    headline="Chăm da đúng loại, thành phần ghi rõ",
    subhead="mỗi sản phẩm ghi loại da phù hợp, thành phần và hạn dùng.",
    closing="Chưa biết da mình hợp gì? Gửi vài dòng về da, cửa hàng gợi ý quy trình giúp bạn.",
    tabs=[("Mô tả", "Công dụng và loại da phù hợp."), ("Thành phần", "Bảng thành phần đầy đủ."),
          ("Cách dùng", "Thứ tự dùng và lưu ý.")],
    form=dict(offer="Bán gì, cho ai — mỹ phẩm thuần chay cho da nhạy cảm",
              different="Thuần chay | không thử nghiệm trên động vật\nCó mẫu thử | 5ml cho mọi sản phẩm",
              items="Sữa rửa mặt dịu nhẹ | 189.000₫ | da nhạy cảm\nKem chống nắng | 279.000₫ | SPF 50",
              numbers="3.000 | khách đã mua năm 2025\n4,8/5 | 900 đánh giá trên Shopee",
              reviews="Da mình rất kén mà dùng không bị kích ứng | Chị Vy, Quận 3",
              faqs="Da nhạy cảm dùng được không? | Nên thử mẫu nhỏ trước",
              contact="Shopee: mypham.lanh · Zalo 0909 123 456"),
)

FURNITURE = dict(
    label="nội thất",
    nav=["Bộ sưu tập", "Câu chuyện", "Hỏi đáp", "Liên hệ"],
    facts=[("48h", "giao nội thành"), ("30 ngày", "đổi trả miễn phí"), ("2 năm", "bảo hành"),
           ("Lắp đặt", "tại nhà, không tính phí")],
    items=[("Bàn gỗ sồi 120", "Mặt bàn liền khối", "6.900.000₫", "Mới"),
           ("Ghế đẩu gỗ", "Cao 45cm, xếp chồng được", "890.000₫", ""),
           ("Kệ sách treo tường", "3 tầng, chịu 30kg", "1.450.000₫", ""),
           ("Tủ đầu giường", "2 ngăn kéo ray giảm chấn", "1.690.000₫", "")],
    categories=["Phòng khách", "Phòng ngủ", "Phòng làm việc", "Phụ kiện"],
    faqs=[("Bao lâu thì nhận được hàng?", "Nội thành 48 giờ, tỉnh khác 3–5 ngày làm việc."),
          ("Tôi có được đổi trả không?", "Đổi trả miễn phí trong 30 ngày nếu sản phẩm còn nguyên vẹn."),
          ("Có lắp đặt tại nhà không?", "Có, đội lắp đặt đi kèm khi giao hàng, không tính phí."),
          ("Thanh toán bằng cách nào?", "Chuyển khoản, thẻ hoặc thanh toán khi nhận hàng."),
          ("Bảo hành ra sao?", "Bảo hành 2 năm cho lỗi kỹ thuật, bảo trì trọn đời có tính phí.")],
    story=[("Chọn vật liệu trước, thiết kế sau", "Mỗi lựa chọn bắt đầu từ vật liệu bền và an toàn, rồi mới đến hình dáng."),
           ("Làm ít mẫu, làm thật kỹ", "Danh mục gọn để mỗi sản phẩm được kiểm tra kỹ trước khi đến tay bạn."),
           ("Ở lại sau khi bán", "Bảo hành, bảo trì và tư vấn sau mua là một phần của sản phẩm."),
           ("Giao tận nơi, lắp đặt tận tay", "Đội giao hàng của cửa hàng lắp đặt và hướng dẫn sử dụng ngay tại nhà."),
           ("Giá rõ ràng từ đầu", "Giá niêm yết đã gồm thuế và phí giao nội thành, không phát sinh khi thanh toán."),
           ("Đổi ý vẫn kịp", "Trong 30 ngày, sản phẩm còn nguyên vẹn được đổi hoặc hoàn tiền.")],
    quotes=["Hàng giao đúng hẹn, lắp đặt gọn gàng, dùng mấy tháng vẫn như mới.",
            "Tư vấn kỹ, không ép mua, giá đúng như trên web."],
    headline="Từng món được kiểm tra trước khi giao",
    subhead="chất liệu, kích thước, giá và thời gian giao ghi rõ ở từng sản phẩm.",
    closing="Chưa biết chọn cỡ nào? Gửi kích thước phòng, cửa hàng gợi ý giúp bạn.",
    tabs=[("Mô tả", "Thông tin tổng quan về sản phẩm và cách sử dụng."), ("Chất liệu", "Thành phần, nguồn gốc và cách bảo quản."),
          ("Giao hàng", "Thời gian giao, phí vận chuyển và chính sách đổi trả.")],
    form=dict(offer="Bán gì, cho ai — đồ nội thất gỗ sồi làm thủ công tại Đà Lạt, cho căn hộ nhỏ",
              different="Gỗ sồi nguyên khối | không dùng ván ép, kể cả mặt sau ngăn kéo\nBảo hành 5 năm | sửa tận nhà",
              items="Bàn gỗ sồi Mộc 120 | 6.900.000₫ | gỗ sồi Nga, dầu lau thực vật\nGhế đẩu Mộc | 890.000₫ | cao 45cm",
              numbers="1.200 | đơn đã giao năm 2025\n4,8/5 | 320 đánh giá trên Shopee",
              reviews="Bàn chắc, giao đúng hẹn, thợ lắp rất cẩn thận | Chị Hạnh, Thủ Đức",
              faqs="Có giao tỉnh không? | Có, phí theo kích thước, báo trước khi giao",
              contact="12 Lê Lợi, Đà Lạt · 9h–20h · 0909 123 456"),
)

# Booking: places people come to
_SERVICE_BASE = dict(
    nav=["Dịch vụ", "Bảng giá", "Đặt lịch", "Liên hệ"],
    facts=[("9:00–21:00", "mỗi ngày"), ("15 phút", "xác nhận lịch"), ("Phòng riêng", "cho từng khách"),
           ("Miễn phí", "đổi lịch trước 2 giờ")],
    story=[("Đặt lịch trong 30 giây", "Chọn dịch vụ, chọn giờ trống và xác nhận, không cần gọi điện."),
           ("Nhắc lịch tự động", "Tin nhắn nhắc trước một ngày và trước hai giờ để không lỡ hẹn."),
           ("Kỹ thuật viên có chứng chỉ", "Mỗi người phụ trách đều qua đào tạo và có chứng chỉ hành nghề."),
           ("Dụng cụ vô trùng", "Dụng cụ được hấp sấy sau mỗi lượt khách."),
           ("Bảng giá công khai", "Giá từng dịch vụ hiển thị rõ trước khi đặt."),
           ("Đổi lịch linh hoạt", "Đổi miễn phí trước hai giờ ngay trong tin nhắn xác nhận.")],
    features=[("Chọn kỹ thuật viên", "Xem lịch trống của từng người và chọn người quen."),
              ("Giữ chỗ trước", "Giữ giờ đẹp bằng chuyển khoản hoặc ví điện tử."),
              ("Thẻ thành viên", "Tích điểm sau mỗi lần đến, đổi lấy buổi miễn phí."),
              ("Thẻ quà tặng", "Mua thẻ quà theo dịch vụ hoặc theo giá trị."),
              ("Đánh giá sau buổi", "Góp ý trực tiếp cho từng kỹ thuật viên."),
              ("Nhắc lịch định kỳ", "Lời nhắc khi đến hạn làm lại.")],
    quotes=["Đặt lịch nhanh, đến nơi không phải chờ.", "Nhân viên nhẹ nhàng, chỗ ngồi sạch, giá rõ ràng."],
    headline="Chọn giờ trống, đến là được phục vụ ngay",
    subhead="xem giờ trống của từng kỹ thuật viên và đặt ngay, không cần gọi điện.",
    closing="Cuối tuần thường kín lịch, đặt trước để giữ giờ bạn muốn.",
)
SPA = dict(_SERVICE_BASE, label="spa, massage",
           items=[("Gội dưỡng thảo mộc", "45 phút", "180.000₫", ""), ("Massage cổ vai gáy", "60 phút", "320.000₫", "Được chọn nhiều"),
                  ("Chăm sóc da mặt", "75 phút", "450.000₫", ""), ("Gói 5 buổi", "Dùng trong 3 tháng", "1.400.000₫", "")],
           categories=["Gội đầu", "Massage", "Chăm sóc da", "Gói liệu trình"],
           faqs=[("Tôi có cần đặt trước không?", "Nên đặt trước để giữ khung giờ, nhận khách vãng lai khi còn chỗ."),
                 ("Đổi lịch thế nào?", "Đổi miễn phí trước 2 giờ qua link trong tin nhắn xác nhận."),
                 ("Có phòng riêng không?", "Có phòng riêng cho massage và chăm sóc da."),
                 ("Thanh toán ra sao?", "Tiền mặt, thẻ hoặc chuyển khoản tại quầy."),
                 ("Có thẻ quà tặng không?", "Có thẻ quà theo giá trị hoặc theo dịch vụ.")],
           form=dict(offer="Dịch vụ gì, ở đâu — tiệm gội dưỡng sinh ở quận 3, mở 9h–21h",
                     different="Thảo mộc tự nấu | bồ kết, hương nhu nấu mỗi sáng\nPhòng riêng | cho massage",
                     items="Gội dưỡng thảo mộc | 180.000₫ | 45 phút\nMassage cổ vai gáy | 320.000₫ | 60 phút",
                     numbers="8.000 | lượt khách năm 2025\n4,9/5 | 600 đánh giá trên Google Maps",
                     reviews="Gội rất thư giãn, nhân viên nhẹ tay | Chị Lan, Quận 3",
                     faqs="Có cần đặt trước không? | Nên đặt trước cuối tuần",
                     contact="22 Trần Quốc Thảo, Q3 · 9h–21h · 0909 123 456"))
NAIL = dict(_SERVICE_BASE, label="tiệm nail",
            facts=[("9:00–21:00", "mỗi ngày"), ("15 phút", "xác nhận lịch"), ("Dụng cụ", "hấp sấy sau mỗi khách"),
                   ("Miễn phí", "đổi lịch trước 2 giờ")],
            items=[("Sơn gel tay", "45 phút, 200+ màu", "150.000₫", ""), ("Đắp móng bột", "90 phút", "350.000₫", "Được chọn nhiều"),
                   ("Vẽ móng theo mẫu", "Từ 20.000₫ mỗi ngón", "Từ 200.000₫", ""), ("Chăm sóc da tay", "30 phút", "120.000₫", "")],
            categories=["Sơn gel", "Đắp móng", "Vẽ móng", "Chăm sóc"],
            faqs=[("Sơn gel giữ được bao lâu?", "Thường 3–4 tuần tùy móng và công việc."),
                  ("Có mang mẫu tới được không?", "Được, gửi ảnh mẫu khi đặt lịch để thợ chuẩn bị màu."),
                  ("Dụng cụ có vệ sinh không?", "Dụng cụ kim loại hấp sấy, dũa và bông dùng một lần."),
                  ("Đổi lịch thế nào?", "Đổi miễn phí trước 2 giờ qua tin nhắn xác nhận."),
                  ("Thanh toán ra sao?", "Tiền mặt hoặc chuyển khoản tại tiệm.")],
            story=[("Đặt lịch trong 30 giây", "Chọn dịch vụ, chọn giờ trống và gửi ảnh mẫu nếu có."),
                   ("Bảng màu thật", "Hơn 200 màu gel, xem bảng màu thật tại tiệm."),
                   ("Dụng cụ vô trùng", "Dụng cụ kim loại được hấp sấy sau mỗi khách."),
                   ("Thợ chuyên vẽ", "Vẽ theo mẫu bạn gửi, báo giá trước khi làm."),
                   ("Bảng giá công khai", "Giá từng dịch vụ ghi rõ trước khi đặt."),
                   ("Bảo hành móng", "Bong trong 3 ngày được làm lại miễn phí.")],
            quotes=["Làm móng tỉ mỉ, màu y như mẫu mình gửi.", "Đặt lịch xong tới là làm luôn, không phải chờ."],
            headline="Móng đẹp đúng mẫu, đặt giờ trước khỏi chờ",
            subhead="chọn dịch vụ, gửi ảnh mẫu và giờ bạn muốn, tiệm xác nhận qua tin nhắn.",
            closing="Có mẫu móng đang thích? Gửi ảnh khi đặt lịch để thợ chuẩn bị màu.",
            form=dict(offer="Dịch vụ gì, ở đâu — tiệm nail ở quận 7, chuyên sơn gel và vẽ móng",
                      different="Hơn 200 màu gel | xem bảng màu thật tại tiệm\nBảo hành 3 ngày | bong là làm lại",
                      items="Sơn gel tay | 150.000₫ | 45 phút\nĐắp móng bột | 350.000₫ | 90 phút",
                      numbers="4,9/5 | 380 đánh giá trên Google Maps\n6 | thợ đang làm tại tiệm",
                      reviews="Vẽ y như mẫu mình gửi, giữ được 4 tuần | Ngọc, Quận 7",
                      faqs="Sơn gel giữ được bao lâu? | Thường 3–4 tuần",
                      contact="15 Nguyễn Thị Thập, Q7 · 9h–21h · 0909 123 456"))
HAIR = dict(_SERVICE_BASE, label="tiệm tóc",
            facts=[("9:00–20:00", "mỗi ngày"), ("15 phút", "xác nhận lịch"), ("Tư vấn", "kiểu tóc trước khi cắt"),
                   ("Miễn phí", "đổi lịch trước 2 giờ")],
            items=[("Cắt và tạo kiểu", "45 phút, gồm gội", "150.000₫", ""), ("Uốn tóc", "2–3 giờ", "Từ 650.000₫", "Được chọn nhiều"),
                   ("Nhuộm màu", "2 giờ", "Từ 550.000₫", ""), ("Phục hồi tóc", "60 phút", "350.000₫", "")],
            categories=["Cắt", "Uốn", "Nhuộm", "Phục hồi"],
            faqs=[("Có tư vấn kiểu hợp mặt không?", "Có, thợ tư vấn trước khi cắt, bạn có thể mang ảnh mẫu."),
                  ("Uốn nhuộm mất bao lâu?", "Khoảng 2–3 giờ tùy độ dài và tình trạng tóc."),
                  ("Giá có thay đổi theo độ dài tóc không?", "Có, giá ghi “từ” là cho tóc ngắn; thợ báo giá trước khi làm."),
                  ("Đổi lịch thế nào?", "Đổi miễn phí trước 2 giờ qua tin nhắn xác nhận."),
                  ("Thanh toán ra sao?", "Tiền mặt, thẻ hoặc chuyển khoản tại tiệm.")],
            story=[("Đặt lịch trong 30 giây", "Chọn dịch vụ, chọn thợ và giờ trống."),
                   ("Tư vấn trước khi cắt", "Thợ xem chất tóc và khuôn mặt, đề xuất kiểu trước khi làm."),
                   ("Báo giá trước", "Uốn, nhuộm được báo giá theo độ dài tóc trước khi bắt đầu."),
                   ("Thuốc rõ nguồn gốc", "Thuốc uốn nhuộm có tên hãng, xem được hộp tại tiệm."),
                   ("Chọn thợ quen", "Xem lịch trống của từng thợ và chọn người bạn tin."),
                   ("Chỉnh lại miễn phí", "Chưa ưng trong 7 ngày được chỉnh lại không tính phí.")],
            features=[("Chọn thợ quen", "Xem lịch trống của từng thợ và chọn người quen."),
                      ("Giữ chỗ trước", "Giữ giờ đẹp bằng chuyển khoản hoặc ví điện tử."),
                      ("Thẻ thành viên", "Tích điểm sau mỗi lần cắt, đổi lấy lần gội miễn phí."),
                      ("Gửi ảnh mẫu", "Đính kèm ảnh kiểu tóc khi đặt lịch."),
                      ("Đánh giá sau buổi", "Góp ý trực tiếp cho từng thợ."),
                      ("Nhắc lịch cắt", "Lời nhắc sau 4–6 tuần.")],
            quotes=["Thợ tư vấn kỹ, kiểu mới hợp mặt hơn hẳn.", "Đặt lịch xong tới là làm, không phải ngồi chờ."],
            headline="Cắt đúng kiểu bạn muốn, đặt giờ trước khỏi chờ",
            subhead="chọn thợ, chọn giờ và mang ảnh mẫu, thợ tư vấn trước khi làm.",
            closing="Đang muốn đổi kiểu? Gửi ảnh mẫu khi đặt lịch để thợ tư vấn trước.",
            form=dict(offer="Dịch vụ gì, ở đâu — salon tóc nam nữ ở Cầu Giấy, chuyên uốn và nhuộm",
                      different="Tư vấn trước khi cắt | xem chất tóc, khuôn mặt\nChỉnh lại 7 ngày | miễn phí",
                      items="Cắt và tạo kiểu | 150.000₫ | 45 phút\nUốn tóc | từ 650.000₫ | 2–3 giờ",
                      numbers="4,8/5 | 500 đánh giá trên Google Maps\n10 năm | thợ chính trong nghề",
                      reviews="Kiểu mới hợp mặt, thợ rất kỹ | Anh Tuấn, Cầu Giấy",
                      faqs="Uốn mất bao lâu? | Khoảng 2–3 giờ",
                      contact="88 Trần Thái Tông, Cầu Giấy · 9h–20h · 0909 123 456"))

_TABLE_BASE = dict(
    order=dict(item_label="Gọi món trước (không bắt buộc)", item_required=False, when="Ngày đặt bàn", party=True),
    nav=["Thực đơn", "Đặt bàn", "Không gian", "Liên hệ"],
    story=[("Đặt bàn trong 30 giây", "Chọn ngày, giờ và số người, quán giữ bàn cho bạn."),
           ("Giữ bàn 15 phút", "Bàn được giữ 15 phút sau giờ hẹn, đến muộn hơn nhắn quán trước."),
           ("Nhóm đông báo trước", "Từ 8 người nên đặt trước một ngày để quán xếp chỗ."),
           ("Thực đơn có giá", "Giá từng món ghi rõ trên web, không phụ thu."),
           ("Chỗ gửi xe", "Gửi xe máy miễn phí ngay trước cửa."),
           ("Tiệc nhỏ", "Nhận đặt sinh nhật, họp lớp, có bánh và trang trí theo yêu cầu.")],
    features=[("Chọn chỗ ngồi", "Trong nhà, ngoài trời hay tầng trên."),
              ("Đặt món trước", "Gọi sẵn món để lên bàn ngay khi tới."),
              ("Tiệc sinh nhật", "Trang trí, bánh và nhạc theo yêu cầu."),
              ("Mang về", "Đặt món mang về, nhận tại quầy."),
              ("Thanh toán nhanh", "Quét mã tại bàn, không phải chờ."),
              ("Nhắc lịch", "Tin nhắn nhắc trước giờ hẹn.")],
    faqs=[("Có cần đặt bàn trước không?", "Cuối tuần nên đặt trước; ngày thường vẫn nhận khách vãng lai."),
          ("Bàn được giữ bao lâu?", "15 phút sau giờ hẹn; đến muộn hơn hãy nhắn quán."),
          ("Đi nhóm đông được không?", "Được, từ 8 người nên đặt trước một ngày."),
          ("Có chỗ gửi xe không?", "Có, gửi xe máy miễn phí ngay trước cửa."),
          ("Thanh toán thế nào?", "Tiền mặt, thẻ hoặc chuyển khoản.")],
    closing="Cuối tuần thường kín bàn, đặt trước để giữ chỗ bạn thích.",
)
CAFE = dict(_TABLE_BASE, label="quán cà phê",
            facts=[("7:00–22:00", "mỗi ngày"), ("Wifi", "ổ cắm ở mọi bàn"), ("Giữ bàn", "15 phút sau giờ hẹn"),
                   ("Gửi xe", "miễn phí")],
            items=[("Cà phê sữa đá", "Phin truyền thống", "35.000₫", "Bán chạy"), ("Bạc xỉu", "Ít cà phê, nhiều sữa", "39.000₫", ""),
                   ("Trà đào cam sả", "Ít ngọt", "45.000₫", ""), ("Bánh croissant", "Nướng mỗi sáng", "35.000₫", "")],
            categories=["Cà phê", "Trà", "Đá xay", "Bánh"],
            quotes=["Quán yên tĩnh, ngồi làm việc cả buổi rất thoải mái.", "Cà phê đậm, nhân viên nhớ cả món mình hay gọi."],
            headline="Một chỗ ngồi yên tĩnh, cà phê pha mỗi sáng",
            subhead="xem thực đơn có giá và giữ bàn trước cho buổi làm việc hay buổi hẹn.",
            closing="Cuối tuần quán thường kín chỗ, đặt bàn trước để giữ góc bạn thích.",
            form=dict(offer="Quán gì, ở đâu — quán cà phê yên tĩnh để làm việc ở Hải Châu, mở 7h–22h",
                      different="Ổ cắm mọi bàn | ngồi làm việc cả ngày\nRang hạt tại quán | mỗi tuần một mẻ",
                      items="Cà phê sữa đá | 35.000₫ | phin\nTrà đào cam sả | 45.000₫ | ít ngọt",
                      numbers="4,7/5 | 800 đánh giá trên Google Maps\n60 | chỗ ngồi, 2 tầng",
                      reviews="Quán yên, wifi mạnh, ngồi cả buổi | Hà, Hải Châu",
                      faqs="Có chỗ ngồi làm việc không? | Có, tầng 2 yên tĩnh, ổ cắm mọi bàn",
                      contact="12 Bạch Đằng, Đà Nẵng · 7h–22h · 0905 123 456"))
RESTAURANT = dict(_TABLE_BASE, label="nhà hàng, quán ăn",
                  facts=[("10:00–22:00", "mỗi ngày"), ("Giữ bàn", "15 phút sau giờ hẹn"), ("Nhóm đông", "báo trước 1 ngày"),
                         ("Gửi xe", "miễn phí")],
                  items=[("Món khai vị", "Cho 2–3 người", "89.000₫", ""), ("Món chính", "Phục vụ kèm cơm", "159.000₫", "Được gọi nhiều"),
                         ("Lẩu", "Cho 4 người", "390.000₫", ""), ("Tráng miệng", "Làm trong ngày", "39.000₫", "")],
                  categories=["Khai vị", "Món chính", "Lẩu", "Đồ uống"],
                  quotes=["Món ra nhanh, nêm vừa miệng, đi nhóm rất hợp.", "Đặt bàn trước tới là có chỗ ngay, phục vụ chu đáo."],
                  headline="Đặt bàn trước, tới là có món ngay",
                  subhead="xem thực đơn có giá, chọn giờ và số người, quán giữ bàn cho bạn.",
                  form=dict(offer="Quán gì, ở đâu — quán lẩu bò ở Hải Châu, hợp đi nhóm 4–8 người",
                            different="Bò tươi trong ngày | không dùng thịt đông lạnh\nNước dùng ninh 12 giờ | từ xương bò",
                            items="Lẩu bò nhúng giấm | 390.000₫ | 4 người\nBò lá lốt | 89.000₫ | 10 cuốn",
                            numbers="4,6/5 | 1.100 đánh giá trên Google Maps\n120 | chỗ ngồi",
                            reviews="Bò tươi, nước lẩu ngọt, đi nhóm rất hợp | Anh Khoa, Đà Nẵng",
                            faqs="Đi nhóm 10 người được không? | Được, đặt trước một ngày",
                            contact="90 Nguyễn Văn Linh, Đà Nẵng · 10h–22h · 0905 123 456"))
CLINIC = dict(label="phòng khám",
              order=dict(when="Ngày khám"),
              nav=["Dịch vụ", "Bác sĩ", "Đặt lịch", "Liên hệ"],
              facts=[("8:00–20:00", "thứ hai đến thứ bảy"), ("Bác sĩ", "khám và tư vấn trực tiếp"),
                     ("Báo giá", "trước khi điều trị"), ("Miễn phí", "đổi lịch trước 2 giờ")],
              items=[("Khám và tư vấn", "30 phút", "150.000₫", ""), ("Lấy cao răng", "45 phút", "300.000₫", "Được chọn nhiều"),
                     ("Trám răng", "Theo từng răng", "Từ 300.000₫", ""), ("Tẩy trắng", "60 phút", "2.500.000₫", "")],
              categories=["Khám", "Vệ sinh", "Điều trị", "Thẩm mỹ"],
              faqs=[("Có cần đặt lịch trước không?", "Nên đặt trước để không phải chờ; vẫn nhận khách đến trực tiếp."),
                    ("Chi phí điều trị thế nào?", "Bác sĩ khám và báo giá chi tiết trước khi điều trị."),
                    ("Dụng cụ có vô trùng không?", "Dụng cụ được hấp tiệt trùng sau mỗi lượt khám."),
                    ("Đổi lịch thế nào?", "Đổi miễn phí trước 2 giờ qua tin nhắn xác nhận."),
                    ("Thanh toán ra sao?", "Tiền mặt, thẻ hoặc chuyển khoản tại quầy.")],
              story=[("Khám trước, báo giá sau", "Bác sĩ khám, giải thích và báo giá trước khi điều trị."),
                     ("Đặt lịch không chờ", "Chọn giờ trống, đến là vào khám."),
                     ("Dụng cụ tiệt trùng", "Hấp tiệt trùng sau mỗi lượt, có nhật ký từng ngày."),
                     ("Hồ sơ lưu lại", "Kết quả khám được lưu để lần sau theo dõi tiếp."),
                     ("Nhắc lịch tái khám", "Tin nhắn nhắc khi đến hạn kiểm tra lại."),
                     ("Bảng giá công khai", "Giá từng dịch vụ ghi rõ trên web.")],
              features=[("Chọn bác sĩ", "Xem lịch trống của từng bác sĩ."), ("Hồ sơ điện tử", "Xem lại kết quả khám."),
                        ("Nhắc tái khám", "Lời nhắc theo lịch điều trị."), ("Trả góp", "Cho các gói điều trị lớn."),
                        ("Tư vấn trước", "Gửi ảnh để được tư vấn sơ bộ."), ("Hóa đơn", "Xuất hóa đơn khi cần.")],
              quotes=["Bác sĩ giải thích rõ, báo giá trước nên rất yên tâm.", "Đặt lịch đến là khám luôn, không phải chờ."],
              headline="Khám trước, báo giá rõ, rồi mới điều trị",
              subhead="chọn giờ trống và bác sĩ, phòng khám xác nhận qua tin nhắn.",
              closing="Đặt lịch khám và tư vấn trước, chưa cần quyết định điều trị.",
              form=dict(offer="Phòng khám gì, ở đâu — nha khoa gia đình ở Thanh Khê, mở cả thứ bảy",
                        different="Báo giá trước | không phát sinh khi điều trị\nBác sĩ 12 năm | chuyên niềng răng",
                        items="Khám và tư vấn | 150.000₫ | 30 phút\nLấy cao răng | 300.000₫ | 45 phút",
                        numbers="4,9/5 | 420 đánh giá trên Google Maps\n12 năm | kinh nghiệm bác sĩ chính",
                        reviews="Bác sĩ nhẹ tay, giải thích rõ | Chị Hoa, Thanh Khê",
                        faqs="Có làm thứ bảy không? | Có, 8h–17h",
                        contact="30 Hà Huy Tập, Đà Nẵng · 8h–20h · 0905 123 456"))

# (pattern, pack, domains it applies to) — first match wins
RULES: list[tuple[re.Pattern, dict, tuple]] = [
    (_p("tiệm bánh", "bánh mì", "bánh ngọt", "bánh kem", "bánh sinh nhật", "sourdough", "croissant", "bakery",
        "cookie", "bánh bông lan", "tiramisu", "patisserie"), BAKERY, _SHOP),
    (_p("quán cà phê", "quán cafe", "cà phê", "cafe", "coffee", "trà sữa", "tiệm trà"), CAFE, (Domain.BOOKING,)),
    (_p("nhà hàng", "quán ăn", "quán lẩu", "quán nướng", "lẩu", "nướng", "đặt bàn", "bistro", "restaurant", "buffet"),
     RESTAURANT, (Domain.BOOKING,)),
    (_p("nail", "làm móng", "móng tay", "sơn gel"), NAIL, (Domain.BOOKING,)),
    (_p("tóc", "salon", "barber", "hair", "cắt tóc", "uốn", "nhuộm"), HAIR, (Domain.BOOKING,)),
    (_p("nha khoa", "phòng khám", "bác sĩ", "khám bệnh", "răng", "clinic", "dental"), CLINIC, (Domain.BOOKING,)),
    (_p("spa", "massage", "gội đầu", "gội dưỡng sinh", "chăm sóc da mặt", "thư giãn", "xông hơi"), SPA, (Domain.BOOKING,)),
    (_p("đồ ăn", "món ăn", "thực phẩm", "đặc sản", "đồ khô", "hạt dinh dưỡng", "cà phê", "cafe", "coffee", "trà xanh",
        "trà ô long", "trà thảo mộc", "tiệm trà", "mứt", "nông sản", "healthy", "granola", "mật ong", "đồ uống"), FOOD, _SHOP),
    (_p("quần áo", "thời trang", "áo thun", "áo", "váy", "đầm", "quần", "giày", "dép", "sneaker", "túi xách", "local brand",
        "fashion", "đồ bơi", "đồ ngủ"), FASHION, _SHOP),
    (_p("mỹ phẩm", "skincare", "chăm sóc da", "son", "nước hoa", "serum", "kem dưỡng", "makeup", "trang điểm",
        "cosmetic"), BEAUTY, _SHOP),
    (_p("nội thất", "bàn ghế", "sofa", "giường", "tủ", "kệ", "đồ gỗ", "furniture", "decor"), FURNITURE, _SHOP),
]


BY_LABEL = {pack["label"]: pack for _, pack, _ in RULES}


def detect(text: str, domain: Domain | None) -> dict | None:
    """The industry pack for what the prompt describes, or None (neutral domain samples)."""
    d = domain or Domain.OTHER
    for pattern, pack, domains in RULES:
        if d in domains and pattern.search(text or ""):
            return pack
    return None


def user_text(state) -> str:
    """Everything the user wrote about the business (prompt, audience, real content)."""
    real = state.real_content or {}
    items = " ".join(i.get("name", "") for i in real.get("items", []) if isinstance(i, dict))
    return " ".join([state.raw_prompt or "", str(real.get("offer", "")), items,
                     " ".join((state.brief or {}).get("products") or [])])


def pack_for(state) -> dict | None:
    return detect(user_text(state), state.domain)


# ------------------------------------------------------------------ stray words
# word → the packs it belongs to. Anywhere else (and not written by the user) it is a sign the copy
# was written for another kind of business.
STRAY: dict[str, tuple[dict, ...]] = {
    "lắp đặt": (FURNITURE,), "kích thước phòng": (FURNITURE,), "bảo trì": (FURNITURE,), "vật liệu": (FURNITURE,),
    "bảo hành": (FURNITURE, NAIL), "phòng khách": (FURNITURE,), "phòng ngủ": (FURNITURE,),
    "kỹ thuật viên": (SPA, NAIL), "phòng riêng": (SPA,), "liệu trình": (SPA,),
    "bảng size": (FASHION,), "đổi size": (FASHION,), "loại da": (BEAUTY,),
}


def stray(text: str, pack: dict | None, user: str = "") -> list[str]:
    """Words in `text` that belong to another industry than `pack` and that the user did not write."""
    low, mine = (text or "").lower(), (user or "").lower()
    return [w for w, owners in STRAY.items()
            if w in low and w not in mine and not any(pack is o for o in owners)]
