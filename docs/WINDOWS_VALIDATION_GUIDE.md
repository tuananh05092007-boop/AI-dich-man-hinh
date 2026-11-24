# Hướng dẫn kiểm chứng trên Windows (Milestone 0)

**Trạng thái:** chuẩn bị xong, **chưa có kết quả nào từ Windows**. Tài liệu này chỉ nói cách chạy; nó không
chứng minh điều gì. Một hạng mục M0 chỉ được ghi "đã kiểm chứng trên Windows" khi có báo cáo thật từ máy đích.

Máy mục tiêu: Windows 11, Python 3.11, Ryzen 7 8745H, 16 GB RAM, RTX 4050 Laptop 6 GB VRAM.
Chi tiết từng bài và các lưu ý riêng: [`scripts/windows_tests/README.md`](../scripts/windows_tests/README.md).

## 0. Quy tắc thứ tự

1. Chạy **W0 rồi W1** trước. Gửi kết quả cho mình, **dừng ở đó**.
2. **Chỉ khi cả W0 và W1 là `PASS` trên Windows** mới chạy W2–W8 (xem mục 6). W0/W1 chưa đạt thì kết quả các bài sau
   không đáng tin và chỉ tốn thời gian (W4 tải ~2,4 GB).
3. Chạy mọi lệnh từ **thư mục gốc của repo**, bằng PowerShell thường (không cần quyền Administrator).

Các trạng thái kết quả: `PASS`, `PARTIAL` (có mục cần quan sát tay, không tính là đạt), `FAIL`, `SKIP`
(không thực hiện được, có lý do), `NOT_RUN` (chưa chạy). Báo cáo chạy ngoài Windows mang nhãn `DRY_RUN_*` và không
được tính là bằng chứng.

## 1. Lấy code

Lần đầu:

```powershell
git clone https://github.com/tuananh05092007-boop/AI-dich-man-hinh.git
cd AI-dich-man-hinh
git checkout feature/m0-data-contracts
```

Nếu đã có repo:

```powershell
git fetch origin
git checkout feature/m0-data-contracts
git pull --ff-only
git status --short   # nên trống
git log -1 --oneline # ghi lại commit này để gửi kèm kết quả
```

Không merge gì vào `main`; nhánh này chỉ để chạy test.

## 2. Môi trường ảo và dependencies

Dùng môi trường ảo **riêng** `.venv-w` (đã được `.gitignore`) để không đụng vào `uv.lock`. Gói bên dưới là
**ứng viên, chưa chốt phiên bản** (M0-09 chốt sau khi W2–W8 qua).

```powershell
uv --version                       # cần có uv; nếu thiếu: https://docs.astral.sh/uv/
uv venv .venv-w --python 3.11
$py = ".venv-w\Scripts\python.exe"

uv pip install --python $py -e . numpy opencv-python pillow pyyaml psutil
uv pip install --python $py paddlepaddle "paddleocr>=3,<4" rapidfuzz imagehash scikit-image
uv pip install --python $py torch --index-url https://download.pytorch.org/whl/cpu
uv pip install --python $py transformers sentencepiece openai PySide6 dxcam
```

