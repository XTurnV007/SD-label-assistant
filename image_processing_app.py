import os
import re
import threading
import time
import json  # 用于保存和加载模型列表
from tkinter import messagebox, filedialog, Toplevel, Listbox, Entry, Button, END, Scrollbar
import customtkinter as ctk
from PIL import Image  # 用于加载图标和图片压缩
import cairosvg  # 用于将 SVG 转换为 PNG
import io  # 用于处理内存中的 PNG 数据
import base64
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from threading import Lock  # 引入线程锁

# 初始化主窗口
ctk.set_appearance_mode("light")  # 设置主题
ctk.set_default_color_theme("blue")  # 设置颜色主题

root = ctk.CTk()
root.title("辣椒炒肉-图片打标器v2.2.2")

# 修改：动态调整窗口大小，限制最大和最小尺寸
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
scaling_factor = root.tk.call('tk', 'scaling')  # 获取屏幕缩放倍率

# 设置窗口宽高，限制最大尺寸
window_width = min(int(1200 * scaling_factor), screen_width)
window_height = min(int(770 * scaling_factor), screen_height)
root.geometry(f"{window_width}x{window_height}")
root.minsize(800, 600)  # 设置最小尺寸
root.maxsize(screen_width, screen_height)  # 限制最大尺寸
root.configure(bg="#E5F1FB")  # 浅蓝色背景

# 全局变量
current_page = None
status_var = ctk.StringVar(value="欢迎来到辣椒炒肉-图片打标器!")
api_keys_var = ctk.StringVar()
api_url_var = ctk.StringVar()
image_directory_var = ctk.StringVar()
output_directory_var = ctk.StringVar()
txt_directory_var = ctk.StringVar()
txt_input_var = ctk.StringVar()

# 定义文件夹路径
CONFIG_DIR = "config"
ASSETS_DIR = "assets"

# 确保文件夹存在
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

# 更新配置文件路径
MODEL_LIST_FILE = os.path.join(CONFIG_DIR, "models.json")
SELECTED_MODEL_FILE = os.path.join(CONFIG_DIR, "selected_model.json")
PROMPT_FILE = os.path.join(CONFIG_DIR, "prompts.json")
SELECTED_PROMPT_FILE = os.path.join(CONFIG_DIR, "selected_prompt.json")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
INVALID_API_KEYS_FILE = os.path.join(CONFIG_DIR, "invalid_api_keys.json")
REMOVED_INVALID_API_KEYS_FILE = os.path.join(CONFIG_DIR, "removed_invalid_api_keys.json")

# 更新图标文件路径
DELETE_ICON_PATH = os.path.join(ASSETS_DIR, "delete_icon.svg")

# 添加全局变量，用于控制处理状态
processing_paused = False  # 默认未暂停

# 添加一个列表来存储失效的 API Keys
invalid_api_keys = []

# 新增：记录被移除的失效 API Key 的列表
removed_invalid_api_keys = []

# 加载配置
def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}  # 如果文件损坏，返回空字典
    return {}  # 如果文件不存在，返回空字典

