# Comprehensive Import Analysis Report

**Generated:** 2025-06-08 00:15:59

## Summary Statistics

- **Files scanned:** 1260
- **Files with errors:** 0
- **Unique stdlib imports:** 311
- **Unique external imports:** 661
- **Unique internal imports:** 1467

## External Dependencies

These are third-party packages that need to be installed:

| Package | Usage Count | Files Using |
|---------|-------------|-------------|
| `numpy` | 290 | 290 files |
| `pytest` | 56 | 56 files |
| `torch` | 42 | 42 files |
| `__future__.annotations` | 34 | 34 files |
| `requests` | 31 | 31 files |
| `capnp` | 27 | 27 files |
| `tqdm.tqdm` | 25 | 25 files |
| `opendbc.can.parser.CANParser` | 25 | 25 files |
| `PIL.Image` | 23 | 23 files |
| `opendbc.can.packer.CANPacker` | 18 | 18 files |
| `parameterized.parameterized` | 16 | 16 files |
| `hexdump.hexdump` | 16 | 16 files |
| `hypothesis.strategies` | 15 | 15 files |
| `hypothesis.given` | 14 | 14 files |
| `hypothesis.settings` | 14 | 14 files |
| `matplotlib.pyplot` | 13 | 13 files |
| `onnx` | 13 | 13 files |
| `opendbc.can.can_define.CANDefine` | 12 | 12 files |
| `extra.optimization.helpers.load_worlds` | 12 | 12 files |
| `abc.ABC` | 11 | 11 files |
| `abc.abstractmethod` | 11 | 11 files |
| `extra.optimization.helpers.ast_str_to_lin` | 11 | 11 files |
| `aiortc` | 10 | 10 files |
| `tensorflow` | 10 | 10 files |
| `parameterized.parameterized_class` | 9 | 9 files |
| `cv2` | 9 | 9 files |
| `extra.datasets.fetch_mnist` | 9 | 9 files |
| `utils.casadi_length` | 8 | 8 files |
| `extra.onnx.get_run_onnx` | 8 | 8 files |
| `extra.lr_scheduler.OneCycleLR` | 8 | 8 files |
| `tqdm.trange` | 7 | 7 files |
| `casadi` | 7 | 7 files |
| `sympy` | 7 | 7 files |
| `onnxruntime` | 7 | 7 files |
| `extra.models.efficientnet.EfficientNet` | 7 | 7 files |
| `setproctitle.setproctitle` | 6 | 6 files |
| `usb1` | 6 | 6 files |
| `extra.training.train` | 6 | 6 files |
| `extra.models.resnet.ResNet50` | 6 | 6 files |
| `sentencepiece.SentencePieceProcessor` | 6 | 6 files |
| `extra.optimization.helpers.lin_to_feats` | 6 | 6 files |
| `zmq` | 5 | 5 files |
| `pyaudio` | 5 | 5 files |
| `constants.McuType` | 5 | 5 files |
| `utils.is_empty` | 5 | 5 files |
| `check_reformulation.check_reformulation` | 5 | 5 files |
| `extra.training.evaluate` | 5 | 5 files |
| `extra.models.llama.Transformer` | 5 | 5 files |
| `extra.models.resnet.ResNet` | 5 | 5 files |
| `tiktoken` | 5 | 5 files |
| `extra.datasets.imagenet.get_val_files` | 5 | 5 files |
| `SCons` | 4 | 4 files |
| `SCons.Action.Action` | 4 | 4 files |
| `SCons.Scanner.Scanner` | 4 | 4 files |
| `psutil` | 4 | 4 files |
| `errno` | 4 | 4 files |
| `aiortc.mediastreams.AudioStreamTrack` | 4 | 4 files |
| `flaky.flaky` | 4 | 4 files |
| `base.BaseHandle` | 4 | 4 files |
| `cffi.FFI` | 4 | 4 files |
| `acados_model.AcadosModel` | 4 | 4 files |
| `utils.get_lib_ext` | 4 | 4 files |
| `casadi.SX` | 4 | 4 files |
| `determine_input_nonlinearity_function.determine_input_nonlinearity_function` | 4 | 4 files |
| `jinja2` | 4 | 4 files |
| `extra.models.vit.ViT` | 4 | 4 files |
| `extra.models.llama.convert_from_huggingface` | 4 | 4 files |
| `extra.models.llama.fix_bf16` | 4 | 4 files |
| `onnx.helper.tensor_dtype_to_np_dtype` | 4 | 4 files |
| `torch.mps` | 4 | 4 files |
| `examples.hlb_cifar10.UnsyncedBatchNorm` | 4 | 4 files |
| `examples.mlperf.metrics.dice_score` | 4 | 4 files |
| `extra.datasets.imagenet.get_train_files` | 4 | 4 files |
| `extra.hip_gpu_driver.hip_ioctl` | 4 | 4 files |
| `extra.qcom_gpu_driver.opencl_ioctl` | 4 | 4 files |
| `extra.nv_gpu_driver.nv_ioctl` | 4 | 4 files |
| `examples.llama.Transformer` | 4 | 4 files |
| `__future__.absolute_import` | 4 | 4 files |
| `__future__.division` | 4 | 4 files |
| `__future__.print_function` | 4 | 4 files |
| `serial` | 3 | system/ugpsd.py, system/ubloxd/pigeond.py, system/hardware/tici/esim.py |
| `setuptools.setup` | 3 | panda/setup.py, rednose_repo/setup.py, tinygrad_repo/setup.py |
| `PyQt5.QtWidgets.QApplication` | 3 | scripts/pyqt_demo.py, selfdrive/test/ciui.py, selfdrive/ui/ui.py |
| `PyQt5.QtWidgets.QLabel` | 3 | scripts/pyqt_demo.py, selfdrive/test/ciui.py, selfdrive/ui/ui.py |
| `azure.storage.fileshare.ShareFileClient` | 3 | tools/azure_upload_tiles.py, system/athena/athenad.py, selfdrive/frogpilot/frogpilot_utilities.py |
| `azure.storage.fileshare.ShareDirectoryClient` | 3 | tools/azure_upload_tiles.py, system/athena/athenad.py, selfdrive/frogpilot/frogpilot_utilities.py |
| `azure.core.exceptions.ResourceNotFoundError` | 3 | tools/azure_upload_tiles.py, system/athena/athenad.py, selfdrive/frogpilot/frogpilot_utilities.py |
| `azure.core.exceptions.ResourceExistsError` | 3 | tools/azure_upload_tiles.py, system/athena/athenad.py, selfdrive/frogpilot/frogpilot_utilities.py |
| `tabulate.tabulate` | 3 | tinygrad_repo/sz.py, system/hardware/tici/tests/test_power_draw.py, tinygrad_repo/examples/self_tokenize.py |
| `aiortc.mediastreams.VideoStreamTrack` | 3 | system/webrtc/webrtcd.py, teleoprtc_repo/tests/test_integration.py, teleoprtc_repo/examples/videostream_cli/cli.py |
| `Crypto.PublicKey.RSA` | 3 | system/athena/tests/test_registration.py, panda/crypto/sign.py, body/crypto/sign.py |
| `av` | 3 | system/webrtc/device/audio.py, system/webrtc/device/video.py, tools/camerastream/compressed_vipc.py |
| `abc` | 3 | teleoprtc_repo/teleoprtc/stream.py, teleoprtc_repo/teleoprtc/builder.py, panda/tests/safety/common.py |
| `pygame` | 3 | teleoprtc_repo/examples/face_detection/face_detection.py, tools/replay/ui.py, tools/replay/lib/ui_helpers.py |
| `base.BaseSTBootloaderHandle` | 3 | panda/python/spi.py, panda/python/usb.py, panda/python/dfu.py |
| `utils.get_acados_path` | 3 | third_party/acados/acados_template/acados_ocp.py, third_party/acados/acados_template/acados_sim.py, third_party/acados/acados_template/__init__.py |
| `acados_ocp.AcadosOcp` | 3 | third_party/acados/acados_template/__init__.py, third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `utils.get_python_interface_path` | 3 | third_party/acados/acados_template/__init__.py, third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `utils.check_casadi_version` | 3 | third_party/acados/acados_template/__init__.py, third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `utils.make_object_json_dumpable` | 3 | third_party/acados/acados_template/__init__.py, third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `casadi.vertcat` | 3 | third_party/acados/acados_template/gnsf/detect_gnsf_structure.py, selfdrive/controls/lib/lateral_mpc_lib/lat_mpc.py, selfdrive/controls/lib/longitudinal_mpc_lib/long_mpc.py |
| `google.protobuf.descriptor` | 3 | selfdrive/frogpilot/navigation/mapd_py/osm_speed_data_pb2.py, tools/map_processing/osm_speed_data_pb2.py, tinygrad_repo/extra/junk/sentencepiece_model_pb2.py |
| `google.protobuf.descriptor_pool` | 3 | selfdrive/frogpilot/navigation/mapd_py/osm_speed_data_pb2.py, tools/map_processing/osm_speed_data_pb2.py, tinygrad_repo/extra/junk/sentencepiece_model_pb2.py |
| `google.protobuf.symbol_database` | 3 | selfdrive/frogpilot/navigation/mapd_py/osm_speed_data_pb2.py, tools/map_processing/osm_speed_data_pb2.py, tinygrad_repo/extra/junk/sentencepiece_model_pb2.py |
| `google.protobuf.internal.builder` | 3 | selfdrive/frogpilot/navigation/mapd_py/osm_speed_data_pb2.py, tools/map_processing/osm_speed_data_pb2.py, tinygrad_repo/extra/junk/sentencepiece_model_pb2.py |
| `crcmod` | 3 | selfdrive/car/hyundai/hyundaican.py, selfdrive/car/nissan/nissancan.py, selfdrive/car/tesla/teslacan.py |
| `hypothesis.Phase` | 3 | selfdrive/car/tests/test_models.py, selfdrive/car/tests/test_car_interfaces.py, selfdrive/test/process_replay/test_fuzzy.py |
| `pyopencl` | 3 | selfdrive/test/process_replay/test_imgproc.py, tools/sim/lib/camerad.py, tinygrad_repo/extra/thneed.py |
| `extra.models.unet.UNetModel` | 3 | tinygrad_repo/examples/stable_diffusion.py, tinygrad_repo/examples/sdxl.py, tinygrad_repo/examples/sdv2.py |
| `soundfile` | 3 | tinygrad_repo/examples/so_vits_svc.py, tinygrad_repo/examples/sovits_helpers/preprocess.py, tinygrad_repo/extra/datasets/librispeech.py |
| `examples.mlperf.helpers.get_mlperf_bert_model` | 3 | tinygrad_repo/examples/handcode_opt.py, tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/test/external/mlperf_bert/external_test_checkpoint_loading.py |
| `yaml` | 3 | tinygrad_repo/examples/conversation.py, tinygrad_repo/extra/backends/rdna.py, tinygrad_repo/extra/assembly/assembly_rdna.py |
| `transformers.AutoTokenizer` | 3 | tinygrad_repo/examples/qwq.py, tinygrad_repo/examples/mamba.py, tinygrad_repo/test/external/external_test_mamba.py |
| `extra.export_model.export_model` | 3 | tinygrad_repo/examples/compile_efficientnet.py, tinygrad_repo/examples/webgpu/yolov8/compile.py, tinygrad_repo/test/testextra/test_export_model.py |
| `librosa` | 3 | tinygrad_repo/examples/whisper.py, tinygrad_repo/examples/sovits_helpers/preprocess.py, tinygrad_repo/extra/datasets/librispeech.py |
| `extra.models.mask_rcnn.MaskRCNN` | 3 | tinygrad_repo/examples/mask_rcnn.py, tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/examples/mlperf/model_spec.py |
| `torch.nn.functional` | 3 | tinygrad_repo/examples/mask_rcnn.py, tinygrad_repo/extra/datasets/kits19.py, tinygrad_repo/test/external/mlperf_unet3d/dice.py |
| `extra.models.unet3d.UNet3D` | 3 | tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/examples/mlperf/model_spec.py |
| `extra.datasets.kits19.iterate` | 3 | tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/test/external/external_test_datasets.py |
| `extra.datasets.kits19.get_val_files` | 3 | tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/examples/mlperf/dataloader.py |
| `extra.models.bert.BertForQuestionAnswering` | 3 | tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/examples/mlperf/model_spec.py, tinygrad_repo/test/models/test_bert.py |
| `wandb` | 3 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/examples/mlperf/model_train.py |
| `extra.models.resnet` | 3 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/test/models/test_resnet.py, tinygrad_repo/test/external/external_benchmark_resnet.py |
| `examples.mlperf.lr_schedulers.PolynomialDecayWithWarmup` | 3 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/test/external/external_test_optim.py |
| `mlx.core` | 3 | tinygrad_repo/examples/other_mnist/beautiful_mnist_mlx.py, tinygrad_repo/extra/resnet18/resnet_mlx.py, tinygrad_repo/extra/gemm/mlx_matmul.py |
| `torch.nn` | 3 | tinygrad_repo/examples/other_mnist/beautiful_mnist_torch.py, tinygrad_repo/test/models/test_end2end.py, tinygrad_repo/test/external/mlperf_unet3d/dice.py |
| `extra.optimization.pretrain_valuenet.ValueNet` | 3 | tinygrad_repo/extra/optimization/extract_sa_pairs.py, tinygrad_repo/extra/optimization/test_net.py, tinygrad_repo/extra/optimization/run_qnet.py |
| `ane.ANE` | 3 | tinygrad_repo/extra/accel/ane/2_compile/struct_recover.py, tinygrad_repo/extra/accel/ane/2_compile/hwx_parse.py, tinygrad_repo/extra/accel/ane/lib/testconv.py |
| `tensorflow.python.ops.math_ops` | 3 | tinygrad_repo/test/external/external_test_optim.py, tinygrad_repo/test/external/mlperf_resnet/lars_util.py, tinygrad_repo/test/external/mlperf_resnet/lars_optimizer.py |
| `sounddevice` | 2 | system/micd.py, selfdrive/ui/soundd.py |
| `stat` | 2 | scripts/code_stats.py, system/updated/tests/test_base.py |
| `jwt` | 2 | system/athena/registration.py, common/api/__init__.py |
| `zstandard` | 2 | system/athena/athenad.py, selfdrive/frogpilot/frogpilot_functions.py |
| `aiohttp.web` | 2 | system/webrtc/webrtcd.py, tools/bodyteleop/web.py |
| `aiortc.mediastreams.VIDEO_CLOCK_RATE` | 2 | system/webrtc/tests/test_stream_session.py, teleoprtc_repo/teleoprtc/tracks.py |
| `aiortc.mediastreams.VIDEO_TIME_BASE` | 2 | system/webrtc/tests/test_stream_session.py, teleoprtc_repo/teleoprtc/tracks.py |
| `constants.FW_PATH` | 2 | panda/python/__init__.py, panda/python/dfu.py |
| `spi.PandaSpiException` | 2 | panda/python/__init__.py, panda/python/dfu.py |
| `base.TIMEOUT` | 2 | panda/python/spi.py, panda/python/usb.py |
| `termcolor.cprint` | 2 | panda/board/jungle/scripts/echo_loopback_test.py, panda/board/jungle/scripts/loopback_test.py |
| `utils.J_to_idx` | 2 | third_party/acados/acados_template/acados_ocp.py, third_party/acados/acados_template/__init__.py |
| `acados_sim.AcadosSim` | 2 | third_party/acados/acados_template/__init__.py, third_party/acados/acados_template/acados_sim_solver.py |
| `utils.print_casadi_expression` | 2 | third_party/acados/acados_template/__init__.py, third_party/acados/acados_template/gnsf/detect_affine_terms_reduce_nonlinearity.py |
| `casadi_function_generation.generate_c_code_explicit_ode` | 2 | third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `casadi_function_generation.generate_c_code_implicit_ode` | 2 | third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `casadi_function_generation.generate_c_code_gnsf` | 2 | third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `gnsf.detect_gnsf_structure.detect_gnsf_structure` | 2 | third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `utils.is_column` | 2 | third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `utils.render_template` | 2 | third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `utils.format_class_dict` | 2 | third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `utils.make_model_consistent` | 2 | third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `utils.set_up_imported_gnsf_model` | 2 | third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `builders.CMakeBuilder` | 2 | third_party/acados/acados_template/acados_ocp_solver.py, third_party/acados/acados_template/acados_sim_solver.py |
| `casadi.Function` | 2 | third_party/acados/acados_template/utils.py, third_party/acados/acados_template/gnsf/detect_gnsf_structure.py |
| `utils.idx_perm_to_ipiv` | 2 | third_party/acados/acados_template/gnsf/determine_trivial_gnsf_transcription.py, third_party/acados/acados_template/gnsf/reformulate_with_LOS.py |
| `pandas` | 2 | selfdrive/debug/can_table.py, tinygrad_repo/extra/datasets/openimages.py |
| `filecmp` | 2 | selfdrive/frogpilot/frogpilot_functions.py, opendbc/generator/test_generator.py |
| `PyQt5.QtCore.QTimer` | 2 | selfdrive/test/ciui.py, selfdrive/ui/ui.py |
| `PyQt5.QtWidgets.QWidget` | 2 | selfdrive/test/ciui.py, selfdrive/ui/ui.py |
| `PyQt5.QtWidgets.QVBoxLayout` | 2 | selfdrive/test/ciui.py, selfdrive/ui/ui.py |
| `uvicorn` | 2 | selfdrive/chauffeur/concierge/main.py, selfdrive/chauffeur/concierge/main.py |
| `flask.Flask` | 2 | selfdrive/frogpilot/fleetmanager/fleet_manager.py, tools/web/app.py |
| `flask.Response` | 2 | selfdrive/frogpilot/fleetmanager/fleet_manager.py, tools/web/app.py |
| `flask.render_template` | 2 | selfdrive/frogpilot/fleetmanager/fleet_manager.py, tools/web/app.py |
| `flask.send_from_directory` | 2 | selfdrive/frogpilot/fleetmanager/fleet_manager.py, tools/web/app.py |
| `shapely.geometry.Point` | 2 | selfdrive/frogpilot/navigation/mapd_py/mapd_daemon.py, selfdrive/frogpilot/navigation/mapd_py/reader.py |
| `rtree.index` | 2 | selfdrive/frogpilot/navigation/mapd_py/matcher.py, selfdrive/frogpilot/navigation/mapd_py/reader.py |
| `logging_utils.log_event` | 2 | selfdrive/frogpilot/navigation/mapd_py/matcher.py, selfdrive/frogpilot/navigation/mapd_py/reader.py |
| `google.protobuf.runtime_version` | 2 | selfdrive/frogpilot/navigation/mapd_py/osm_speed_data_pb2.py, tools/map_processing/osm_speed_data_pb2.py |
| `opendbc.DBC_PATH` | 2 | selfdrive/car/hyundai/values.py, opendbc/can/tests/__init__.py |
| `numbers` | 2 | selfdrive/test/process_replay/compare_logs.py, cereal/messaging/tests/test_messaging.py |
| `hypothesis.HealthCheck` | 2 | selfdrive/test/process_replay/test_fuzzy.py, tinygrad_repo/test/test_dtype_alu.py |
| `pyautogui` | 2 | selfdrive/ui/tests/test_ui/run.py, selfdrive/ui/tests/test_ui/run.py |
| `opendbc.can.parser_pyx.CANDefine` | 2 | opendbc/can/can_define.py, opendbc/can/parser.py |
| `opendbc.generator.tesla.radar_common.get_radar_point_definition` | 2 | opendbc/generator/tesla/tesla_radar_continental.py, opendbc/generator/tesla/tesla_radar_bosch.py |
| `opendbc.generator.tesla.radar_common.get_val_definition` | 2 | opendbc/generator/tesla/tesla_radar_continental.py, opendbc/generator/tesla/tesla_radar_bosch.py |
| `opendbc.can.tests.ALL_DBCS` | 2 | opendbc/can/tests/test_define.py, opendbc/can/tests/test_dbc_parser.py |
| `opendbc.can.tests.TEST_DBC` | 2 | opendbc/can/tests/test_dbc_exceptions.py, opendbc/can/tests/test_packer_parser.py |
| `opendbc.can.tests.test_packer_parser.can_list_to_can_capnp` | 2 | opendbc/can/tests/test_parser_performance.py, opendbc/can/tests/test_checksums.py |
| `webbrowser` | 2 | tools/lib/auth.py, tinygrad_repo/tinygrad/viz/serve.py |
| `tqdm` | 2 | tools/lib/logreader.py, tinygrad_repo/test/external/external_test_whisper_librispeech.py |
| `extra.models.transformer.Transformer` | 2 | tinygrad_repo/examples/transformer.py, tinygrad_repo/test/models/test_train.py |
| `gymnasium` | 2 | tinygrad_repo/examples/beautiful_cartpole.py, tinygrad_repo/examples/rl/lightupbutton.py |
| `extra.junk.sentencepiece_model_pb2` | 2 | tinygrad_repo/examples/conversation.py, tinygrad_repo/examples/coder.py |
| `extra.models.clip.FrozenClosedClipEmbedder` | 2 | tinygrad_repo/examples/sdxl.py, tinygrad_repo/examples/flux1.py |
| `extra.models.clip.FrozenOpenClipEmbedder` | 2 | tinygrad_repo/examples/sdxl.py, tinygrad_repo/examples/sdv2.py |
| `extra.models.llama.FeedForward` | 2 | tinygrad_repo/examples/mixtral.py, tinygrad_repo/test/external/external_test_llama3_ff.py |
| `tiktoken.load.load_tiktoken_bpe` | 2 | tinygrad_repo/examples/llama.py, tinygrad_repo/examples/llama3.py |
| `torchvision.transforms` | 2 | tinygrad_repo/examples/mask_rcnn.py, tinygrad_repo/test/external/mlperf_unet3d/kits19.py |
| `torchvision.transforms.functional` | 2 | tinygrad_repo/examples/mask_rcnn.py, tinygrad_repo/extra/datasets/openimages.py |
| `extra.export_model.compile_net` | 2 | tinygrad_repo/examples/compile_tensorflow.py, tinygrad_repo/examples/webgpu/stable_diffusion/compile.py |
| `extra.export_model.jit_model` | 2 | tinygrad_repo/examples/compile_tensorflow.py, tinygrad_repo/examples/webgpu/stable_diffusion/compile.py |
| `examples.vgg7_helpers.waifu2x.image_load` | 2 | tinygrad_repo/examples/vgg7.py, tinygrad_repo/test/models/test_waifu2x.py |
| `examples.vgg7_helpers.waifu2x.Vgg7` | 2 | tinygrad_repo/examples/vgg7.py, tinygrad_repo/test/models/test_waifu2x.py |
| `examples.beautiful_mnist.Model` | 2 | tinygrad_repo/examples/stunning_mnist.py, tinygrad_repo/test/models/test_real_world.py |
| `networkx` | 2 | tinygrad_repo/extra/mcts_search.py, tinygrad_repo/extra/accel/ane/2_compile/dcompile.py |
| `resnet.ResNet18` | 2 | tinygrad_repo/test/test_multitensor.py, tinygrad_repo/test/test_multitensor.py |
| `extra.models.unet.ResBlock` | 2 | tinygrad_repo/test/test_jit.py, tinygrad_repo/test/models/test_real_world.py |
| `examples.gpt2.Transformer` | 2 | tinygrad_repo/test/test_method_cache.py, tinygrad_repo/test/models/test_real_world.py |
| `examples.mlperf.dataloader.batch_load_resnet` | 2 | tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/examples/mlperf/model_train.py |
| `extra.datasets.kits19.sliding_window_inference` | 2 | tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/examples/mlperf/model_train.py |
| `extra.models.resnet.ResNeXt50_32X4D` | 2 | tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/extra/models/retinanet.py |
| `extra.models.retinanet.RetinaNet` | 2 | tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/examples/mlperf/model_spec.py |
| `pycocotools.coco.COCO` | 2 | tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/extra/datasets/coco.py |
| `pycocotools.cocoeval.COCOeval` | 2 | tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/extra/datasets/coco.py |
| `extra.models.rnnt.RNNT` | 2 | tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/examples/mlperf/model_spec.py |
| `transformers.BertTokenizer` | 2 | tinygrad_repo/examples/mlperf/model_eval.py, tinygrad_repo/extra/datasets/squad.py |
| `mlperf_logging.mllog.constants` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/examples/mlperf/model_train.py |
| `extra.lr_scheduler.LRSchedulerGroup` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/test/external/external_test_optim.py |
| `examples.mlperf.initializers.Conv2dHeNormal` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/test/external/external_benchmark_resnet.py |
| `examples.mlperf.initializers.Linear` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/test/external/external_benchmark_resnet.py |
| `mlperf_logging.mllog` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/examples/mlperf/model_train.py |
| `examples.mlperf.losses.dice_ce_loss` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/test/external/external_test_losses.py |
| `examples.mlperf.dataloader.batch_load_unet3d` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/test/external/external_test_datasets.py |
| `extra.datasets.kits19.get_train_files` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/examples/mlperf/dataloader.py |
| `extra.datasets.kits19.preprocess_dataset` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/examples/mlperf/dataloader.py |
| `extra.datasets.kits19.TRAIN_PREPROCESSED_DIR` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/examples/mlperf/dataloader.py |
| `extra.datasets.kits19.VAL_PREPROCESSED_DIR` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/examples/mlperf/dataloader.py |
| `examples.mlperf.dataloader.batch_load_val_bert` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/test/external/mlperf_bert/external_test_checkpoint_loading.py |
| `examples.mlperf.helpers.get_data_bert` | 2 | tinygrad_repo/examples/mlperf/model_train.py, tinygrad_repo/test/external/mlperf_bert/external_test_checkpoint_loading.py |
| `scipy.signal` | 2 | tinygrad_repo/examples/mlperf/helpers.py, tinygrad_repo/extra/datasets/kits19.py |
| `extra.models.bert` | 2 | tinygrad_repo/examples/mlperf/helpers.py, tinygrad_repo/test/external/mlperf_bert/external_benchmark_bert.py |
| `mlx.nn` | 2 | tinygrad_repo/examples/other_mnist/beautiful_mnist_mlx.py, tinygrad_repo/extra/resnet18/resnet_mlx.py |
| `examples.yolov8.YOLOv8` | 2 | tinygrad_repo/examples/webgpu/yolov8/compile.py, tinygrad_repo/test/external/external_test_yolov8.py |
| `extra.f16_decompress.u32_to_f16` | 2 | tinygrad_repo/examples/webgpu/stable_diffusion/compile.py, tinygrad_repo/test/testextra/test_f16_decompress.py |
| `examples.stable_diffusion.StableDiffusion` | 2 | tinygrad_repo/examples/webgpu/stable_diffusion/compile.py, tinygrad_repo/test/external/external_benchmark_load_stable_diffusion.py |
| `nibabel` | 2 | tinygrad_repo/extra/datasets/kits19.py, tinygrad_repo/test/external/external_test_datasets.py |
| `scipy.ndimage` | 2 | tinygrad_repo/extra/datasets/kits19.py, tinygrad_repo/test/external/mlperf_unet3d/kits19.py |
| `triton.compiler.compile` | 2 | tinygrad_repo/extra/backends/triton.py, tinygrad_repo/extra/gemm/triton_nv_matmul.py |
| `huggingface_hub.snapshot_download` | 2 | tinygrad_repo/extra/resnet18/resnet_tinygrad.py, tinygrad_repo/extra/resnet18/resnet_mlx.py |
| `extra.optimization.extract_policynet.PolicyNet` | 2 | tinygrad_repo/extra/optimization/test_net.py, tinygrad_repo/extra/optimization/rl.py |
| `extra.helpers.enable_early_exec` | 2 | tinygrad_repo/extra/assembly/assembly_rdna.py, tinygrad_repo/extra/assembly/rocm/rdna3/asm.py |
| `llvmlite.binding` | 2 | tinygrad_repo/extra/dsp/compile.py, tinygrad_repo/tinygrad/runtime/ops_llvm.py |
| `jax` | 2 | tinygrad_repo/extra/gemm/jax_pmatmul.py, tinygrad_repo/test/unit/test_gradient.py |
| `jax.numpy` | 2 | tinygrad_repo/extra/gemm/jax_pmatmul.py, tinygrad_repo/test/unit/test_gradient.py |
| `onnx2torch.convert` | 2 | tinygrad_repo/test/models/test_onnx.py, tinygrad_repo/test/external/external_model_benchmark.py |
| `extra.models.convnext.ConvNeXt` | 2 | tinygrad_repo/test/models/test_train.py, tinygrad_repo/test/external/external_test_opt.py |
| `extra.models.resnet.ResNet18` | 2 | tinygrad_repo/test/models/test_train.py, tinygrad_repo/test/external/external_test_opt.py |
| `examples.stable_diffusion.UNetModel` | 2 | tinygrad_repo/test/models/test_real_world.py, tinygrad_repo/test/external/external_test_jit_on_models.py |
| `examples.stable_diffusion.unet_params` | 2 | tinygrad_repo/test/models/test_real_world.py, tinygrad_repo/test/external/external_test_jit_on_models.py |
| `examples.whisper.init_whisper` | 2 | tinygrad_repo/test/models/test_whisper.py, tinygrad_repo/test/external/external_test_whisper_librispeech.py |
| `examples.whisper.transcribe_waveform` | 2 | tinygrad_repo/test/models/test_whisper.py, tinygrad_repo/test/external/external_test_whisper_librispeech.py |
| `extra.optimization.helpers.kern_str_to_lin` | 2 | tinygrad_repo/test/external/verify_kernel.py, tinygrad_repo/test/external/fuzz_linearizer.py |
| `safetensors.torch.save_file` | 2 | tinygrad_repo/test/unit/test_disk_tensor.py, tinygrad_repo/test/unit/test_disk_tensor.py |
| `safetensors.safe_open` | 2 | tinygrad_repo/test/unit/test_disk_tensor.py, tinygrad_repo/test/unit/test_disk_tensor.py |
| `absl.flags` | 2 | tinygrad_repo/test/external/mlperf_resnet/lars_util.py, tinygrad_repo/test/external/mlperf_bert/preprocessing/tokenization.py |
| `tensorflow.python.framework.ops` | 2 | tinygrad_repo/test/external/mlperf_resnet/lars_util.py, tinygrad_repo/test/external/mlperf_resnet/lars_optimizer.py |
| `timezonefinder.TimezoneFinder` | 1 | system/timed.py |
| `sentry_sdk` | 1 | system/sentry.py |
| `sentry_sdk.integrations.threading.ThreadingIntegration` | 1 | system/sentry.py |
| `setproctitle.getproctitle` | 1 | common/realtime.py |
| `python.constants.McuType` | 1 | panda/__init__.py |
| `python.constants.BASEDIR` | 1 | panda/__init__.py |
| `python.constants.FW_PATH` | 1 | panda/__init__.py |
| `python.constants.USBPACKET_MAX_SIZE` | 1 | panda/__init__.py |
| `python.spi.PandaSpiException` | 1 | panda/__init__.py |
| `python.spi.PandaProtocolMismatch` | 1 | panda/__init__.py |
| `python.spi.STBootloaderSPIHandle` | 1 | panda/__init__.py |
| `python.serial.PandaSerial` | 1 | panda/__init__.py |
| `python.canhandle.CanHandle` | 1 | panda/__init__.py |
| `python.Panda` | 1 | panda/__init__.py |
| `python.PandaDFU` | 1 | panda/__init__.py |
| `python.pack_can_buffer` | 1 | panda/__init__.py |
| `python.unpack_can_buffer` | 1 | panda/__init__.py |
| `python.calculate_checksum` | 1 | panda/__init__.py |
| `python.DLC_TO_LEN` | 1 | panda/__init__.py |
| `python.LEN_TO_DLC` | 1 | panda/__init__.py |
| `python.ALTERNATIVE_EXPERIENCE` | 1 | panda/__init__.py |
| `python.CANPACKET_HEAD_SIZE` | 1 | panda/__init__.py |
| `board.jungle.PandaJungle` | 1 | panda/__init__.py |
| `board.jungle.PandaJungleDFU` | 1 | panda/__init__.py |
| `setuptools.find_packages` | 1 | rednose_repo/setup.py |
| `zoneinfo.ZoneInfo` | 1 | system/updated/updated.py |
| `azure.core.exceptions.ServiceResponseError` | 1 | system/athena/athenad.py |
| `aiortc.rtcdatachannel.RTCDataChannel` | 1 | system/webrtc/webrtcd.py |
| `aiortc.exceptions.InvalidStateError` | 1 | system/webrtc/webrtcd.py |
| `aiortc.contrib.media.MediaBlackhole` | 1 | system/webrtc/webrtcd.py |
| `serial.Serial` | 1 | system/qcomgpsd/modemdiag.py |
| `crcmod.mkCrcFun` | 1 | system/qcomgpsd/modemdiag.py |
| `Crypto.Hash.SHA512` | 1 | system/updated/casync/casync.py |
| `websocket.ABNF` | 1 | system/athena/tests/test_athenad.py |
| `websocket._exceptions.WebSocketConnectionClosedException` | 1 | system/athena/tests/test_athenad.py |
| `smbus2.SMBus` | 1 | system/hardware/tici/amplifier.py |
| `dbus` | 1 | system/hardware/tici/hardware.py |
| `aiortc.RTCDataChannel` | 1 | system/webrtc/tests/test_stream_session.py |
| `aiortc.contrib.media.MediaRelay` | 1 | teleoprtc_repo/teleoprtc/stream.py |
| `aiohttp` | 1 | teleoprtc_repo/examples/face_detection/face_detection.py |
| `dfu.PandaDFU` | 1 | panda/python/__init__.py |
| `isotp.isotp_send` | 1 | panda/python/__init__.py |
| `isotp.isotp_recv` | 1 | panda/python/__init__.py |
| `spi.PandaSpiHandle` | 1 | panda/python/__init__.py |
| `spi.PandaProtocolMismatch` | 1 | panda/python/__init__.py |
| `usb.PandaUsbHandle` | 1 | panda/python/__init__.py |
| `spidev` | 1 | panda/python/spi.py |
| `spidev2` | 1 | panda/python/spi.py |
| `constants.MCU_TYPE_BY_IDCODE` | 1 | panda/python/spi.py |
| `constants.USBPACKET_MAX_SIZE` | 1 | panda/python/spi.py |
| `spi.STBootloaderSPIHandle` | 1 | panda/python/dfu.py |
| `usb.STBootloaderUSBHandle` | 1 | panda/python/dfu.py |
| `utils.J_to_idx_slack` | 1 | third_party/acados/acados_template/acados_ocp.py |
| `acados_ocp.AcadosOcpConstraints` | 1 | third_party/acados/acados_template/__init__.py |
| `acados_ocp.AcadosOcpCost` | 1 | third_party/acados/acados_template/__init__.py |
| `acados_ocp.AcadosOcpDims` | 1 | third_party/acados/acados_template/__init__.py |
| `acados_ocp.AcadosOcpOptions` | 1 | third_party/acados/acados_template/__init__.py |
| `acados_sim.AcadosSimDims` | 1 | third_party/acados/acados_template/__init__.py |
| `acados_sim.AcadosSimOpts` | 1 | third_party/acados/acados_template/__init__.py |
| `acados_ocp_solver.AcadosOcpSolver` | 1 | third_party/acados/acados_template/__init__.py |
| `acados_ocp_solver.get_simulink_default_opts` | 1 | third_party/acados/acados_template/__init__.py |
| `acados_ocp_solver.ocp_get_default_cmake_builder` | 1 | third_party/acados/acados_template/__init__.py |
| `acados_sim_solver.AcadosSimSolver` | 1 | third_party/acados/acados_template/__init__.py |
| `acados_sim_solver.sim_get_default_cmake_builder` | 1 | third_party/acados/acados_template/__init__.py |
| `utils.get_tera_exec_path` | 1 | third_party/acados/acados_template/__init__.py |
| `utils.get_tera` | 1 | third_party/acados/acados_template/__init__.py |
| `utils.acados_dae_model_json_dump` | 1 | third_party/acados/acados_template/__init__.py |
| `utils.get_default_simulink_opts` | 1 | third_party/acados/acados_template/__init__.py |
| `zoro_description.ZoroDescription` | 1 | third_party/acados/acados_template/__init__.py |
| `zoro_description.process_zoro_description` | 1 | third_party/acados/acados_template/__init__.py |
| `casadi_function_generation.generate_c_code_discrete_dynamics` | 1 | third_party/acados/acados_template/acados_ocp_solver.py |
| `casadi_function_generation.generate_c_code_constraint` | 1 | third_party/acados/acados_template/acados_ocp_solver.py |
| `casadi_function_generation.generate_c_code_nls_cost` | 1 | third_party/acados/acados_template/acados_ocp_solver.py |
| `casadi_function_generation.generate_c_code_conl_cost` | 1 | third_party/acados/acados_template/acados_ocp_solver.py |
| `casadi_function_generation.generate_c_code_external_cost` | 1 | third_party/acados/acados_template/acados_ocp_solver.py |
| `utils.get_ocp_nlp_layout` | 1 | third_party/acados/acados_template/acados_ocp_solver.py |
| `casadi.MX` | 1 | third_party/acados/acados_template/utils.py |
| `casadi.DM` | 1 | third_party/acados/acados_template/utils.py |
| `casadi.CasadiMeta` | 1 | third_party/acados/acados_template/utils.py |
| `acados_template.utils.casadi_length` | 1 | third_party/acados/acados_template/gnsf/check_reformulation.py |
| `casadi.jacobian` | 1 | third_party/acados/acados_template/gnsf/detect_gnsf_structure.py |
| `casadi.horzcat` | 1 | third_party/acados/acados_template/gnsf/detect_gnsf_structure.py |
| `determine_trivial_gnsf_transcription.determine_trivial_gnsf_transcription` | 1 | third_party/acados/acados_template/gnsf/detect_gnsf_structure.py |
| `detect_affine_terms_reduce_nonlinearity.detect_affine_terms_reduce_nonlinearity` | 1 | third_party/acados/acados_template/gnsf/detect_gnsf_structure.py |
| `reformulate_with_LOS.reformulate_with_LOS` | 1 | third_party/acados/acados_template/gnsf/detect_gnsf_structure.py |
| `reformulate_with_invertible_E_mat.reformulate_with_invertible_E_mat` | 1 | third_party/acados/acados_template/gnsf/detect_gnsf_structure.py |
| `structure_detection_print_summary.structure_detection_print_summary` | 1 | third_party/acados/acados_template/gnsf/detect_gnsf_structure.py |
| `casadi.n_nodes` | 1 | third_party/acados/acados_template/gnsf/structure_detection_print_summary.py |
| `kinematic_kf.KinematicKalman` | 1 | rednose_repo/examples/test_kinematic_kf.py |
| `kinematic_kf.ObservationKind` | 1 | rednose_repo/examples/test_kinematic_kf.py |
| `kinematic_kf.States` | 1 | rednose_repo/examples/test_kinematic_kf.py |
| `SCons.Script.Dir` | 1 | rednose_repo/site_scons/site_tools/rednose_filter.py |
| `SCons.Script.File` | 1 | rednose_repo/site_scons/site_tools/rednose_filter.py |
| `numpy.dot` | 1 | rednose_repo/rednose/helpers/ekf_sym.py |
| `sympy.utilities.codegen` | 1 | rednose_repo/rednose/helpers/sympy_helpers.py |
| `scipy.stats.chi2` | 1 | rednose_repo/rednose/helpers/chi2_lookup.py |
| `sklearn.linear_model` | 1 | selfdrive/debug/toyota_eps_factor.py |
| `Crypto.Hash.CMAC` | 1 | selfdrive/car/secoc.py |
| `Crypto.Cipher.AES` | 1 | selfdrive/car/secoc.py |
| `tomllib` | 1 | selfdrive/car/interfaces.py |
| `natsort.natsorted` | 1 | selfdrive/car/docs.py |
| `polyline` | 1 | selfdrive/navd/map_renderer.py |
| `PyQt5.QtCore.Qt` | 1 | selfdrive/ui/ui.py |
| `PyQt5.QtWidgets.QStackedLayout` | 1 | selfdrive/ui/ui.py |
| `opendbc.car.car_helpers.get_demo_car_params` | 1 | selfdrive/tinygrad_modeld/tests/test_modeld.py |
| `shlex` | 1 | selfdrive/chauffeur/concierge/main.py |
| `zmq.asyncio` | 1 | selfdrive/chauffeur/concierge/main.py |
| `pydantic.BaseModel` | 1 | selfdrive/chauffeur/concierge/main.py |
| `fastapi.FastAPI` | 1 | selfdrive/chauffeur/concierge/main.py |
| `fastapi.Request` | 1 | selfdrive/chauffeur/concierge/main.py |
| `fastapi.HTTPException` | 1 | selfdrive/chauffeur/concierge/main.py |
| `fastapi.responses.HTMLResponse` | 1 | selfdrive/chauffeur/concierge/main.py |
| `fastapi.responses.FileResponse` | 1 | selfdrive/chauffeur/concierge/main.py |
| `fastapi.responses.StreamingResponse` | 1 | selfdrive/chauffeur/concierge/main.py |
| `fastapi.responses.PlainTextResponse` | 1 | selfdrive/chauffeur/concierge/main.py |
| `fastapi.staticfiles.StaticFiles` | 1 | selfdrive/chauffeur/concierge/main.py |
| `jinja2.Environment` | 1 | selfdrive/chauffeur/concierge/main.py |
| `jinja2.FileSystemLoader` | 1 | selfdrive/chauffeur/concierge/main.py |
| `jinja2.select_autoescape` | 1 | selfdrive/chauffeur/concierge/main.py |
| `flask.jsonify` | 1 | selfdrive/frogpilot/fleetmanager/fleet_manager.py |
| `flask.redirect` | 1 | selfdrive/frogpilot/fleetmanager/fleet_manager.py |
| `flask.request` | 1 | selfdrive/frogpilot/fleetmanager/fleet_manager.py |
| `flask.session` | 1 | selfdrive/frogpilot/fleetmanager/fleet_manager.py |
| `flask.url_for` | 1 | selfdrive/frogpilot/fleetmanager/fleet_manager.py |
| `requests.exceptions.ConnectionError` | 1 | selfdrive/frogpilot/fleetmanager/fleet_manager.py |
| `dateutil.easter` | 1 | selfdrive/frogpilot/assets/theme_manager.py |
| `shapely` | 1 | selfdrive/frogpilot/navigation/mapd_py/mapd_daemon_wrapper.py |
| `shapely.geometry.LineString` | 1 | selfdrive/frogpilot/navigation/mapd_py/reader.py |
| `google.protobuf.message.DecodeError` | 1 | selfdrive/frogpilot/navigation/mapd_py/reader.py |
| `dictdiffer` | 1 | selfdrive/test/process_replay/compare_logs.py |
| `ipykernel.iostream.OutStream` | 1 | selfdrive/test/process_replay/capture.py |
| `pprofile` | 1 | selfdrive/test/profiling/profiler.py |
| `pyprof2calltree` | 1 | selfdrive/test/profiling/profiler.py |
| `numpy.linalg.solve` | 1 | selfdrive/controls/lib/vehicle_model.py |
| `numbers.Number` | 1 | selfdrive/controls/lib/pid.py |
| `PIL.ImageDraw` | 1 | selfdrive/controls/tests/test_alerts.py |
| `PIL.ImageFont` | 1 | selfdrive/controls/tests/test_alerts.py |
| `control.StateSpace` | 1 | selfdrive/controls/lib/tests/test_vehicle_model.py |
| `casadi.sin` | 1 | selfdrive/controls/lib/lateral_mpc_lib/lat_mpc.py |
| `casadi.cos` | 1 | selfdrive/controls/lib/lateral_mpc_lib/lat_mpc.py |
| `sip` | 1 | selfdrive/ui/qt/python_helpers.py |
| `pywinctl` | 1 | selfdrive/ui/tests/test_ui/run.py |
| `opendbc.generator.generator.create_all` | 1 | opendbc/generator/test_generator.py |
| `opendbc.generator.generator.opendbc_root` | 1 | opendbc/generator/test_generator.py |
| `opendbc.can.parser_pyx.CANParser` | 1 | opendbc/can/parser.py |
| `opendbc.can.packer_pyx.CANPacker` | 1 | opendbc/can/packer.py |
| `opendbc.can.parser.CANDefine` | 1 | opendbc/can/tests/test_dbc_exceptions.py |
| `PyNvCodec` | 1 | tools/camerastream/compressed_vipc.py |
| `opendbc.can.common.dbc.dbc` | 1 | tools/debug/can_message_interrogator.py |
| `rerun` | 1 | tools/rerun/run.py |
| `rerun.blueprint` | 1 | tools/rerun/run.py |
| `rosgraph` | 1 | tools/web/app.py |
| `matplotlib.patches` | 1 | tools/latencylogger/latency_logger.py |
| `mpld3` | 1 | tools/latencylogger/latency_logger.py |
| `aiohttp.ClientSession` | 1 | tools/bodyteleop/web.py |
| `inputs.get_gamepad` | 1 | tools/joystick/joystickd.py |
| `urllib3.PoolManager` | 1 | tools/lib/url_file.py |
| `urllib3.Retry` | 1 | tools/lib/url_file.py |
| `urllib3.response.BaseHTTPResponse` | 1 | tools/lib/url_file.py |
| `urllib3.util.Timeout` | 1 | tools/lib/url_file.py |
| `_io` | 1 | tools/lib/framereader.py |
| `lru.LRU` | 1 | tools/lib/framereader.py |
| `azure.identity.AzureCliCredential` | 1 | tools/lib/azure_container.py |
| `azure.storage.blob.BlobServiceClient` | 1 | tools/lib/azure_container.py |
| `azure.storage.blob.ContainerSasPermissions` | 1 | tools/lib/azure_container.py |
| `azure.storage.blob.generate_container_sas` | 1 | tools/lib/azure_container.py |
| `azure.storage.blob.ContainerClient` | 1 | tools/lib/azure_container.py |
| `azure.storage.blob.BlobClient` | 1 | tools/lib/azure_container.py |
| `urllib3` | 1 | tools/plotjuggler/juggle.py |
| `pyopencl.array` | 1 | tools/sim/lib/camerad.py |
| `evdev` | 1 | tools/sim/lib/manual_ctrl.py |
| `evdev.ecodes` | 1 | tools/sim/lib/manual_ctrl.py |
| `evdev.InputDevice` | 1 | tools/sim/lib/manual_ctrl.py |
| `panda3d.core.Vec3` | 1 | tools/sim/bridge/metadrive/metadrive_process.py |
| `metadrive.engine.core.engine_core.EngineCore` | 1 | tools/sim/bridge/metadrive/metadrive_process.py |
| `metadrive.engine.core.image_buffer.ImageBuffer` | 1 | tools/sim/bridge/metadrive/metadrive_process.py |
| `metadrive.envs.metadrive_env.MetaDriveEnv` | 1 | tools/sim/bridge/metadrive/metadrive_process.py |
| `metadrive.obs.image_obs.ImageObservation` | 1 | tools/sim/bridge/metadrive/metadrive_process.py |
| `metadrive.component.sensors.rgb_camera.RGBCamera` | 1 | tools/sim/bridge/metadrive/metadrive_common.py |
| `panda3d.core.Texture` | 1 | tools/sim/bridge/metadrive/metadrive_common.py |
| `panda3d.core.GraphicsOutput` | 1 | tools/sim/bridge/metadrive/metadrive_common.py |
| `metadrive.component.sensors.base_camera._cuda_enable` | 1 | tools/sim/bridge/metadrive/metadrive_bridge.py |
| `metadrive.component.map.pg_map.MapGenerateMethod` | 1 | tools/sim/bridge/metadrive/metadrive_bridge.py |
| `matplotlib.backends.backend_agg.FigureCanvasAgg` | 1 | tools/replay/lib/ui_helpers.py |
| `examples.llama3.Tokenizer` | 1 | tinygrad_repo/examples/self_tokenize.py |
| `extra.models.clip.Closed` | 1 | tinygrad_repo/examples/stable_diffusion.py |
| `extra.models.clip.Tokenizer` | 1 | tinygrad_repo/examples/stable_diffusion.py |
| `extra.datasets.fetch_cifar` | 1 | tinygrad_repo/examples/train_efficientnet.py |
| `extra.datasets.imagenet.fetch_batch` | 1 | tinygrad_repo/examples/train_efficientnet.py |
| `examples.vits.ResidualCouplingBlock` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `examples.vits.PosteriorEncoder` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `examples.vits.Encoder` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `examples.vits.ResBlock1` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `examples.vits.ResBlock2` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `examples.vits.LRELU_SLOPE` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `examples.vits.sequence_mask` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `examples.vits.split` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `examples.vits.get_hparams_from_file` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `examples.vits.load_checkpoint` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `examples.vits.weight_norm` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `examples.vits.HParams` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `examples.sovits_helpers.preprocess` | 1 | tinygrad_repo/examples/so_vits_svc.py |
| `extra.mcts_search.mcts_search` | 1 | tinygrad_repo/examples/handcode_opt.py |
| `nltk` | 1 | tinygrad_repo/examples/conversation.py |
| `llama.LLaMa` | 1 | tinygrad_repo/examples/conversation.py |
| `vits.MODELS` | 1 | tinygrad_repo/examples/conversation.py |
| `vits.Y_LENGTH_ESTIMATE_SCALARS` | 1 | tinygrad_repo/examples/conversation.py |
| `vits.HParams` | 1 | tinygrad_repo/examples/conversation.py |
| `vits.Synthesizer` | 1 | tinygrad_repo/examples/conversation.py |
| `vits.TextMapper` | 1 | tinygrad_repo/examples/conversation.py |
| `vits.get_hparams_from_file` | 1 | tinygrad_repo/examples/conversation.py |
| `vits.load_model` | 1 | tinygrad_repo/examples/conversation.py |
| `whisper.init_whisper` | 1 | tinygrad_repo/examples/conversation.py |
| `whisper.transcribe_waveform` | 1 | tinygrad_repo/examples/conversation.py |
| `extra.models.clip.Embedder` | 1 | tinygrad_repo/examples/sdxl.py |
| `extra.models.unet.Upsample` | 1 | tinygrad_repo/examples/sdxl.py |
| `extra.models.unet.Downsample` | 1 | tinygrad_repo/examples/sdxl.py |
| `extra.models.unet.timestep_embedding` | 1 | tinygrad_repo/examples/sdxl.py |
| `examples.stable_diffusion.ResnetBlock` | 1 | tinygrad_repo/examples/sdxl.py |
| `examples.stable_diffusion.Mid` | 1 | tinygrad_repo/examples/sdxl.py |
| `examples.llama3.load` | 1 | tinygrad_repo/examples/qwq.py |
| `extra.augment.augment_img` | 1 | tinygrad_repo/examples/serious_mnist.py |
| `sdxl.FirstStage` | 1 | tinygrad_repo/examples/flux1.py |
| `extra.models.t5.T5Embedder` | 1 | tinygrad_repo/examples/flux1.py |
| `torchvision.utils.make_grid` | 1 | tinygrad_repo/examples/mnist_gan.py |
| `torchvision.utils.save_image` | 1 | tinygrad_repo/examples/mnist_gan.py |
| `ultralytics.YOLO` | 1 | tinygrad_repo/examples/yolov8-onnx.py |
| `eng_to_ipa` | 1 | tinygrad_repo/examples/vits.py |
| `inflect` | 1 | tinygrad_repo/examples/vits.py |
| `phonemizer.phonemize.default_separator` | 1 | tinygrad_repo/examples/vits.py |
| `phonemizer.phonemize._phonemize` | 1 | tinygrad_repo/examples/vits.py |
| `phonemizer.backend.EspeakBackend` | 1 | tinygrad_repo/examples/vits.py |
| `phonemizer.punctuation.Punctuation` | 1 | tinygrad_repo/examples/vits.py |
| `unidecode.unidecode` | 1 | tinygrad_repo/examples/vits.py |
| `llama3.Int8Linear` | 1 | tinygrad_repo/examples/llama.py |
| `llama3.NF4Linear` | 1 | tinygrad_repo/examples/llama.py |
| `extra.models.mask_rcnn.BoxList` | 1 | tinygrad_repo/examples/mask_rcnn.py |
| `extra.models.llama.convert_from_gguf` | 1 | tinygrad_repo/examples/llama3.py |
| `bottle.Bottle` | 1 | tinygrad_repo/examples/llama3.py |
| `bottle.request` | 1 | tinygrad_repo/examples/llama3.py |
| `bottle.response` | 1 | tinygrad_repo/examples/llama3.py |
| `bottle.HTTPResponse` | 1 | tinygrad_repo/examples/llama3.py |
| `bottle.abort` | 1 | tinygrad_repo/examples/llama3.py |
| `bottle.static_file` | 1 | tinygrad_repo/examples/llama3.py |
| `tf2onnx` | 1 | tinygrad_repo/examples/compile_tensorflow.py |
| `extra.export_model.export_model_clang` | 1 | tinygrad_repo/examples/compile_tensorflow.py |
| `examples.vgg7_helpers.waifu2x.image_save` | 1 | tinygrad_repo/examples/vgg7.py |
| `examples.stable_diffusion.AutoencoderKL` | 1 | tinygrad_repo/examples/sdv2.py |
| `examples.stable_diffusion.get_alphas_cumprod` | 1 | tinygrad_repo/examples/sdv2.py |
| `examples.sdxl.DPMPP2MSampler` | 1 | tinygrad_repo/examples/sdv2.py |
| `examples.sdxl.append_dims` | 1 | tinygrad_repo/examples/sdv2.py |
| `examples.sdxl.LegacyDDPMDiscretization` | 1 | tinygrad_repo/examples/sdv2.py |
| `extra.onnx.dtype_parse` | 1 | tinygrad_repo/extra/onnx_ops.py |
| `extra.onnx.to_python_const` | 1 | tinygrad_repo/extra/onnx_ops.py |
| `onnx.AttributeProto` | 1 | tinygrad_repo/extra/onnx.py |
| `onnx.ModelProto` | 1 | tinygrad_repo/extra/onnx.py |
| `onnx.TensorProto` | 1 | tinygrad_repo/extra/onnx.py |
| `onnx.ValueInfoProto` | 1 | tinygrad_repo/extra/onnx.py |
| `onnx.mapping.TENSOR_TYPE_TO_NP_TYPE` | 1 | tinygrad_repo/extra/onnx.py |
| `extra.optimization.helpers.ast_str_to_ast` | 1 | tinygrad_repo/extra/to_movement_ops.py |
| `typeguard.install_import_hook` | 1 | tinygrad_repo/tinygrad/__init__.py |
| `contextvars` | 1 | tinygrad_repo/tinygrad/helpers.py |
| `copyreg` | 1 | tinygrad_repo/tinygrad/helpers.py |
| `examples.gpt2.Attention` | 1 | tinygrad_repo/test/test_symbolic_ops.py |
| `torch.cuda` | 1 | tinygrad_repo/test/test_speed_v_torch.py |
| `extra.models.llama.precompute_freqs_cis` | 1 | tinygrad_repo/test/test_schedule.py |
| `hypothesis.assume` | 1 | tinygrad_repo/test/test_fuzz_shape_ops.py |
| `hypothesis.extra.numpy` | 1 | tinygrad_repo/test/test_fuzz_shape_ops.py |
| `extra.gradcheck.numerical_jacobian` | 1 | tinygrad_repo/test/test_tensor.py |
| `extra.gradcheck.jacobian` | 1 | tinygrad_repo/test/test_tensor.py |
| `extra.gradcheck.gradcheck` | 1 | tinygrad_repo/test/test_tensor.py |
| `ocdiff` | 1 | tinygrad_repo/test/helpers.py |
| `extra.lr_scheduler.LR_Scheduler` | 1 | tinygrad_repo/examples/mlperf/lr_schedulers.py |
| `extra.datasets.openimages.download_dataset` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `extra.datasets.openimages.iterate` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `extra.datasets.openimages.BASEDIR` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `extra.datasets.librispeech.iterate` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `examples.mlperf.metrics.word_error_rate` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `extra.datasets.squad.iterate` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `examples.mlperf.helpers.get_bert_qa_prediction` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `examples.mlperf.metrics.f1_score` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `extra.datasets.coco.BASEDIR` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `extra.datasets.coco.images` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `extra.datasets.coco.convert_prediction_to_coco_bbox` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `extra.datasets.coco.convert_prediction_to_coco_mask` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `extra.datasets.coco.accumulate_predictions_for_coco` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `extra.datasets.coco.evaluate_predictions_on_coco` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `extra.datasets.coco.iterate` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `examples.mask_rcnn.compute_prediction_batched` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `examples.mask_rcnn.Image` | 1 | tinygrad_repo/examples/mlperf/model_eval.py |
| `examples.mlperf.helpers.get_training_state` | 1 | tinygrad_repo/examples/mlperf/model_train.py |
| `examples.mlperf.helpers.load_training_state` | 1 | tinygrad_repo/examples/mlperf/model_train.py |
| `examples.mlperf.dataloader.batch_load_train_bert` | 1 | tinygrad_repo/examples/mlperf/model_train.py |
| `examples.mlperf.helpers.get_fake_data_bert` | 1 | tinygrad_repo/examples/mlperf/model_train.py |
| `extra.datasets.imagenet.center_crop` | 1 | tinygrad_repo/examples/mlperf/dataloader.py |
| `extra.datasets.imagenet.preprocess_train` | 1 | tinygrad_repo/examples/mlperf/dataloader.py |
| `extra.datasets.imagenet.get_imagenet_categories` | 1 | tinygrad_repo/examples/mlperf/dataloader.py |
| `extra.datasets.wikipedia.get_wiki_train_files` | 1 | tinygrad_repo/examples/mlperf/dataloader.py |
| `extra.datasets.kits19.rand_balanced_crop` | 1 | tinygrad_repo/examples/mlperf/dataloader.py |
| `extra.datasets.kits19.rand_flip` | 1 | tinygrad_repo/examples/mlperf/dataloader.py |
| `extra.datasets.kits19.random_brightness_augmentation` | 1 | tinygrad_repo/examples/mlperf/dataloader.py |
| `extra.datasets.kits19.gaussian_noise` | 1 | tinygrad_repo/examples/mlperf/dataloader.py |
| `examples.mlperf.initializers.LinearBert` | 1 | tinygrad_repo/examples/mlperf/helpers.py |
| `examples.mlperf.initializers.EmbeddingBert` | 1 | tinygrad_repo/examples/mlperf/helpers.py |
| `examples.mlperf.initializers.LayerNormBert` | 1 | tinygrad_repo/examples/mlperf/helpers.py |
| `extra.models.bert.BertForPretraining` | 1 | tinygrad_repo/examples/mlperf/helpers.py |
| `extra.models.mask_rcnn.ResNet` | 1 | tinygrad_repo/examples/mlperf/model_spec.py |
| `mlx.optimizers` | 1 | tinygrad_repo/examples/other_mnist/beautiful_mnist_mlx.py |
| `torch.optim` | 1 | tinygrad_repo/examples/other_mnist/beautiful_mnist_torch.py |
| `gymnasium.envs.registration.register` | 1 | tinygrad_repo/examples/rl/lightupbutton.py |
| `train_gpt2.GPT` | 1 | tinygrad_repo/examples/llm.c/export.py |
| `train_gpt2.GPTConfig` | 1 | tinygrad_repo/examples/llm.c/export.py |
| `parselmouth` | 1 | tinygrad_repo/examples/sovits_helpers/preprocess.py |
| `examples.yolov8.get_weights_location` | 1 | tinygrad_repo/examples/webgpu/yolov8/compile.py |
| `extra.export_model.dtype_to_js_type` | 1 | tinygrad_repo/examples/webgpu/stable_diffusion/compile.py |
| `gdown` | 1 | tinygrad_repo/extra/datasets/wikipedia_download.py |
| `tqdm.contrib.concurrent.process_map` | 1 | tinygrad_repo/extra/datasets/wikipedia.py |
| `extra.datasets.fake_imagenet_from_mnist.create_fake_mnist_imagenet` | 1 | tinygrad_repo/extra/datasets/imagenet.py |
| `pycocotools._mask` | 1 | tinygrad_repo/extra/datasets/coco.py |
| `examples.mask_rcnn.Masker` | 1 | tinygrad_repo/extra/datasets/coco.py |
| `extra.datasets.imagenet.iterate` | 1 | tinygrad_repo/extra/datasets/preprocess_imagenet.py |
| `boto3` | 1 | tinygrad_repo/extra/datasets/openimages.py |
| `botocore` | 1 | tinygrad_repo/extra/datasets/openimages.py |
| `extra.models.transformer.TransformerBlock` | 1 | tinygrad_repo/extra/models/vit.py |
| `torch.hub.load_state_dict_from_url` | 1 | tinygrad_repo/extra/models/retinanet.py |
| `scipy.linalg` | 1 | tinygrad_repo/extra/models/inception.py |
| `extra.models.retinanet.nms` | 1 | tinygrad_repo/extra/models/mask_rcnn.py |
| `extra.qcom_gpu_driver.msm_kgsl` | 1 | tinygrad_repo/extra/qcom_gpu_driver/opencl_ioctl.py |
| `extra.disassemblers.adreno.disasm_raw` | 1 | tinygrad_repo/extra/qcom_gpu_driver/opencl_ioctl.py |
| `extra.optimization.helpers.MAX_DIMS` | 1 | tinygrad_repo/extra/optimization/pretrain_valuenet.py |
| `extra.optimization.helpers.assert_same_lin` | 1 | tinygrad_repo/extra/optimization/extract_policynet.py |
| `run` | 1 | tinygrad_repo/extra/dsp/compile.py |
| `adsprpc` | 1 | tinygrad_repo/extra/dsp/compile.py |
| `ion` | 1 | tinygrad_repo/extra/dsp/compile.py |
| `msm_ion` | 1 | tinygrad_repo/extra/dsp/compile.py |
| `llvmlite.ir` | 1 | tinygrad_repo/extra/gemm/amx.py |
| `triton` | 1 | tinygrad_repo/extra/gemm/triton_nv_matmul.py |
| `triton.language` | 1 | tinygrad_repo/extra/gemm/triton_nv_matmul.py |
| `triton.compiler.AttrsDescriptor` | 1 | tinygrad_repo/extra/gemm/triton_nv_matmul.py |
| `triton.compiler.ASTSource` | 1 | tinygrad_repo/extra/gemm/triton_nv_matmul.py |
| `tvm` | 1 | tinygrad_repo/extra/gemm/tvm_gemm.py |
| `tvm.te` | 1 | tinygrad_repo/extra/gemm/tvm_gemm.py |
| `openvino.runtime.Core` | 1 | tinygrad_repo/extra/accel/intel/benchmark_matmul.py |
| `pylab` | 1 | tinygrad_repo/extra/accel/ane/2_compile/dcompile.py |
| `networkx.drawing.nx_pydot.read_dot` | 1 | tinygrad_repo/extra/accel/ane/2_compile/dcompile.py |
| `macholib.MachO` | 1 | tinygrad_repo/extra/accel/ane/2_compile/hwx_parse.py |
| `macholib.SymbolTable` | 1 | tinygrad_repo/extra/accel/ane/2_compile/hwx_parse.py |
| `ane.ANE_Struct` | 1 | tinygrad_repo/extra/accel/ane/2_compile/hwx_parse.py |
| `termcolor.colored` | 1 | tinygrad_repo/extra/accel/ane/2_compile/hwx_parse.py |
| `ane.ANETensor` | 1 | tinygrad_repo/extra/accel/ane/lib/testconv.py |
| `faulthandler` | 1 | tinygrad_repo/extra/accel/ane/lib/ane.py |
| `tensor.Device` | 1 | tinygrad_repo/extra/accel/ane/tinygrad/ops_ane.py |
| `tensor.Function` | 1 | tinygrad_repo/extra/accel/ane/tinygrad/ops_ane.py |
| `tensor.register` | 1 | tinygrad_repo/extra/accel/ane/tinygrad/ops_ane.py |
| `coremltools` | 1 | tinygrad_repo/extra/accel/ane/1_build/coreml_ane.py |
| `coremltools.models.neural_network.datatypes` | 1 | tinygrad_repo/extra/accel/ane/1_build/coreml_ane.py |
| `coremltools.models.neural_network.NeuralNetworkBuilder` | 1 | tinygrad_repo/extra/accel/ane/1_build/coreml_ane.py |
| `extra.dsp.run` | 1 | tinygrad_repo/tinygrad/runtime/ops_dsp.py |
| `_posixshmem` | 1 | tinygrad_repo/tinygrad/runtime/ops_disk.py |
| `wgpu` | 1 | tinygrad_repo/tinygrad/runtime/ops_webgpu.py |
| `extra.introspection.print_objects` | 1 | tinygrad_repo/test/models/test_train.py |
| `examples.gpt2.MODEL_PARAMS` | 1 | tinygrad_repo/test/models/test_real_world.py |
| `examples.hlb_cifar10.SpeedyResNet` | 1 | tinygrad_repo/test/models/test_real_world.py |
| `examples.hlb_cifar10.hyp` | 1 | tinygrad_repo/test/models/test_real_world.py |
| `transformers.BertForQuestionAnswering` | 1 | tinygrad_repo/test/models/test_bert.py |
| `transformers.BertConfig` | 1 | tinygrad_repo/test/models/test_bert.py |
| `extra.models.rnnt.LSTM` | 1 | tinygrad_repo/test/models/test_rnnt.py |
| `examples.whisper.load_file_waveform` | 1 | tinygrad_repo/test/models/test_whisper.py |
| `examples.whisper.transcribe_file` | 1 | tinygrad_repo/test/models/test_whisper.py |
| `gpuctypes.hip` | 1 | tinygrad_repo/test/external/external_hip_compiler_bug.py |
| `ultralytics` | 1 | tinygrad_repo/test/external/external_test_yolov8.py |
| `examples.yolov8.get_variant_multiples` | 1 | tinygrad_repo/test/external/external_test_yolov8.py |
| `examples.yolov8.preprocess` | 1 | tinygrad_repo/test/external/external_test_yolov8.py |
| `examples.yolov8.postprocess` | 1 | tinygrad_repo/test/external/external_test_yolov8.py |
| `examples.yolov8.label_predictions` | 1 | tinygrad_repo/test/external/external_test_yolov8.py |
| `onnx.backend.test` | 1 | tinygrad_repo/test/external/external_test_onnx_backend.py |
| `onnx.backend.base.Backend` | 1 | tinygrad_repo/test/external/external_test_onnx_backend.py |
| `onnx.backend.base.BackendRep` | 1 | tinygrad_repo/test/external/external_test_onnx_backend.py |
| `extra.datasets.kits19.preprocess` | 1 | tinygrad_repo/test/external/external_test_datasets.py |
| `torchaudio` | 1 | tinygrad_repo/test/external/external_test_whisper_librispeech.py |
| `jiwer` | 1 | tinygrad_repo/test/external/external_test_whisper_librispeech.py |
| `whisper.normalizers.EnglishTextNormalizer` | 1 | tinygrad_repo/test/external/external_test_whisper_librispeech.py |
| `examples.llama.MODEL_PARAMS` | 1 | tinygrad_repo/test/external/external_test_speed_llama.py |
| `examples.mamba.Mamba` | 1 | tinygrad_repo/test/external/external_test_mamba.py |
| `examples.mamba.generate` | 1 | tinygrad_repo/test/external/external_test_mamba.py |
| `examples.yolov3.Darknet` | 1 | tinygrad_repo/test/external/external_test_yolo.py |
| `examples.yolov3.infer` | 1 | tinygrad_repo/test/external/external_test_yolo.py |
| `examples.yolov3.show_labels` | 1 | tinygrad_repo/test/external/external_test_yolo.py |
| `lm_eval.base.BaseLM` | 1 | tinygrad_repo/test/external/external_llama_eval.py |
| `lm_eval.evaluator` | 1 | tinygrad_repo/test/external/external_llama_eval.py |
| `lm_eval.tasks` | 1 | tinygrad_repo/test/external/external_llama_eval.py |
| `examples.llama.LLaMa` | 1 | tinygrad_repo/test/external/external_llama_eval.py |
| `tensorflow_addons` | 1 | tinygrad_repo/test/external/external_test_optim.py |
| `safetensors.numpy.save_file` | 1 | tinygrad_repo/test/unit/test_disk_tensor.py |
| `ggml` | 1 | tinygrad_repo/test/unit/test_gguf.py |
| `typing_extensions` | 1 | tinygrad_repo/test/testextra/test_mockgpu.py |
| `extra.lr_scheduler.MultiStepLR` | 1 | tinygrad_repo/test/testextra/test_lr_scheduler.py |
| `extra.lr_scheduler.ReduceLROnPlateau` | 1 | tinygrad_repo/test/testextra/test_lr_scheduler.py |
| `extra.lr_scheduler.CosineAnnealingLR` | 1 | tinygrad_repo/test/testextra/test_lr_scheduler.py |
| `extra.export_model.EXPORT_SUPPORTED_DEVICE` | 1 | tinygrad_repo/test/testextra/test_export_model.py |
| `builtins` | 1 | tinygrad_repo/test/mockgpu/mockgpu.py |
| `torch.utils.data.Dataset` | 1 | tinygrad_repo/test/external/mlperf_unet3d/kits19.py |
| `tensorflow.python.eager.context` | 1 | tinygrad_repo/test/external/mlperf_resnet/lars_util.py |
| `tensorflow.python.keras.optimizer_v2.learning_rate_schedule` | 1 | tinygrad_repo/test/external/mlperf_resnet/lars_util.py |
| `tensorflow.python.keras.backend_config` | 1 | tinygrad_repo/test/external/mlperf_resnet/lars_optimizer.py |
| `tensorflow.python.keras.optimizer_v2.optimizer_v2` | 1 | tinygrad_repo/test/external/mlperf_resnet/lars_optimizer.py |
| `tensorflow.python.ops.array_ops` | 1 | tinygrad_repo/test/external/mlperf_resnet/lars_optimizer.py |
| `tensorflow.python.ops.linalg_ops` | 1 | tinygrad_repo/test/external/mlperf_resnet/lars_optimizer.py |
| `tensorflow.python.training.training_ops` | 1 | tinygrad_repo/test/external/mlperf_resnet/lars_optimizer.py |
| `tensorflow.python.ops.state_ops` | 1 | tinygrad_repo/test/external/mlperf_resnet/lars_optimizer.py |
| `examples.mlperf.model_train.eval_step_bert` | 1 | tinygrad_repo/test/external/mlperf_bert/external_test_checkpoint_loading.py |
| `tokenization` | 1 | tinygrad_repo/test/external/mlperf_bert/preprocessing/create_pretraining_data.py |
| `six` | 1 | tinygrad_repo/test/external/mlperf_bert/preprocessing/tokenization.py |
| `tensorflow.compat.v1` | 1 | tinygrad_repo/test/external/mlperf_bert/preprocessing/tokenization.py |

