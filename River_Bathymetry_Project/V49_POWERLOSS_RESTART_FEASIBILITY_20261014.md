**V49 — Khả năng phục hồi sau mất điện và thiết kế lần chạy tiếp nối**

Ngày: 14/10/2026. Phạm vi: wrapper V49-G, observer và các import solver cục bộ trực tiếp liên quan.
Quy ước: **Mã** = source đã đọc; **E1** = bằng chứng người dùng cung cấp, không đo lại; **Suy luận** = hệ quả; **Đề xuất** = chưa triển khai/chưa chạy.
Chỉ đọc source Python và tạo báo cáo này; không đọc bất kỳ NetCDF nào, không chạy/import solver, không sửa cấu hình, state hay tệp có sẵn.

**Kết luận có thể hành động**

- **Mã:** đường chạy hiện tại tạo mô hình và điều kiện ban đầu mới; chưa có đường nạp checkpoint để tiếp tục trạng thái bị gián đoạn. [run_bgflood.py:112–129](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/run_bgflood.py:112); [initial_conditions.py:292–307](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/initial_conditions.py:292).
- **Suy luận:** output float32 dạng raster không đủ tái lập trạng thái solver float64; chưa có cơ sở tuyên bố exact resume. [model.py:23–28](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/model.py:23); [write_output.py:79–104](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_output.py:79); [write_output.py:140–190](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_output.py:140).
- **Mã:** wrapper không phục hồi queue từ state cũ và kết thúc vẫn ở trạng thái chờ acceptance; Gate G/promotion chưa được tự động chấp thuận. [wrapper:121–160](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:121); [evaluate:163–167](D:/VTP/River_Bathymetry_Project/v49_evaluate_hydraulic_validation.py:163).

**Bằng chứng E1 và giới hạn thời điểm phục hồi**

| Nội dung | E1, không kiểm tra lại tệp/process |
| --- | --- |
| CENTRAL gốc | NetCDF mở được; 11 frame từ khoảng 3 đến 33 giờ |
| Frame cuối | time float32 = 118800.4453125 s, tương đương 33.0001236979 giờ |
| Biến đã biết | h/zs/zb/u/v đều float32 |
| Log cuối | 127444.14 s, khoảng 35.40115 giờ |
| Budget cuối | 127438.348 s |
| Tiến trình | Không còn Python chạy, theo bằng chứng người dùng |

**E2 — xác nhận mới từ nhánh chính:** salvage kiểm tra 11/11 frame đều finite; hash các tệp gốc không đổi; execution state đã được ghi nhận `INTERRUPTED_POWER_LOSS` sau lưu trữ, không còn process sống. Sidecar chỉ tiếp nhận xác nhận này, không đọc NetCDF hay sửa execution state.

**Suy luận từ E1:** phần tiến triển chưa có frame không gian tương ứng khoảng 33→35.4 giờ: 8643.6946875 s, khoảng 2.4010263 giờ; đây không phải phép đo mới.
Log/budget là bằng chứng thời gian vô hướng, không mã hóa h/u/v tại 35.4 giờ và không xác định chính xác thời điểm dừng cuối cùng.
Với lịch output 3 giờ được cung cấp, mốc log chưa đến lịch frame 36 giờ; không suy diễn rằng đã tồn tại frame 36 giờ.
Việc CENTRAL mở được chỉ hỗ trợ salvage/nghiên cứu; không chứng minh hoàn thành 120 giờ, checkpoint đầy đủ hay full acceptance.

| Phương án | Đánh giá hiện tại |
| --- | --- |
| Salvage/phân tích bằng chứng đã lưu | Được phép; nhánh chính phụ trách đọc dữ liệu và so sánh số |
| Resume chính xác ở khoảng 35.4 giờ | Chưa có trạng thái đầy đủ để chứng minh khả thi |
| Khởi tạo từ frame khoảng 33 giờ | Chỉ là đề xuất nhánh thử nghiệm, cần loader mới; không phải exact resume |
| Chạy lại từ đầu trong attempt mới | Đề xuất riêng, chưa được thực hiện và không khôi phục công việc đã mất |

**Wrapper: chuyển trạng thái và queue**