**Kích hoạt venv (tùy chọn).** Các lệnh trong hướng dẫn dùng `$py` nên *không cần* kích hoạt. Nếu muốn:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # chỉ áp dụng cho cửa sổ PowerShell này
.\.venv-w\Scripts\Activate.ps1
```

`$py` chỉ tồn tại trong cửa sổ PowerShell hiện tại; mở cửa sổ mới thì gán lại `$py = ".venv-w\Scripts\python.exe"`.

Nếu một gói cài lỗi, **đó là một phát hiện cần báo**, đừng tự đổi stack. W1 sẽ nói rõ gói nào thiếu.

## 3. Chạy W0 và W1 (copy nguyên khối)

```powershell
$py = ".venv-w\Scripts\python.exe"
& $py scripts\windows_tests\W0_env_snapshot.py
& $py scripts\windows_tests\W1_dependency_imports.py
& $py scripts\windows_tests\summarize_results.py
```

Chúng chỉ đọc thông tin (xem mục 7), không tải model, không gọi mạng.

**Kết quả mong đợi:** cuối mỗi bài có dòng `RESULT W0: PASS` và `RESULT W1: PASS`, và bảng tóm tắt cuối cùng có
dòng "W0 and W1 PASSED on Windows; W2-W8 may be run."

- **W0** so máy với mục tiêu: Python 3.11.x, Windows 11 (build ≥ 22000), CPU có "8745H", RAM 14–17 GiB, GPU có
  "4050". Nếu một mục *không đọc được* thì nó là `N/A` (không phải PASS) và W0 thành `PARTIAL`; nếu máy khác mục tiêu
  thì W0 `FAIL` và các kết quả sau **không** là bằng chứng cho máy mục tiêu, hãy báo trước khi chạy tiếp.
- **W1** import từng gói, kiểm tra PaddleOCR là 3.x, PaddlePaddle là bản **CPU**, interpreter là 3.11. Gói tùy
  chọn (`psutil`, `dxcam`) thiếu không làm W1 trượt, nhưng W2 sẽ cần `dxcam`.

Ngoài ra W0 cần bạn ghi tay (script không biết): Game Mode bật/tắt, Hardware-accelerated GPU scheduling, đang cắm sạc
hay dùng pin, chế độ GPU (hybrid/discrete).

## 4. Lưu và gửi kết quả

JSON nằm ở `windows_test_results\` (đã gitignore, **không commit**): mỗi bài một file `Wx_<thời điểm>.json`, thêm
`SUMMARY.json` sau khi chạy `summarize_results.py`. Dùng thư mục khác bằng `$env:W_RESULTS_DIR = "D:\kq"`.

Gửi cho mình:

```powershell
git log -1 --oneline
Get-Content windows_test_results\W0_*.json
Get-Content windows_test_results\W1_*.json
Get-Content windows_test_results\SUMMARY.json
```

hoặc dán các dòng `RESULT Wx: ...` kèm các dòng `[FAIL]` / `[N/A ]` của bài đó. Báo cáo có thông tin máy (CPU, GPU,
phiên bản gói; đường dẫn Python đã che thư mục home) nhưng **không có API key**; vẫn nên liếc qua trước khi gửi.
Mình sẽ phân tích, rồi chỉ cập nhật trạng thái M0 theo đúng báo cáo thật.

## 5. Xử lý lỗi thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `Activate.ps1 cannot be loaded... running scripts is disabled` | Bỏ qua kích hoạt và dùng `$py`, hoặc `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` (chỉ cửa sổ hiện tại) |
| `uv: command not found` | Cài uv, mở lại PowerShell |
| `No interpreter found for Python 3.11` | `uv python install 3.11` rồi chạy lại `uv venv` |
| Lỗi cài `paddlepaddle` / `paddleocr` | Chép nguyên văn lỗi gửi mình; không đổi sang bản GPU để "cho chạy" (W1 sẽ trượt nếu Paddle là bản CUDA) |
| Cài `torch` từ index CPU lỗi thiếu phụ thuộc | Thử `uv pip install --python $py torch` (trên Windows, bản PyPI là bản CPU) và ghi lại việc này |
| W1 `FAIL: import ...` | Cài lại đúng gói đó vào `.venv-w` rồi chạy lại W1; gửi lỗi nếu vẫn trượt |
| `RESULT Wx: DRY_RUN_*` | Script thấy hệ điều hành không phải Windows (đang chạy nhầm trong WSL/Linux) |
| Không thấy file JSON | Bạn đang đứng ngoài thư mục gốc repo; `cd` về gốc, hoặc xem `$env:W_RESULTS_DIR` |

## 6. Sau khi W0 và W1 đạt: các bài còn lại

Đừng chạy nếu cổng W0/W1 chưa mở. Lệnh đầy đủ và cách làm nằm trong README của `scripts/windows_tests`.

| Bài | Nội dung | Điều cần biết trước khi chạy |
|---|---|---|
| W2 | DXGI Desktop Duplication (dxcam) | Chạy riêng 3 lần: `desktop`, game Windowed/Borderless, game Fullscreen Exclusive. Exclusive **không** được giả định là chạy được; khung đen hay không có khung là kết quả cần ghi |
| W3 | PP-OCRv6 Small CPU | Tải model lần đầu. Tên `PP-OCRv6_small_det/rec` có trong collection chính thức, nhưng việc bản PaddleOCR đã cài nhận tên đó chỉ biết khi chạy. CER và độ trễ chỉ được ghi, chưa chấm vì chưa có ngưỡng được duyệt |
| W4 | NLLB-200 Distilled 600M CPU | Tải ~2,4 GB vào cache Hugging Face. Ghi RAM, độ trễ; bản dịch bạn tự đọc. Giấy phép CC-BY-NC-4.0, ổn cho dùng cá nhân, phải xem lại trước khi phân phối |
| W5 | OpenAI API | Key chỉ qua biến môi trường của cửa sổ hiện tại (`$env:OPENAI_API_KEY`, `$env:OPENAI_MODEL`); không dán key vào file, chat hay Git. Có tốn một ít token |
| W6 | Overlay, click-through, hotkey | Đăng ký tạm F6–F9 và Ctrl+Alt+E trong lúc chạy (tự hủy khi kết thúc); đóng phần mềm đang dùng các phím đó. Hotkey mới chỉ **được đặc tả**, chưa có hotkey nào được triển khai trong code sản phẩm |
| W7 | Hàng đợi/timeout/guard | Mô phỏng khái niệm. Tối đa `PARTIAL`, không phải bằng chứng pipeline thật hoạt động (chưa có pipeline) |
| W8 | FPS, CPU, RAM, GPU, độ trễ | Cần game và PresentMon; cùng lộ trình, cắm sạc, baseline chạy ít nhất 2 lần. Không có ngân sách FPS được duyệt nên không có kết luận đạt/trượt tự động |

## 7. Script có thay đổi gì trên máy bạn?

Mình đã rà soát: không script nào sửa registry, cài đặt hệ thống, hay xóa file.

| Bài | Tác động |
|---|---|
| W0 | Chỉ đọc: `Get-CimInstance Win32_Processor`, `nvidia-smi --query-gpu`, `powercfg /getactivescheme`, `uv --version` |
| W1 | Chỉ `import` gói (thư viện có thể tạo cache nhỏ của chính nó) |
| W2 | Chụp màn hình trong bộ nhớ; chỉ ghi PNG nếu thêm `--save-sample` (có thể chứa nội dung riêng tư; đã gitignore) |
| W3, W4 | Tải model vào cache người dùng (`~\.paddlex`, `~\.cache\huggingface`), không vào repo |
| W5 | Gọi API OpenAI qua mạng bằng key trong biến môi trường; có chủ đích gửi một key giả để thử lỗi 401 |
| W6 | Mở cửa sổ overlay của chính nó, đăng ký rồi hủy hotkey toàn cục, đổi style cửa sổ **của nó** |
| W7 | Chỉ mô phỏng trong tiến trình |
| W8 | Đọc tài nguyên (`nvidia-smi`, psutil), ghi CSV trong thư mục hiện tại (đã gitignore); chạy tải OCR/NLLB trong lúc bạn chơi |

## 8. Chưa quyết định (không tự chốt)

Các mục dưới đây chưa được bạn duyệt; script và tài liệu chỉ *ghi nhận* chúng. Chi tiết ở `docs/DECISIONS.md`.

**Câu hỏi mở**

- **Q1:** F8 overlay tồn tại bao lâu và xóa bằng cơ chế nào (timeout, phím, hay chỉ bị F8 kế tiếp thay thế).
- **Q2:** Settings contract cho hotkey tùy chỉnh (v0.2 chưa có; thêm là đổi contract, cần bạn duyệt).
- **Q3:** Master Prompt trong Project instructions còn "beside the original" và "multiple overlay display modes",
  mâu thuẫn với D-07 (chỉ hiển thị tiếng Việt). Cần bạn cập nhật Project instructions.
- **Q4:** ADR 0001–0003 đang `Proposed`; có chuyển sang `Accepted` khi chấp nhận M0 hay không.

**Giá trị tạm (đề xuất của Claude, chưa duyệt)**

- P-01 "trùng vị trí" = overlap coefficient ≥ 0.5 (giao ÷ hộp nhỏ hơn, không phải IoU).
- P-02 debounce F8 ≈ 300 ms.
- P-03 quá 20 khối: lấy 20 khối đầu theo thứ tự đọc và hiện thông báo.
- P-04 chế độ chỉnh sửa có viền báo hiệu và có thể bật/tắt từ cửa sổ chính hoặc tray.
- P-05 `subtitle_id` của F8 dạng `f8_<batch_id>_<n>`, `generation_id = 1`.
- P-06 `OverlayStyle` mặc định (phía dưới, 24 px, `#FFFFFF` trên `#000000`, độ mờ 0.85).

Con số 20 khối/F8 và thời gian tự thoát chế độ chỉnh sửa 60 s **đã** được duyệt (D-16, D-18); các giá trị P-xx ở trên thì chưa.