## Files with External Dependencies

### body/crypto/sign.py
- `Crypto.PublicKey.RSA`

### cereal/__init__.py
- `capnp`

### cereal/messaging/__init__.py
- `capnp`

### cereal/messaging/tests/test_messaging.py
- `capnp`
- `numbers`
- `parameterized.parameterized`

### cereal/messaging/tests/test_services.py
- `parameterized.parameterized`

### common/api/__init__.py
- `jwt`
- `requests`

### common/conversions.py
- `numpy`

### common/realtime.py
- `setproctitle.getproctitle`

### common/simple_kalman.py
- `numpy`

### common/stat_live.py
- `numpy`

### common/swaglog.py
- `zmq`

### common/tests/test_numpy_fast.py
- `numpy`

### common/tests/test_params.py
- `pytest`

### common/transformations/camera.py
- `numpy`

### common/transformations/model.py
- `numpy`

### common/transformations/orientation.py
- `numpy`

### common/transformations/tests/test_coordinates.py
- `numpy`

### common/transformations/tests/test_orientation.py
- `numpy`

### conftest.py
- `pytest`

### msgq_repo/msgq/tests/test_fake.py
- `parameterized.parameterized_class`

### msgq_repo/msgq/visionipc/tests/test_visionipc.py
- `numpy`