- **Mã:** không có state thì status trả NOT_STARTED; có state thì chỉ thêm supervisor_alive/worker_alive, không chuyển RUNNING thành INTERRUPTED. [wrapper:103–110](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:103).
- **Mã:** thứ tự cố định CENTRAL→LOW→HIGH→BASE; supervise tạo RUNNING với runs rỗng và queue mới, rồi duyệt ARMS thay vì tiếp tục queue đã lưu. [wrapper:23](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:23); [wrapper:121–135](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:121).
- **Mã:** worker lỗi chuyển arm sang FAILED và supervisor sang FAILED_NEEDS_REVIEW; exit 0 chuyển sang SIMULATION_COMPLETED_PENDING_EVALUATION; hết vòng chuyển MATCHED_RUNS_COMPLETED_PENDING_ACCEPTANCE. [wrapper:151–166](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:151).
- **Suy luận:** mất điện có thể để lại RUNNING cũ vì không thực thi except/finally; không coi chuỗi status này là chứng cứ tiến trình còn sống. [wrapper:103–110](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:103); [wrapper:161–166](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:161).
- **Mã/rủi ro:** supervise ghi state mới trước khi kiểm tra result/run.log đã có; gọi lại trực tiếp có thể thay lịch sử state rồi mới báo va chạm. [wrapper:121–132](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:121).
- **Mã:** start trả state nếu PID còn sống và từ chối khi V49_G_supervisor.log tồn tại; không có recovery action trong CLI. [wrapper:169–187](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:169).
- **Mã:** preflight gọi validate_v49_g; validator có thể đọc result và ghi lại report, nên đã không gọi preflight trong nghiên cứu này. [wrapper:63–69](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:63); [validate:365–370](D:/VTP/River_Bathymetry_Project/v49_validate_hydraulic_validation.py:365); [validate:475](D:/VTP/River_Bathymetry_Project/v49_validate_hydraulic_validation.py:475).
- **Mã/suy luận:** validator/evaluator bỏ qua arm được ghi RUNNING mà không đối chiếu PID; stale state có thể che khuất kết quả cần salvage. [validate:365–370](D:/VTP/River_Bathymetry_Project/v49_validate_hydraulic_validation.py:365); [evaluate:154–162](D:/VTP/River_Bathymetry_Project/v49_evaluate_hydraulic_validation.py:154).

**Tên tệp, va chạm, cấu hình và lineage**

- **Mã:** generator sao chép BASE_CONFIG, chỉ thay bathy/outfile, dùng tên BG_param_V49_G_<arm>.txt và results/V49_G_<arm>.nc; write_text không có chặn ghi đè config. [prepare:239–255](D:/VTP/River_Bathymetry_Project/v49_prepare_hydraulic_validation.py:239).
- **Mã:** generator không thêm/chuyển precision hoặc hotstart; các giá trị khác được kế thừa từ cấu hình BASE. Báo cáo không đọc config thực tế để khẳng định giá trị cụ thể. [prepare:240–248](D:/VTP/River_Bathymetry_Project/v49_prepare_hydraulic_validation.py:240).
- **Mã:** normalized hash chỉ chuẩn hóa bathy/outfile; thay hotstart/totaltime trong một arm sẽ phá điều kiện cấu hình tương đồng trừ khi có protocol/manifest riêng. [prepare:224–236](D:/VTP/River_Bathymetry_Project/v49_prepare_hydraulic_validation.py:224); [validate:323–346](D:/VTP/River_Bathymetry_Project/v49_validate_hydraulic_validation.py:323).
- **Mã:** state lưu config_sha256, result/log và timestamps theo arm, nhưng không có attempt_id, parent_attempt, checkpoint_hash/frame hay resume_time. [wrapper:121–137](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:121).
- **Mã/suy luận:** chỉ đổi --output-dir không đủ cô lập output nếu manifest/config vẫn trỏ đường cũ; worker lấy planned_result và config path từ manifest. [wrapper:86–100](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:86); [prepare:241–255](D:/VTP/River_Bathymetry_Project/v49_prepare_hydraulic_validation.py:241).
- **Mã:** supervise chặn result hoặc run.log đã tồn tại, mở run.log bằng x; worker chỉ chặn planned_result, không chặn engine_log/budget cũ. [wrapper:89–98](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:89); [wrapper:129–138](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:129).
- **Mã:** run_model gọi create_logfile; hàm này mở w và truncate _LOG_FILE, mặc định BG_log.txt, được wrapper đổi thành engine_log theo arm. [run_bgflood.py:55](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/run_bgflood.py:55); [write_txtlog.py:12–21](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_txtlog.py:12); [wrapper:95–96](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:95).
- **Mã:** ghi engine text log đã bị vô hiệu bằng pass; progress wrapper lấy từ stdout/stderr được chuyển vào run.log. [write_txtlog.py:28–44](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_txtlog.py:28); [wrapper:72–83](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:72); [wrapper:138–149](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:138).
- **Mã/suy luận:** writer chọn hậu tố _1/_2 khi outfile đã có, nhưng init_loop luôn khởi tạo output mới; append chỉ ghi vào param.outfile đã chọn, không phục hồi run cũ. [write_output.py:61–70](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_output.py:61); [mainloop.py:26–47](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/mainloop.py:26); [write_output.py:123–127](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_output.py:123).
- **Mã:** budget và metrics dùng tên cố định theo arm, JSON thay bản cũ; evaluator gắn result hash nhưng budget được lấy theo tên arm, chưa có liên kết attempt/checkpoint. [observer:15–18](D:/VTP/River_Bathymetry_Project/v49_runtime_observer.py:15); [evaluate:117–141](D:/VTP/River_Bathymetry_Project/v49_evaluate_hydraulic_validation.py:117).

