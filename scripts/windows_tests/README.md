# Kiểm thử thực tế trên Windows (W0–W8)

**Trạng thái: các script đã viết nhưng CHƯA được chạy trên Windows.** Chưa có kết quả nào từ máy đích.
Script chỉ ghi nhận số liệu và quan sát; không script nào tự tuyên bố "đạt" cho thứ nó không đo được
(mục không đo được ghi `N/A` và làm kết quả chung thành `PARTIAL`, không bao giờ là `PASS`).
Chạy trên hệ điều hành khác Windows chỉ là *dry run* và báo cáo sẽ ghi rõ `executed_on_target: false`.

## 1. Chuẩn bị (một lần)

Dùng một môi trường ảo **riêng** để không động vào `uv.lock` của repo trước khi xong M0-09.
Các gói dưới đây là **ứng viên, chưa được xác nhận phiên bản**.

```powershell
uv venv .venv-w --python 3.11
$py = ".venv-w\Scripts\python.exe"
uv pip install --python $py -e . numpy opencv-python pillow pyyaml psutil
uv pip install --python $py paddlepaddle "paddleocr>=3,<4" rapidfuzz imagehash scikit-image
uv pip install --python $py torch --index-url https://download.pytorch.org/whl/cpu
uv pip install --python $py transformers sentencepiece openai PySide6 dxcam
```