### msgq_repo/site_scons/site_tools/cython.py
- `SCons`
- `SCons.Action.Action`
- `SCons.Scanner.Scanner`

### opendbc/can/can_define.py
- `opendbc.can.parser_pyx.CANDefine`

### opendbc/can/packer.py
- `opendbc.can.packer_pyx.CANPacker`

### opendbc/can/parser.py
- `opendbc.can.parser_pyx.CANDefine`
- `opendbc.can.parser_pyx.CANParser`

### opendbc/can/tests/__init__.py
- `opendbc.DBC_PATH`

### opendbc/can/tests/test_checksums.py
- `opendbc.can.packer.CANPacker`
- `opendbc.can.parser.CANParser`
- `opendbc.can.tests.test_packer_parser.can_list_to_can_capnp`

### opendbc/can/tests/test_dbc_exceptions.py
- `opendbc.can.packer.CANPacker`
- `opendbc.can.parser.CANDefine`
- `opendbc.can.parser.CANParser`
- `opendbc.can.tests.TEST_DBC`

### opendbc/can/tests/test_dbc_parser.py
- `opendbc.can.parser.CANParser`
- `opendbc.can.tests.ALL_DBCS`

### opendbc/can/tests/test_define.py
- `opendbc.can.can_define.CANDefine`
- `opendbc.can.tests.ALL_DBCS`

