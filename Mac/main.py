import os
import time
import threading
from datetime import datetime

# ==============================================
# ================= 可修改参数区 =================
# ==============================================
SCAN_INTERVAL = 6000
SAVE_FOLDER = "/Users/liyi/Documents/Ryan's Brain No.2/DiskMd"
EXCLUDE_SYSTEM_DISK = True
EXCLUDE_DIR_LIST = {
    ".DS_Store", "__pycache__", "lost+found",
    "System", "Library", "private", "cores"
}
MAX_EXPAND_DEPTH = 5        # 超过5层自动折叠
MAX_ITEM_TO_EXPAND = 10     # 超过10项自动折叠
CHECK_UNMOUNT_INTERVAL = 2
# ==============================================

FILE_ICON_MAP = {
    ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️", ".webp": "🖼️", ".heic": "🖼️",
    ".mp4": "🎬", ".mov": "🎬", ".avi": "🎬", ".mkv": "🎬", ".flv": "🎬", ".wmv": "🎬",
    ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵", ".aac": "🎵", ".ogg": "🎵",
    ".pdf": "📕", ".doc": "📘", ".docx": "📘", ".xls": "📗", ".xlsx": "📗", ".ppt": "📙", ".pptx": "📙",
    ".txt": "📄", ".md": "📝",
    ".zip": "📦", ".rar": "📦", ".7z": "📦", ".tar": "📦", ".gz": "📦",
    ".exe": "⚙️", ".py": "💻", ".js": "💻", ".html": "🌐", ".css": "🎨",
    ".iso": "💿"
}

os.makedirs(SAVE_FOLDER, exist_ok=True)
scanned_disk_set = set()
last_disk_list = []

def format_file_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    unit_list = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while size_bytes >= 1024 and index < len(unit_list)-1:
        size_bytes /= 1024
        index += 1
    return f"{size_bytes:.2f} {unit_list[index]}"

def get_external_disks():
    disk_list = []
    volumes_path = "/Volumes"
    if os.path.exists(volumes_path):
        for disk_name in os.listdir(volumes_path):
            disk_full_path = os.path.join(volumes_path, disk_name)
            if os.path.ismount(disk_full_path):
                if EXCLUDE_SYSTEM_DISK and disk_name == "Macintosh HD":
                    continue
                disk_list.append((disk_full_path, disk_name))
    return disk_list

