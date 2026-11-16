# TÀI LIỆU TỔNG HỢP BÀN GIAO CHO CLAUDE SCIENCE & CLAUDE CODE (`CLAUDE.md`)
**Tên Đề tài Nghiên cứu:** *SwarmUI — Hệ thống Đa Tác tử (Multi-Agent) Thiết kế & Xây dựng Frontend Chuẩn Product Dành Cho Người Không Chuyên (Lấy cảm hứng từ Swarm Rebuild & Playwright)*
**Ngăn xếp Công nghệ Chốt (Tech Stack):**
* **Hệ thống Agent & Điều phối Trình duyệt (Backend Agents):** **Python 3.11+** (`playwright-python`, `FastAPI` + `WebSockets`, `Pydantic`, `LangGraph` / `Anthropic Python SDK`).
* **Giao diện Sản phẩm & Swarm Studio (Frontend Target):** **Next.js 15 (App Router, TypeScript, Tailwind CSS)** (có thể mở rộng Adapter sang React/Angular).
* **Phương pháp Nghiên cứu & Thực nghiệm:** Kết hợp **Claude Science** (xây dựng mô hình toán học màu sắc OKLCH, hàm phạt Anti-AI-Slop, thiết kế thực nghiệm) và **Claude Code** (triển khai hệ thống Python Multi-Agent + Next.js).

**Phân công theo mode:**
* **Mode Creative** (chat → đọc brief → 5 trụ cột → dựng trang): **Cường** phụ trách chính (nhánh `quoccuong`); Chuki1234 chỉ hỗ trợ.
* **Mode Clone** (link → đọc trang mẫu → dựng lại): **Chuki1234** phụ trách chính; Cường hỗ trợ.
* Phần dùng chung (graph, pipeline state, planner, codegen Next.js, engines, QA, FRONTEND_STANDARDS) sửa thì báo người còn lại và giữ test của cả hai mode luôn xanh. Chi tiết file thuộc ai: mục *Team & ownership* trong `CLAUDE.md`.

---

## PHẦN 1: QUY TRÌNH 12 BƯỚC BẮT BUỘC CỦA HỆ THỐNG AGENT (PYTHON ORCHESTRATOR)

Hệ thống Python Agent hoạt động theo **State Machine 12 Bước nghiêm ngặt**, xây dựng **từng trang một (Page-by-Page)** và **chặn hoàn toàn việc Model tự đoán mò**:

1. **Bước 1 (`B1 - Read Prompt`):** Đọc User Prompt thô $\rightarrow$ Phân tích yêu cầu khởi tạo (Ví dụ: *"Xây dựng trang web bán hàng"*).
2. **Bước 2 (`B2 - Product Sitemap Advisory`):** Phân tích và tư vấn ngược lại cho User: Một trang web bán hàng **có thể sử dụng được trong thực tế** sẽ bao gồm những trang gì (`Landing Page`, `Login / Register`, `Home / Storefront`, `Product Detail`, `Cart & Checkout`...). Yêu cầu User chọn 1 trang để bắt đầu trước (xây dựng từng trang một).
3. **Bước 3 (`B3 - Socratic Elicitation`):** Hỏi đáp khai thác sâu ý tưởng của User dựa trên tài liệu chuẩn `FRONTEND_STANDARDS.md` (Một giao diện đẹp chuẩn Product cần những gì). Chuỗi hỏi đáp đi theo 5 trụ cột:
   $$\text{Chủ đề (Theme)} \longrightarrow \text{Layout} \longrightarrow \text{Color Palette} \longrightarrow \text{Margins} \longrightarrow \text{Scope (Người dùng là ai \& Mục đích gì?)}$$
   *(Cơ chế Hard-Gate: Nghiêm cấm Agent tự đoán mò hoặc sinh code khi chưa hỏi xong).*
4. **Bước 4 (`B4 - Assets & Reference Collection`):**
   - Yêu cầu người dùng gửi các thông tin/tài nguyên cần thiết (Assets: Logo, ảnh sản phẩm, nội dung chữ...).
   - Khi người dùng gửi **Ảnh chụp màn hình (Screenshot)** giao diện mẫu: Hệ thống tự động **Recommend người dùng gửi kèm cả Link URL** của trang web đó.
   - **Nguyên tắc cốt lõi:** Model chỉ học **ĐẶC TRƯNG THIẾT KẾ (Design DNA)** bên trong ảnh/link chứ **tuyệt đối không copy 100%** giao diện bên trong.