**Solver: hotstart, precision và trạng thái bị thiếu**

- **Mã:** hotstartfile/hotstep có field và parser nhưng init_evolv chỉ chọn cold/warm theo zsinit; các logging call không tạo loader. [param.py:124–125](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/param.py:124); [read_input.py:269–275](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/read_input.py:269); [initial_conditions.py:292–304](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/initial_conditions.py:292); [write_txtlog.py:123–125](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_txtlog.py:123).
- **Mã:** warm_start là nội suy mực nước từ biên theo khoảng cách; u/v=0, zs=max(zsbnd,zb), h=max(zs-zb,0), không nạp frame. [init_evolv.py:74–79](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/init_evolv.py:74); [init_evolv.py:140–143](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/init_evolv.py:140).
- **Mã/suy luận:** đổi totaltime đổi đồng hồ và nextoutputtime, không khôi phục trường thủy lực; forcing uniform được chọn lại từ thời gian tuyệt đối. [read_input.py:164–166](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/read_input.py:164); [mainloop.py:30–47](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/mainloop.py:30); [forcing_update.py:31–63](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/forcing_update.py:31).
- **Mã:** h/zs/u/v/cum_infilt và zb/cf/il/cl cấp phát float64; chuyển GPU dùng cp.asarray không ép dtype cho cả evolv/evolv_o. [model.py:23–28](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/model.py:23); [model.py:212–215](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/model.py:212); [gpu_backend.py:34–38](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/gpu_backend.py:34); [mesh.py:182–187](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/mesh.py:182).
- **Mã:** doubleprecision được parser nhận nhưng không điều khiển các allocation trên; không có outputprecision knob trong source đã rà. [read_input.py:67–69](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/read_input.py:67); [model.py:23–28](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/model.py:23).
- **Mã/suy luận:** time và mọi outvars được ghi f4, raster trung gian float32; upcast không phục hồi các bit float64 đã mất, thời gian double gốc của frame E1 chưa biết. [write_output.py:79–104](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_output.py:79); [bg_flood/write_output.py:148](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_output.py:148).
- **Mã:** output ánh xạ nội thất block active sang raster, bỏ/mask một số ô; không tuần tự hóa đầy đủ block/neighbor/halo/loop. [write_output.py:12–52](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_output.py:12); [write_output.py:140–190](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_output.py:140).
- **Mã/suy luận:** mesh có active/origin/level/neighbors và được dựng từ input; tái dựng cần kiểm tra hash và đúng layout/index, không suy diễn V49 đã có lịch sử adaptive nào. [model.py:91–125](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/model.py:91); [mesh.py:142–172](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/mesh.py:142).
- **Mã:** infiltration thay đổi cum_infilt ở evolv trong half-step và ở evolv_o trong full-step; cả hai là trạng thái phải bảo toàn khi thiết kế restart. [flow_gpu.py:564–565](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/flow_gpu.py:564); [flow_gpu.py:607–608](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/flow_gpu.py:607); [updateforcing.py:391–418](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/updateforcing.py:391).
- **Mã:** adv_kernel/cleanup/copy_evolv chỉ cập nhật h/u/v/zs, không sao chép cum_infilt; đây là yêu cầu bảo toàn hành vi hiện tại, không phải kết luận hay sửa lỗi infiltration. [flow_gpu.py:336–368](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/flow_gpu.py:336); [initial_conditions.py:65–77](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/initial_conditions.py:65).
- **Suy luận:** đặt cum về 0 có thể tái cấp initial loss vì rem_il=max(0,il_m-cum); thêm cum_infilt vào outvars vẫn chỉ lưu một trường f4, chưa thành exact checkpoint. [updateforcing.py:407–418](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/updateforcing.py:407); [model.py:222–228](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/model.py:222); [write_output.py:103–104](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_output.py:103).
- **Giới hạn E1:** bộ trường h/zs/zb/u/v được cung cấp thiếu thông tin về cả hai cum_infilt, mesh/layout và loop/observer state; không mở NetCDF nên đây không phải kiểm kê toàn bộ biến trong tệp.

