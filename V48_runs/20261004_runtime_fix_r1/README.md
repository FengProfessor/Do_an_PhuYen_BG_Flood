# V48 runtime fix R1

Đã sửa chuẩn hóa đơn vị mưa và lưới DEM/NetCDF. Trạng thái phát hành: `READY_TO_START_FORMAL_BG_FLOOD_PAIR_RUNTIME_R1`. Chưa chạy formal 120 giờ.

Đọc [báo cáo triển khai và lệnh chạy](D:/VTP/V48_RUNTIME_FIX_REPORT_20261004.md). [Runtime manifest](D:/VTP/V48_runs/20261004_runtime_fix_r1/V48_RUNTIME_MANIFEST_R1.json) khóa mã, interpreter, thư viện, config và bằng chứng kiểm tra; [run pair](D:/VTP/V48_runs/20261004_runtime_fix_r1/V48_FORMAL_RUN_PAIR_R1.json) xác định hai nhánh và output.

```powershell
& 'C:\Users\CuongHM\anaconda3\python.exe' -X utf8 -B 'D:\VTP\V48_runs\20261004_runtime_fix_r1\launch_formal.py' --check
```

Runtime gốc và hồ sơ ngày 02/10 được giữ nguyên. Các file `*_GRID_INPUT_PROBE.nc` chỉ là kiểm tra cao độ khởi tạo tại t=0.