# 保存配置
def save_config(config):
    """保存配置到文件"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)

# 初始化配置
config = load_config()

# 修改：支持多个 API_KEYS
api_keys_list = config.get("api_keys_list", [])  # 从配置中加载 API_KEYS 列表
if not isinstance(api_keys_list, list):
    api_keys_list = []  # 如果配置中不是列表，初始化为空列表

# 新增：为每个 API Key 添加失败计数器
api_key_failures = {key: 0 for key in api_keys_list}  # 初始化失败计数器

# 加载失效的 API Keys
def load_invalid_api_keys():
    """从文件中加载失效的 API Keys"""
    if os.path.exists(INVALID_API_KEYS_FILE):
        with open(INVALID_API_KEYS_FILE, "r", encoding="utf-8") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []  # 如果文件损坏，返回空列表
    return []  # 如果文件不存在，返回空列表

# 保存失效的 API Keys
def save_invalid_api_keys():
    """将失效的 API Keys 保存到文件"""
    with open(INVALID_API_KEYS_FILE, "w", encoding="utf-8") as file:
        json.dump(invalid_api_keys, file, indent=4, ensure_ascii=False)

# 初始化失效的 API Keys 列表
invalid_api_keys = load_invalid_api_keys()

# 保存 API_KEYS 列表到配置
def save_api_keys_list():
    """保存 API_KEYS 列表到配置文件"""
    config["api_keys_list"] = api_keys_list
    save_config(config)

# 添加新的 API_KEY
def add_api_key(new_key):
    """添加新的 API_KEY"""
    if new_key and new_key not in api_keys_list:
        api_keys_list.append(new_key)
        save_api_keys_list()
        update_status(f"API Key '{new_key}' 添加成功!")
    elif new_key in api_keys_list:
        update_status(f"API Key '{new_key}' 已经存在了!")
    else:
        update_status("API Key 不能为空!")

# 删除指定的 API_KEY
def delete_api_key(key_to_delete):
    """删除指定的 API_KEY"""
    if key_to_delete in api_keys_list:
        api_keys_list.remove(key_to_delete)
        save_api_keys_list()
        update_status(f"API Key '{key_to_delete}' 删除成功!")
    else:
        update_status(f"API Key '{key_to_delete}' 不存在!")

# 修改指定的 API_KEY
def update_api_key(old_key, new_key):
    """修改指定的 API_KEY"""
    if old_key in api_keys_list and new_key and new_key not in api_keys_list:
        index = api_keys_list.index(old_key)
        api_keys_list[index] = new_key
        save_api_keys_list()
        update_status(f"API Key '{old_key}' 更新为 '{new_key}' 成功!")
    elif new_key in api_keys_list:
        update_status(f"API Key '{new_key}' 已经存在了!")
    else:
        update_status("API Key 更新失败!")

# 设置默认 API URL
DEFAULT_API_URL = "https://api.cursorai.art/v1/chat/completions"
api_url_var = ctk.StringVar(value=DEFAULT_API_URL)  # 默认值设置为指定的 URL

# 当用户更新 API Key 或 URL 时，自动保存到配置文件
def on_api_keys_change(*args):
    config["api_keys_list"] = api_keys_var.get()
    save_config(config)
    update_status("API Key 保存成功!")  # 在状态栏显示保存成功的消息

def on_api_url_change(*args):
    config["api_url"] = api_url_var.get()
    save_config(config)
    update_status("API URL 保存成功!")  # 在状态栏显示保存成功的消息

# 绑定变量的变化事件
api_keys_var.trace_add("write", on_api_keys_change)
api_url_var.trace_add("write", on_api_url_change)

# 定义函数：加载上一次选择的 Prompt
def load_selected_prompt():
    """加载用户上一次选择的 Prompt"""
    if os.path.exists(SELECTED_PROMPT_FILE):
        with open(SELECTED_PROMPT_FILE, "r", encoding="utf-8") as file:
            try:
                data = json.load(file)
                return data.get("selected_prompt", "")  # 返回保存的 Prompt 名称
            except json.JSONDecodeError:
                return ""  # 如果文件损坏，返回空字符串
    return ""  # 如果文件不存在，返回空字符串

# 定义函数：保存用户选择的 Prompt
def save_selected_prompt(selected_prompt):
    """保存用户选择的 Prompt"""
    with open(SELECTED_PROMPT_FILE, "w", encoding="utf-8") as file:
        json.dump({"selected_prompt": selected_prompt}, file, indent=4, ensure_ascii=False)

# 加载模型列表
def load_model_list():
    """加载模型列表"""
    if os.path.exists(MODEL_LIST_FILE):
        with open(MODEL_LIST_FILE, "r") as file:
            return json.load(file)
    # 如果文件不存在，返回默认模型列表
    return ['gpt-4o', 'claude-3-7-sonnet', 'gemini-2.0-flash']

# 保存模型列表
def save_model_list(models):
    """保存模型列表"""
    with open(MODEL_LIST_FILE, "w") as file:
        json.dump(models, file)

# 初始化模型列表
model_list = load_model_list()

# 保存用户选择的模型
def save_selected_model(selected_model):
    """保存用户选择的模型到文件"""
    with open(SELECTED_MODEL_FILE, "w") as file:
        json.dump({"selected_model": selected_model}, file)

# 加载用户选择的模型
def load_selected_model():
    """加载用户上一次选择的模型"""
    if os.path.exists(SELECTED_MODEL_FILE):
        with open(SELECTED_MODEL_FILE, "r") as file:
            data = json.load(file)
            return data.get("selected_model", model_list[0])  # 如果文件中没有记录，返回默认模型
    return model_list[0]  # 如果文件不存在，返回默认模型

# 初始化模型选择
selected_model_var = ctk.StringVar(value=load_selected_model())  # 加载上一次选择的模型

# 加载删除图标（支持 SVG）
def load_svg_as_image(svg_path, size):
    """将 SVG 文件转换为 PNG 并加载为 PIL 图像"""
    png_data = cairosvg.svg2png(url=svg_path, output_width=size[0], output_height=size[1])
    return Image.open(io.BytesIO(png_data))

# 加载删除图标
delete_icon = ctk.CTkImage(load_svg_as_image(DELETE_ICON_PATH, size=(20, 20)), size=(20, 20))

# 修改：新增进度变量
progress_var = ctk.StringVar(value="进度: 0/0 (0.00%)")  # 初始化进度显示

# 修改 update_status 函数，支持进度显示
def update_status(message, update_progress=False):
    """
    更新状态栏信息。
    :param message: 要显示的状态消息
    :param update_progress: 是否更新进度显示
    """
    if update_progress:
        # 如果是进度更新，直接更新 progress_var
        progress_var.set(message)
    else:
        # 否则更新状态消息
        status_var.set(message)

# 页面切换函数
def show_page(page):
    """切换页面"""
    global current_page
    if current_page:
        current_page.pack_forget()  # 隐藏当前页面
    page.pack(fill="both", expand=True)  # 显示目标页面
    current_page = page

# API 配置页面功能
def save_api_config():
    """保存 API 配置"""
    api_url = api_url_var.get()
    if not api_url:
        messagebox.showerror("Error", "API URL 不能为空!")
        update_status("Error: API URL 不能为空!")
        return
    # 假装保存成功
    update_status("API 配置保存成功!")
    messagebox.showinfo("Info", "API 配置保存成功!")

# 模型管理功能
def add_model():
    """添加新模型到列表"""
    new_model = new_model_var.get().strip()
    if new_model and new_model not in model_list:
        model_list.append(new_model)
        save_model_list(model_list)
        model_dropdown.configure(values=model_list)  # 更新下拉框选项
        update_status(f"模型 '{new_model}' 添加成功!")
        new_model_var.set("")  # 清空输入框
    elif new_model in model_list:
        update_status(f"模型 '{new_model}' 已经存在了!")
    else:
        update_status("模型名称不能为空!")

def delete_model():
    """从列表中删除当前选中的模型"""
    selected_model = selected_model_var.get()
    if selected_model in model_list:
        model_list.remove(selected_model)
        save_model_list(model_list)
        model_dropdown.configure(values=model_list)  # 更新下拉框选项
        selected_model_var.set(model_list[0] if model_list else "")  # 设置默认选项
        update_status(f"模型 '{selected_model}' 删除成功!")
    else:
        update_status("未选择模型或模型不存在!")

# 图片处理页面功能
def select_image_directory():
    """选择图片目录"""
    directory = filedialog.askdirectory(title="Select Image Directory")
    if directory:
        image_directory_var.set(directory)
        update_status("图片目录选择成功!")
        update_progress()  # 更新进度条
    else:
        update_status("图片目录选择取消!")

def select_output_directory():
    """选择输出目录"""
    directory = filedialog.askdirectory(title="Select Output Directory")
    if directory:
        output_directory_var.set(directory)
        update_status("输出目录选择成功!")
        update_progress()  # 更新进度条
    else:
        update_status("输出目录选择取消!")

def update_progress():
    """更新进度条"""
    image_directory = image_directory_var.get()
    output_directory = output_directory_var.get()

    if not os.path.exists(image_directory) or not os.path.exists(output_directory):
        progress_var.set("进度: 0/0 (0.00%)")
        return

    # 获取图片列表
    image_filenames = [f for f in os.listdir(image_directory) if f.endswith(('.png', '.jpg', '.jpeg', '.JPG', '.PNG'))]
    total_images = len(image_filenames)

    # 统计已处理的 .txt 文件数量
    processed_count = sum(
        1 for image_filename in image_filenames
        if os.path.exists(os.path.join(output_directory, os.path.splitext(image_filename)[0] + '.txt'))
    )

    # 更新进度条
    progress = processed_count / total_images * 100 if total_images > 0 else 0
    progress_var.set(f"图片处理进度: {processed_count}/{total_images} ({progress:.2f}%)")

def set_output_to_image_directory():
    """将输出目录设置为图片目录"""
    output_directory_var.set(image_directory_var.get())
    update_status("输出目录已设置为图片目录!")

# 定义一个函数来读取图片并进行base64编码
def encode_image(image_path):
    """将图片编码为 Base64 格式"""
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# 准备请求头
def get_headers(api_key):
    """生成请求头"""
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

# 修改：轮询使用 API_KEYS
api_key_index = 0  # 全局变量，用于轮询 API_KEYS

def get_next_api_key():
    """获取下一个可用的 API_KEY"""
    global api_key_index
    if not api_keys_list:
        raise ValueError("没有可用的 API Keys!")
    
    # 循环查找有效的 API Key
    for _ in range(len(api_keys_list)):
        api_key = api_keys_list[api_key_index]
        api_key_index = (api_key_index + 1) % len(api_keys_list)  # 轮询到下一个 API_KEY
        if api_key not in invalid_api_keys:  # 跳过失效的 API Key
            return api_key
    
    raise ValueError("所有 API Keys 都失效了!")

# 新增：保存被移除的失效 API Key 到文件
def save_removed_invalid_api_keys():
    """保存被移除的失效 API Key 到文件"""
    with open(REMOVED_INVALID_API_KEYS_FILE, "w", encoding="utf-8") as file:
        json.dump(removed_invalid_api_keys, file, indent=4, ensure_ascii=False)

def load_removed_invalid_api_keys():
    """加载被移除的失效 API Key"""
    if os.path.exists(REMOVED_INVALID_API_KEYS_FILE):
        with open(REMOVED_INVALID_API_KEYS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

# 初始化加载被移除的失效 API Key
removed_invalid_api_keys = load_removed_invalid_api_keys()

# 新增：压缩图片函数
def compress_image_to_target_size(image_path, target_size_mb=1):
    """
    压缩图片到目标大小（MB），返回压缩后的图片字节数据。
    :param image_path: 原始图片路径
    :param target_size_mb: 目标大小（以MB为单位）
    :return: 压缩后的图片字节数据
    """
    target_size_bytes = target_size_mb * 1024 * 1024  # 转换为字节
    with Image.open(image_path) as img:
        # 确保图片是 RGB 模式
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # 初始化压缩参数
        quality = 85  # 初始质量
        step = 20  # 每次减少的质量步长
        buffer = io.BytesIO()

        # 循环压缩图片直到满足目标大小
        while True:
            buffer.seek(0)  # 重置缓冲区
            img.save(buffer, format="JPEG", quality=quality)
            size = buffer.tell()  # 获取当前图片大小
            if size <= target_size_bytes or quality <= step:
                break
            quality -= step  # 减少质量

        buffer.seek(0)  # 重置缓冲区
        return buffer.read()  # 返回压缩后的图片字节数据

# 修改 process_image 函数，增加图片大小检查和压缩逻辑
def process_image(image_filename, api_url, model, prompt, image_directory, output_directory, quality="auto", api_key=None):
    """处理单张图片并保存结果"""
    global processing_paused

    # 等待暂停状态解除
    while processing_paused:
        time.sleep(0.5)  # 每0.5秒检查一次暂停状态

    image_path = os.path.join(image_directory, image_filename)
    
    # 检查是否存在同名的txt文件
    txt_filename = os.path.splitext(image_filename)[0] + '.txt'
    txt_filepath = os.path.join(output_directory, txt_filename)
    
    if os.path.exists(txt_filepath):
        update_status(f"{txt_filename} 已经存在，跳过图片 {image_filename}。")
        time.sleep(0.1)
        return True
    
    # 检查图片大小并压缩（如果大于2MB）
    if os.path.getsize(image_path) > 2 * 1024 * 1024:  # 大于2MB
        update_status(f"图片 {image_filename} 较大，正在压缩...")
        time.sleep(0.1)
        encoded_image = base64.b64encode(compress_image_to_target_size(image_path, target_size_mb=1)).decode('utf-8')
    else:
        # 编码图片
        encoded_image = encode_image(image_path)
    
    # 准备请求数据
    data = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_image}",
                            "detail": f"{quality}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        "max_tokens": 1000
    }
    
    # 发送请求并处理响应，最多重试三次
    for attempt in range(3):
        try:
            # 在每次请求前检查暂停状态
            while processing_paused:
                time.sleep(0.5)  # 每0.5秒检查一次暂停状态

            if api_key is None:
                api_key = get_next_api_key()  # 获取下一个 API_KEY
            response = requests.post(api_url, headers=get_headers(api_key), data=json.dumps(data))
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']

                cleaned_content = re.sub(r'^\s*\d+[\.\)]\s*', '', content, flags=re.MULTILINE)  # 匹配编号并移除

                update_status(f"Processed {image_filename}: {cleaned_content[:50]}...")  # 显示部分内容
                time.sleep(0.1)
                
                # 保存content到同名的txt文件
                with open(txt_filepath, 'w', encoding='utf-8') as txt_file:
                    txt_file.write(cleaned_content)

                # 在生成 .txt 文件后，更新进度条
                update_progress()
                
                # 如果 API Key 恢复正常，重置其失败计数
                if api_key in api_key_failures:
                    api_key_failures[api_key] = 0
                
                return True
            elif response.status_code in [500, 502, 503, 504]:  # 服务器错误或不可用
                # update_status(f"服务器错误 {response.status_code} 对于 {image_filename}. 重试中...")
                time.sleep(2)  # 等待2秒后重试
            else:
                update_status(f"第 {attempt + 1} 次尝试失败 对于 {image_filename}: {response.status_code}")
                if attempt < 2:
                    time.sleep(2)  # 等待2秒后重试
        except Exception as e:
            update_status(f"对于 {image_filename} 发生异常: {e}")
    
    # 如果所有重试都失败，增加 API Key 的失败计数
    if api_key in api_key_failures:
        api_key_failures[api_key] += 1
        if api_key_failures[api_key] >= 3:  # 连续失败3次，标记为失效
            if api_key not in invalid_api_keys:
                invalid_api_keys.append(api_key)
                save_invalid_api_keys()  # 保存失效的 API Keys 到文件
                update_status(f"API Key '{api_key}' 标记为失效 连续失败3次.")
            
            # 自动移除失效的 API Key
            if api_key in api_keys_list:
                api_keys_list.remove(api_key)  # 从 API Key 列表中移除
                removed_invalid_api_keys.append(api_key)  # 添加到被移除的列表
                save_removed_invalid_api_keys()  # 保存到文件
                save_api_keys_list()  # 保存更新后的 API Key 列表到文件

    return False

# 修改 start_processing 函数，增加进度显示逻辑
def start_processing():
    """开始处理图片"""
    global processing_paused

    # 如果当前是暂停状态，点击"开始打标"时需要重置暂停状态
    if processing_paused:
        processing_paused = False
        pause_button.configure(text="暂停打标")  # 确保按钮显示为"暂停打标"

    # 获取最新的图片目录和输出目录
    image_directory = image_directory_var.get()
    output_directory = output_directory_var.get()

    # 检查图片目录是否存在
    if not os.path.exists(image_directory):
        messagebox.showerror("Error", "图片目录无效!")
        update_status("Error: 图片目录无效!")
        return
    if not os.path.exists(output_directory):
        messagebox.showerror("Error", "输出目录无效!")
        update_status("Error: 输出目录无效!")
        return

    # 准备图片列表
    image_filenames = [f for f in os.listdir(image_directory) if f.endswith(('.png', '.jpg', '.jpeg', '.JPG', '.PNG'))]
    if not image_filenames:
        messagebox.showinfo("Info", "图片目录中没有图片!")
        update_status("Info: 图片目录中没有图片!")
        return

    total_images = len(image_filenames)  # 总图片数量
    processed_count = 0  # 已处理的图片数量
    lock = Lock()  # 创建线程锁

    # 更新初始进度
    progress = processed_count / total_images * 100 if total_images > 0 else 0
    progress_var.set(f"图片处理进度: {processed_count}/{total_images} ({progress:.2f}%)")  # 实时更新进度显示

    api_url = DEFAULT_API_URL  # 使用默认的 API URL
    model = selected_model_var.get()
    prompt = prompt_textbox.get("1.0", "end").strip()  # 获取用户选择的 Prompt 内容

    # 检查必填项是否完整
    if not image_directory:
        messagebox.showerror("Error", "图片目录不能为空!")
        update_status("Error: 图片目录不能为空!")
        return
    if not output_directory:
        messagebox.showerror("Error", "输出目录不能为空!")
        update_status("Error: 输出目录不能为空!")
        return
    if not model:
        messagebox.showerror("Error", "模型选择不能为空!")
        update_status("Error: 模型选择不能为空!")
        return
    if not prompt:
        messagebox.showerror("Error", "Prompt 不能为空!")
        update_status("Error: Prompt 不能为空!")
        return

    if not api_keys_list:
        messagebox.showerror("Error", "没有可用的 API Keys! 请至少添加一个 API Key.")
        update_status("Error: 没有可用的 API Keys!")
        return

    # 并行处理图片
    def process():
        update_status("处理开始...")
        task_queue = Queue()

        # 清空任务队列并重新加载图片列表
        while not task_queue.empty():
            task_queue.get()  # 清空队列
        for image_filename in image_filenames:
            task_queue.put(image_filename)

        # 初始化成功和失败的计数器，以及开始时间
        nonlocal processed_count
        success_count = 0
        failure_count = 0
        start_time = time.time()

        # 为每个 API Key 创建一个线程池
        api_key_pools = {}
        max_concurrent_requests_per_key = 15  # 每个 API Key 的最大并发请求数
        for api_key in api_keys_list:
            if api_key not in invalid_api_keys:
                api_key_pools[api_key] = ThreadPoolExecutor(max_workers=max_concurrent_requests_per_key)

        # 分配任务到线程池
        futures = []
        while not task_queue.empty():
            # 检查暂停状态
            while processing_paused:
                update_status("处理已暂停...")
                time.sleep(0.5)  # 每0.5秒检查一次暂停状态

            for api_key, pool in api_key_pools.items():
                if not task_queue.empty():
                    image_filename = task_queue.get()
                    futures.append(pool.submit(process_image, image_filename, api_url, model, prompt, image_directory, output_directory, api_key=api_key))
                    time.sleep(0.1)

        # 等待所有任务完成
        for future in as_completed(futures):
            while processing_paused:
                update_status("处理已暂停...")
                time.sleep(0.5)  # 每0.5秒检查一次暂停状态
            try:
                success = future.result()
                with lock:
                    processed_count += 1  # 更新已处理数量
                    if success:
                        success_count += 1  # 成功计数 +1
                    else:
                        failure_count += 1  # 失败计数 +1

                    # 更新进度显示
                    progress = processed_count / total_images * 100 if total_images > 0 else 0
                    progress_var.set(f"图片处理进度: {processed_count}/{total_images} ({progress:.2f}%)")
            except Exception as e:
                update_status(f"发生异常: {e}")

        # 关闭所有线程池
        for pool in api_key_pools.values():
            pool.shutdown()

        total_time = time.time() - start_time  # 计算总耗时
        update_status(f"处理完成! 成功处理 {success_count} 张图片，失败 {failure_count} 张图片，耗时 {total_time:.2f} 秒。")

    threading.Thread(target=process).start()

# 左侧导航栏
sidebar = ctk.CTkFrame(root, width=200, corner_radius=0, fg_color="#005BB5")  # 深蓝色背景
sidebar.pack(side="left", fill="y")

image_button = ctk.CTkButton(
    sidebar, text="📷 图片处理", command=lambda: show_page(image_page),
    width=200, height=50, corner_radius=10,
    fg_color="white", hover_color="#E5F1FB",  # 白色按钮，悬停时浅蓝色
    font=ctk.CTkFont(family="Microsoft YaHei", size=15, weight="bold"),  # 修改为更美观的中文字体
    text_color="#005BB5",  # 深蓝色文字
)
image_button.pack(pady=10, padx=5)  # 添加左右边距5像素

api_button = ctk.CTkButton(
    sidebar, text="⚙️ API 配置", command=lambda: show_page(api_page),
    width=200, height=50, corner_radius=10,
    fg_color="white", hover_color="#E5F1FB",  # 白色按钮，悬停时浅蓝色
    font=ctk.CTkFont(family="Microsoft YaHei", size=15, weight="bold"),  # 修改为更美观的中文字体
    text_color="#005BB5",  # 深蓝色文字
)
api_button.pack(pady=10, padx=5)  # 添加左右边距5像素

# 状态栏
status_bar = ctk.CTkFrame(root, fg_color="#005BB5")  # 使用框架容纳状态栏内容
status_bar.pack(side="bottom", fill="x", padx=20, pady=10)

status_label = ctk.CTkLabel(
    status_bar, textvariable=status_var, anchor="w",
    font=ctk.CTkFont(size=14), fg_color="#005BB5", text_color="white", corner_radius=5
)
status_label.pack(side="left", fill="x", expand=True)

# 新增：进度显示标签
progress_label = ctk.CTkLabel(
    status_bar, textvariable=progress_var, anchor="e",
    font=ctk.CTkFont(size=14), fg_color="#005BB5", text_color="white", corner_radius=5
)
progress_label.pack(side="right", padx=10)

# 主内容页面
api_page = ctk.CTkScrollableFrame(root, corner_radius=15, fg_color="white")
image_page = ctk.CTkScrollableFrame(root, corner_radius=15, fg_color="white")
txt_page = ctk.CTkScrollableFrame(root, corner_radius=15, fg_color="white")
table_page = ctk.CTkScrollableFrame(root, corner_radius=15, fg_color="white")

# API 配置页面内容
api_title = ctk.CTkLabel(
    api_page, text="API 配置",
    font=ctk.CTkFont(family="Microsoft YaHei", size=24, weight="bold"),  # 修改为更美观的中文字体
    text_color="#005BB5", anchor="w"
)
api_title.pack(pady=20, padx=20, anchor="w")

# 保留 API_KEYS 标题，移除输入框和 Show/Hide 按钮
api_keys_label = ctk.CTkLabel(
    api_page, text="API_KEYS:", font=ctk.CTkFont(size=16), text_color="#005BB5", anchor="w"
)
api_keys_label.pack(pady=10, padx=20, anchor="w")

# 确保 open_manage_api_keys_modal 函数定义在调用之前
def open_manage_api_keys_modal():
    """打开管理 API_KEYS 的窗口"""
    # 创建弹窗
    modal = Toplevel()
    modal.title("管理 API_KEYS")

    # 动态调整弹窗大小，根据屏幕缩放倍率动态变化
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    scaling_factor = root.tk.call('tk', 'scaling')  # 获取屏幕缩放倍率

    # 修改：调整弹窗尺寸为更适合的大小
    modal_width = int(800 * scaling_factor)  # 弹窗宽度
    modal_height = int(600 * scaling_factor)  # 弹窗高度

    # 确保弹窗从软件窗口的正中间弹出
    root_x = root.winfo_rootx()
    root_y = root.winfo_rooty()
    root_width = root.winfo_width()
    root_height = root.winfo_height()
    modal_x = root_x + (root_width - modal_width) // 2
    modal_y = root_y + (root_height - modal_height) // 2

    modal.geometry(f"{modal_width}x{modal_height}+{modal_x}+{modal_y}")
    modal.resizable(False, False)  # 禁止用户调整弹窗大小

    # 禁止与主程序交互
    modal.grab_set()

    # 添加滚动条
    scrollbar = Scrollbar(modal)
    scrollbar.pack(side="right", fill="y")

    # 修改：调整 Listbox 的高度和字体大小
    keys_listbox = Listbox(
        modal, height=10, width=40, font=("Microsoft YaHei", int(12 * scaling_factor))  # 调整字体大小
    )
    keys_listbox.pack(pady=10, padx=10, fill="both", expand=True)

    # 将滚动条绑定到 Listbox
    keys_listbox.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=keys_listbox.yview)
    
    # 新增：维护一个映射列表，存储实际的 API Keys
    visible_keys = []  # 用于存储当前显示的 API Keys

    def update_keys_listbox(show_keys=False):
        """更新 Listbox 中的 API Keys"""
        keys_listbox.delete(0, END)
        visible_keys.clear()  # 清空映射列表
        for key in api_keys_list:
            visible_keys.append(key)  # 添加实际的 API Key
            if show_keys:
                keys_listbox.insert(END, key)
            else:
                keys_listbox.insert(END, '*' * len(key))

    update_keys_listbox()

    # 添加输入框和按钮的容器
    input_frame = ctk.CTkFrame(modal, fg_color="transparent")
    input_frame.pack(pady=10, padx=10, fill="x")

    # 输入框
    new_key_var = ctk.StringVar()
    new_key_entry = ctk.CTkEntry(
        input_frame, textvariable=new_key_var, width=int(300 * scaling_factor), height=int(30 * scaling_factor),
        corner_radius=10, fg_color="white", border_color="#005BB5", border_width=2, text_color="#005BB5", show="*"
    )
    new_key_entry.pack(side="left", padx=(0, 10), fill="x", expand=True)

    # 添加按钮
    def add_key():
        new_key = new_key_var.get().strip()
        if new_key:
            add_api_key(new_key)
            update_keys_listbox(show_keys=toggle_visibility_button.cget("text") == "隐藏 API_KEYS")
            new_key_var.set("")

    add_button = ctk.CTkButton(
        input_frame, text="添加 API_KEY", command=add_key,
        width=int(100 * scaling_factor), height=int(30 * scaling_factor), corner_radius=10,
        fg_color="#005BB5", hover_color="#003F7F", text_color="white",
        font=ctk.CTkFont(family="Microsoft YaHei", size=int(12 * scaling_factor), weight="bold")
    )
    add_button.pack(side="left")

    # 删除按钮和显示/隐藏按钮的容器，居中放置
    button_frame = ctk.CTkFrame(modal, fg_color="transparent")
    button_frame.pack(pady=20, padx=10, fill="x")

    # 删除按钮
    def delete_selected_key():
        """删除选中的 API Key"""
        selected_index = keys_listbox.curselection()
        if selected_index:
            # 使用 visible_keys 获取实际的 API Key
            key_to_delete = visible_keys[selected_index[0]]
            delete_api_key(key_to_delete)
            update_keys_listbox(show_keys=toggle_visibility_button.cget("text") == "隐藏 API_KEYS")

    delete_button = ctk.CTkButton(
        button_frame, text="删除 API_KEY", command=delete_selected_key,
        width=int(150 * scaling_factor), height=int(30 * scaling_factor), corner_radius=10,
        fg_color="#FF5C5C", hover_color="#FF3C3C", text_color="white",
        font=ctk.CTkFont(family="Microsoft YaHei", size=int(12 * scaling_factor), weight="bold")
    )
    delete_button.pack(side="left", padx=(0, 10), anchor="e")  # 修改：调整为靠右对称分布

    # 新增：显示和隐藏 API Key 可见性的按钮
    def toggle_key_visibility():
        """切换 API Key 的可见性"""
        if toggle_visibility_button.cget("text") == "显示 API_KEYS":
            update_keys_listbox(show_keys=True)
            toggle_visibility_button.configure(text="隐藏 API_KEYS")
        else:
            update_keys_listbox(show_keys=False)
            toggle_visibility_button.configure(text="显示 API_KEYS")

    toggle_visibility_button = ctk.CTkButton(
        button_frame, text="显示 API_KEYS", command=toggle_key_visibility,
        width=int(150 * scaling_factor), height=int(30 * scaling_factor), corner_radius=10,
        fg_color="#005BB5", hover_color="#003F7F", text_color="white",
        font=ctk.CTkFont(family="Microsoft YaHei", size=int(12 * scaling_factor), weight="bold")
    )
    toggle_visibility_button.pack(side="right", padx=(10, 0), anchor="w")  # 修改：调整为靠左对称分布

# 新增：显示被移除的失效 API Key 的窗口
def show_removed_invalid_api_keys():
    """显示被移除的失效 API Key"""
    modal = Toplevel()
    modal.title("被移除的失效 API_KEYS")
    modal.geometry("800x600")
    modal.resizable(False, False)

    # 窗口从软件窗口的中间弹出
    root_x = root.winfo_rootx()
    root_y = root.winfo_rooty()
    root_width = root.winfo_width()
    root_height = root.winfo_height()
    modal_width = 800
    modal_height = 600
    modal_x = root_x + (root_width - modal_width) // 2
    modal_y = root_y + (root_height - modal_height) // 2
    modal.geometry(f"{modal_width}x{modal_height}+{modal_x}+{modal_y}")

    # 禁止与主程序交互
    modal.grab_set()

    # 添加列表显示被移除的 API Key
    keys_listbox = Listbox(
        modal, height=15, width=50, font=("Microsoft YaHei", 14)  # 调整为更美观的中文字体
    )
    keys_listbox.pack(pady=10, padx=10, fill="both", expand=True)
    
    # 确保加载最新的 removed_invalid_api_keys 列表
    for key in removed_invalid_api_keys:
        keys_listbox.insert(END, key)

    # 添加清空按钮
    def clear_removed_keys():
        """清空被移除的失效 API Key"""
        global removed_invalid_api_keys
        removed_invalid_api_keys.clear()  # 清空列表
        save_removed_invalid_api_keys()  # 保存到文件
        keys_listbox.delete(0, END)  # 清空列表框中的内容
        update_status("被移除的失效 API_KEYS 列表已清空.")  # 更新状态栏

    clear_button = ctk.CTkButton(
        modal, text="清空", command=clear_removed_keys,
        width=200, height=40, corner_radius=10,
        fg_color="#FF5C5C", hover_color="#FF3C3C", text_color="white",
        font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")  # 修改为更美观的中文字体
    )
    clear_button.pack(pady=10)

# 修改 "Manage API Keys" 界面，新增一个水平框架容纳两个按钮
keys_button_frame = ctk.CTkFrame(api_page, fg_color="transparent")  # 创建一个透明框架
keys_button_frame.pack(pady=10, padx=20, anchor="w", fill="x")  # 放置在页面中

# "Manage API Keys" 按钮
manage_keys_button = ctk.CTkButton(
    keys_button_frame, text="管理 API_KEYS", command=open_manage_api_keys_modal,
    width=200, height=40, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")  # 修改为更美观的中文字体
)
manage_keys_button.pack(side="left", padx=(0, 10))  # 左侧对齐，右侧留出间距

# 新增按钮：显示被移除的失效 API Key
removed_keys_button = ctk.CTkButton(
    keys_button_frame, text="失效的 API_KEYS", command=show_removed_invalid_api_keys,
    width=200, height=40, corner_radius=10,
    fg_color="#FF5C5C", hover_color="#FF3C3C", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")  # 修改为更美观的中文字体
)
removed_keys_button.pack(side="left")  # 紧邻 "Manage API Keys" 按钮右侧

# Add a reminder below the API_KEYS section with a clickable hyperlink
def open_api_keys_website():
    """Open the API_KEYS website in the default web browser."""
    import webbrowser
    webbrowser.open("https://api.cursorai.art/register?aff=xoXg")

api_keys_reminder_label = ctk.CTkLabel(
    api_page, 
    text="🔗 点击这里获取 API_KEYS", 
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold", slant="italic"),  # 使用更美观的中文字体
    text_color="#005BB5",  # Blue text to indicate a hyperlink
    anchor="w",
    cursor="hand2",  # Change cursor to hand when hovering
    underline=True  # Underline the text to emphasize the hyperlink
)
api_keys_reminder_label.pack(pady=10, padx=20, anchor="w")  # Adjust spacing and alignment
api_keys_reminder_label.bind("<Button-1>", lambda e: open_api_keys_website())  # Bind click event to open the website

# 模型选择部分
model_label = ctk.CTkLabel(
    api_page, text="选择模型:", font=ctk.CTkFont(family="Microsoft YaHei", size=16), text_color="#005BB5", anchor="w"
)
model_label.pack(pady=10, padx=20, anchor="w")

model_frame = ctk.CTkFrame(api_page, fg_color="transparent")  # 创建一个框架容纳下拉框和删除按钮
model_frame.pack(pady=10, padx=20, anchor="w", fill="x")

# 创建一个带蓝色边框的框架
model_dropdown_frame = ctk.CTkFrame(
    model_frame,
    fg_color="white",  # 背景颜色
    border_color="#005BB5",  # 蓝色边框颜色
    border_width=2,  # 边框宽度
    corner_radius=10  # 圆角
)
model_dropdown_frame.pack(side="left", padx=(0, 10))

# 在框架中放置下拉框
model_dropdown = ctk.CTkOptionMenu(
    model_dropdown_frame, 
    variable=selected_model_var, 
    values=model_list,
    width=400,  # 调整宽度
    height=40,  # 调整高度
    corner_radius=12,  # 增加圆角，使其更柔和
    fg_color="white",  # 背景颜色
    button_color="white",  # 按钮主体颜色改为白色
    button_hover_color="#D9EFFF",  # 悬浮时按钮颜色为深蓝色
    text_color="#005BB5",  # 文本颜色
    dropdown_text_color="#005BB5",  # 下拉框文本颜色
    dropdown_fg_color="white",  # 下拉框背景颜色
    dropdown_hover_color="#D9EFFF",  # 下拉框悬停颜色
    font=ctk.CTkFont(size=14, weight="bold"),  # 调整字体大小和加粗
    dropdown_font=ctk.CTkFont(size=14)  # 下拉框字体样式
)
model_dropdown.pack(padx=5, pady=5)  # 增加内边距

delete_model_button = ctk.CTkButton(
    model_frame, text="", image=delete_icon, command=delete_model,
    width=40, height=40, corner_radius=10,
    fg_color="#FF5C5C", hover_color="#FF3C3C"
)
delete_model_button.pack(side="left")

# 添加新模型部分
new_model_var = ctk.StringVar()
new_model_frame = ctk.CTkFrame(api_page, fg_color="transparent")
new_model_frame.pack(pady=10, padx=20, anchor="w", fill="x")

new_model_entry = ctk.CTkEntry(
    new_model_frame, textvariable=new_model_var, width=400, height=40, corner_radius=10,  # 宽度与 API_KEYS 一致
    fg_color="white", border_color="#005BB5", border_width=2, text_color="#005BB5"
)
new_model_entry.pack(side="left", padx=(0, 10))

add_model_button = ctk.CTkButton(
    new_model_frame, text="添加模型", command=add_model,
    width=100, height=40, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")  # 修改为更美观的中文字体
)
add_model_button.pack(side="left")

# 添加应用简介
data_security_label_title = ctk.CTkLabel(
    api_page,
    text="\n📘 应用简介",
    font=ctk.CTkFont(family="Microsoft YaHei", size=20, weight="bold"),  # 增大字体
    text_color="black",  # 红色字体以强调警告
    anchor="w"  # 左对齐
)
data_security_label_title.pack(pady=(15, 0), padx=20, anchor="w")  # 增加上下间距

app_intro_label = ctk.CTkLabel(
    api_page,
    text=(
        "辣椒炒肉-图片打标器是一个批量给图片进行文字标注的免费工具，为基于 SD 的模型训练（如 LoRA）提供标注数据。\n"
        "本工具是在各种多模态-图像理解模型的基础上通过微调 prompt 开发。\n"
    ),
    font=ctk.CTkFont(family="Microsoft YaHei", size=15, weight="bold"),  # 默认字体样式
    text_color="black",  # 黑色字体
    anchor="w",  # 左对齐
    justify="left"  # 多行文本左对齐
)
app_intro_label.pack(pady=(15, 0), padx=20, anchor="w")  # 调整间距

# 单独增大"数据安全"四个字的字体大小
data_security_label_title = ctk.CTkLabel(
    api_page,
    text="\n🚨 数据安全",
    font=ctk.CTkFont(family="Microsoft YaHei", size=20, weight="bold"),  # 增大字体
    text_color="#FF0000",  # 红色字体以强调警告
    anchor="w"  # 左对齐
)
data_security_label_title.pack(pady=(15, 0), padx=20, anchor="w")  # 增加上下间距

data_security_label = ctk.CTkLabel(
    api_page,
    text=(
        "辣椒炒肉-图片打标器本质是一个转发工具，您上传的图片会从本地发送给 OpenAI 处理，再返回标注数据给你。\n"
        "因此，辣椒炒肉-图片打标器不会且无法访问及储存你上传的任何信息及数据、APIKEY。\n\n\n"
        "***本应用不对生成、处理的任何图像文字数据负责，请严格遵循法律法规。***"
    ),
    font=ctk.CTkFont(family="Microsoft YaHei", size=15, weight="bold"),  # 默认字体样式
    text_color="#FF0000",  # 红色字体以强调警告
    anchor="w",  # 左对齐
    justify="left"  # 多行文本左对齐
)
data_security_label.pack(pady=(5, 15), padx=20, anchor="w")  # 调整间距

# 图片处理页面内容
image_title = ctk.CTkLabel(
    image_page, text="图片处理",
    font=ctk.CTkFont(family="Microsoft YaHei", size=24, weight="bold"), text_color="#005BB5", anchor="w"
)
image_title.pack(pady=20, padx=20, anchor="w")

# 添加简介
image_description = ctk.CTkLabel(
    image_page,
    text=("本软件后台一站式默认图片压缩处理，贴心为炼丹佬考虑一切。"          ),
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold"),  # 设置字体大小
    text_color="#005BB5",  # 深蓝色文字
    anchor="w",  # 左对齐
    justify="left"  # 多行文本左对齐
)
image_description.pack(pady=(0, 0), padx=20, anchor="w")  # 调整间距

# 添加红色提示
image_compression_tip = ctk.CTkLabel(
    image_page,
    text="Tips:图片压缩并不会影响到文件夹中的原始图片，请放心食用。",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold"),  # 设置字体大小
    text_color="#FF0000",  # 红色文字
    anchor="w",  # 左对齐
    justify="left"  # 多行文本左对齐
)
image_compression_tip.pack(pady=(0, 5), padx=20, anchor="w")  # 调整间距

image_dir_label = ctk.CTkLabel(
    image_page, text="图片目录:", font=ctk.CTkFont(family="Microsoft YaHei", size=16), text_color="#005BB5", anchor="w"
)
image_dir_label.pack(pady=10, padx=20, anchor="w")

image_dir_frame = ctk.CTkFrame(image_page, fg_color="transparent")
image_dir_frame.pack(pady=10, padx=20, anchor="w", fill="x")

image_dir_entry = ctk.CTkEntry(
    image_dir_frame, textvariable=image_directory_var, width=600, height=40, corner_radius=10,
    fg_color="white", border_color="#005BB5", border_width=2, text_color="#005BB5"
)
image_dir_entry.pack(side="left", padx=(0, 10))

image_dir_button = ctk.CTkButton(
    image_dir_frame, text="浏览", command=select_image_directory,
    width=100, height=40, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")  # 修改为更美观的中文字体
)
image_dir_button.pack(side="left")

output_dir_label = ctk.CTkLabel(
    image_page, text="输出目录:", font=ctk.CTkFont(family="Microsoft YaHei", size=16), text_color="#005BB5", anchor="w"
)
output_dir_label.pack(pady=10, padx=20, anchor="w")

output_dir_frame = ctk.CTkFrame(image_page, fg_color="transparent")
output_dir_frame.pack(pady=10, padx=20, anchor="w", fill="x")

output_dir_entry = ctk.CTkEntry(
    output_dir_frame, textvariable=output_directory_var, width=600, height=40, corner_radius=10,
    fg_color="white", border_color="#005BB5", border_width=2, text_color="#005BB5"
)
output_dir_entry.pack(side="left", padx=(0, 10))

output_dir_button = ctk.CTkButton(
    output_dir_frame, text="浏览", command=select_output_directory,
    width=100, height=40, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")  # 修改为更美观的中文字体
)
output_dir_button.pack(side="left")

# 添加"Match Output to Image Directory"按钮
match_button = ctk.CTkButton(
    image_page, text="匹配输出到图片目录", 
    command=set_output_to_image_directory,
    width=200, height=30, corner_radius=10,
    fg_color="white", hover_color="#E5F1FB",  # 白色按钮，悬停时浅蓝色
    font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),  # 修改为更美观的中文字体
    text_color="#005BB5"  # 深蓝色文字
)
match_button.pack(pady=10, padx=20, anchor="w")  # 调整为靠左对齐

# 根据图片目录是否存在来启用或禁用按钮
def update_match_button_state(*args):
    """更新 Match Output 按钮的状态"""
    if image_directory_var.get():
        match_button.configure(state="normal")
    else:
        match_button.configure(state="disabled")

# 绑定图片目录变量的变化事件
image_directory_var.trace_add("write", update_match_button_state)

# 初始化按钮状态
update_match_button_state()

# 加载 prompts.json 文件
def load_prompts():
    """加载保存的 prompts"""
    if os.path.exists(PROMPT_FILE):
        with open(PROMPT_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {
        "Photography": "As an AI image tagging expert, please provide precise tags for these images to enhance CLIP model's understanding of the content. "
                       "Please describe directly without including other content. Employ succinct keywords or phrases, steering clear of elaborate sentences and extraneous conjunctions. "
                       "This is a school swimsuit Photography, please use 20 English tags to describe the subject, apparel, posture, details, Composition, background scene non-repetitively, in order of importance from primary to secondary. "
                       "These tags will use for image re-creation, so the closer the resemblance to the original image, the better the tag quality. Tags should be comma-separated. "
                       "Exceptional tagging will be rewarded with $10 per image. If there is any information other than the label, money will be deducted."
    }

# 保存 prompts.json 文件
def save_prompts():
    """保存 prompts 到文件"""
    with open(PROMPT_FILE, "w", encoding="utf-8") as file:
        json.dump(prompt_dict, file, indent=4, ensure_ascii=False)

# 初始化 prompt 数据
prompt_dict = load_prompts()
selected_prompt_var = ctk.StringVar(value=load_selected_prompt())  # 加载上一次选择的 Prompt
new_prompt_name_var = ctk.StringVar()  # For adding a new prompt
new_prompt_value_var = ctk.StringVar()  # For editing or adding a prompt value

# Add prompt selection dropdown with blue border
prompt_label = ctk.CTkLabel(
    image_page, text="选择 Prompt:", font=ctk.CTkFont(family="Microsoft YaHei", size=16), text_color="#005BB5", anchor="w"
)
prompt_label.pack(pady=10, padx=20, anchor="w")

# Create a frame for dropdown and add button
prompt_dropdown_container = ctk.CTkFrame(
    image_page,
    fg_color="transparent"  # Transparent background
)
prompt_dropdown_container.pack(pady=10, padx=20, anchor="w", fill="x")

# Create a frame with a blue border for the dropdown
prompt_dropdown_frame = ctk.CTkFrame(
    prompt_dropdown_container,
    fg_color="white",  # Background color
    border_color="#005BB5",  # Blue border color
    border_width=2,  # Border width
    corner_radius=10  # Rounded corners
)
prompt_dropdown_frame.pack(side="left", padx=(0, 10))  # Align to the left

# Place the dropdown inside the frame
prompt_dropdown = ctk.CTkOptionMenu(
    prompt_dropdown_frame,
    variable=selected_prompt_var,
    values=list(prompt_dict.keys()),
    width=300,  # Adjusted width to make it narrower
    height=40,
    corner_radius=10,
    fg_color="white",
    button_color="white",
    button_hover_color="#D9EFFF",
    text_color="#005BB5",
    dropdown_text_color="#005BB5",
    dropdown_fg_color="white",
    dropdown_hover_color="#D9EFFF",
    font=ctk.CTkFont(size=14, weight="bold"),
    dropdown_font=ctk.CTkFont(size=14)
)
prompt_dropdown.pack(padx=5, pady=5)  # Add padding inside the frame

# Add "+" button to open the add prompt modal
def open_add_prompt_modal():
    """Open a modal window to add a new prompt with responsive layout."""
    modal = Toplevel(root)  # Create a new top-level window, parent is root
    modal.title("添加新 Prompt")

    # 获取主窗口的位置和尺寸
    root_x = root.winfo_rootx()
    root_y = root.winfo_rooty()
    root_width = root.winfo_width()
    root_height = root.winfo_height()

    # 获取屏幕分辨率和 DPI 缩放比例
    screen_width = modal.winfo_screenwidth()
    screen_height = modal.winfo_screenheight()
    scaling_factor = modal.tk.call('tk', 'scaling')  # 获取 DPI 缩放比例

    # 根据 DPI 缩放调整弹窗尺寸
    base_width = 800  # 基础宽度
    base_height = 500  # 基础高度
    modal_width = int(base_width * scaling_factor)  # 根据缩放比例调整宽度
    modal_height = int(base_height * scaling_factor)  # 根据缩放比例调整高度

    # 确保弹窗宽度和高度不超过屏幕尺寸
    modal_width = min(modal_width, screen_width - 100)
    modal_height = min(modal_height, screen_height - 100)

    # 计算弹窗居中位置（相对于主窗口）
    modal_x = root_x + (root_width - modal_width) // 2
    modal_y = root_y + (root_height - modal_height) // 2
    modal.geometry(f"{modal_width}x{modal_height}+{modal_x}+{modal_y}")

    # 禁止调整大小
    modal.resizable(True, True)  # 允许调整大小

    # 设置模态窗口，阻止与主窗口交互
    modal.grab_set()  # 捕获所有事件，限制用户只能与弹窗交互

    # 添加一个框架作为弹窗内容容器
    modal_frame = ctk.CTkFrame(modal, fg_color="white", corner_radius=10)
    modal_frame.pack(fill="both", expand=True, padx=20, pady=20)  # 自适应填充

    # 使用 grid 布局管理器，设置权重以实现动态调整
    modal_frame.grid_rowconfigure(0, weight=1)  # 第一行（名称输入框）动态调整高度
    modal_frame.grid_rowconfigure(1, weight=3)  # 第二行（Prompt 文本框）动态调整高度
    modal_frame.grid_rowconfigure(2, weight=1)  # 第三行（按钮）动态调整高度
    modal_frame.grid_columnconfigure(0, weight=1)  # 第一列动态调整宽度
    modal_frame.grid_columnconfigure(1, weight=3)  # 第二列动态调整宽度

    # 添加输入框和按钮
    name_label = ctk.CTkLabel(
        modal_frame, text="名称:", font=ctk.CTkFont(family="Microsoft YaHei", size=14), text_color="#005BB5", anchor="w"
    )
    name_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")  # 减少间距

    new_prompt_name_var = ctk.StringVar()
    name_entry = ctk.CTkEntry(
        modal_frame, textvariable=new_prompt_name_var, corner_radius=10
    )
    # 让输入框跨越两列，占满整行
    name_entry.grid(row=0, column=1, columnspan=2, padx=10, pady=5, sticky="ew")  

    # 调整网格列的权重，确保输入框可以动态拉伸
    modal_frame.grid_columnconfigure(0, weight=0)  # 第一列（名称标签）固定宽度
    modal_frame.grid_columnconfigure(1, weight=1)  # 第二列（输入框）动态拉伸
    modal_frame.grid_columnconfigure(2, weight=0)  # 第三列（如果有其他内容）固定宽度

    prompt_label = ctk.CTkLabel(
        modal_frame, text="Prompt:", font=ctk.CTkFont(family="Microsoft YaHei", size=14), text_color="#005BB5", anchor="w"
    )
    prompt_label.grid(row=1, column=0, padx=10, pady=5, sticky="nw")  # 减少间距

    new_prompt_value_var = ctk.StringVar()
    prompt_textbox = ctk.CTkTextbox(
        modal_frame,
        corner_radius=10,
        fg_color="white",
        border_width=1,
        text_color="#005BB5",
        font=ctk.CTkFont(size=12)  # 调整字体大小
    )
    # 让文本框跨越两列，占满整行
    prompt_textbox.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky="nsew")  

    # 调整网格行的权重，确保文本框可以动态拉伸
    modal_frame.grid_rowconfigure(1, weight=1)  # 第二行（Prompt 文本框）动态拉伸

    # 添加按钮
    def add_prompt():
        """Add the new prompt to the dictionary."""
        name = new_prompt_name_var.get().strip()
        prompt = prompt_textbox.get("1.0", "end").strip()
        if not name or not prompt:
            messagebox.showerror("错误", "名称和 Prompt 不能为空!")
            return
        if name in prompt_dict:
            messagebox.showerror("错误", f"名称 '{name}' 已存在!")
            return
        prompt_dict[name] = prompt
        save_prompts()
        update_prompt_dropdown()
        selected_prompt_var.set(name)
        update_prompt_textbox()
        update_status(f"Prompt '{name}' 添加成功!")
        modal.destroy()

    def cancel_add_prompt():
        """Close the modal without adding a prompt."""
        modal.destroy()

    # 修改按钮布局部分
    button_frame = ctk.CTkFrame(modal_frame, fg_color="transparent")
    button_frame.grid(row=2, column=0, columnspan=2, pady=10, sticky="nsew")  # 自适应填充
    button_frame.grid_columnconfigure(0, weight=1)  # 左侧按钮列
    button_frame.grid_columnconfigure(1, weight=1)  # 中间空白列
    button_frame.grid_columnconfigure(2, weight=1)  # 右侧按钮列

    # 添加按钮放置在中线两侧
    add_button = ctk.CTkButton(
        button_frame, 
        text="添加", 
        command=add_prompt,
        fg_color="#005BB5", 
        text_color="white", 
        corner_radius=10,  # 与"添加 API Key"按钮一致
        width=120,  # 按钮宽度调整为 120
        height=35,  # 按钮高度调整为 35
        font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")  # 字体调整为 12
    )
    add_button.grid(row=0, column=0, padx=10, sticky="e")  # 按钮靠右对齐

    cancel_button = ctk.CTkButton(
        button_frame, 
        text="取消", 
        command=cancel_add_prompt,
        fg_color="gray", 
        text_color="white", 
        corner_radius=10,  # 与"添加 API Key"按钮一致
        width=120,  # 按钮宽度调整为 120
        height=35,  # 按钮高度调整为 35
        font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")  # 字体调整为 12
    )
    cancel_button.grid(row=0, column=2, padx=10, sticky="w")  # 按钮靠左对齐

# Add "+" button next to the dropdown
add_prompt_button = ctk.CTkButton(
    prompt_dropdown_container, text="+", command=open_add_prompt_modal,
    width=80, height=40, corner_radius=10,  # Circular button
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(size=20, weight="bold")  # Larger font for "+"
)
add_prompt_button.pack(side="left", padx=(10, 0))  # Align to the right of the dropdown

# Add "Delete" button to delete the selected prompt
def delete_selected_prompt():
    """Delete the currently selected prompt after confirmation."""
    selected_prompt = selected_prompt_var.get()
    if selected_prompt in prompt_dict:
        # Create a custom confirmation dialog centered on the main application window
        confirm_window = Toplevel(root)  # Create a new top-level window
        confirm_window.title("删除")
        confirm_window.geometry("600x200")  # Set the size of the confirmation window
        confirm_window.resizable(False, False)  # Disable resizing

        # Center the confirmation window on the main application window
        root_x = root.winfo_rootx()
        root_y = root.winfo_rooty()
        root_width = root.winfo_width()
        root_height = root.winfo_height()
        confirm_width = 600
        confirm_height = 200
        confirm_x = root_x + (root_width - confirm_width) // 2
        confirm_y = root_y + (root_height - confirm_height) // 2
        confirm_window.geometry(f"{confirm_width}x{confirm_height}+{confirm_x}+{confirm_y}")

        # Make the confirmation window modal (disable interaction with other windows)
        confirm_window.grab_set()

        # Add a label with the confirmation message
        confirm_label = ctk.CTkLabel(
            confirm_window,
            text=f"确定要删除 Prompt '{selected_prompt}'?\n此操作无法撤销.",
            font=ctk.CTkFont(family="Microsoft YaHei", size=14),
            text_color="#005BB5",
            anchor="center",
            justify="center"
        )
        confirm_label.pack(pady=20, padx=20)

        # Add buttons for "Yes" and "No"
        def confirm_delete():
            """Perform the deletion and close the confirmation window."""
            del prompt_dict[selected_prompt]  # Remove the prompt from the dictionary
            save_prompts()  # Save changes to the file
            update_prompt_dropdown()
            selected_prompt_var.set("")  # Clear the selection
            prompt_textbox.delete("1.0", "end")  # Clear the textbox
            update_status(f"Prompt '{selected_prompt}' 已删除.")  # Update status
            confirm_window.destroy()  # Close the confirmation window

        def cancel_delete():
            """Close the confirmation window without deleting."""
            confirm_window.destroy()

        # Add a frame for the buttons
        button_frame = ctk.CTkFrame(confirm_window, fg_color="transparent")
        button_frame.pack(pady=20)

        # "Yes" button
        yes_button = ctk.CTkButton(
            button_frame, text="确定", command=confirm_delete,
            fg_color="#FF5C5C", hover_color="#FF3C3C", text_color="white",
            width=100, height=40, corner_radius=10
        )
        yes_button.pack(side="left", padx=10)

        # "No" button
        no_button = ctk.CTkButton(
            button_frame, text="取消", command=cancel_delete,
            fg_color="#005BB5", hover_color="#003F7F", text_color="white",
            width=100, height=40, corner_radius=10
        )
        no_button.pack(side="left", padx=10)
    else:
        messagebox.showerror("错误", "没有选择要删除的 Prompt!")

delete_prompt_button = ctk.CTkButton(
    prompt_dropdown_container, text="删除", command=delete_selected_prompt,
    width=80, height=40, corner_radius=10,  # Adjusted size for the button
    fg_color="#FF5C5C", hover_color="#FF3C3C", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")  # Font size and weight
)
delete_prompt_button.pack(side="left", padx=(10, 0))  # Align between "+" and "Save" buttons

# Add "Save" button to save changes to the selected prompt
def save_prompt_changes():
    """Save changes made to the selected prompt."""
    selected_prompt = selected_prompt_var.get()
    if selected_prompt in prompt_dict:
        updated_prompt = prompt_textbox.get("1.0", "end").strip()  # Get updated content
        if updated_prompt:
            prompt_dict[selected_prompt] = updated_prompt  # Update the dictionary
            save_prompts()  # Save changes to the file
            update_status(f"Prompt '{selected_prompt}' 已更新并保存!")  # Update status
        else:
            messagebox.showerror("错误", "Prompt 内容不能为空!")
    else:
        messagebox.showerror("错误", "没有选择要保存的 Prompt!")

save_prompt_button = ctk.CTkButton(
    prompt_dropdown_container, text="保存", command=save_prompt_changes,
    width=80, height=40, corner_radius=10,  # Adjusted size for the button
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")  # Font size and weight
)
save_prompt_button.pack(side="left", padx=(10, 0))  # Align to the right of the "Delete" button

# Add text box for editing the selected prompt (below the dropdown)
prompt_textbox_frame = ctk.CTkFrame(
    image_page,
    fg_color="white",  # Background color
    border_color="#005BB5",  # Blue border color
    border_width=2,  # Border width
    corner_radius=10  # Rounded corners
)
prompt_textbox_frame.pack(pady=10, padx=20, anchor="w", fill="x")  # Adjusted to fill horizontally

prompt_textbox = ctk.CTkTextbox(
    prompt_textbox_frame,
    width=600,  # Adjusted width
    height=150,  # Initial height
    corner_radius=10,
    fg_color="white",
    border_width=0,  # No additional border inside the frame
    text_color="#005BB5",
    font=ctk.CTkFont(size=14)  # Adjusted font size for readability
)
prompt_textbox.pack(padx=5, pady=5, fill="both", expand=True)  # Allow the textbox to expand within the frame

# Function to adjust the height of the textbox based on its content
def adjust_textbox_height():
    """Adjust the height of the prompt_textbox based on its content."""
    content = prompt_textbox.get("1.0", "end").strip()  # Get the content of the textbox
    num_lines = content.count("\n") + 1  # Count the number of lines
    line_height = 20  # Approximate height of a single line (adjust as needed)
    new_height = max(150, num_lines * line_height)  # Minimum height is 150
    prompt_textbox.configure(height=new_height)  # Update the height of the textbox

# Function to update the prompt text box when a new prompt is selected
def update_prompt_textbox(*args):
    selected_prompt = selected_prompt_var.get()
    if selected_prompt in prompt_dict:
        prompt_textbox.delete("1.0", "end")  # Clear the textbox
        prompt_textbox.insert("1.0", prompt_dict[selected_prompt])  # Insert the new prompt value
        save_selected_prompt(selected_prompt)  # 保存用户选择的 Prompt
    else:
        prompt_textbox.delete("1.0", "end")  # Clear the textbox if no prompt is selected
    adjust_textbox_height()  # Adjust the height after updating the content

# Function to update the dropdown menu
def update_prompt_dropdown():
    """Update the dropdown menu with the latest prompt keys."""
    prompt_dropdown.configure(values=list(prompt_dict.keys()))

# Initialize the prompt dropdown and text box
update_prompt_dropdown()
update_prompt_textbox()

# Bind the dropdown variable to update the textbox when the selection changes
selected_prompt_var.trace_add("write", update_prompt_textbox)

# 修改"开始处理"和"暂停处理"按钮的布局
button_frame = ctk.CTkFrame(image_page, fg_color="transparent")  # 创建一个容器框架
button_frame.pack(pady=10, padx=20, anchor="w")  # 放置在 prompt_textbox 下方

def toggle_processing_pause():
    """暂停或恢复图片处理"""
    global processing_paused
    processing_paused = not processing_paused  # 切换暂停状态
    if processing_paused:
        update_status("暂停打标.")
        pause_button.configure(text="恢复打标")  # 更新按钮文本
    else:
        update_status("恢复打标.")
        pause_button.configure(text="暂停打标")  # 更新按钮文本

# 在图片处理页面添加"开始处理"和"暂停处理"按钮
start_button = ctk.CTkButton(
    button_frame, text="开始打标", command=start_processing,
    width=150, height=50, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",  # 恢复为深蓝色按钮
    font=ctk.CTkFont(family="Microsoft YaHei", size=16, weight="bold")  # 修改为更美观的中文字体
)
start_button.pack(side="left", padx=10, pady=20)

pause_button = ctk.CTkButton(
    button_frame, text="暂停打标", command=toggle_processing_pause,
    width=150, height=50, corner_radius=10,
    fg_color="#FF9800", hover_color="#FF8C00", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=16, weight="bold")  # 修改为更美观的中文字体
)
pause_button.pack(side="left", padx=10, pady=20)

# 新增：批量处理 TXT 文件页面功能
def select_txt_directory():
    """选择 TXT 文件目录"""
    directory = filedialog.askdirectory(title="Select TXT Directory")
    if directory:
        txt_directory_var.set(directory)
        update_status("TXT 文件目录选择成功!")
    else:
        update_status("TXT 文件目录选择取消!")

def batch_add_to_txt(position):
    """批量在 TXT 文件中添加内容"""
    directory = txt_directory_var.get()
    content = txt_input_var.get().strip()

    if not directory:
        messagebox.showerror("Error", "TXT 文件目录不能为空!")
        update_status("Error: TXT 文件目录不能为空!")
        return
    if not content:
        messagebox.showerror("Error", "添加内容不能为空!")
        update_status("Error: 添加内容不能为空!")
        return

    # 遍历目录中的所有 .txt 文件
    for filename in os.listdir(directory):
        if filename.endswith(".txt"):
            file_path = os.path.join(directory, filename)
            try:
                with open(file_path, "r+", encoding="utf-8") as file:
                    lines = file.readlines()
                    if position == "start":
                        # 在内容后面加上英文逗号和空格
                        lines.insert(0, content + ", ")  # 添加到首部
                    elif position == "end":
                        # 在内容前面加上英文逗号和空格
                        if lines and not lines[-1].endswith("\n"):
                            lines[-1] = lines[-1].strip() + ", " + content  # 直接追加到最后一行
                        else:
                            lines.append(", " + content)  # 添加到尾部
                    file.seek(0)
                    file.truncate(0)  # 清空文件
                    file.writelines(lines)
                update_status(f"内容已添加到 {filename}")
            except Exception as e:
                update_status(f"处理 {filename} 时发生错误: {e}")

    messagebox.showinfo("Info", "批量添加完成!")
    update_status("批量添加完成!")

def batch_delete_from_txt():
    """批量从 TXT 文件中删除内容"""
    directory = txt_directory_var.get()
    content = txt_input_var.get().strip()

    if not directory:
        messagebox.showerror("Error", "TXT 文件目录不能为空!")
        update_status("Error: TXT 文件目录不能为空!")
        return
    if not content:
        messagebox.showerror("Error", "删除内容不能为空!")
        update_status("Error: 删除内容不能为空!")
        return

    # 遍历目录中的所有 .txt 文件
    for filename in os.listdir(directory):
        if filename.endswith(".txt"):
            file_path = os.path.join(directory, filename)
            try:
                with open(file_path, "r+", encoding="utf-8") as file:
                    lines = file.readlines()
                    new_lines = []
                    for line in lines:
                        # 优先删除内容后面的逗号和空格
                        line = line.replace(content + ", ", "")  # 删除 "内容, "
                        line = line.replace(content + ",\n", "\n")  # 删除 "内容, 换行符"
                        # 删除内容前面的逗号和空格（如果内容在末尾）
                        line = line.replace(", " + content, "")  # 删除 ", 内容"
                        line = line.replace(",\n" + content, "\n")  # 删除 ", 换行符 + 内容"
                        # 最后删除内容本身
                        line = line.replace(content, "")  # 删除单独的 "内容"
                        new_lines.append(line)

                    # 清空文件并写入更新后的内容
                    file.seek(0)
                    file.truncate(0)
                    file.writelines(new_lines)
                update_status(f"内容已从 {filename} 中删除")
            except Exception as e:
                update_status(f"处理 {filename} 时发生错误: {e}")

    messagebox.showinfo("Info", "批量删除完成!")
    update_status("批量删除完成!")

# 新增：批量处理 TXT 文件页面
txt_title = ctk.CTkLabel(
    txt_page, text="批量处理 TXT 文件",
    font=ctk.CTkFont(family="Microsoft YaHei", size=24, weight="bold"),
    text_color="#005BB5", anchor="w"
)
txt_title.pack(pady=20, padx=20, anchor="w")

txt_description = ctk.CTkLabel(
    txt_page,  # 缺少父容器参数，已修复
    text=(
        "📄 批量处理文件夹中的 TXT 文件，您可以：\n"
        "1. 在 TXT 文件的开头或结尾批量添加指定内容。\n"
        "2. 删除 TXT 文件中任意位置出现的指定内容。"
    ),
    font=ctk.CTkFont(family="Microsoft YaHei", size=14),  # 正文字体
    text_color="#005BB5",  # 深蓝色文字
    anchor="w",
    justify="left",  # 左对齐
    padx=10,  # 内边距
    pady=10  # 内边距
)
txt_description.pack(fill="x", padx=10, pady=10)  # 填充水平空间

txt_tips = ctk.CTkLabel(
    txt_page,  # 缺少父容器参数，已修复
    text="Tips:无需添加任何逗号和空格，直接输入内容即可。",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold"),  # 正文字体
    text_color="#FF0000",  # 红色文字
    anchor="w",
    justify="left",  # 左对齐
    padx=10,  # 内边距
    pady=10  # 内边距
)
txt_tips.pack(padx=10, fill="x")  # 填充水平空间

# 添加小标题：txt文件目录
txt_directory_label = ctk.CTkLabel(
    txt_page, text="TXT 文件目录:", font=ctk.CTkFont(family="Microsoft YaHei", size=16), text_color="#005BB5", anchor="w"
)
txt_directory_label.pack(pady=(10, 0), padx=20, anchor="w")  # 添加标题并调整间距

# 文件夹选择部分
txt_directory_frame = ctk.CTkFrame(txt_page, fg_color="transparent")
txt_directory_frame.pack(pady=10, padx=20, anchor="w", fill="x")

txt_directory_entry = ctk.CTkEntry(
    txt_directory_frame, textvariable=txt_directory_var, width=600, height=40, corner_radius=10,  # 调整宽度为600
    fg_color="white", border_color="#005BB5", border_width=2, text_color="#005BB5"
)
txt_directory_entry.pack(side="left", padx=(0, 10))

txt_directory_button = ctk.CTkButton(
    txt_directory_frame, text="选择文件夹", command=select_txt_directory,
    width=100, height=40, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")
)
txt_directory_button.pack(side="left")

# 文本输入框
txt_input_label = ctk.CTkLabel(
    txt_page, text="输入内容:", font=ctk.CTkFont(family="Microsoft YaHei", size=16), text_color="#005BB5", anchor="w"
)
txt_input_label.pack(pady=10, padx=20, anchor="w")

txt_input_entry = ctk.CTkEntry(
    txt_page, textvariable=txt_input_var, width=600, height=40, corner_radius=10,  # 调整宽度为600
    fg_color="white", border_color="#005BB5", border_width=2, text_color="#005BB5"
)
txt_input_entry.pack(pady=10, padx=20, anchor="w")

# 批量操作按钮
txt_button_frame = ctk.CTkFrame(txt_page, fg_color="transparent")
txt_button_frame.pack(pady=20, padx=20, anchor="w", fill="x")

add_to_start_button = ctk.CTkButton(
    txt_button_frame, text="批量添加到首部", command=lambda: batch_add_to_txt("start"),
    width=150, height=40, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")
)
add_to_start_button.pack(side="left", padx=(0, 20))

add_to_end_button = ctk.CTkButton(
    txt_button_frame, text="批量添加到尾部", command=lambda: batch_add_to_txt("end"),
    width=150, height=40, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")
)
add_to_end_button.pack(side="left", padx=(0, 130))

delete_button = ctk.CTkButton(
    txt_button_frame, text="批量删除", command=batch_delete_from_txt,
    width=150, height=40, corner_radius=10,
    fg_color="#FF5C5C", hover_color="#FF3C3C", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")
)
delete_button.pack(side="left")

# 将新页面添加到导航栏
txt_button = ctk.CTkButton(
    sidebar, text="📄 批量处理 TXT", command=lambda: show_page(txt_page),
    width=200, height=50, corner_radius=10,
    fg_color="white", hover_color="#E5F1FB",
    font=ctk.CTkFont(family="Microsoft YaHei", size=15, weight="bold"),
    text_color="#005BB5"
)
txt_button.pack(pady=10, padx=5)

# 新增：生图标签生成页面
def extract_words_and_phrases(text):
    """提取文本中的单个单词或多词组"""
    # 定义正则表达式，提取所有的单词或词组（至少两个单词）
    pattern = re.compile(r'\b[a-zA-Z0-9-]+(?:\s[a-zA-Z0-9-]+)*\b')
    return re.findall(pattern, text)

def process_files(folder_path):
    """读取所有文件并提取唯一的单词和词组"""
    unique_terms = set()
    for filename in os.listdir(folder_path):
        if filename.endswith(".txt"):
            with open(os.path.join(folder_path, filename), "r", encoding="utf-8") as file:
                text = file.read()
                terms = extract_words_and_phrases(text)
                unique_terms.update(terms)
    return sorted(unique_terms)

def select_table_directory():
    """选择文件夹"""
    directory = filedialog.askdirectory(title="选择 TXT 文件夹")
    if directory:
        table_directory_var.set(directory)
        update_status("TXT 文件夹选择成功!")
    else:
        update_status("TXT 文件夹选择取消!")

# 分页变量
txt_current_page = 0  # 当前页码
txt_items_per_page = 500  # 每页显示的条目数量
all_terms = []  # 存储所有结果的全局变量

def update_result_textbox_paginated(page):
    """分页更新结果到文本框，以逗号分隔"""
    global txt_current_page, all_terms
    txt_current_page = page
    result_textbox.delete("1.0", "end")  # 清空文本框

    # 计算当前页的内容
    start_index = page * txt_items_per_page
    end_index = start_index + txt_items_per_page
    page_terms = all_terms[start_index:end_index]

    # 将当前页的内容用逗号分隔后插入到文本框
    comma_separated_terms = ", ".join(page_terms)
    result_textbox.insert("1.0", comma_separated_terms)  # 显示结果

    # 更新状态栏，显示当前页信息
    update_status(f"显示第 {page + 1} 页，共 {len(all_terms) // txt_items_per_page + 1} 页")

def next_page():
    """显示下一页"""
    global txt_current_page, all_terms
    if (txt_current_page + 1) * txt_items_per_page < len(all_terms):
        update_result_textbox_paginated(txt_current_page + 1)

def previous_page():
    """显示上一页"""
    global txt_current_page
    if txt_current_page > 0:
        update_result_textbox_paginated(txt_current_page - 1)

def process_files_in_thread(folder_path):
    """后台线程中处理文件夹中的 TXT 文件"""
    global all_terms
    try:
        unique_terms = set()
        for filename in os.listdir(folder_path):
            if filename.endswith(".txt"):
                file_path = os.path.join(folder_path, filename)
                with open(file_path, "r", encoding="utf-8") as file:
                    text = file.read()
                    terms = extract_words_and_phrases(text)
                    unique_terms.update(terms)

        # 将结果排序并存储到全局变量
        all_terms = sorted(unique_terms)

        # 在主线程中更新 UI
        result_textbox.after(0, update_result_textbox_paginated, 0)  # 显示第一页
        update_status(f"处理完成! 共提取 {len(all_terms)} 个唯一标签")
    except Exception as e:
        # 在主线程中显示错误信息
        result_textbox.after(0, lambda: messagebox.showerror("Error", f"处理文件时发生错误: {e}"))
        update_status(f"Error: 处理文件时发生错误: {e}")


def start_table_processing():
    """开始处理文件夹中的 TXT 文件"""
    directory = table_directory_var.get()
    if not directory:
        messagebox.showerror("Error", "文件夹路径不能为空!")
        update_status("Error: 文件夹路径不能为空!")
        return

    if not os.path.exists(directory):
        messagebox.showerror("Error", "文件夹路径无效!")
        update_status("Error: 文件夹路径无效!")
        return

    # 启动后台线程处理文件
    update_status("正在处理文件夹，请稍候...")
    processing_thread = threading.Thread(target=process_files_in_thread, args=(directory,))
    processing_thread.start()

# 修改保存结果的函数
def save_table_results():
    """保存所有结果到本地 TXT 文件，使用英文逗号分隔"""
    global all_terms  # 确保访问全局变量
    save_path = filedialog.asksaveasfilename(
        title="保存结果", defaultextension=".txt",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
    )
    if save_path:
        try:
            # 将所有结果用英文逗号分隔
            comma_separated_content = ", ".join(all_terms)

            # 保存到文件
            with open(save_path, "w", encoding="utf-8") as file:
                file.write(comma_separated_content)

            update_status(f"结果已成功保存到: {save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"保存文件时发生错误: {e}")
            update_status(f"Error: 保存文件时发生错误: {e}")

# 添加生图标签生成页面
table_title = ctk.CTkLabel(
    table_page, text="生图标签生成",
    font=ctk.CTkFont(family="Microsoft YaHei", size=24, weight="bold"),
    text_color="#005BB5", anchor="w"
)
table_title.pack(pady=20, padx=20, anchor="w")

table_description = ctk.CTkLabel(
    table_page,
    text="📄  选择一个包含 TXT 文件的文件夹，提取所有TXT文件里唯一的单词和词组。",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14),
    text_color="#005BB5", anchor="w", justify="left", padx=10, pady=10
)
table_description.pack(fill="x", padx=10, pady=10)

# 文件夹选择部分
table_directory_var = ctk.StringVar()
table_directory_label = ctk.CTkLabel(
    table_page, text="TXT 文件夹路径:", font=ctk.CTkFont(family="Microsoft YaHei", size=16), text_color="#005BB5", anchor="w"
)
table_directory_label.pack(pady=(10, 0), padx=20, anchor="w")

table_directory_frame = ctk.CTkFrame(table_page, fg_color="transparent")
table_directory_frame.pack(pady=10, padx=20, anchor="w", fill="x")

table_directory_entry = ctk.CTkEntry(
    table_directory_frame, textvariable=table_directory_var, width=600, height=40, corner_radius=10,
    fg_color="white", border_color="#005BB5", border_width=2, text_color="#005BB5"
)
table_directory_entry.pack(side="left", padx=(0, 10))

table_directory_button = ctk.CTkButton(
    table_directory_frame, text="选择文件夹", command=select_table_directory,
    width=100, height=40, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")
)
table_directory_button.pack(side="left")

# 开始处理按钮
start_table_button = ctk.CTkButton(
    table_page, text="开始处理", command=start_table_processing,
    width=150, height=40, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")
)
start_table_button.pack(pady=20, padx=20, anchor="w")

# 结果显示框
result_label = ctk.CTkLabel(
    table_page, text="处理结果:", font=ctk.CTkFont(family="Microsoft YaHei", size=16), text_color="#005BB5", anchor="w"
)
result_label.pack(pady=(10, 0), padx=20, anchor="w")

result_textbox = ctk.CTkTextbox(
    table_page, width=800, height=300, corner_radius=10,
    fg_color="white", border_color="#005BB5", border_width=2, text_color="#005BB5",
    font=ctk.CTkFont(family="Microsoft YaHei", size=16)  # 调整字体大小为16
)
result_textbox.pack(pady=10, padx=20, anchor="w", fill="x")

# 添加分页按钮
pagination_frame = ctk.CTkFrame(table_page, fg_color="transparent")
pagination_frame.pack(pady=10, padx=20, anchor="w", fill="x")

previous_page_button = ctk.CTkButton(
    pagination_frame, text="上一页", command=previous_page,
    width=100, height=40, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")
)
previous_page_button.pack(side="left", padx=(0, 10))

next_page_button = ctk.CTkButton(
    pagination_frame, text="下一页", command=next_page,
    width=100, height=40, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")
)
next_page_button.pack(side="left", padx=(0, 10))

save_table_button = ctk.CTkButton(
    pagination_frame, text="保存结果", command=save_table_results,
    width=150, height=40, corner_radius=10,
    fg_color="#005BB5", hover_color="#003F7F", text_color="white",
    font=ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")
)
save_table_button.pack(side="left")

# 将新页面添加到导航栏
table_button = ctk.CTkButton(
    sidebar, text="📋 生图标签生成", command=lambda: show_page(table_page),
    width=200, height=50, corner_radius=10,
    fg_color="white", hover_color="#E5F1FB",
    font=ctk.CTkFont(family="Microsoft YaHei", size=15, weight="bold"),
    text_color="#005BB5"
)
table_button.pack(pady=10, padx=5)

# 默认显示"📷 Image Processing"页面
show_page(image_page)

# 启动主循环
root.mainloop()