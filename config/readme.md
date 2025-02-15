# Image Processing App

## 项目目标
这是一个图像处理应用程序，旨在对图像进行各种处理操作。

## 使用方法
1. 安装依赖：
    ```bash
    pip install -r requirements.txt
    ```
2. 运行程序：
    ```bash
    python image_processing_app.py
    ```

## 打包方法
使用 `pyinstaller` 将程序打包成可执行文件，并包含所有配置文件。

### 步骤
1. 安装 `pyinstaller`：
    ```bash
    pip install pyinstaller
    ```
2. 使用以下命令打包程序：
    ```bash
    pyinstaller --onefile --add-data "config.json;." image_processing_app.py
    ```

    这里的 `--add-data` 参数用于包含配置文件。假设配置文件名为 `config.json`，并且位于当前目录。

3. 生成的可执行文件将在 `dist` 目录下。

## 参数说明
- `--onefile`：将所有文件打包成一个可执行文件。
- `--add-data`：包含额外的文件。

## 返回值说明
生成的可执行文件将在 `dist` 目录下，可以直接运行。 