**Monitoring hiện tại không phải checkpoint**

- **Mã:** supervisor lấy progress từ 16 KiB cuối log và cập nhật state khoảng mỗi 30 giây; observer tạo bộ đếm/ngân sách mới, không nạp snapshot cũ. [wrapper:72–83](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:72); [wrapper:146–150](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:146); [observer:26–47](D:/VTP/River_Bathymetry_Project/v49_runtime_observer.py:26).
- **Mã:** observer ghi khi cách lần trước ≥60 giây wall time hoặc đạt endtime, ghi đè snapshot; timestamp là loop.totaltime+loop.dt, không chứa arrays hay full loop state. [observer:134–148](D:/VTP/River_Bathymetry_Project/v49_runtime_observer.py:134).
- **Mã/suy luận:** hook observer kết thúc trong flow_gpu, trước tăng time/deform/meanmax/TS/map/reset của main_loop; snapshot này không đại diện checkpoint sau toàn bộ bookkeeping. [observer:134–149](D:/VTP/River_Bathymetry_Project/v49_runtime_observer.py:134); [mainloop.py:175–205](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/mainloop.py:175).
- **Mã/suy luận:** atomic_json dùng .tmp rồi replace, không có fsync/commit bảo đảm lưu bền vững, hai generation hay khóa; không có cơ sở bảo đảm durability khi mất điện. [observer:15–18](D:/VTP/River_Bathymetry_Project/v49_runtime_observer.py:15).
- **Mã/suy luận:** writer sync/close mỗi frame giúp giải phóng file và hỗ trợ salvage, không chứng minh frame/checkpoint atomic khi mất điện. [write_output.py:195–196](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_output.py:195).

**Đề xuất attempt và queue tương lai — toàn bộ chưa thực hiện**

- Cô lập attempt mới trong thư mục/tên riêng cho config, manifest, result, mọi log/budget/metrics/state; giữ nguyên toàn bộ chứng cứ attempt gốc.
- Ghi parent_attempt_id, lý do gián đoạn, hashes input/code/runtime/config, checkpoint id/hash/schema/time/step, output lineage và loại restart: cold/approximate/exact-tested.
- Dùng nhãn đề xuất INTERRUPTED → RESUME_PLANNED → RUNNING cho attempt mới; lưu liên hệ cha/con. Các nhãn INTERRUPTED/RESUME_PLANNED hiện chưa có trong wrapper.
- Reconcile queue mới từ bằng chứng hoàn thành được kiểm tra, giữ đủ CENTRAL/LOW/HIGH/BASE; không dùng RUNNING cũ hay tồn tại output làm tiêu chí bỏ qua arm.
- Chặn va chạm mọi tệp trước ghi state; ràng buộc lock/PID với identity và thời điểm tạo process. pid_alive hiện chỉ kiểm tra PID còn hoạt động. [wrapper:30–45](D:/VTP/River_Bathymetry_Project/v49_run_hydraulic_validation.py:30).
- Tách trạng thái tiến trình, hoàn thành mô phỏng, numerical checks, hydraulic evaluation và acceptance; không tự đổi gate_g_pass/promotion chỉ vì restart thành công.

