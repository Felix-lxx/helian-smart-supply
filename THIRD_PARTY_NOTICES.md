# 第三方代码与资源说明

本次发布整理保留第三方代码原有许可证，不为原项目整体新增许可证或改变既有权属。

| 组件 | 来源 / 本地位置 | 许可与说明 |
| --- | --- | --- |
| YOLOv5 | `vendor/yolov5/`；上游 `ultralytics/yolov5` | 随附 [AGPL-3.0 许可证](vendor/yolov5/LICENSE)，基准提交和省略资源见 [vendor 说明](vendor/README.md)。使用、修改、分发或提供网络服务时需核对其完整条款及对集成部分的影响。 |
| Vue、Vite、Element Plus、Pinia、ECharts、Leaflet 等 | 前端 `package.json` / `package-lock.json` | 依赖通过 npm 安装；其许可证以各发布包内容为准。 |
| Django、DRF、SciPy、NumPy、PyTorch 等 | `requirements.txt` / `requirements-ai.txt` | 依赖通过 pip 安装；可选 AI 依赖与基础业务依赖分开。许可证以各发布包内容为准。 |
| 天地图 | 使用者配置自己的服务密钥 | 底图版权标注保留。申请、服务授权及公开部署须遵守服务方使用条款，仓库不提供密钥。 |
| 演示商品图片 | 演示初始化脚本中的远程 Unsplash 图片 URL | 本仓库未下载或打包这些远程图片；外部资源可能不可用。部署前核对使用条件或替换为自有图片。 |
| 原项目静态素材 | 前端 `src/assets/` 中保留的既有素材 | 本次未新增授权声明；正式对外使用前确认权利来源。个人收款二维码未包含在发布内容中。 |

本仓库不发布训练数据、模型权重或用户上传证据；演示截图仅展示明确标识的虚构业务记录。
