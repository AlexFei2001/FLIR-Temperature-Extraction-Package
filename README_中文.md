# FLIR 温度矩阵提取工具 1.0.1

[English](README.md) | [Italiano](README_IT.md) | **中文**

GitHub仓库：[FLIR-Temperature-Extraction-Package](https://github.com/AlexFei2001/FLIR-Temperature-Extraction-Package)。可在仓库的 `dist/` 中下载独立工具包，或使用 **Code → Download ZIP** 下载全部代码。

这个文件夹可单独复制给同事使用，不需要原论文项目、YOLO、OpenCV、PyTorch、Labelme 或相机SDK。支持包含内嵌热数据与必要标定参数的 FLIR 辐射 JPEG（R-JPEG）。普通照片、截图或只有配色的导出图无法用于提取摄氏温度。

程序读取文件内嵌的16位热测量计数，结合原文件测温参数进行环境补偿和 Planck 温度反算，得到二维摄氏温度矩阵。不会裁剪、旋转、翻转或缩放矩阵。换算不读取色条来猜测温度。

## 1. 安装 Python 依赖

使用 Python 3.10–3.14。已有 Python 或 Conda 可直接使用；没有 Conda 也可以运行。先解压整个工具包，在该文件夹打开终端：

```powershell
python -m pip install -r requirements.txt
```

仅需 NumPy 和 Pillow。Pillow要求12.2或以上、低于13，以采用经过测试的16位图像解码方式并保留Python3.10支持。精确复现本次环境可安装 `requirements-tested.txt`。

如使用 Conda，可以新建一个小环境（不需要安装YOLO）：

```powershell
conda create -n flir_export python=3.11 -y
conda activate flir_export
python -m pip install -r requirements.txt
```

## 2. 安装 ExifTool 并配置路径

ExifTool未打包在此工具内，请从官方安装页面下载：

- https://exiftool.sourceforge.net/install.html
- 标签与原始热数据说明：https://exiftool.sourceforge.net/TagNames/FLIR.html

Windows建议选择Windows可执行版本，解压后将 `exiftool(-k).exe` 改名为 `exiftool.exe`。移动它时需要同时保留其配套 `exiftool_files` 文件夹；不要只复制一个exe。详细要求以官方安装说明为准。

将 `config.example.json` 复制为 `config.json`：

```powershell
Copy-Item config.example.json config.json
```

如果ExifTool不在PATH中，编辑为自己机器上的路径，例如：

```json
{
  "exiftool_command": ["C:/Tools/ExifTool/exiftool.exe"],
  "raw_byte_order": "swap16",
  "measurement_overrides": {}
}
```

JSON路径推荐使用 `/`。路径中有空格也可以，保持整个路径为一个JSON字符串，不要在字符串里面额外加引号。相对工具路径按 `config.json` 所在文件夹解析。

Linux/macOS或已将ExifTool加入PATH时，`["exiftool"]` 即可。若使用完整Perl版本，配置可为 `["perl", "vendor/exiftool/exiftool"]`；需要保留其配套 `lib` 文件夹，并已有Perl解释器。

### 字节序必须明确

- `swap16`：交换每个16位原始数值的两个字节。
- `native`：按Pillow解码得到的16位数值使用，不交换字节。

**示例的 `swap16` 来自本项目四张FLIR T1020文件的已使用配置，不代表所有FLIR型号或JPEG都应使用这个值。** 新设备或新文件类型应结合原始格式并与FLIR软件的同一像素读数核对。程序不会根据“图像看起来合理”静默选择字节序；错误字节序可能报错，也可能产生错误但有限的温度，不能只看是否成功输出。

检查依赖与配置：

```powershell
python extract_flir.py --check --config config.json
```

该检查只证明工具能运行，不证明字节序和绝对温度已核验。

## 3. 提取单张或整个文件夹

单张：

```powershell
python extract_flir.py --input "D:/FLIR photos/IR_0016.jpg" --output "D:/FLIR exports" --config config.json --csv
```

整个文件夹：

```powershell
python extract_flir.py --input "D:/FLIR photos" --output "D:/FLIR exports" --config config.json --csv
```

包括子文件夹时增加 `--recursive`。也可以在 `--input` 后列出多个文件或文件夹，以空格分隔、每条路径各自加引号。

`--csv` 表示同时生成完整温度CSV。若只需要NPY可去掉它。文件夹可能混有可见光照片：程序会逐个记录不支持/缺失参数的文件，不会给它们生成假的温度矩阵，其他可处理图片仍继续执行。结束后查看 `summary.csv`。

终端交互模式：

```powershell
python extract_flir.py --interactive
```

它会读取工具包内的 `config.json`（若存在），并询问一个输入文件/文件夹、输出位置和是否导出CSV。Windows也可以双击 `run_windows.cmd`。使用Conda时，优先在已激活环境的终端执行上述命令，以保证使用正确的Python；双击启动通常使用Windows默认Python。

查看全部参数：`python extract_flir.py --help`。

## 4. 输出文件是什么

每次执行都会在指定输出位置创建新的UTC时间戳/随机编号目录，不覆盖旧结果或原始图片：

```text
FLIR exports/
└─ <UTC时间戳_随机编号>/
   ├─ manifest.json
   ├─ summary.csv
   ├─ summary.json
   └─ 0001_IR_0016/
      ├─ temperature.npy
      ├─ temperature.csv        # 指定--csv时生成
      ├─ radiometry.json
      ├─ preview_gray.png
      └─ source_display.png
```

| 文件 | 含义 |
|---|---|
| `temperature.npy` | **完整摄氏温度矩阵**，float64，形状为 `(图像高度, 图像宽度)`。科学计算优先使用它。 |
| `temperature.csv` | 同一温度矩阵，无表头、无行号，逗号分隔、小数点为`.`，17位有效数字保留浮点读回精度。 |
| `radiometry.json` | 原始与实际使用的测温参数、字节序、原始/导出数据校验值、温度单位和维度等。 |
| `preview_gray.png` | 原生网格的8位灰度显示图，默认按1–99百分位显示，**像素值不是摄氏度**。显示裁剪不改变温度矩阵。 |
| `source_display.png` | 原JPEG可见的显示画面，用于方向/内容核对，可能含色条和文字，也不是温度矩阵。 |
| `summary.csv/json` | 每个输入是否成功、输出位置、温度范围、异常原因。 |
| `manifest.json` | 批次参数、工具与依赖版本、输入及输出校验信息。 |

输出子目录带序号，以区分不同文件夹内的同名文件。CSV体积较大；Excel可通过“数据→从文本/CSV”导入，明确逗号分隔和小数点，避免区域设置误读。程序不把多位小数解释为相机测温精度。

## 5. 如何读取温度矩阵

```python
import numpy as np
T = np.load("temperature.npy", allow_pickle=False)
print(T.shape)           # (height, width)
print(T[20, 10])         # x=10、y=20处的摄氏温度；坐标从0开始
print(T.min(), T.max(), T.mean())
```

或使用附带示例：

```powershell
python read_temperature_example.py "D:/FLIR exports/<run>/0001_IR_0016/temperature.npy" --x 10 --y 20
```

矩阵坐标是原始热数据网格。JPEG可见画面若包含外框、色条、可见光叠加等，不能假设其坐标直接等于温度矩阵坐标。

## 6. 测温参数与数值验证

默认保留JPEG元数据中的发射率、距离、反射温度、大气温度、湿度、窗口温度和透过率，以及Planck和大气补偿常数。缺少必要参数时拒绝换算，不静默补某型号的默认标定常数。

确需使用已知测温设置时，可在 `measurement_overrides` 中显式填写以下字段；原值与替换值都会保存：

| 字段 | 单位/范围 |
|---|---|
| `Emissivity` | 发射率，0–1且大于0 |
| `ObjectDistance` | 距离，米，非负 |
| `RelativeHumidity` | 相对湿度，0–1，60%应填写0.6 |
| `ReflectedApparentTemperature` | 反射表观温度，°C |
| `AtmosphericTemperature` | 大气温度，°C |
| `IRWindowTemperature` | 红外窗口温度，°C |
| `IRWindowTransmission` | 窗口透过率，0–1且大于0 |

不要为了让结果“好看”修改这些参数。当前补偿模型沿用既有实现，采用两个相等的大气半路径、窗口位于两者之间的假设。对特殊测量路径、不同相机/固件或缺失元数据的文件，不能自动保证与厂商软件完全一致。

**输出是按文件测温参数换算的温度估计；成功解码不等于独立测温校准。** 对新来源文件，请在FLIR软件中使用相同发射率、距离等设置，核对多个位置的数值与坐标。标签 `absolute_numeric_validation_complete: false` 会保留，程序不自行宣称绝对精度已验证。

## 7. 常见问题

- **找不到ExifTool**：检查 `config.json` 路径，或将其加入PATH；Windows需配套 `exiftool_files`，Perl版本需配套 `lib`。
- **缺少RawThermalImage**：文件可能是可见光图、截图、非辐射导出图，或不支持的文件类型；需要原始辐射JPEG。
- **缺少标定参数**：当前工具不能可靠恢复温度；使用完整原始文件或由厂商软件导出温度矩阵。
- **nonpositive corrected signal / invalid Planck inversion**：检查字节序及测温参数；不要当作有效结果忽略。
- **raw image must be exact-size 16-bit**：检查输入类型和Pillow版本。当前只支持二维16位原始热图。
- **有些图失败但其他图成功**：查看 `summary.csv`。退出码0表示全部成功且源文件不变；2表示部分失败或源文件校验不通过；1表示工具/配置等启动错误。
- **预览和原JPEG尺寸不同**：原JPEG可能含标尺、边框或融合显示；温度矩阵始终保持热数据网格尺寸。

## 8. 工具文件与测试

- `extract_flir.py`：单张/批量运行和导出。
- `flir_reader.py`：独立FLIR解码和温度换算；沿用既有项目的数值表达式。
- `config.example.json`：可移植配置模板，无原开发电脑路径。
- `read_temperature_example.py`：读取矩阵与单点温度示例。
- `run_windows.cmd`：终端交互启动器。
- `tests/test_exporter.py`：不依赖真实照片或ExifTool的自动测试。
- `VALIDATION.md`：实际验证范围与限制。
- `SOURCE_PROVENANCE.json`：核心代码来源和版本信息。
- `README.md` / `README_IT.md`：英文与意大利语完整使用说明。
- `LICENSE`：沿用独立仓库的MIT许可证；第三方工具按其各自许可证安装使用。

可选运行测试：

```powershell
python -m pip install -r requirements-test.txt
python -m pytest tests -q
```

工具包不包含原始照片、温度数据集、ExifTool程序、Python解释器或论文其他模块；运行结果保存在你自行指定的输出目录。