**Đề xuất checkpoint tối thiểu và commit bền vững**

- Chỉ chụp ở ranh giới full-step xác định, sau time/deform/output/observer bookkeeping, không giữa predictor/corrector. Cơ sở thứ tự: [mainloop.py:168–205](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/mainloop.py:168).
- Lưu raw current Evolving float64 với dtype/shape đầy đủ vector block và halo; bảo toàn riêng cả evolv.cum_infilt và evolv_o.cum_infilt.
- Predictor h/zs/u/v và scratch gradient/flux/dtmax chỉ được bỏ nếu kiểm thử chứng minh tái tính quyết định tại ranh giới bước; dtmax được reset mỗi predictor, không mặc định là trạng thái thủy động lực phải lưu. [flow_gpu.py:458–469](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/flow_gpu.py:458).
- Lưu mesh/static/maps hoặc tái dựng có xác minh hash và layout/index chính xác; lưu các trường vật lý thay đổi nếu có deformation.
- Lưu exact t/dt/nextoutputtime/counters, mean/max và TS buffers khi hoạt động; không dùng init_loop để vô tình reset lịch/counter.
- Với forcing, giữ đúng input hash và absolute time; lưu cached state khi không tái dựng. Không có bằng chứng rainstep lịch sử bắt buộc vì uniform forcing chọn lại mỗi call. [forcing_update.py:31–63](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/forcing_update.py:31).
- Lưu cumulative observer budget đồng bộ cùng checkpoint; nếu chỉ phân đoạn monitoring thì ghi rõ phạm vi thời gian, không ghép budget 35.4 giờ vào frame 33 giờ như trạng thái tương ứng.
- Schema có version, metadata/hash/shape/dtype/step/time đầy đủ; ghi .tmp → flush/fsync → close → xác minh hoàn chỉnh → atomic rename, rồi đánh dấu commit.
- Giữ hai generation và manifest/commit marker có hashes; reject checkpoint thiếu/không nhất quán. Đây là thiết kế tăng khả năng phục hồi, không cam kết tuyệt đối với HDF5/filesystem khi mất điện.
- Giữ cùng backend/GPU, môi trường, reductions, input/code hashes; chỉ gọi exact khi phục hồi và tái chạy vượt kiểm thử tương đương.

**Đề xuất kiểm thử và phạm vi được phép hiện tại**

- Dựng thử nghiệm ngắn tách biệt: baseline không gián đoạn so với tiến trình thứ hai commit checkpoint rồi bị cưỡng bức ngắt; sau đó một tiến trình mới nạp checkpoint, chạy tiếp và đối chiếu phần đuôi căn thời gian; chọn checkpoint không trùng lịch map output.
- Bao phủ wet/dry, rainfall/infiltration, boundary/river, đi qua forcing knots; so bitwise trạng thái bộ nhớ cần bảo toàn, chuỗi time/dt, diagnostics và output căn thời gian.
- Nếu chỉ đạt tolerance, ghi rõ approximate restart và sai khác chấp nhận; không gắn nhãn exact. Thử ngắt/truncate trước commit phải còn đọc được generation cũ.
- Những kiểm thử, viết loader/checkpoint, restart, chạy lại và phục hồi queue đều là đề xuất hoãn lại; chưa chạy thử hay thay cấu hình/trạng thái nào.
- Công việc hiện được phép là nghiên cứu source và salvage/phân tích bằng chứng; nhánh chính sở hữu đọc dữ liệu/so sánh số. Báo cáo này là tệp mới duy nhất được tạo.
- Acceptance vẫn cần bằng chứng và đánh giá riêng; evaluator hiện giữ gate_g_pass=False và hydraulic_promotion_ready=False kể cả có đủ metrics. [evaluate:163–167](D:/VTP/River_Bathymetry_Project/v49_evaluate_hydraulic_validation.py:163).