5. **Bước 5 (`B5 - Distill DESIGN.md`):** Phân tích toàn bộ thông tin người dùng đã đưa + dữ liệu trích xuất từ Ảnh/URL (qua Python Playwright) để xuất bản thành file **`DESIGN.md`** và chắt lọc **Triết lý Thiết kế (Design Philosophy)**.
6. **Bước 6 (`B6 - Master Plan Generation`):** Phát triển kế hoạch triển khai chi tiết từ bộ 3 tài liệu: **`DESIGN.md`**, **`PRODUCT.md`** và **`PLAN.md`**.
7. **Bước 7 (`B7 - User Approval Gate`):** Chờ người dùng duyệt kế hoạch (`Approve`). Nếu chưa duyệt thì quay lại tinh chỉnh tài liệu.
8. **Bước 8 (`B8 - Micro-Subagent Dispatch & Design Department`):**
   - Phân chia nhân sự (`Subagents`) ở mức độ vi mô (**Micro-level**) thành **2 Phòng ban làm việc song song với nhau**: **Phòng Design** (chạy bằng Python Playwright trên Browser) và **Phòng Developer** (Next.js Code Generator).
   - **Phía Phòng Design:** Dựa trên triết lý thiết kế và `DESIGN.md`, điều khiển đàn con trỏ đa màu sắc (**Swarm Cursors** lấy cảm hứng từ Chrome Extension *Swarm Rebuild*) trực tiếp trên trình duyệt Playwright để bố trí khung, đo `Margins`, áp bảng màu.
   - **Bước 8.1 (`B8.1 - OPTIONAL MCP 2D/3D`):** Sử dụng **MCP (Model Context Protocol)** để hiện thực hóa các hiệu ứng (`Effects`), hoạt ảnh **Animation 2D** (GSAP / Framer Motion / Canvas) hoặc **3D** (Three.js / React Three Fiber / WebGL Shaders).
9. **Bước 9 (`B9 - Developer Department Parallel Codegen`):** Phía **Phòng Developer** (Python Code Agent) sinh code **Next.js (App Router `.tsx`)** song song theo thời gian thực với giao diện đang dựng của Phòng Design (thông qua Hot Module Replacement & WebSocket).
10. **Bước 10 (`B10 - Integrated Artifact`):** Hợp nhất thành phẩm trang web hoàn chỉnh chạy trực tiếp trên trình duyệt.
11. **Bước 11 (`B11 - Master Cursor E2E Test Case`):**
    - Sau khi đàn cursor nhỏ rút lui, **Cursor Lớn Nhất (Master QA Cursor)** xuất hiện trên trình duyệt Playwright.
    - Thực hiện thao tác kiểm thử tự động trên toàn bộ giao diện: **bấm/di chuột từng nút một (`button-by-button`) – cuộn trang (`scroll`) – kiểm tra đa màn hình (`responsive`)** dựa trên tài liệu chuẩn `FRONTEND_STANDARDS.md`. Nếu phát hiện lỗi sẽ tự động yêu cầu sửa ngay.
12. **Bước 12 (`B12 - User Live Handover & Next Page Loop`):** Chuyển nhượng quyền điều khiển trình duyệt cho người dùng thao tác, bấm test trực tiếp; sau đó người dùng chọn **Upgrade (nâng cấp trang hiện tại)** hoặc **Build Page tiếp theo** trong `PRODUCT.md`.

---

## PHẦN 2: KIẾN TRÚC KỸ THUẬT PYTHON AGENT + NEXT.JS (DÀNH CHO CLAUDE CODE)

Khi đưa vào **Claude Code**, yêu cầu xây dựng cấu trúc dự án chuẩn như sau:

```text
swarm-ui-project/
├── CLAUDE.md                        # File chỉ dẫn tổng thể này cho Claude Code
├── docs/                            # Bộ 4 Tài liệu Nghiên cứu & Chuẩn Frontend đã chốt
│   ├── 01_RESEARCH_AND_ARCHITECTURE.md
│   ├── 02_MODEL_TRAINING_PLAN.md
│   ├── 03_FRONTEND_STANDARDS.md     # Tài liệu chuẩn nạp cho Agent ở B3, B5, B8, B11
│   └── 04_SUBAGENTS_AND_ENGINE_SPEC.md
├── backend-python/                  # Hệ thống Đa Tác tử viết bằng Python
│   ├── pyproject.toml / requirements.txt
│   ├── main.py                      # FastAPI + WebSocket Server điều phối 12 bước
│   ├── state_machine/
│   │   └── pipeline_state.py        # Pydantic State cho B1 -> B12 (Hard-Gate ở B4 & B7)
│   ├── agents/
│   │   ├── consultant_agent.py      # B1-B4: Tư vấn Sitemap & Hỏi 5 trụ cột (Chặn đoán mò)
│   │   ├── dna_extractor_agent.py   # B5: Python Playwright đọc URL + Vision đọc Ảnh -> DESIGN.md
│   │   ├── architect_planner.py     # B6-B7: Sinh DESIGN.md, PRODUCT.md, PLAN.md
│   │   ├── dept_design_swarm.py     # B8 & B8.1: Điều khiển đàn Cursor trên Playwright + MCP 2D/3D
│   │   ├── dept_developer_nextjs.py # B9: Sinh code Next.js (.tsx) song song có gắn [data-swarm-id]
│   │   └── master_qa_cursor.py      # B11: Điều khiển "Cursor Lớn Nhất" test từng nút, scroll, responsive
│   └── playwright_engine/
│       ├── browser_manager.py       # Quản lý phiên Chromium của Playwright Python
│       ├── swarm_overlay.js         # Script tiêm vào trang Next.js để vẽ đàn Cursor & Master Cursor
│       └── style_dna_scraper.py     # Trích xuất OKLCH, Font, Margins từ URL mà không copy DOM
└── frontend-nextjs/                 # Ứng dụng Next.js 15 (App Router + TypeScript + Tailwind)
    ├── package.json
    ├── src/
    │   ├── app/                     # Nơi Phòng Developer (B9) sinh ra từng trang (Landing, Home, Login...)
    │   ├── components/              # Các Component chuẩn Product + Hiệu ứng 2D/3D (B8.1)
    │   └── styles/                  # Hệ biến CSS OKLCH 60-30-10 sinh từ DESIGN.md
    └── artifacts/                   # Lưu DESIGN.md, PRODUCT.md, PLAN.md của dự án đang chạy
```