### opendbc/can/tests/test_packer_parser.py
- `opendbc.can.packer.CANPacker`
- `opendbc.can.parser.CANParser`
- `opendbc.can.tests.TEST_DBC`

### opendbc/can/tests/test_parser_performance.py
- `opendbc.can.packer.CANPacker`
- `opendbc.can.parser.CANParser`
- `opendbc.can.tests.test_packer_parser.can_list_to_can_capnp`

### opendbc/generator/tesla/tesla_radar_bosch.py
- `opendbc.generator.tesla.radar_common.get_radar_point_definition`
- `opendbc.generator.tesla.radar_common.get_val_definition`

### opendbc/generator/tesla/tesla_radar_continental.py
- `opendbc.generator.tesla.radar_common.get_radar_point_definition`
- `opendbc.generator.tesla.radar_common.get_val_definition`

### opendbc/generator/test_generator.py
- `filecmp`
- `opendbc.generator.generator.create_all`
- `opendbc.generator.generator.opendbc_root`

### opendbc/site_scons/site_tools/cython.py
- `SCons`
- `SCons.Action.Action`
- `SCons.Scanner.Scanner`

### panda/__init__.py
- `board.jungle.PandaJungle`
- `board.jungle.PandaJungleDFU`
- `python.ALTERNATIVE_EXPERIENCE`
- `python.CANPACKET_HEAD_SIZE`
- `python.DLC_TO_LEN`
- `python.LEN_TO_DLC`
- `python.Panda`
- `python.PandaDFU`
- `python.calculate_checksum`
- `python.canhandle.CanHandle`
- `python.constants.BASEDIR`
- `python.constants.FW_PATH`
- `python.constants.McuType`
- `python.constants.USBPACKET_MAX_SIZE`
- `python.pack_can_buffer`
- `python.serial.PandaSerial`
- `python.spi.PandaProtocolMismatch`
- `python.spi.PandaSpiException`
- `python.spi.STBootloaderSPIHandle`
- `python.unpack_can_buffer`

### panda/board/jungle/scripts/echo_loopback_test.py
- `termcolor.cprint`

### panda/board/jungle/scripts/loopback_test.py
- `termcolor.cprint`

### panda/crypto/sign.py
- `Crypto.PublicKey.RSA`

### panda/examples/query_fw_versions.py
- `tqdm.tqdm`

### panda/examples/query_vin_and_stats.py
- `hexdump.hexdump`

### panda/python/__init__.py
- `base.BaseHandle`
- `constants.FW_PATH`
- `constants.McuType`
- `dfu.PandaDFU`
- `isotp.isotp_recv`
- `isotp.isotp_send`
- `spi.PandaProtocolMismatch`
- `spi.PandaSpiException`
- `spi.PandaSpiHandle`
- `usb.PandaUsbHandle`
- `usb1`

### panda/python/base.py
- `abc.ABC`
- `abc.abstractmethod`
- `constants.McuType`

### panda/python/canhandle.py
- `base.BaseHandle`

### panda/python/dfu.py
- `base.BaseSTBootloaderHandle`
- `constants.FW_PATH`
- `constants.McuType`
- `spi.PandaSpiException`
- `spi.STBootloaderSPIHandle`
- `usb.STBootloaderUSBHandle`
- `usb1`

### panda/python/spi.py
- `base.BaseHandle`
- `base.BaseSTBootloaderHandle`
- `base.TIMEOUT`
- `constants.MCU_TYPE_BY_IDCODE`
- `constants.McuType`
- `constants.USBPACKET_MAX_SIZE`
- `spidev`
- `spidev2`

### panda/python/usb.py
- `base.BaseHandle`
- `base.BaseSTBootloaderHandle`
- `base.TIMEOUT`
- `constants.McuType`

### panda/setup.py
- `setuptools.setup`

### panda/tests/development/register_hashmap_spread.py
- `matplotlib.pyplot`

### panda/tests/hitl/1_program.py
- `pytest`

### panda/tests/hitl/2_health.py
- `pytest`

### panda/tests/hitl/3_usb_to_can.py
- `flaky.flaky`

### panda/tests/hitl/4_can_loopback.py
- `flaky.flaky`
- `pytest`

### panda/tests/hitl/5_spi.py
- `pytest`

### panda/tests/hitl/7_internal.py
- `pytest`

### panda/tests/hitl/9_harness.py
- `pytest`

### panda/tests/hitl/conftest.py
- `pytest`

### panda/tests/libpanda/libpanda_py.py
- `cffi.FFI`

### panda/tests/libs/resetter.py
- `usb1`

### panda/tests/message_drop_test.py
- `usb1`

### panda/tests/misra/test_mutation.py
- `pytest`

### panda/tests/read_winusb_descriptors.py
- `hexdump.hexdump`

### panda/tests/safety/common.py
- `abc`
- `numpy`
- `opendbc.can.packer.CANPacker`

### panda/tests/safety/test_ford.py
- `numpy`

### panda/tests/safety/test_honda.py
- `numpy`

### panda/tests/safety/test_hyundai_canfd.py
- `parameterized.parameterized_class`

### panda/tests/safety/test_tesla.py
- `numpy`

### panda/tests/safety/test_toyota.py
- `numpy`

### panda/tests/safety/test_volkswagen_mqb.py
- `numpy`

### panda/tests/som/test_bootkick.py
- `pytest`

### rednose_repo/examples/kinematic_kf.py
- `numpy`
- `sympy`

### rednose_repo/examples/live_kf.py
- `numpy`
- `sympy`

### rednose_repo/examples/test_compare.py
- `numpy`
- `sympy`

### rednose_repo/examples/test_kinematic_kf.py
- `kinematic_kf.KinematicKalman`
- `kinematic_kf.ObservationKind`
- `kinematic_kf.States`
- `matplotlib.pyplot`
- `numpy`

### rednose_repo/rednose/helpers/__init__.py
- `cffi.FFI`

### rednose_repo/rednose/helpers/chi2_lookup.py
- `numpy`
- `scipy.stats.chi2`

### rednose_repo/rednose/helpers/ekf_sym.py
- `numpy`
- `numpy.dot`
- `sympy`

### rednose_repo/rednose/helpers/kalmanfilter.py
- `numpy`

### rednose_repo/rednose/helpers/sympy_helpers.py
- `numpy`
- `sympy`
- `sympy.utilities.codegen`

### rednose_repo/setup.py
- `setuptools.find_packages`
- `setuptools.setup`

### rednose_repo/site_scons/site_tools/cython.py
- `SCons`
- `SCons.Action.Action`
- `SCons.Scanner.Scanner`

### rednose_repo/site_scons/site_tools/rednose_filter.py
- `SCons.Script.Dir`
- `SCons.Script.File`

### scripts/code_stats.py
- `stat`

### scripts/pyqt_demo.py
- `PyQt5.QtWidgets.QApplication`
- `PyQt5.QtWidgets.QLabel`

### scripts/waste.py
- `numpy`
- `setproctitle.setproctitle`

### selfdrive/car/__init__.py
- `capnp`

### selfdrive/car/body/carcontroller.py
- `numpy`
- `opendbc.can.packer.CANPacker`

### selfdrive/car/body/carstate.py
- `opendbc.can.parser.CANParser`

### selfdrive/car/chrysler/carcontroller.py
- `opendbc.can.packer.CANPacker`

### selfdrive/car/chrysler/carstate.py
- `opendbc.can.can_define.CANDefine`
- `opendbc.can.parser.CANParser`

### selfdrive/car/chrysler/radar_interface.py
- `opendbc.can.parser.CANParser`

### selfdrive/car/docs.py
- `jinja2`
- `natsort.natsorted`

### selfdrive/car/ecu_addrs.py
- `capnp`

### selfdrive/car/ford/carcontroller.py
- `opendbc.can.packer.CANPacker`

### selfdrive/car/ford/carstate.py
- `opendbc.can.can_define.CANDefine`
- `opendbc.can.parser.CANParser`

### selfdrive/car/ford/radar_interface.py
- `opendbc.can.parser.CANParser`

### selfdrive/car/ford/tests/test_ford.py
- `capnp`
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `parameterized.parameterized`

### selfdrive/car/fw_query_definitions.py
- `capnp`

### selfdrive/car/fw_versions.py
- `capnp`
- `tqdm.tqdm`

### selfdrive/car/gm/carcontroller.py
- `opendbc.can.packer.CANPacker`

### selfdrive/car/gm/carstate.py
- `opendbc.can.can_define.CANDefine`
- `opendbc.can.parser.CANParser`

### selfdrive/car/gm/radar_interface.py
- `opendbc.can.parser.CANParser`

### selfdrive/car/gm/tests/test_gm.py
- `parameterized.parameterized`

### selfdrive/car/honda/carcontroller.py
- `opendbc.can.packer.CANPacker`

### selfdrive/car/honda/carstate.py
- `opendbc.can.can_define.CANDefine`
- `opendbc.can.parser.CANParser`

### selfdrive/car/honda/radar_interface.py
- `opendbc.can.parser.CANParser`

### selfdrive/car/hyundai/carcontroller.py
- `opendbc.can.packer.CANPacker`