Nếu một gói không cài được, đó là một phát hiện cần ghi lại (W1 sẽ báo), đừng đổi stack để "cho chạy".
Chạy mọi lệnh từ thư mục gốc của repo. Báo cáo JSON nằm ở `windows_test_results\` (đã bị gitignore).

## 2. Thứ tự và lệnh

| ID | Mục đích | Lệnh | Cần |
|---|---|---|---|
| W0 | Ảnh chụp môi trường (OS, CPU, RAM, GPU, màn hình, DPI) | `& $py scripts\windows_tests\W0_env_snapshot.py` | — |
| W1 | Import các gói, xác nhận Paddle là bản CPU | `& $py scripts\windows_tests\W1_dependency_imports.py` | bước 1 |
| W2 | DXGI capture (độ trễ, fps, ROI, frame đen) | `& $py scripts\windows_tests\W2_dxgi_capture.py --seconds 10 --roi 200,800,1400,1000` | dxcam; nên có thứ gì đó chuyển động trên màn hình |
| W3 | PP-OCRv6 Small CPU: nạp model, CER, độ trễ | `& $py scripts\windows_tests\W3_ocr_ppocr.py` | paddleocr; tải model lần đầu |
| W4 | NLLB-200 600M CPU: RAM, độ trễ, dịch EN→VI | `& $py scripts\windows_tests\W4_nllb.py` | ~2,4 GB tải về |
| W5 | OpenAI Responses API | `$env:OPENAI_API_KEY="..."; $env:OPENAI_MODEL="<model>"; & $py scripts\windows_tests\W5_openai.py` | key + tên model |
| W6 | Overlay click-through, chế độ chỉnh sửa, hotkey | `& $py scripts\windows_tests\W6_overlay_hotkeys.py` | PySide6; làm theo các bước trong docstring |
| W7 | Hàng đợi giới hạn, timeout, guard (mô phỏng) | `& $py scripts\windows_tests\W7_queue_timeout.py` | — |
| W8 | Tác động lên game: tài nguyên + FPS | xem bên dưới | game, PresentMon |

### Lưu ý riêng từng bài
* **W2:** chạy 3 lần và giữ cả 3 báo cáo: màn hình desktop (`--label desktop`), game Windowed/Borderless
  (`--label game-borderless`), và game Fullscreen Exclusive (`--label game-exclusive`). Exclusive **không** được
  mặc định là hoạt động; nếu ra khung đen hoặc không có khung, đó là kết quả cần ghi lại. Màn hình thứ hai:
  thêm `--monitor 1`.
* **W3:** tên model PP-OCRv6 *small* mặc định (`PP-OCRv6_small_det/rec`) là **suy đoán theo quy tắc đặt tên,
  chưa xác nhận**. Nếu nạp lỗi, tra tên đúng trong tài liệu chính thức rồi truyền `--det-model/--rec-model` và
  ghi lại cặp tên chạy được. Để kết quả có ý nghĩa hơn, dùng ảnh chụp game thật: `--dir thu_muc` với mỗi
  `ten.png` kèm `ten.txt` chứa đúng nội dung chữ. **Đừng commit ảnh riêng tư.** CER và độ trễ chỉ được ghi,
  chưa chấm đạt/trượt vì chưa có ngưỡng được duyệt.
* **W4:** bản dịch cần bạn tự đọc (được lưu trong báo cáo). Script không chấm chất lượng.
* **W5:** key chỉ đọc từ biến môi trường, không bao giờ in ra hay ghi vào báo cáo. Model là cấu hình, không có
  mặc định (M0-08 cần tài liệu API hiện hành và bạn duyệt).
* **W6:** chạy hai lần: mặc định (`--method win32`) và `--method qt` để so sánh hai cách bật/tắt click-through.
  Thêm `--idle-seconds 5` để thử nhanh cơ chế tự thoát, rồi chạy một lần với 60 s thật. Bài này kiểm tra:
  F6/F7/F8/F9 và Ctrl+Alt+E có đăng ký được không (lỗi 1409 = phím đã bị chương trình khác giữ), phím có tới
  được game hay không, click xuyên qua overlay, kéo thả ở chế độ chỉnh sửa, bộ đếm 60 s tính từ lần tương
  tác cuối, không tự thoát khi đang kéo, thoát xong phải click-through trở lại, overlay còn topmost không.
  Cuối bài có 5 câu hỏi quan sát tay.
* **W8:** hai bước.
  1. Với mỗi kịch bản (`baseline` lặp ít nhất 2 lần, `capture`, `capture_ocr`, `capture_ocr_nllb`), bật
     PresentMon cho tiến trình game, rồi chạy
     `& $py scripts\windows_tests\W8_game_impact.py run --scenario capture_ocr --seconds 120 --roi 200,800,1400,1000`
     và chơi cùng một lộ trình cố định trong game cùng khoảng thời gian.
  2. So sánh FPS:
     `& $py scripts\windows_tests\W8_game_impact.py analyze --baseline pm_baseline.csv --scenario capture=pm_capture.csv --scenario ocr=pm_ocr.csv`
  Cùng điểm xuất phát, cùng cài đặt đồ họa, laptop cắm sạc, ghi lại chế độ nguồn. Script **không** đưa ra
  kết luận đạt/trượt về FPS vì chưa có ngân sách được duyệt; bạn so với độ dao động giữa hai lần baseline.
  Chi phí của chính overlay không được tạo ra ở đây; hãy mở overlay W6 song song để đo riêng.

## 3. Gửi lại kết quả

Dán cho mình phần cuối `RESULT Wx: ...` của mỗi bài, hoặc gửi file JSON. Báo cáo chứa thông tin máy (CPU,
GPU, phiên bản gói) nhưng không chứa key; hãy xem qua trước khi chia sẻ, nhất là nếu dùng `--save-sample`
(ảnh chụp màn hình có thể có nội dung riêng tư). Mình chỉ đánh dấu một hạng mục M0 là "đã kiểm chứng trên
Windows" khi có báo cáo thật từ máy của bạn.

## 4. Những gì các bài này KHÔNG chứng minh

* Không có ngưỡng chất lượng/độ trễ/FPS nào được duyệt, nên các con số chỉ là dữ liệu.
* W3 dùng ảnh tổng hợp theo mặc định, dễ hơn khung hình game thật.
* W7 là mô phỏng khái niệm (chạy được ngoài Windows), không phải kiểm thử code sản phẩm.
* Chưa kiểm tra: mất thiết bị DXGI sau alt-tab/đổi độ phân giải, thay đổi DPI giữa chừng, nhiều GPU, chạy
  nhiều giờ liên tục.