def scan_disk_and_save_md(disk_path, disk_name):
    """
    最终修复版
    1. 正确的HTML嵌套结构：父details包裹子 → 关闭父自动收起所有子
    2. 正确的层级缩进：逐级递增，Obsidian显示正常
    3. 修复了os.walk深度优先遍历导致的层级错位和子文件夹丢失问题
    4. 自动折叠规则、彩色方块图标、右对齐信息全部保留
    5. 无一键收纳/JS，标题行保留注释
    """
    md_file_path = os.path.join(SAVE_FOLDER, f"{disk_name}.md")
    total_file_count = 0
    start_time = time.time()

    item_count = {}
    dir_total_size = {}

    def calc_total_size(path):
        """递归计算目录总大小"""
        total_bytes = 0
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR_LIST]
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    total_bytes += os.path.getsize(fp)
                except:
                    continue
        return total_bytes

    # 预扫描统计数据
    for root, dirs, files in os.walk(disk_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR_LIST]
        size_byte = calc_total_size(root)
        total_items = len(dirs) + len(files)
        dir_total_size[root] = size_byte
        item_count[root] = total_items

    def get_folder_icon(depth):
        """层级纯色方块图标"""
        level = depth % 10
        if level == 0: return "📁"
        elif level == 1: return "🟦"
        elif level == 2: return "🟩"
        elif level == 3: return "🟧"
        elif level == 4: return "🟥"
        elif level == 5: return "🟪"
        elif level == 6: return "🟨"
        elif level == 7: return "🟫"
        elif level == 8: return "⬛"
        elif level == 9: return "⬜"
        else: return "📁"

    with open(md_file_path, "w", encoding="utf-8") as f:
        # 保留但注释的标题行
        # f.write(f"# {disk_name} 文件目录\n")
        
        f.write(f"**硬盘名称**: {disk_name}\n")
        f.write(f"**硬盘路径**: {disk_path}\n")
        f.write(f"**更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("---\n\n")

        # 栈结构：维护嵌套层级
        stack = []

        for folder_path, sub_folders, file_list in os.walk(disk_path):
            sub_folders[:] = [d for d in sub_folders if d not in EXCLUDE_DIR_LIST]
            depth = folder_path.replace(disk_path, "").count(os.sep)
            folder_name = os.path.basename(folder_path) if folder_path != disk_path else "硬盘根目录"

            total_items = item_count[folder_path]
            folder_size = format_file_size(dir_total_size[folder_path])
            info = f"{folder_size} · {total_items} 项"

            # 折叠规则
            need_collapse = (depth >= MAX_EXPAND_DEPTH) or (total_items > MAX_ITEM_TO_EXPAND)
            icon = get_folder_icon(depth)

            # 修复1：先处理栈，闭合比当前层级更深的标签
            while stack and stack[-1] >= depth:
                f.write("</div>\n</details>\n")
                stack.pop()

            # 写入当前文件夹（嵌套开启）
            open_attr = "open" if not need_collapse else ""
            f.write(f"<details {open_attr}>\n")
            f.write(f"<summary>{icon} {folder_name} <span style='float:right'>{info}</span></summary>\n")
            # 修复2：使用固定的margin-left实现缩进，保证每一级都正确
            f.write(f"<div style='margin-left: 1.5em;'>\n")
            stack.append(depth)

            # 写入当前文件夹内的文件
            for fname in file_list:
                if fname in EXCLUDE_DIR_LIST:
                    continue
                fp = os.path.join(folder_path, fname)
                try:
                    size = format_file_size(os.path.getsize(fp))
                    mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M')
                    ext = os.path.splitext(fname)[1].lower()
                    file_icon = FILE_ICON_MAP.get(ext, "📄")
                    f.write(f"<div>{file_icon} {fname} <span style='float:right'>{size} · {mtime}</span></div>\n")
                    total_file_count += 1
                except:
                    continue

        # 闭合所有剩余标签
        while stack:
            f.write("</div>\n</details>\n")
            stack.pop()

        # 底部统计
        cost = round(time.time() - start_time, 2)
        f.write(f"\n---\n📊 总计文件：{total_file_count} 个 | 耗时：{cost} 秒\n")

    print(f"✅ MD已更新：{disk_name}")

def unmount_monitor_task():
    global last_disk_list
    while True:
        now_list = get_external_disks()
        now_set = {p for p,_ in now_list}
        last_set = {p for p,_ in last_disk_list}
        removed = last_set - now_set

        for path in removed:
            name = next((n for p,n in last_disk_list if p == path), "")
            if name:
                print(f"\n🚨 【{name}】 正在弹出！")
                choice = input(f"👉 是否最后扫描一次并更新MD？(y/n) 默认n：").strip().lower()
                if choice in ["y", "yes"]:
                    print(f"🔍 正在最终扫描：{name}")
                    scan_disk_and_save_md(path, name)
                    print(f"✅ {name} 已归档完成，可以安全拔出！\n")
                else:
                    print(f"⏭️ 跳过扫描，直接弹出：{name}\n")

        last_disk_list = now_list
        time.sleep(CHECK_UNMOUNT_INTERVAL)

def background_scan_task():
    global scanned_disk_set
    print("========================================")
    print("🚀 硬盘自动扫描已启动")
    print("========================================")
    while True:
        disks = get_external_disks()
        current_paths = {p for p,_ in disks}
        for p,n in disks:
            if p not in scanned_disk_set:
                print(f"\n🔌 新硬盘：{n}")
                scanned_disk_set.add(p)
            scan_disk_and_save_md(p,n)
        scanned_disk_set.intersection_update(current_paths)
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    t1 = threading.Thread(target=unmount_monitor_task, daemon=True)
    t1.start()
    t2 = threading.Thread(target=background_scan_task, daemon=True)
    t2.start()
    while True:
        time.sleep(1)