### Giao thức Đồng bộ giữa Python Playwright (Phòng Design - B8) & Next.js (Phòng Developer - B9)
1. **Gắn nhãn phần tử (`DOM Instrumentation`):**
   Mọi Component Next.js do `dept_developer_nextjs.py` sinh ra ở Bước 9 đều gắn thuộc tính:
   - `data-swarm-section="hero-section"`
   - `data-swarm-id="cta-buy-now"`
   - `data-swarm-role="button | link | input | filter-tab"`
   - `data-swarm-mcp="2d-gsap | 3d-threejs"` *(nếu có Bước 8.1)*
2. **Tiêm Lớp Phủ Cursor (`page.add_init_script` trong Python Playwright):**
   - Ở **Bước 8**, `dept_design_swarm.py` bắn tọa độ qua WebSocket để 4 con trỏ của Phòng Design (`Layout Cursor`, `Color OKLCH Cursor`, `Typography Cursor`, `MCP 2D/3D Cursor`) bay tới từng `[data-swarm-section]` trên cửa sổ trình duyệt Next.js đang chạy (`http://localhost:3000`), vẽ thước gióng và kiểm tra khoảng cách ngay khi Next.js Hot-Reload.
   - Ở **Bước 11**, `master_qa_cursor.py` kích hoạt **Cursor Lớn Nhất (kích thước `2.2x`)**, dùng hàm thật của Playwright Python (`await locator.hover()`, `await locator.click()`, `await page.mouse.wheel()`, `await page.set_viewport_size()`) để kiểm tra từng nút một từ trên xuống dưới trước mặt người dùng.

---

## PHẦN 3: HƯỚNG DẪN SỬ DỤNG KẾT HỢP CLAUDE SCIENCE & CLAUDE CODE

### 3.1. Đối với Claude Science (Phát triển Bài báo Khoa học & Thực nghiệm)
Bạn đưa các file **`01_RESEARCH_AND_ARCHITECTURE.md`**, **`02_MODEL_TRAINING_PLAN.md`** và **`03_FRONTEND_STANDARDS.md`** vào **Claude Science** để:
1. Thiết lập mô hình toán học cho **Design DNA Extraction** (công thức chuyển đổi không gian màu sang $\text{OKLCH}(L, C, H)$ theo tỷ lệ $60:30:10$ và hàm phạt chống sao chép cấu trúc cây DOM $\text{Tree-Edit-Distance}$).
2. Thiết kế hàm thưởng **Execution-Guided RLAIF / Aesthetic-DPO** dựa trên kết quả chấm điểm tự động của **Cursor Lớn Nhất (Bước 11)**.
3. Sinh bảng biểu thực nghiệm so sánh giữa **SwarmUI (12 Bước)** với **Baseline One-shot LLM (v0 / Bolt / GPT)** trên các chỉ số: *AI-Slop Detection Rate*, *APCA Contrast Compliance*, *8pt Grid Adherence*, và *Interactive Test Pass Rate*.

### 3.2. Đối với Claude Code (Triển khai Code Python Agent + Next.js Prototype)
Bạn chỉ cần mở terminal tại thư mục dự án và giao cho **Claude Code** câu lệnh khởi tạo sau:
> *"Hãy đọc toàn bộ tài liệu trong thư mục `docs/` và file `CLAUDE.md`. Xây dựng cho mình hệ thống SwarmUI gồm: (1) Backend Multi-Agent bằng **Python** (`FastAPI` + `Playwright Python`) thực thi chuẩn xác State Machine 12 Bước (B1 đến B12), và (2) Frontend **Next.js 15 App Router** để hiển thị giao diện được sinh ra theo từng trang một cùng lớp phủ Swarm Multi-Cursor (B8) và Cursor Lớn Nhất tự động chạy Test Case (B11)."*