### selfdrive/car/hyundai/carstate.py
- `opendbc.can.can_define.CANDefine`
- `opendbc.can.parser.CANParser`

### selfdrive/car/hyundai/chubbs/longitudinal_tuning.py
- `numpy`

### selfdrive/car/hyundai/hyundaican.py
- `crcmod`

### selfdrive/car/hyundai/radar_interface.py
- `opendbc.can.parser.CANParser`

### selfdrive/car/hyundai/tests/test_hyundai.py
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `pytest`

### selfdrive/car/hyundai/values.py
- `opendbc.DBC_PATH`

### selfdrive/car/interfaces.py
- `abc.ABC`
- `abc.abstractmethod`
- `numpy`
- `tomllib`

### selfdrive/car/mazda/carcontroller.py
- `opendbc.can.packer.CANPacker`

### selfdrive/car/mazda/carstate.py
- `opendbc.can.can_define.CANDefine`
- `opendbc.can.parser.CANParser`

### selfdrive/car/nissan/carcontroller.py
- `opendbc.can.packer.CANPacker`

### selfdrive/car/nissan/carstate.py
- `opendbc.can.can_define.CANDefine`
- `opendbc.can.parser.CANParser`

### selfdrive/car/nissan/nissancan.py
- `crcmod`

### selfdrive/car/secoc.py
- `Crypto.Cipher.AES`
- `Crypto.Hash.CMAC`

### selfdrive/car/subaru/carcontroller.py
- `opendbc.can.packer.CANPacker`

### selfdrive/car/subaru/carstate.py
- `opendbc.can.can_define.CANDefine`
- `opendbc.can.parser.CANParser`

### selfdrive/car/tesla/carcontroller.py
- `opendbc.can.packer.CANPacker`

### selfdrive/car/tesla/carstate.py
- `opendbc.can.can_define.CANDefine`
- `opendbc.can.parser.CANParser`

### selfdrive/car/tesla/radar_interface.py
- `opendbc.can.parser.CANParser`

### selfdrive/car/tesla/teslacan.py
- `crcmod`

### selfdrive/car/tests/test_can_fingerprint.py
- `parameterized.parameterized`

### selfdrive/car/tests/test_car_interfaces.py
- `hypothesis.Phase`
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `parameterized.parameterized`

### selfdrive/car/tests/test_docs.py
- `pytest`

### selfdrive/car/tests/test_fw_fingerprint.py
- `parameterized.parameterized`
- `pytest`

### selfdrive/car/tests/test_lateral_limits.py
- `parameterized.parameterized_class`
- `pytest`

### selfdrive/car/tests/test_models.py
- `capnp`
- `hypothesis.Phase`
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `parameterized.parameterized_class`
- `pytest`

### selfdrive/car/toyota/carcontroller.py
- `numpy`
- `opendbc.can.packer.CANPacker`

### selfdrive/car/toyota/carstate.py
- `opendbc.can.can_define.CANDefine`
- `opendbc.can.parser.CANParser`

### selfdrive/car/toyota/radar_interface.py
- `opendbc.can.parser.CANParser`

### selfdrive/car/toyota/tests/test_toyota.py
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`

### selfdrive/car/volkswagen/carcontroller.py
- `opendbc.can.packer.CANPacker`

### selfdrive/car/volkswagen/carstate.py
- `numpy`
- `opendbc.can.parser.CANParser`

### selfdrive/car/volkswagen/values.py
- `opendbc.can.can_define.CANDefine`

### selfdrive/chauffeur/concierge/main.py
- `fastapi.FastAPI`
- `fastapi.HTTPException`
- `fastapi.Request`
- `fastapi.responses.FileResponse`
- `fastapi.responses.HTMLResponse`
- `fastapi.responses.PlainTextResponse`
- `fastapi.responses.StreamingResponse`
- `fastapi.staticfiles.StaticFiles`
- `jinja2.Environment`
- `jinja2.FileSystemLoader`
- `jinja2.select_autoescape`
- `pydantic.BaseModel`
- `shlex`
- `uvicorn`
- `zmq`
- `zmq.asyncio`

### selfdrive/classic_modeld/classic_modeld.py
- `numpy`
- `setproctitle.setproctitle`

### selfdrive/classic_modeld/constants.py
- `numpy`

### selfdrive/classic_modeld/dmonitoringmodeld.py
- `numpy`

### selfdrive/classic_modeld/fill_model_msg.py
- `capnp`
- `numpy`

### selfdrive/classic_modeld/get_model_metadata.py
- `onnx`

### selfdrive/classic_modeld/navmodeld.py
- `numpy`

### selfdrive/classic_modeld/parse_model_outputs.py
- `numpy`

### selfdrive/classic_modeld/runners/onnxmodel.py
- `numpy`
- `onnx`
- `onnxruntime`

### selfdrive/controls/lib/latcontrol.py
- `abc.ABC`
- `abc.abstractmethod`

### selfdrive/controls/lib/latcontrol_torque.py
- `numpy`

### selfdrive/controls/lib/lateral_mpc_lib/lat_mpc.py
- `casadi.SX`
- `casadi.cos`
- `casadi.sin`
- `casadi.vertcat`
- `numpy`

### selfdrive/controls/lib/longitudinal_mpc_lib/long_mpc.py
- `casadi.SX`
- `casadi.vertcat`
- `numpy`

### selfdrive/controls/lib/longitudinal_planner.py
- `numpy`

### selfdrive/controls/lib/pid.py
- `numbers.Number`
- `numpy`

### selfdrive/controls/lib/tests/test_latcontrol.py
- `parameterized.parameterized`

### selfdrive/controls/lib/tests/test_vehicle_model.py
- `control.StateSpace`
- `numpy`
- `pytest`

### selfdrive/controls/lib/vehicle_model.py
- `numpy`
- `numpy.linalg.solve`

### selfdrive/controls/radard.py
- `capnp`
- `numpy`

### selfdrive/controls/tests/test_alerts.py
- `PIL.Image`
- `PIL.ImageDraw`
- `PIL.ImageFont`

### selfdrive/controls/tests/test_cruise_speed.py
- `numpy`
- `parameterized.parameterized_class`
- `pytest`

### selfdrive/controls/tests/test_following_distance.py
- `parameterized.parameterized_class`
- `pytest`

### selfdrive/controls/tests/test_lateral_mpc.py
- `numpy`
- `pytest`

### selfdrive/controls/tests/test_startup.py
- `parameterized.parameterized`

### selfdrive/debug/can_table.py
- `pandas`

### selfdrive/debug/check_can_parser_performance.py
- `numpy`
- `tqdm.tqdm`

### selfdrive/debug/check_freq.py
- `numpy`

### selfdrive/debug/check_timings.py
- `numpy`

### selfdrive/debug/cpu_usage_stat.py
- `numpy`
- `psutil`

### selfdrive/debug/dump.py
- `hexdump.hexdump`

### selfdrive/debug/format_fingerprints.py
- `jinja2`

### selfdrive/debug/internal/fuzz_fw_fingerprint.py
- `tqdm.tqdm`

### selfdrive/debug/internal/qlog_size.py
- `matplotlib.pyplot`

### selfdrive/debug/live_cpu_and_temp.py
- `capnp`

### selfdrive/debug/test_fw_query_on_routes.py
- `tqdm.tqdm`

### selfdrive/debug/toyota_eps_factor.py
- `matplotlib.pyplot`
- `numpy`
- `sklearn.linear_model`

### selfdrive/frogpilot/assets/download_functions.py
- `requests`

### selfdrive/frogpilot/assets/model_manager.py
- `requests`

### selfdrive/frogpilot/assets/theme_manager.py
- `dateutil.easter`
- `requests`

### selfdrive/frogpilot/controls/lib/chauffeur_mtsc.py
- `__future__.annotations`
- `numpy`

### selfdrive/frogpilot/controls/lib/chauffeur_vtsc.py
- `numpy`

### selfdrive/frogpilot/controls/lib/frogpilot_following.py
- `numpy`

### selfdrive/frogpilot/controls/lib/frogpilot_vcruise.py
- `numpy`

### selfdrive/frogpilot/fleetmanager/fleet_manager.py
- `flask.Flask`
- `flask.Response`
- `flask.jsonify`
- `flask.redirect`
- `flask.render_template`
- `flask.request`
- `flask.send_from_directory`
- `flask.session`
- `flask.url_for`
- `requests`
- `requests.exceptions.ConnectionError`

### selfdrive/frogpilot/fleetmanager/helpers.py
- `requests`

### selfdrive/frogpilot/frogpilot_functions.py
- `filecmp`
- `zstandard`

### selfdrive/frogpilot/frogpilot_utilities.py
- `azure.core.exceptions.ResourceExistsError`
- `azure.core.exceptions.ResourceNotFoundError`
- `azure.storage.fileshare.ShareDirectoryClient`
- `azure.storage.fileshare.ShareFileClient`
- `numpy`

### selfdrive/frogpilot/frogpilot_variables.py
- `numpy`

### selfdrive/frogpilot/navigation/mapd_py/downloader/params.py
- `errno`

### selfdrive/frogpilot/navigation/mapd_py/geometry.py
- `numpy`

### selfdrive/frogpilot/navigation/mapd_py/logging_utils.py
- `zmq`

### selfdrive/frogpilot/navigation/mapd_py/mapd_daemon.py
- `numpy`
- `shapely.geometry.Point`

### selfdrive/frogpilot/navigation/mapd_py/mapd_daemon_wrapper.py
- `shapely`

### selfdrive/frogpilot/navigation/mapd_py/matcher.py
- `logging_utils.log_event`
- `rtree.index`

### selfdrive/frogpilot/navigation/mapd_py/osm_speed_data_pb2.py
- `google.protobuf.descriptor`
- `google.protobuf.descriptor_pool`
- `google.protobuf.internal.builder`
- `google.protobuf.runtime_version`
- `google.protobuf.symbol_database`

### selfdrive/frogpilot/navigation/mapd_py/reader.py
- `google.protobuf.message.DecodeError`
- `logging_utils.log_event`
- `rtree.index`
- `shapely.geometry.LineString`
- `shapely.geometry.Point`

### selfdrive/locationd/calibrationd.py
- `capnp`
- `numpy`

### selfdrive/locationd/helpers.py
- `numpy`

### selfdrive/locationd/models/car_kf.py
- `numpy`
- `sympy`

### selfdrive/locationd/models/live_kf.py
- `numpy`
- `sympy`

### selfdrive/locationd/paramsd.py
- `numpy`

### selfdrive/locationd/test/test_calibrationd.py
- `numpy`

### selfdrive/locationd/test/test_locationd.py
- `capnp`
- `pytest`

### selfdrive/locationd/test/test_locationd_scenarios.py
- `numpy`
- `pytest`

### selfdrive/locationd/torqued.py
- `numpy`

### selfdrive/modeld/constants.py
- `numpy`

### selfdrive/modeld/dmonitoringmodeld.py
- `numpy`

### selfdrive/modeld/fill_model_msg.py
- `capnp`
- `numpy`

### selfdrive/modeld/get_model_metadata.py
- `onnx`

### selfdrive/modeld/modeld.py
- `numpy`
- `setproctitle.setproctitle`

### selfdrive/modeld/parse_model_outputs.py
- `numpy`

### selfdrive/modeld/runners/onnxmodel.py
- `numpy`
- `onnx`
- `onnxruntime`

### selfdrive/modeld/runners/ort_helpers.py
- `numpy`
- `onnx`
- `onnxruntime`

### selfdrive/monitoring/test_monitoring.py
- `numpy`

### selfdrive/navd/helpers.py
- `__future__.annotations`

### selfdrive/navd/map_renderer.py
- `cffi.FFI`
- `matplotlib.pyplot`
- `numpy`
- `polyline`

### selfdrive/navd/navd.py
- `requests`

### selfdrive/navd/tests/test_map_renderer.py
- `numpy`
- `pytest`
- `requests`

### selfdrive/navd/tests/test_navd.py
- `numpy`
- `parameterized.parameterized`

### selfdrive/pandad/pandad.py
- `usb1`

### selfdrive/pandad/tests/test_pandad.py
- `pytest`

### selfdrive/pandad/tests/test_pandad_loopback.py
- `pytest`

### selfdrive/pandad/tests/test_pandad_spi.py
- `numpy`
- `pytest`

### selfdrive/test/ciui.py
- `PyQt5.QtCore.QTimer`
- `PyQt5.QtWidgets.QApplication`
- `PyQt5.QtWidgets.QLabel`
- `PyQt5.QtWidgets.QVBoxLayout`
- `PyQt5.QtWidgets.QWidget`

### selfdrive/test/fuzzy_generation.py
- `capnp`
- `hypothesis.strategies`

### selfdrive/test/helpers.py
- `pytest`

### selfdrive/test/longitudinal_maneuvers/maneuver.py
- `numpy`

### selfdrive/test/longitudinal_maneuvers/plant.py
- `numpy`

### selfdrive/test/longitudinal_maneuvers/test_longitudinal.py
- `parameterized.parameterized_class`

### selfdrive/test/process_replay/capture.py
- `ipykernel.iostream.OutStream`

### selfdrive/test/process_replay/compare_logs.py
- `capnp`
- `dictdiffer`
- `numbers`

### selfdrive/test/process_replay/model_replay.py
- `requests`

### selfdrive/test/process_replay/process_replay.py
- `capnp`
- `tqdm.tqdm`

### selfdrive/test/process_replay/regen.py
- `capnp`
- `numpy`

### selfdrive/test/process_replay/regen_all.py
- `tqdm.tqdm`

### selfdrive/test/process_replay/test_fuzzy.py
- `hypothesis.HealthCheck`
- `hypothesis.Phase`
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `parameterized.parameterized`

### selfdrive/test/process_replay/test_imgproc.py
- `numpy`
- `pyopencl`

### selfdrive/test/process_replay/test_processes.py
- `tqdm.tqdm`

### selfdrive/test/process_replay/test_regen.py
- `parameterized.parameterized`

### selfdrive/test/profiling/lib.py
- `capnp`

### selfdrive/test/profiling/profiler.py
- `pprofile`
- `pyprof2calltree`

### selfdrive/test/test_onroad.py
- `numpy`
- `psutil`
- `pytest`

### selfdrive/test/test_time_to_onroad.py
- `pytest`

### selfdrive/test/test_updated.py
- `pytest`

### selfdrive/test/update_ci_routes.py
- `tqdm.tqdm`

### selfdrive/tinygrad_modeld/constants.py
- `numpy`

### selfdrive/tinygrad_modeld/dmonitoringmodeld.py
- `numpy`
- `setproctitle.setproctitle`

### selfdrive/tinygrad_modeld/fill_model_msg.py
- `capnp`
- `numpy`

### selfdrive/tinygrad_modeld/get_model_metadata.py
- `onnx`

### selfdrive/tinygrad_modeld/parse_model_outputs.py
- `numpy`

### selfdrive/tinygrad_modeld/runners/ort_helpers.py
- `numpy`
- `onnx`
- `onnxruntime`

### selfdrive/tinygrad_modeld/tests/test_modeld.py
- `numpy`
- `opendbc.car.car_helpers.get_demo_car_params`

### selfdrive/tinygrad_modeld/tests/tf_test/pb_loader.py
- `tensorflow`

### selfdrive/tinygrad_modeld/tests/timing/benchmark.py
- `numpy`

### selfdrive/tinygrad_modeld/tinygrad_modeld.py
- `numpy`
- `setproctitle.setproctitle`

### selfdrive/ui/qt/python_helpers.py
- `cffi.FFI`
- `sip`

### selfdrive/ui/soundd.py
- `numpy`
- `sounddevice`

### selfdrive/ui/tests/test_translations.py
- `parameterized.parameterized_class`
- `pytest`
- `requests`

### selfdrive/ui/tests/test_ui/run.py
- `jinja2`
- `matplotlib.pyplot`
- `numpy`
- `pyautogui`
- `pywinctl`

### selfdrive/ui/translations/auto_translate.py
- `requests`

### selfdrive/ui/translations/create_badges.py
- `requests`

### selfdrive/ui/ui.py
- `PyQt5.QtCore.QTimer`
- `PyQt5.QtCore.Qt`
- `PyQt5.QtWidgets.QApplication`
- `PyQt5.QtWidgets.QLabel`
- `PyQt5.QtWidgets.QStackedLayout`
- `PyQt5.QtWidgets.QVBoxLayout`
- `PyQt5.QtWidgets.QWidget`

### site_scons/site_tools/cython.py
- `SCons`
- `SCons.Action.Action`
- `SCons.Scanner.Scanner`

### system/athena/athenad.py
- `__future__.annotations`
- `azure.core.exceptions.ResourceExistsError`
- `azure.core.exceptions.ResourceNotFoundError`
- `azure.core.exceptions.ServiceResponseError`
- `azure.storage.fileshare.ShareDirectoryClient`
- `azure.storage.fileshare.ShareFileClient`
- `zstandard`

### system/athena/registration.py
- `jwt`

### system/athena/tests/test_athenad.py
- `pytest`
- `requests`
- `websocket.ABNF`
- `websocket._exceptions.WebSocketConnectionClosedException`

### system/athena/tests/test_athenad_ping.py
- `pytest`

### system/athena/tests/test_registration.py
- `Crypto.PublicKey.RSA`

### system/camerad/snapshot/snapshot.py
- `PIL.Image`
- `numpy`

### system/camerad/test/get_thumbnails_for_segment.py
- `tqdm.tqdm`

### system/camerad/test/test_camerad.py
- `flaky.flaky`
- `numpy`
- `pytest`

### system/camerad/test/test_exposure.py
- `numpy`

### system/hardware/base.py
- `abc.ABC`
- `abc.abstractmethod`

### system/hardware/fan_controller.py
- `abc.ABC`
- `abc.abstractmethod`

### system/hardware/hardwared.py
- `psutil`

### system/hardware/tests/test_fan_controller.py
- `pytest`

### system/hardware/tests/test_power_monitoring.py
- `pytest`

### system/hardware/tici/agnos.py
- `requests`

### system/hardware/tici/amplifier.py
- `smbus2.SMBus`

### system/hardware/tici/esim.py
- `requests`
- `serial`

### system/hardware/tici/hardware.py
- `dbus`

### system/hardware/tici/power_monitor.py
- `numpy`

### system/hardware/tici/precise_power_measure.py
- `numpy`

### system/hardware/tici/tests/compare_casync_manifest.py
- `requests`
- `tqdm.tqdm`

### system/hardware/tici/tests/test_agnos_updater.py
- `requests`

### system/hardware/tici/tests/test_amplifier.py
- `pytest`

### system/hardware/tici/tests/test_hardware.py
- `numpy`
- `pytest`

### system/hardware/tici/tests/test_power_draw.py
- `numpy`
- `pytest`
- `tabulate.tabulate`

### system/loggerd/tests/test_encoder.py
- `parameterized.parameterized`
- `pytest`
- `tqdm.trange`

### system/loggerd/tests/test_loggerd.py
- `flaky.flaky`
- `numpy`

### system/loggerd/uploader.py
- `requests`

### system/loggerd/xattr_cache.py
- `errno`

### system/logmessaged.py
- `zmq`

### system/manager/helpers.py
- `errno`

### system/manager/process.py
- `abc.ABC`
- `abc.abstractmethod`
- `setproctitle.setproctitle`

### system/manager/test/test_manager.py
- `parameterized.parameterized`
- `pytest`

### system/micd.py
- `numpy`
- `sounddevice`

### system/qcomgpsd/modemdiag.py
- `crcmod.mkCrcFun`
- `serial.Serial`

### system/qcomgpsd/qcomgpsd.py
- `requests`

### system/qcomgpsd/tests/test_qcomgpsd.py
- `pytest`

### system/sensord/tests/test_sensord.py
- `numpy`
- `pytest`

### system/sentry.py
- `sentry_sdk`
- `sentry_sdk.integrations.threading.ThreadingIntegration`

### system/statsd.py
- `zmq`

### system/timed.py
- `timezonefinder.TimezoneFinder`

### system/ubloxd/pigeond.py
- `requests`
- `serial`

### system/ubloxd/tests/test_pigeond.py
- `pytest`

### system/ugpsd.py
- `numpy`
- `serial`

### system/updated/casync/casync.py
- `Crypto.Hash.SHA512`
- `abc.ABC`
- `abc.abstractmethod`
- `requests`

### system/updated/casync/tests/test_casync.py
- `pytest`

### system/updated/tests/test_base.py
- `pytest`
- `stat`

### system/updated/updated.py
- `psutil`
- `zoneinfo.ZoneInfo`

### system/webrtc/device/audio.py
- `aiortc`
- `av`
- `numpy`
- `pyaudio`

### system/webrtc/device/video.py
- `av`

### system/webrtc/schema.py
- `capnp`

### system/webrtc/tests/test_stream_session.py
- `aiortc.RTCDataChannel`
- `aiortc.mediastreams.VIDEO_CLOCK_RATE`
- `aiortc.mediastreams.VIDEO_TIME_BASE`
- `capnp`
- `pyaudio`

### system/webrtc/tests/test_webrtcd.py
- `aiortc`
- `parameterized.parameterized_class`
- `pytest`

### system/webrtc/webrtcd.py
- `aiohttp.web`
- `aiortc.contrib.media.MediaBlackhole`
- `aiortc.exceptions.InvalidStateError`
- `aiortc.mediastreams.AudioStreamTrack`
- `aiortc.mediastreams.VideoStreamTrack`
- `aiortc.rtcdatachannel.RTCDataChannel`
- `capnp`

### teleoprtc_repo/examples/face_detection/face_detection.py
- `aiohttp`
- `aiortc`
- `cv2`
- `pygame`

### teleoprtc_repo/examples/videostream_cli/cli.py
- `aiortc`
- `aiortc.mediastreams.AudioStreamTrack`
- `aiortc.mediastreams.VideoStreamTrack`

### teleoprtc_repo/teleoprtc/builder.py
- `abc`
- `aiortc`

### teleoprtc_repo/teleoprtc/info.py
- `aiortc`

### teleoprtc_repo/teleoprtc/stream.py
- `abc`
- `aiortc`
- `aiortc.contrib.media.MediaRelay`

### teleoprtc_repo/teleoprtc/tracks.py
- `aiortc`
- `aiortc.mediastreams.VIDEO_CLOCK_RATE`
- `aiortc.mediastreams.VIDEO_TIME_BASE`

### teleoprtc_repo/tests/test_integration.py
- `aiortc.mediastreams.AudioStreamTrack`
- `aiortc.mediastreams.VideoStreamTrack`
- `parameterized.parameterized`

### teleoprtc_repo/tests/test_stream.py
- `aiortc`
- `aiortc.mediastreams.AudioStreamTrack`

### teleoprtc_repo/tests/test_track.py
- `aiortc`

### third_party/acados/acados_template/__init__.py
- `acados_model.AcadosModel`
- `acados_ocp.AcadosOcp`
- `acados_ocp.AcadosOcpConstraints`
- `acados_ocp.AcadosOcpCost`
- `acados_ocp.AcadosOcpDims`
- `acados_ocp.AcadosOcpOptions`
- `acados_ocp_solver.AcadosOcpSolver`
- `acados_ocp_solver.get_simulink_default_opts`
- `acados_ocp_solver.ocp_get_default_cmake_builder`
- `acados_sim.AcadosSim`
- `acados_sim.AcadosSimDims`
- `acados_sim.AcadosSimOpts`
- `acados_sim_solver.AcadosSimSolver`
- `acados_sim_solver.sim_get_default_cmake_builder`
- `utils.J_to_idx`
- `utils.acados_dae_model_json_dump`
- `utils.casadi_length`
- `utils.check_casadi_version`
- `utils.get_acados_path`
- `utils.get_default_simulink_opts`
- `utils.get_python_interface_path`
- `utils.get_tera`
- `utils.get_tera_exec_path`
- `utils.make_object_json_dumpable`
- `utils.print_casadi_expression`
- `zoro_description.ZoroDescription`
- `zoro_description.process_zoro_description`

### third_party/acados/acados_template/acados_ocp.py
- `acados_model.AcadosModel`
- `numpy`
- `utils.J_to_idx`
- `utils.J_to_idx_slack`
- `utils.get_acados_path`
- `utils.get_lib_ext`

### third_party/acados/acados_template/acados_ocp_solver.py
- `acados_model.AcadosModel`
- `acados_ocp.AcadosOcp`
- `builders.CMakeBuilder`
- `casadi_function_generation.generate_c_code_conl_cost`
- `casadi_function_generation.generate_c_code_constraint`
- `casadi_function_generation.generate_c_code_discrete_dynamics`
- `casadi_function_generation.generate_c_code_explicit_ode`
- `casadi_function_generation.generate_c_code_external_cost`
- `casadi_function_generation.generate_c_code_gnsf`
- `casadi_function_generation.generate_c_code_implicit_ode`
- `casadi_function_generation.generate_c_code_nls_cost`
- `gnsf.detect_gnsf_structure.detect_gnsf_structure`
- `numpy`
- `utils.casadi_length`
- `utils.check_casadi_version`
- `utils.format_class_dict`
- `utils.get_lib_ext`
- `utils.get_ocp_nlp_layout`
- `utils.get_python_interface_path`
- `utils.is_column`
- `utils.is_empty`
- `utils.make_model_consistent`
- `utils.make_object_json_dumpable`
- `utils.render_template`
- `utils.set_up_imported_gnsf_model`

### third_party/acados/acados_template/acados_sim.py
- `acados_model.AcadosModel`
- `numpy`
- `utils.get_acados_path`
- `utils.get_lib_ext`

### third_party/acados/acados_template/acados_sim_solver.py
- `acados_ocp.AcadosOcp`
- `acados_sim.AcadosSim`
- `builders.CMakeBuilder`
- `casadi_function_generation.generate_c_code_explicit_ode`
- `casadi_function_generation.generate_c_code_gnsf`
- `casadi_function_generation.generate_c_code_implicit_ode`
- `gnsf.detect_gnsf_structure.detect_gnsf_structure`
- `numpy`
- `utils.casadi_length`
- `utils.check_casadi_version`
- `utils.format_class_dict`
- `utils.get_lib_ext`
- `utils.get_python_interface_path`
- `utils.is_column`
- `utils.is_empty`
- `utils.make_model_consistent`
- `utils.make_object_json_dumpable`
- `utils.render_template`
- `utils.set_up_imported_gnsf_model`

### third_party/acados/acados_template/casadi_function_generation.py
- `casadi`
- `utils.casadi_length`
- `utils.is_empty`

### third_party/acados/acados_template/gnsf/check_reformulation.py
- `acados_template.utils.casadi_length`
- `casadi`
- `numpy`

### third_party/acados/acados_template/gnsf/detect_affine_terms_reduce_nonlinearity.py
- `casadi`
- `check_reformulation.check_reformulation`
- `determine_input_nonlinearity_function.determine_input_nonlinearity_function`
- `utils.casadi_length`
- `utils.print_casadi_expression`

### third_party/acados/acados_template/gnsf/detect_gnsf_structure.py
- `casadi.Function`
- `casadi.SX`
- `casadi.horzcat`
- `casadi.jacobian`
- `casadi.vertcat`
- `check_reformulation.check_reformulation`
- `detect_affine_terms_reduce_nonlinearity.detect_affine_terms_reduce_nonlinearity`
- `determine_trivial_gnsf_transcription.determine_trivial_gnsf_transcription`
- `reformulate_with_LOS.reformulate_with_LOS`
- `reformulate_with_invertible_E_mat.reformulate_with_invertible_E_mat`
- `structure_detection_print_summary.structure_detection_print_summary`

### third_party/acados/acados_template/gnsf/determine_input_nonlinearity_function.py
- `casadi`
- `utils.casadi_length`
- `utils.is_empty`

### third_party/acados/acados_template/gnsf/determine_trivial_gnsf_transcription.py
- `casadi`
- `check_reformulation.check_reformulation`
- `determine_input_nonlinearity_function.determine_input_nonlinearity_function`
- `numpy`
- `utils.casadi_length`
- `utils.idx_perm_to_ipiv`

### third_party/acados/acados_template/gnsf/reformulate_with_LOS.py
- `casadi`
- `check_reformulation.check_reformulation`
- `determine_input_nonlinearity_function.determine_input_nonlinearity_function`
- `utils.casadi_length`
- `utils.idx_perm_to_ipiv`
- `utils.is_empty`

### third_party/acados/acados_template/gnsf/reformulate_with_invertible_E_mat.py
- `casadi`
- `check_reformulation.check_reformulation`
- `determine_input_nonlinearity_function.determine_input_nonlinearity_function`

### third_party/acados/acados_template/gnsf/structure_detection_print_summary.py
- `casadi.n_nodes`
- `numpy`

### third_party/acados/acados_template/utils.py
- `casadi.CasadiMeta`
- `casadi.DM`
- `casadi.Function`
- `casadi.MX`
- `casadi.SX`
- `numpy`

### third_party/acados/acados_template/zoro_description.py
- `numpy`

### tinygrad_repo/examples/beautiful_cartpole.py
- `gymnasium`
- `numpy`

### tinygrad_repo/examples/beautiful_cifar.py
- `extra.lr_scheduler.OneCycleLR`
- `numpy`

### tinygrad_repo/examples/benchmark_onnx.py
- `extra.onnx.get_run_onnx`
- `onnx`

### tinygrad_repo/examples/coder.py
- `extra.junk.sentencepiece_model_pb2`
- `extra.models.llama.Transformer`
- `extra.models.llama.convert_from_huggingface`
- `extra.models.llama.fix_bf16`
- `sentencepiece.SentencePieceProcessor`

### tinygrad_repo/examples/compile_efficientnet.py
- `extra.export_model.export_model`
- `extra.models.efficientnet.EfficientNet`

### tinygrad_repo/examples/compile_tensorflow.py
- `extra.export_model.compile_net`
- `extra.export_model.export_model_clang`
- `extra.export_model.jit_model`
- `extra.onnx.get_run_onnx`
- `numpy`
- `tensorflow`
- `tf2onnx`

### tinygrad_repo/examples/conversation.py
- `extra.junk.sentencepiece_model_pb2`
- `llama.LLaMa`
- `nltk`
- `numpy`
- `pyaudio`
- `sentencepiece.SentencePieceProcessor`
- `vits.HParams`
- `vits.MODELS`
- `vits.Synthesizer`
- `vits.TextMapper`
- `vits.Y_LENGTH_ESTIMATE_SCALARS`
- `vits.get_hparams_from_file`
- `vits.load_model`
- `whisper.init_whisper`
- `whisper.transcribe_waveform`
- `yaml`

### tinygrad_repo/examples/efficientnet.py
- `PIL.Image`
- `cv2`
- `extra.models.efficientnet.EfficientNet`
- `numpy`

### tinygrad_repo/examples/flux1.py
- `PIL.Image`
- `extra.models.clip.FrozenClosedClipEmbedder`
- `extra.models.t5.T5Embedder`
- `numpy`
- `sdxl.FirstStage`

### tinygrad_repo/examples/gpt2.py
- `tiktoken`

### tinygrad_repo/examples/handcode_opt.py
- `examples.mlperf.helpers.get_mlperf_bert_model`
- `extra.mcts_search.mcts_search`
- `extra.models.resnet.ResNet50`

### tinygrad_repo/examples/hlb_cifar10.py
- `extra.lr_scheduler.OneCycleLR`
- `numpy`

### tinygrad_repo/examples/llama.py
- `extra.models.llama.Transformer`
- `extra.models.llama.convert_from_huggingface`
- `extra.models.llama.fix_bf16`
- `llama3.Int8Linear`
- `llama3.NF4Linear`
- `numpy`
- `sentencepiece.SentencePieceProcessor`
- `tiktoken`
- `tiktoken.load.load_tiktoken_bpe`

### tinygrad_repo/examples/llama3.py
- `bottle.Bottle`
- `bottle.HTTPResponse`
- `bottle.abort`
- `bottle.request`
- `bottle.response`
- `bottle.static_file`
- `extra.models.llama.Transformer`
- `extra.models.llama.convert_from_gguf`
- `extra.models.llama.convert_from_huggingface`
- `extra.models.llama.fix_bf16`
- `tiktoken`
- `tiktoken.load.load_tiktoken_bpe`

### tinygrad_repo/examples/llm.c/export.py
- `train_gpt2.GPT`
- `train_gpt2.GPTConfig`

### tinygrad_repo/examples/llm.c/train_gpt2.py
- `numpy`
- `tiktoken`

### tinygrad_repo/examples/mamba.py
- `tqdm.tqdm`
- `transformers.AutoTokenizer`

### tinygrad_repo/examples/mask_rcnn.py
- `PIL.Image`
- `cv2`
- `extra.models.mask_rcnn.BoxList`
- `extra.models.mask_rcnn.MaskRCNN`
- `extra.models.resnet.ResNet`
- `numpy`
- `torch`
- `torch.nn.functional`
- `torchvision.transforms`
- `torchvision.transforms.functional`

### tinygrad_repo/examples/mixtral.py
- `extra.models.llama.FeedForward`
- `extra.models.llama.Transformer`
- `sentencepiece.SentencePieceProcessor`

### tinygrad_repo/examples/mlperf/dataloader.py
- `PIL.Image`
- `extra.datasets.imagenet.center_crop`
- `extra.datasets.imagenet.get_imagenet_categories`
- `extra.datasets.imagenet.get_train_files`
- `extra.datasets.imagenet.get_val_files`
- `extra.datasets.imagenet.preprocess_train`
- `extra.datasets.kits19.TRAIN_PREPROCESSED_DIR`
- `extra.datasets.kits19.VAL_PREPROCESSED_DIR`
- `extra.datasets.kits19.gaussian_noise`
- `extra.datasets.kits19.get_train_files`
- `extra.datasets.kits19.get_val_files`
- `extra.datasets.kits19.preprocess_dataset`
- `extra.datasets.kits19.rand_balanced_crop`
- `extra.datasets.kits19.rand_flip`
- `extra.datasets.kits19.random_brightness_augmentation`
- `extra.datasets.wikipedia.get_wiki_train_files`
- `numpy`

### tinygrad_repo/examples/mlperf/helpers.py
- `examples.mlperf.initializers.EmbeddingBert`
- `examples.mlperf.initializers.LayerNormBert`
- `examples.mlperf.initializers.LinearBert`
- `extra.models.bert`
- `extra.models.bert.BertForPretraining`
- `numpy`
- `scipy.signal`

### tinygrad_repo/examples/mlperf/losses.py
- `examples.mlperf.metrics.dice_score`

### tinygrad_repo/examples/mlperf/lr_schedulers.py
- `extra.lr_scheduler.LR_Scheduler`

### tinygrad_repo/examples/mlperf/model_eval.py
- `examples.mask_rcnn.Image`
- `examples.mask_rcnn.compute_prediction_batched`
- `examples.mlperf.dataloader.batch_load_resnet`
- `examples.mlperf.helpers.get_bert_qa_prediction`
- `examples.mlperf.metrics.dice_score`
- `examples.mlperf.metrics.f1_score`
- `examples.mlperf.metrics.word_error_rate`
- `extra.datasets.coco.BASEDIR`
- `extra.datasets.coco.accumulate_predictions_for_coco`
- `extra.datasets.coco.convert_prediction_to_coco_bbox`
- `extra.datasets.coco.convert_prediction_to_coco_mask`
- `extra.datasets.coco.evaluate_predictions_on_coco`
- `extra.datasets.coco.images`
- `extra.datasets.coco.iterate`
- `extra.datasets.kits19.get_val_files`
- `extra.datasets.kits19.iterate`
- `extra.datasets.kits19.sliding_window_inference`
- `extra.datasets.librispeech.iterate`
- `extra.datasets.openimages.BASEDIR`
- `extra.datasets.openimages.download_dataset`
- `extra.datasets.openimages.iterate`
- `extra.datasets.squad.iterate`
- `extra.models.bert.BertForQuestionAnswering`
- `extra.models.mask_rcnn.MaskRCNN`
- `extra.models.resnet.ResNeXt50_32X4D`
- `extra.models.resnet.ResNet`
- `extra.models.resnet.ResNet50`
- `extra.models.retinanet.RetinaNet`
- `extra.models.rnnt.RNNT`
- `extra.models.unet3d.UNet3D`
- `numpy`
- `pycocotools.coco.COCO`
- `pycocotools.cocoeval.COCOeval`
- `tqdm.tqdm`
- `transformers.BertTokenizer`

### tinygrad_repo/examples/mlperf/model_spec.py
- `extra.models.bert.BertForQuestionAnswering`
- `extra.models.mask_rcnn.MaskRCNN`
- `extra.models.mask_rcnn.ResNet`
- `extra.models.resnet.ResNet50`
- `extra.models.retinanet.RetinaNet`
- `extra.models.rnnt.RNNT`
- `extra.models.unet3d.UNet3D`
- `numpy`

### tinygrad_repo/examples/mlperf/model_train.py
- `examples.hlb_cifar10.UnsyncedBatchNorm`
- `examples.mlperf.dataloader.batch_load_resnet`
- `examples.mlperf.dataloader.batch_load_train_bert`
- `examples.mlperf.dataloader.batch_load_unet3d`
- `examples.mlperf.dataloader.batch_load_val_bert`
- `examples.mlperf.helpers.get_data_bert`
- `examples.mlperf.helpers.get_fake_data_bert`
- `examples.mlperf.helpers.get_mlperf_bert_model`
- `examples.mlperf.helpers.get_training_state`
- `examples.mlperf.helpers.load_training_state`
- `examples.mlperf.initializers.Conv2dHeNormal`
- `examples.mlperf.initializers.Linear`
- `examples.mlperf.losses.dice_ce_loss`
- `examples.mlperf.lr_schedulers.PolynomialDecayWithWarmup`
- `examples.mlperf.metrics.dice_score`
- `extra.datasets.imagenet.get_train_files`
- `extra.datasets.imagenet.get_val_files`
- `extra.datasets.kits19.TRAIN_PREPROCESSED_DIR`
- `extra.datasets.kits19.VAL_PREPROCESSED_DIR`
- `extra.datasets.kits19.get_train_files`
- `extra.datasets.kits19.get_val_files`
- `extra.datasets.kits19.iterate`
- `extra.datasets.kits19.preprocess_dataset`
- `extra.datasets.kits19.sliding_window_inference`
- `extra.lr_scheduler.LRSchedulerGroup`
- `extra.models.resnet`
- `extra.models.unet3d.UNet3D`
- `mlperf_logging.mllog`
- `mlperf_logging.mllog.constants`
- `tqdm.tqdm`
- `wandb`

### tinygrad_repo/examples/mnist_gan.py
- `extra.datasets.fetch_mnist`
- `numpy`
- `torch`
- `torchvision.utils.make_grid`
- `torchvision.utils.save_image`

### tinygrad_repo/examples/openelm.py
- `sentencepiece.SentencePieceProcessor`

### tinygrad_repo/examples/openpilot/compile3.py
- `extra.onnx.get_run_onnx`
- `numpy`
- `onnx`
- `onnx.helper.tensor_dtype_to_np_dtype`
- `onnxruntime`

### tinygrad_repo/examples/other_mnist/beautiful_mnist_mlx.py
- `mlx.core`
- `mlx.nn`
- `mlx.optimizers`

### tinygrad_repo/examples/other_mnist/beautiful_mnist_torch.py
- `torch`
- `torch.nn`
- `torch.optim`

### tinygrad_repo/examples/qwq.py
- `examples.llama3.load`
- `extra.models.llama.Transformer`
- `extra.models.llama.convert_from_huggingface`
- `extra.models.llama.fix_bf16`
- `transformers.AutoTokenizer`

### tinygrad_repo/examples/rl/lightupbutton.py
- `gymnasium`
- `gymnasium.envs.registration.register`
- `numpy`

### tinygrad_repo/examples/sdv2.py
- `PIL.Image`
- `examples.sdxl.DPMPP2MSampler`
- `examples.sdxl.LegacyDDPMDiscretization`
- `examples.sdxl.append_dims`
- `examples.stable_diffusion.AutoencoderKL`
- `examples.stable_diffusion.get_alphas_cumprod`
- `extra.models.clip.FrozenOpenClipEmbedder`
- `extra.models.unet.UNetModel`

### tinygrad_repo/examples/sdxl.py
- `PIL.Image`
- `abc.ABC`
- `abc.abstractmethod`
- `examples.stable_diffusion.Mid`
- `examples.stable_diffusion.ResnetBlock`
- `extra.models.clip.Embedder`
- `extra.models.clip.FrozenClosedClipEmbedder`
- `extra.models.clip.FrozenOpenClipEmbedder`
- `extra.models.unet.Downsample`
- `extra.models.unet.UNetModel`
- `extra.models.unet.Upsample`
- `extra.models.unet.timestep_embedding`
- `numpy`

### tinygrad_repo/examples/self_tokenize.py
- `examples.llama3.Tokenizer`
- `tabulate.tabulate`

### tinygrad_repo/examples/serious_mnist.py
- `extra.augment.augment_img`
- `extra.datasets.fetch_mnist`
- `extra.training.evaluate`
- `extra.training.train`
- `numpy`

### tinygrad_repo/examples/so_vits_svc.py
- `__future__.annotations`
- `examples.sovits_helpers.preprocess`
- `examples.vits.Encoder`
- `examples.vits.HParams`
- `examples.vits.LRELU_SLOPE`
- `examples.vits.PosteriorEncoder`
- `examples.vits.ResBlock1`
- `examples.vits.ResBlock2`
- `examples.vits.ResidualCouplingBlock`
- `examples.vits.get_hparams_from_file`
- `examples.vits.load_checkpoint`
- `examples.vits.sequence_mask`
- `examples.vits.split`
- `examples.vits.weight_norm`
- `numpy`
- `soundfile`

### tinygrad_repo/examples/sovits_helpers/preprocess.py
- `librosa`
- `numpy`
- `parselmouth`
- `soundfile`

### tinygrad_repo/examples/stable_diffusion.py
- `PIL.Image`
- `extra.models.clip.Closed`
- `extra.models.clip.Tokenizer`
- `extra.models.unet.UNetModel`
- `numpy`

### tinygrad_repo/examples/stunning_mnist.py
- `examples.beautiful_mnist.Model`

### tinygrad_repo/examples/train_efficientnet.py
- `extra.datasets.fetch_cifar`
- `extra.datasets.imagenet.fetch_batch`
- `extra.models.efficientnet.EfficientNet`
- `numpy`

### tinygrad_repo/examples/train_resnet.py
- `PIL.Image`
- `extra.datasets.fetch_mnist`
- `extra.models.resnet.ResNet`
- `extra.training.evaluate`
- `extra.training.train`
- `numpy`

### tinygrad_repo/examples/transformer.py
- `extra.models.transformer.Transformer`
- `extra.training.evaluate`
- `extra.training.train`
- `numpy`

### tinygrad_repo/examples/vgg7.py
- `PIL.Image`
- `examples.vgg7_helpers.waifu2x.Vgg7`
- `examples.vgg7_helpers.waifu2x.image_load`
- `examples.vgg7_helpers.waifu2x.image_save`
- `numpy`

### tinygrad_repo/examples/vgg7_helpers/waifu2x.py
- `PIL.Image`
- `numpy`

### tinygrad_repo/examples/vit.py
- `PIL.Image`
- `extra.models.vit.ViT`
- `numpy`

### tinygrad_repo/examples/vits.py
- `eng_to_ipa`
- `inflect`
- `numpy`
- `phonemizer.backend.EspeakBackend`
- `phonemizer.phonemize._phonemize`
- `phonemizer.phonemize.default_separator`
- `phonemizer.punctuation.Punctuation`
- `unidecode.unidecode`

### tinygrad_repo/examples/webgpu/stable_diffusion/compile.py
- `examples.stable_diffusion.StableDiffusion`
- `extra.export_model.compile_net`
- `extra.export_model.dtype_to_js_type`
- `extra.export_model.jit_model`
- `extra.f16_decompress.u32_to_f16`
- `numpy`
- `requests`

### tinygrad_repo/examples/webgpu/yolov8/compile.py
- `examples.yolov8.YOLOv8`
- `examples.yolov8.get_weights_location`
- `extra.export_model.export_model`

### tinygrad_repo/examples/whisper.py
- `librosa`
- `numpy`
- `pyaudio`
- `tiktoken`

### tinygrad_repo/examples/yolov3.py
- `PIL.Image`
- `cv2`
- `numpy`

### tinygrad_repo/examples/yolov8-onnx.py
- `extra.onnx.get_run_onnx`
- `onnx`
- `ultralytics.YOLO`

### tinygrad_repo/examples/yolov8.py
- `cv2`
- `numpy`

### tinygrad_repo/extra/accel/ane/1_build/coreml_ane.py
- `coremltools`
- `coremltools.models.neural_network.NeuralNetworkBuilder`
- `coremltools.models.neural_network.datatypes`
- `numpy`

### tinygrad_repo/extra/accel/ane/2_compile/dcompile.py
- `networkx`
- `networkx.drawing.nx_pydot.read_dot`
- `pylab`

### tinygrad_repo/extra/accel/ane/2_compile/hwx_parse.py
- `ane.ANE`
- `ane.ANE_Struct`
- `hexdump.hexdump`
- `macholib.MachO`
- `macholib.SymbolTable`
- `termcolor.colored`

### tinygrad_repo/extra/accel/ane/2_compile/struct_recover.py
- `ane.ANE`

### tinygrad_repo/extra/accel/ane/amfi/new_patch.py
- `hexdump.hexdump`

### tinygrad_repo/extra/accel/ane/lib/ane.py
- `faulthandler`
- `numpy`

### tinygrad_repo/extra/accel/ane/lib/testconv.py
- `ane.ANE`
- `ane.ANETensor`

### tinygrad_repo/extra/accel/ane/tinygrad/ops_ane.py
- `tensor.Device`
- `tensor.Function`
- `tensor.register`

### tinygrad_repo/extra/accel/intel/benchmark_matmul.py
- `openvino.runtime.Core`

### tinygrad_repo/extra/archprobe.py
- `matplotlib.pyplot`
- `numpy`
- `tqdm.tqdm`
- `tqdm.trange`

### tinygrad_repo/extra/assembly/assembly_rdna.py
- `extra.helpers.enable_early_exec`
- `yaml`

### tinygrad_repo/extra/assembly/ptx/test.py
- `numpy`

### tinygrad_repo/extra/assembly/rocm/rdna3/asm.py
- `extra.helpers.enable_early_exec`
- `hexdump.hexdump`
- `numpy`

### tinygrad_repo/extra/augment.py
- `PIL.Image`
- `extra.datasets.fetch_mnist`
- `matplotlib.pyplot`
- `numpy`
- `tqdm.trange`

### tinygrad_repo/extra/backends/ops_hsa.py
- `__future__.annotations`
- `extra.hip_gpu_driver.hip_ioctl`

### tinygrad_repo/extra/backends/rdna.py
- `yaml`

### tinygrad_repo/extra/backends/triton.py
- `triton.compiler.compile`

### tinygrad_repo/extra/datasets/__init__.py
- `numpy`

### tinygrad_repo/extra/datasets/coco.py
- `examples.mask_rcnn.Masker`
- `numpy`
- `pycocotools._mask`
- `pycocotools.coco.COCO`
- `pycocotools.cocoeval.COCOeval`

### tinygrad_repo/extra/datasets/fake_imagenet_from_mnist.py
- `PIL.Image`
- `extra.datasets.fetch_mnist`
- `numpy`

### tinygrad_repo/extra/datasets/imagenet.py
- `PIL.Image`
- `extra.datasets.fake_imagenet_from_mnist.create_fake_mnist_imagenet`
- `numpy`

### tinygrad_repo/extra/datasets/imagenet_download.py
- `tqdm.tqdm`

### tinygrad_repo/extra/datasets/kits19.py
- `nibabel`
- `numpy`
- `scipy.ndimage`
- `scipy.signal`
- `torch`
- `torch.nn.functional`
- `tqdm.tqdm`

### tinygrad_repo/extra/datasets/librispeech.py
- `librosa`
- `numpy`
- `soundfile`

### tinygrad_repo/extra/datasets/openimages.py
- `PIL.Image`
- `boto3`
- `botocore`
- `numpy`
- `pandas`
- `torchvision.transforms.functional`

### tinygrad_repo/extra/datasets/preprocess_imagenet.py
- `extra.datasets.imagenet.get_val_files`
- `extra.datasets.imagenet.iterate`

### tinygrad_repo/extra/datasets/squad.py
- `numpy`
- `transformers.BertTokenizer`

### tinygrad_repo/extra/datasets/wikipedia.py
- `numpy`
- `tqdm.contrib.concurrent.process_map`
- `tqdm.tqdm`

### tinygrad_repo/extra/datasets/wikipedia_download.py
- `gdown`
- `tqdm.tqdm`

### tinygrad_repo/extra/disassemblers/adreno/__init__.py
- `hexdump.hexdump`

### tinygrad_repo/extra/dsp/compile.py
- `adsprpc`
- `hexdump.hexdump`
- `ion`
- `llvmlite.binding`
- `msm_ion`
- `run`

### tinygrad_repo/extra/dsp/run.py
- `hexdump.hexdump`

### tinygrad_repo/extra/dsp/run_3.py
- `hexdump.hexdump`

### tinygrad_repo/extra/gemm/amx.py
- `llvmlite.ir`
- `numpy`

### tinygrad_repo/extra/gemm/cuda_matmul.py
- `numpy`

### tinygrad_repo/extra/gemm/fuzz_matmul.py
- `numpy`

### tinygrad_repo/extra/gemm/gemm.py
- `numpy`

### tinygrad_repo/extra/gemm/hip_matmul.py
- `numpy`

### tinygrad_repo/extra/gemm/intel_xmx.py
- `hexdump.hexdump`
- `numpy`

### tinygrad_repo/extra/gemm/jax_pmatmul.py
- `jax`
- `jax.numpy`

### tinygrad_repo/extra/gemm/metal_conv.py
- `numpy`
- `torch`
- `torch.mps`

### tinygrad_repo/extra/gemm/metal_matmul.py
- `numpy`
- `torch`
- `torch.mps`

### tinygrad_repo/extra/gemm/metal_matvec.py
- `numpy`
- `torch`
- `torch.mps`

### tinygrad_repo/extra/gemm/mlx_matmul.py
- `mlx.core`

### tinygrad_repo/extra/gemm/simple_conv.py
- `numpy`
- `torch`

### tinygrad_repo/extra/gemm/simple_matmul.py
- `numpy`

### tinygrad_repo/extra/gemm/simple_matvec.py
- `numpy`

### tinygrad_repo/extra/gemm/tf_gemm.py
- `tensorflow`

### tinygrad_repo/extra/gemm/torch_gemm.py
- `torch`

### tinygrad_repo/extra/gemm/triton_nv_matmul.py
- `numpy`
- `torch`
- `triton`
- `triton.compiler.ASTSource`
- `triton.compiler.AttrsDescriptor`
- `triton.compiler.compile`
- `triton.language`

### tinygrad_repo/extra/gemm/tvm_gemm.py
- `tvm`
- `tvm.te`

### tinygrad_repo/extra/gradcheck.py
- `numpy`

### tinygrad_repo/extra/hip_gpu_driver/test_kfd_2.py
- `extra.hip_gpu_driver.hip_ioctl`
- `hexdump.hexdump`

### tinygrad_repo/extra/hip_gpu_driver/test_pm4.py
- `hexdump.hexdump`

### tinygrad_repo/extra/junk/sentencepiece_model_pb2.py
- `google.protobuf.descriptor`
- `google.protobuf.descriptor_pool`
- `google.protobuf.internal.builder`
- `google.protobuf.symbol_database`

### tinygrad_repo/extra/mcts_search.py
- `__future__.annotations`
- `networkx`
- `numpy`

### tinygrad_repo/extra/models/bert.py
- `numpy`
- `tensorflow`
- `torch`

### tinygrad_repo/extra/models/clip.py
- `PIL.Image`
- `abc.ABC`
- `abc.abstractmethod`
- `numpy`

### tinygrad_repo/extra/models/inception.py
- `numpy`
- `scipy.linalg`

### tinygrad_repo/extra/models/mask_rcnn.py
- `extra.models.resnet.ResNet`
- `extra.models.retinanet.nms`
- `numpy`

### tinygrad_repo/extra/models/retinanet.py
- `extra.models.resnet.ResNeXt50_32X4D`
- `extra.models.resnet.ResNet`
- `numpy`
- `torch.hub.load_state_dict_from_url`

### tinygrad_repo/extra/models/rnnt.py
- `numpy`
- `torch`

### tinygrad_repo/extra/models/t5.py
- `sentencepiece.SentencePieceProcessor`

### tinygrad_repo/extra/models/unet3d.py
- `torch`

### tinygrad_repo/extra/models/vit.py
- `extra.models.transformer.TransformerBlock`
- `numpy`

### tinygrad_repo/extra/multitensor.py
- `numpy`

### tinygrad_repo/extra/nv_gpu_driver/nv_ioctl.py
- `hexdump.hexdump`

### tinygrad_repo/extra/onnx.py
- `numpy`
- `onnx.AttributeProto`
- `onnx.ModelProto`
- `onnx.TensorProto`
- `onnx.ValueInfoProto`
- `onnx.helper.tensor_dtype_to_np_dtype`
- `onnx.mapping.TENSOR_TYPE_TO_NP_TYPE`

### tinygrad_repo/extra/onnx_ops.py
- `PIL.Image`
- `extra.onnx.dtype_parse`
- `extra.onnx.to_python_const`
- `numpy`

### tinygrad_repo/extra/optimization/extract_policynet.py
- `extra.optimization.helpers.assert_same_lin`
- `extra.optimization.helpers.ast_str_to_lin`
- `extra.optimization.helpers.lin_to_feats`
- `extra.optimization.helpers.load_worlds`
- `matplotlib.pyplot`
- `tqdm.tqdm`
- `tqdm.trange`

### tinygrad_repo/extra/optimization/extract_sa_pairs.py
- `extra.optimization.helpers.lin_to_feats`
- `extra.optimization.pretrain_valuenet.ValueNet`
- `matplotlib.pyplot`
- `numpy`
- `tqdm.tqdm`
- `tqdm.trange`

### tinygrad_repo/extra/optimization/get_action_space.py
- `extra.optimization.helpers.ast_str_to_lin`
- `extra.optimization.helpers.load_worlds`

### tinygrad_repo/extra/optimization/pretrain_valuenet.py
- `extra.optimization.helpers.MAX_DIMS`
- `extra.optimization.helpers.lin_to_feats`
- `matplotlib.pyplot`
- `tqdm.tqdm`
- `tqdm.trange`

### tinygrad_repo/extra/optimization/rl.py
- `extra.optimization.extract_policynet.PolicyNet`
- `extra.optimization.helpers.ast_str_to_lin`
- `extra.optimization.helpers.lin_to_feats`
- `extra.optimization.helpers.load_worlds`
- `numpy`

### tinygrad_repo/extra/optimization/run_qnet.py
- `extra.optimization.helpers.lin_to_feats`
- `extra.optimization.pretrain_valuenet.ValueNet`
- `numpy`

### tinygrad_repo/extra/optimization/search.py
- `extra.optimization.helpers.ast_str_to_lin`

### tinygrad_repo/extra/optimization/test_beam_search.py
- `numpy`

### tinygrad_repo/extra/optimization/test_helpers.py
- `extra.optimization.helpers.load_worlds`

### tinygrad_repo/extra/optimization/test_net.py
- `extra.optimization.extract_policynet.PolicyNet`
- `extra.optimization.helpers.ast_str_to_lin`
- `extra.optimization.helpers.lin_to_feats`
- `extra.optimization.helpers.load_worlds`
- `extra.optimization.pretrain_valuenet.ValueNet`
- `numpy`

### tinygrad_repo/extra/optimization/test_time_linearizer.py
- `extra.optimization.helpers.ast_str_to_lin`
- `extra.optimization.helpers.load_worlds`

### tinygrad_repo/extra/qcom_gpu_driver/opencl_ioctl.py
- `extra.disassemblers.adreno.disasm_raw`
- `extra.qcom_gpu_driver.msm_kgsl`
- `hexdump.hexdump`

### tinygrad_repo/extra/qcom_gpu_driver/qcom_opencl_interop.py
- `extra.qcom_gpu_driver.opencl_ioctl`
- `hexdump.hexdump`

### tinygrad_repo/extra/resnet18/resnet_mlx.py
- `huggingface_hub.snapshot_download`
- `mlx.core`
- `mlx.nn`

### tinygrad_repo/extra/resnet18/resnet_tinygrad.py
- `huggingface_hub.snapshot_download`

### tinygrad_repo/extra/thneed.py
- `numpy`
- `pyopencl`

### tinygrad_repo/extra/to_movement_ops.py
- `extra.optimization.helpers.ast_str_to_ast`
- `extra.optimization.helpers.load_worlds`

### tinygrad_repo/extra/training.py
- `numpy`

### tinygrad_repo/setup.py
- `setuptools.setup`

### tinygrad_repo/sz.py
- `tabulate.tabulate`

### tinygrad_repo/test/external/external_benchmark_hcopt.py
- `extra.optimization.helpers.ast_str_to_lin`
- `extra.optimization.helpers.load_worlds`

### tinygrad_repo/test/external/external_benchmark_load_stable_diffusion.py
- `examples.stable_diffusion.StableDiffusion`

### tinygrad_repo/test/external/external_benchmark_openpilot.py
- `extra.onnx.get_run_onnx`
- `numpy`
- `onnx`
- `onnx.helper.tensor_dtype_to_np_dtype`

### tinygrad_repo/test/external/external_benchmark_resnet.py
- `examples.hlb_cifar10.UnsyncedBatchNorm`
- `examples.mlperf.initializers.Conv2dHeNormal`
- `examples.mlperf.initializers.Linear`
- `extra.models.resnet`

### tinygrad_repo/test/external/external_benchmark_schedule.py
- `extra.models.resnet.ResNet50`

### tinygrad_repo/test/external/external_hip_compiler_bug.py
- `gpuctypes.hip`

### tinygrad_repo/test/external/external_jit_failure.py
- `numpy`

### tinygrad_repo/test/external/external_llama_eval.py
- `examples.llama.LLaMa`
- `lm_eval.base.BaseLM`
- `lm_eval.evaluator`
- `lm_eval.tasks`
- `torch`

### tinygrad_repo/test/external/external_model_benchmark.py
- `extra.onnx.get_run_onnx`
- `numpy`
- `onnx`
- `onnx.helper.tensor_dtype_to_np_dtype`
- `onnx2torch.convert`
- `onnxruntime`
- `torch`

### tinygrad_repo/test/external/external_multi_gpu.py
- `numpy`

### tinygrad_repo/test/external/external_test_datasets.py
- `examples.mlperf.dataloader.batch_load_unet3d`
- `extra.datasets.kits19.iterate`
- `extra.datasets.kits19.preprocess`
- `nibabel`
- `numpy`

### tinygrad_repo/test/external/external_test_hcq_fuzz_failures.py
- `numpy`

### tinygrad_repo/test/external/external_test_image.py
- `numpy`

### tinygrad_repo/test/external/external_test_jit_on_models.py
- `examples.llama.Transformer`
- `examples.stable_diffusion.UNetModel`
- `examples.stable_diffusion.unet_params`
- `numpy`

### tinygrad_repo/test/external/external_test_llama3_ff.py
- `extra.models.llama.FeedForward`

### tinygrad_repo/test/external/external_test_losses.py
- `examples.mlperf.losses.dice_ce_loss`
- `numpy`
- `torch`

### tinygrad_repo/test/external/external_test_mamba.py
- `examples.mamba.Mamba`
- `examples.mamba.generate`
- `transformers.AutoTokenizer`

### tinygrad_repo/test/external/external_test_metrics.py
- `examples.mlperf.metrics.dice_score`
- `numpy`
- `torch`

### tinygrad_repo/test/external/external_test_mnist_data_select.py
- `extra.datasets.fetch_mnist`

### tinygrad_repo/test/external/external_test_onnx_backend.py
- `extra.onnx.get_run_onnx`
- `numpy`
- `onnx.backend.base.Backend`
- `onnx.backend.base.BackendRep`
- `onnx.backend.test`

### tinygrad_repo/test/external/external_test_opt.py
- `examples.llama.Transformer`
- `extra.models.convnext.ConvNeXt`
- `extra.models.efficientnet.EfficientNet`
- `extra.models.resnet.ResNet18`
- `extra.models.vit.ViT`
- `numpy`
- `torch`

### tinygrad_repo/test/external/external_test_optim.py
- `examples.mlperf.lr_schedulers.PolynomialDecayWithWarmup`
- `extra.lr_scheduler.LRSchedulerGroup`
- `numpy`
- `tensorflow`
- `tensorflow.python.ops.math_ops`
- `tensorflow_addons`

### tinygrad_repo/test/external/external_test_speed_llama.py
- `examples.llama.MODEL_PARAMS`
- `examples.llama.Transformer`

### tinygrad_repo/test/external/external_test_whisper_librispeech.py
- `examples.whisper.init_whisper`
- `examples.whisper.transcribe_waveform`
- `jiwer`
- `numpy`
- `torch`
- `torchaudio`
- `tqdm`
- `whisper.normalizers.EnglishTextNormalizer`

### tinygrad_repo/test/external/external_test_yolo.py
- `cv2`
- `examples.yolov3.Darknet`
- `examples.yolov3.infer`
- `examples.yolov3.show_labels`

### tinygrad_repo/test/external/external_test_yolov8.py
- `cv2`
- `examples.yolov8.YOLOv8`
- `examples.yolov8.get_variant_multiples`
- `examples.yolov8.label_predictions`
- `examples.yolov8.postprocess`
- `examples.yolov8.preprocess`
- `numpy`
- `onnxruntime`
- `ultralytics`

### tinygrad_repo/test/external/fuzz_graph.py
- `numpy`

### tinygrad_repo/test/external/fuzz_kfd.py
- `tqdm.trange`

### tinygrad_repo/test/external/fuzz_linearizer.py
- `extra.nv_gpu_driver.nv_ioctl`
- `extra.optimization.helpers.ast_str_to_lin`
- `extra.optimization.helpers.kern_str_to_lin`
- `extra.optimization.helpers.load_worlds`
- `extra.qcom_gpu_driver.opencl_ioctl`
- `numpy`

### tinygrad_repo/test/external/fuzz_schedule.py
- `numpy`

### tinygrad_repo/test/external/fuzz_uops.py
- `numpy`

### tinygrad_repo/test/external/mlperf_bert/external_benchmark_bert.py
- `extra.models.bert`

### tinygrad_repo/test/external/mlperf_bert/external_test_checkpoint_loading.py
- `examples.mlperf.dataloader.batch_load_val_bert`
- `examples.mlperf.helpers.get_data_bert`
- `examples.mlperf.helpers.get_mlperf_bert_model`
- `examples.mlperf.model_train.eval_step_bert`
- `tqdm.tqdm`

### tinygrad_repo/test/external/mlperf_bert/preprocessing/create_pretraining_data.py
- `__future__.absolute_import`
- `__future__.division`
- `__future__.print_function`
- `tensorflow`
- `tokenization`

### tinygrad_repo/test/external/mlperf_bert/preprocessing/external_test_preprocessing_part.py
- `tensorflow`
- `tqdm.tqdm`

### tinygrad_repo/test/external/mlperf_bert/preprocessing/pick_eval_samples.py
- `tensorflow`

### tinygrad_repo/test/external/mlperf_bert/preprocessing/tokenization.py
- `__future__.absolute_import`
- `__future__.division`
- `__future__.print_function`
- `absl.flags`
- `six`
- `tensorflow.compat.v1`

### tinygrad_repo/test/external/mlperf_resnet/lars_optimizer.py
- `__future__.absolute_import`
- `__future__.division`
- `__future__.print_function`
- `tensorflow`
- `tensorflow.python.framework.ops`
- `tensorflow.python.keras.backend_config`
- `tensorflow.python.keras.optimizer_v2.optimizer_v2`
- `tensorflow.python.ops.array_ops`
- `tensorflow.python.ops.linalg_ops`
- `tensorflow.python.ops.math_ops`
- `tensorflow.python.ops.state_ops`
- `tensorflow.python.training.training_ops`

### tinygrad_repo/test/external/mlperf_resnet/lars_util.py
- `__future__.absolute_import`
- `__future__.division`
- `__future__.print_function`
- `absl.flags`
- `tensorflow`
- `tensorflow.python.eager.context`
- `tensorflow.python.framework.ops`
- `tensorflow.python.keras.optimizer_v2.learning_rate_schedule`
- `tensorflow.python.ops.math_ops`

### tinygrad_repo/test/external/mlperf_unet3d/dice.py
- `torch`
- `torch.nn`
- `torch.nn.functional`

### tinygrad_repo/test/external/mlperf_unet3d/kits19.py
- `numpy`
- `scipy.ndimage`
- `torch.utils.data.Dataset`
- `torchvision.transforms`

### tinygrad_repo/test/external/speed_beam_v_hcopt.py
- `extra.optimization.helpers.ast_str_to_lin`
- `extra.optimization.helpers.load_worlds`

### tinygrad_repo/test/external/speed_compare_cuda_nv.py
- `extra.optimization.helpers.ast_str_to_lin`
- `extra.optimization.helpers.load_worlds`
- `numpy`

### tinygrad_repo/test/external/speed_compare_cuda_ptx.py
- `extra.optimization.helpers.ast_str_to_lin`
- `extra.optimization.helpers.load_worlds`

### tinygrad_repo/test/external/verify_kernel.py
- `extra.optimization.helpers.kern_str_to_lin`

### tinygrad_repo/test/helpers.py
- `numpy`
- `ocdiff`

### tinygrad_repo/test/imported/test_indexing.py
- `numpy`

### tinygrad_repo/test/mockgpu/mockgpu.py
- `builtins`

### tinygrad_repo/test/models/test_bert.py
- `extra.models.bert.BertForQuestionAnswering`
- `numpy`
- `torch`
- `transformers.BertConfig`
- `transformers.BertForQuestionAnswering`

### tinygrad_repo/test/models/test_efficientnet.py
- `PIL.Image`
- `extra.models.efficientnet.EfficientNet`
- `extra.models.resnet.ResNet50`
- `extra.models.vit.ViT`
- `numpy`

### tinygrad_repo/test/models/test_end2end.py
- `extra.datasets.fetch_mnist`
- `numpy`
- `torch`
- `torch.nn`

### tinygrad_repo/test/models/test_mnist.py
- `extra.datasets.fetch_mnist`
- `extra.training.evaluate`
- `extra.training.train`
- `numpy`

### tinygrad_repo/test/models/test_onnx.py
- `extra.onnx.get_run_onnx`
- `numpy`
- `onnx`
- `onnx2torch.convert`
- `torch`

### tinygrad_repo/test/models/test_real_world.py
- `examples.beautiful_mnist.Model`
- `examples.gpt2.MODEL_PARAMS`
- `examples.gpt2.Transformer`
- `examples.hlb_cifar10.SpeedyResNet`
- `examples.hlb_cifar10.hyp`
- `examples.llama.Transformer`
- `examples.stable_diffusion.UNetModel`
- `examples.stable_diffusion.unet_params`
- `extra.lr_scheduler.OneCycleLR`
- `extra.models.unet.ResBlock`
- `numpy`

### tinygrad_repo/test/models/test_resnet.py
- `extra.models.resnet`

### tinygrad_repo/test/models/test_rnnt.py
- `extra.models.rnnt.LSTM`
- `numpy`
- `torch`

### tinygrad_repo/test/models/test_train.py
- `extra.introspection.print_objects`
- `extra.models.convnext.ConvNeXt`
- `extra.models.efficientnet.EfficientNet`
- `extra.models.resnet.ResNet18`
- `extra.models.transformer.Transformer`
- `extra.models.vit.ViT`
- `extra.training.train`
- `numpy`

### tinygrad_repo/test/models/test_waifu2x.py
- `examples.vgg7_helpers.waifu2x.Vgg7`
- `examples.vgg7_helpers.waifu2x.image_load`
- `numpy`

### tinygrad_repo/test/models/test_whisper.py
- `examples.whisper.init_whisper`
- `examples.whisper.load_file_waveform`
- `examples.whisper.transcribe_file`
- `examples.whisper.transcribe_waveform`

### tinygrad_repo/test/test_arange.py
- `numpy`
- `torch`

### tinygrad_repo/test/test_assign.py
- `numpy`

### tinygrad_repo/test/test_const_folding.py
- `numpy`

### tinygrad_repo/test/test_conv.py
- `numpy`

### tinygrad_repo/test/test_dtype.py
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `numpy`
- `pytest`
- `torch`

### tinygrad_repo/test/test_dtype_alu.py
- `hypothesis.HealthCheck`
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `numpy`
- `pytest`

### tinygrad_repo/test/test_fusion_op.py
- `numpy`

### tinygrad_repo/test/test_fuzz_shape_ops.py
- `__future__.annotations`
- `hypothesis.assume`
- `hypothesis.extra.numpy`
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `numpy`
- `torch`

### tinygrad_repo/test/test_gc.py
- `numpy`

### tinygrad_repo/test/test_graph.py
- `numpy`

### tinygrad_repo/test/test_image_dtype.py
- `numpy`

### tinygrad_repo/test/test_jit.py
- `extra.models.unet.ResBlock`
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `numpy`

### tinygrad_repo/test/test_lazybuffer.py
- `numpy`

### tinygrad_repo/test/test_linearizer.py
- `numpy`

### tinygrad_repo/test/test_linearizer_failures.py
- `numpy`

### tinygrad_repo/test/test_method_cache.py
- `examples.gpt2.Transformer`

### tinygrad_repo/test/test_multitensor.py
- `examples.hlb_cifar10.UnsyncedBatchNorm`
- `extra.lr_scheduler.OneCycleLR`
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `numpy`
- `resnet.ResNet18`

### tinygrad_repo/test/test_net_speed.py
- `torch`

### tinygrad_repo/test/test_nn.py
- `numpy`
- `torch`

### tinygrad_repo/test/test_ops.py
- `numpy`
- `torch`

### tinygrad_repo/test/test_optim.py
- `numpy`
- `torch`

### tinygrad_repo/test/test_pickle.py
- `numpy`

### tinygrad_repo/test/test_randomness.py
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `numpy`
- `torch`

### tinygrad_repo/test/test_rearrange_einops.py
- `numpy`

### tinygrad_repo/test/test_renderer_failures.py
- `numpy`

### tinygrad_repo/test/test_sample.py
- `numpy`

### tinygrad_repo/test/test_schedule.py
- `extra.models.llama.precompute_freqs_cis`
- `numpy`
- `torch`

### tinygrad_repo/test/test_setitem.py
- `numpy`

### tinygrad_repo/test/test_speed_v_torch.py
- `numpy`
- `torch`
- `torch.cuda`
- `torch.mps`

### tinygrad_repo/test/test_symbolic_jit.py
- `numpy`

### tinygrad_repo/test/test_symbolic_ops.py
- `examples.gpt2.Attention`
- `numpy`

### tinygrad_repo/test/test_tensor.py
- `extra.gradcheck.gradcheck`
- `extra.gradcheck.jacobian`
- `extra.gradcheck.numerical_jacobian`
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `numpy`
- `torch`

### tinygrad_repo/test/test_tensor_variable.py
- `numpy`

### tinygrad_repo/test/test_to_numpy.py
- `numpy`

### tinygrad_repo/test/test_transcendental.py
- `hypothesis.given`
- `hypothesis.settings`
- `hypothesis.strategies`
- `numpy`

### tinygrad_repo/test/test_uops.py
- `numpy`

### tinygrad_repo/test/testextra/test_export_model.py
- `extra.export_model.EXPORT_SUPPORTED_DEVICE`
- `extra.export_model.export_model`

### tinygrad_repo/test/testextra/test_f16_decompress.py
- `extra.f16_decompress.u32_to_f16`
- `numpy`

### tinygrad_repo/test/testextra/test_lr_scheduler.py
- `extra.datasets.fetch_mnist`
- `extra.lr_scheduler.CosineAnnealingLR`
- `extra.lr_scheduler.MultiStepLR`
- `extra.lr_scheduler.OneCycleLR`
- `extra.lr_scheduler.ReduceLROnPlateau`
- `extra.training.evaluate`
- `extra.training.train`
- `numpy`
- `torch`

### tinygrad_repo/test/testextra/test_mockgpu.py
- `typing_extensions`

### tinygrad_repo/test/unit/test_disk_tensor.py
- `extra.models.efficientnet.EfficientNet`
- `numpy`
- `safetensors.numpy.save_file`
- `safetensors.safe_open`
- `safetensors.torch.save_file`
- `torch`

### tinygrad_repo/test/unit/test_gguf.py
- `ggml`
- `numpy`

### tinygrad_repo/test/unit/test_gradient.py
- `jax`
- `jax.numpy`

### tinygrad_repo/test/unit/test_helpers.py
- `PIL.Image`
- `numpy`

### tinygrad_repo/test/unit/test_shapetracker.py
- `numpy`

### tinygrad_repo/test/unit/test_shm_tensor.py
- `numpy`

### tinygrad_repo/test/unit/test_tar.py
- `numpy`

### tinygrad_repo/test/unit/test_tqdm.py
- `numpy`
- `tqdm.tqdm`

### tinygrad_repo/test/unit/test_transcendental_helpers.py
- `numpy`

### tinygrad_repo/test/unit/test_verify_ast.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/__init__.py
- `typeguard.install_import_hook`

### tinygrad_repo/tinygrad/codegen/kernel.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/codegen/linearize.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/codegen/uopgraph.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/device.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/dtype.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/helpers.py
- `__future__.annotations`
- `contextvars`
- `copyreg`

### tinygrad_repo/tinygrad/multi.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/nn/__init__.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/ops.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/renderer/__init__.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/runtime/ops_amd.py
- `__future__.annotations`
- `errno`
- `extra.hip_gpu_driver.hip_ioctl`

### tinygrad_repo/tinygrad/runtime/ops_cloud.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/runtime/ops_cuda.py
- `__future__.annotations`
- `extra.nv_gpu_driver.nv_ioctl`

### tinygrad_repo/tinygrad/runtime/ops_disk.py
- `_posixshmem`

### tinygrad_repo/tinygrad/runtime/ops_dsp.py
- `__future__.annotations`
- `extra.dsp.run`

### tinygrad_repo/tinygrad/runtime/ops_gpu.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/runtime/ops_hip.py
- `extra.hip_gpu_driver.hip_ioctl`

### tinygrad_repo/tinygrad/runtime/ops_llvm.py
- `llvmlite.binding`

### tinygrad_repo/tinygrad/runtime/ops_npy.py
- `numpy`

### tinygrad_repo/tinygrad/runtime/ops_nv.py
- `__future__.annotations`
- `extra.nv_gpu_driver.nv_ioctl`

### tinygrad_repo/tinygrad/runtime/ops_qcom.py
- `__future__.annotations`
- `extra.qcom_gpu_driver.opencl_ioctl`

### tinygrad_repo/tinygrad/runtime/ops_webgpu.py
- `wgpu`

### tinygrad_repo/tinygrad/runtime/support/am/amdev.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/runtime/support/am/ip.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/runtime/support/hcq.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/shape/shapetracker.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/shape/view.py
- `__future__.annotations`

### tinygrad_repo/tinygrad/tensor.py
- `__future__.annotations`
- `numpy`

### tinygrad_repo/tinygrad/viz/serve.py
- `webbrowser`

### tools/azure_upload_tiles.py
- `azure.core.exceptions.ResourceExistsError`
- `azure.core.exceptions.ResourceNotFoundError`
- `azure.storage.fileshare.ShareDirectoryClient`
- `azure.storage.fileshare.ShareFileClient`

### tools/bodyteleop/web.py
- `aiohttp.ClientSession`
- `aiohttp.web`
- `pyaudio`

### tools/camerastream/compressed_vipc.py
- `PyNvCodec`
- `av`
- `numpy`

### tools/debug/can_message_interrogator.py
- `opendbc.can.common.dbc.dbc`

### tools/debug/comm_issue_checker.py
- `__future__.annotations`

### tools/debug/live_root_cause_monitor.py
- `capnp`

### tools/debug/locationd_deep_diagnosis.py
- `__future__.annotations`

### tools/debug/monitor_service.py
- `__future__.annotations`

### tools/joystick/joystickd.py
- `inputs.get_gamepad`

### tools/latencylogger/latency_logger.py
- `matplotlib.patches`
- `matplotlib.pyplot`
- `mpld3`

### tools/lib/api.py
- `requests`

### tools/lib/auth.py
- `webbrowser`

### tools/lib/azure_container.py
- `azure.identity.AzureCliCredential`
- `azure.storage.blob.BlobClient`
- `azure.storage.blob.BlobServiceClient`
- `azure.storage.blob.ContainerClient`
- `azure.storage.blob.ContainerSasPermissions`
- `azure.storage.blob.generate_container_sas`

### tools/lib/comma_car_segments.py
- `requests`

### tools/lib/framereader.py
- `_io`
- `lru.LRU`
- `numpy`

### tools/lib/logreader.py
- `capnp`
- `tqdm`

### tools/lib/tests/test_caching.py
- `pytest`

### tools/lib/tests/test_comma_car_segments.py
- `pytest`
- `requests`

### tools/lib/tests/test_logreader.py
- `capnp`
- `parameterized.parameterized`
- `pytest`
- `requests`

### tools/lib/tests/test_readers.py
- `numpy`
- `pytest`
- `requests`

### tools/lib/url_file.py
- `urllib3.PoolManager`
- `urllib3.Retry`
- `urllib3.response.BaseHTTPResponse`
- `urllib3.util.Timeout`

### tools/map_processing/osm_speed_data_pb2.py
- `google.protobuf.descriptor`
- `google.protobuf.descriptor_pool`
- `google.protobuf.internal.builder`
- `google.protobuf.runtime_version`
- `google.protobuf.symbol_database`

### tools/map_processing/process_osm.py
- `numpy`

### tools/map_processing/test_mtsc_carson_rd.py
- `numpy`

### tools/navd_speed_limit_checker.py
- `requests`

### tools/plotjuggler/juggle.py
- `requests`
- `urllib3`

### tools/replay/can_replay.py
- `usb1`

### tools/replay/lib/ui_helpers.py
- `matplotlib.backends.backend_agg.FigureCanvasAgg`
- `matplotlib.pyplot`
- `numpy`
- `pygame`

### tools/replay/ui.py
- `cv2`
- `numpy`
- `pygame`

### tools/rerun/run.py
- `rerun`
- `rerun.blueprint`

### tools/scripts/fetch_image_from_route.py
- `PIL.Image`
- `requests`

### tools/scripts/setup_ssh_keys.py
- `requests`

### tools/sim/bridge/common.py
- `abc.ABC`
- `abc.abstractmethod`

### tools/sim/bridge/metadrive/metadrive_bridge.py
- `metadrive.component.map.pg_map.MapGenerateMethod`
- `metadrive.component.sensors.base_camera._cuda_enable`

### tools/sim/bridge/metadrive/metadrive_common.py
- `metadrive.component.sensors.rgb_camera.RGBCamera`
- `numpy`
- `panda3d.core.GraphicsOutput`
- `panda3d.core.Texture`

### tools/sim/bridge/metadrive/metadrive_process.py
- `metadrive.engine.core.engine_core.EngineCore`
- `metadrive.engine.core.image_buffer.ImageBuffer`
- `metadrive.envs.metadrive_env.MetaDriveEnv`
- `metadrive.obs.image_obs.ImageObservation`
- `numpy`
- `panda3d.core.Vec3`

### tools/sim/bridge/metadrive/metadrive_world.py
- `numpy`

### tools/sim/lib/camerad.py
- `numpy`
- `pyopencl`
- `pyopencl.array`

### tools/sim/lib/common.py
- `abc.ABC`
- `abc.abstractmethod`
- `numpy`

### tools/sim/lib/manual_ctrl.py
- `evdev`
- `evdev.InputDevice`
- `evdev.ecodes`

### tools/sim/lib/simulated_car.py
- `opendbc.can.packer.CANPacker`
- `opendbc.can.parser.CANParser`

### tools/sim/tests/conftest.py
- `pytest`

### tools/sim/tests/test_metadrive_bridge.py
- `pytest`

### tools/sim/tests/test_sim_bridge.py
- `pytest`

### tools/web/app.py
- `flask.Flask`
- `flask.Response`
- `flask.render_template`
- `flask.send_from_directory`
- `jinja2`
- `rosgraph`

### tools/webcam/camera.py
- `cv2`
- `numpy`

## Most Used Standard Library Modules

| Module | Usage Count |
|--------|-----------|
| `os` | 326 |
| `time` | 271 |
| `unittest` | 172 |
| `sys` | 140 |
| `math` | 105 |
| `json` | 90 |
| `argparse` | 90 |
| `random` | 88 |
| `ctypes` | 87 |
| `collections.defaultdict` | 82 |
| `pathlib.Path` | 78 |
| `subprocess` | 62 |
| `typing.Optional` | 62 |
| `struct` | 61 |
| `typing.Any` | 60 |
| `functools` | 57 |
| `typing.List` | 53 |
| `pathlib` | 51 |
| `dataclasses.dataclass` | 46 |
| `re` | 45 |

## Most Used Internal Modules

| Module | Usage Count |
|--------|-----------|
| `tinygrad.Tensor` | 139 |
| `cereal.messaging` | 132 |
| `tinygrad.helpers.getenv` | 130 |
| `cereal.car` | 123 |
| `tinygrad.dtypes` | 101 |
| `tinygrad.Device` | 99 |
| `tinygrad.tensor.Tensor` | 86 |
| `panda.Panda` | 84 |
| `openpilot.common.params.Params` | 83 |
| `cereal.log` | 73 |
| `tinygrad.ops.UOp` | 68 |
| `tinygrad.ops.Ops` | 65 |
| `tinygrad.dtype.dtypes` | 61 |
| `openpilot.common.swaglog.cloudlog` | 59 |
| `tinygrad.helpers.DEBUG` | 53 |
| `openpilot.common.conversions.Conversions` | 47 |
| `tinygrad.helpers.fetch` | 46 |
| `tinygrad.helpers.CI` | 45 |
| `tinygrad.TinyJit` | 43 |
| `openpilot.common.basedir.BASEDIR` | 37 |
