import os
import time
import platform
import threading
from datetime import datetime

# ==============================================
# ================= 可修改参数区（和Mac版完全一致） =================
# ==============================================
SCAN_INTERVAL = 600                  # 定时全局扫描间隔(秒)
SAVE_FOLDER = r"D:\DiskRecordMd"      # MD保存目录（Windows路径写法）
EXCLUDE_SYSTEM_DISK = True            # 是否跳过系统C盘
EXCLUDE_DIR_LIST = {
    "$RECYCLE.BIN", "System Volume Information",
    "Windows", "Program Files", "Program Files (x86)",
    ".DS_Store", "__pycache__", "lost+found"
}
CHECK_UNMOUNT_INTERVAL = 2           # 硬盘拔出检测频率(秒)
# ==============================================

os.makedirs(SAVE_FOLDER, exist_ok=True)
scanned_disk_set = set()
last_disk_list = []


def format_file_size(size_bytes):
    """文件大小格式化"""
    if size_bytes == 0:
        return "0 B"
    unit_list = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while size_bytes >= 1024 and index < len(unit_list) - 1:
        size_bytes /= 1024
        index += 1
    return f"{size_bytes:.2f} {unit_list[index]}"


def get_win_disks():
    """Windows 获取所有本地/移动硬盘、U盘"""
    disk_list = []
    # 遍历所有盘符
    for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive_path = f"{drive_letter}:\\"
        if os.path.exists(drive_path):
            # 跳过C盘系统盘
            if EXCLUDE_SYSTEM_DISK and drive_letter.upper() == "C":
                continue
            disk_name = f"{drive_letter}盘"
            disk_list.append((drive_path, disk_name))
    return disk_list


def scan_disk_and_save_md(disk_path, disk_name):
    """扫描单盘 + 覆盖写入MD"""
    md_file_path = os.path.join(SAVE_FOLDER, f"{disk_name}.md")
    total_file_count = 0
    start_time = time.time()

    try:
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(f"# {disk_name} 文件目录\n")
            f.write(f"**硬盘路径**: {disk_path}\n")
            f.write(f"**更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("---\n\n")

            for folder_path, sub_folders, file_list in os.walk(disk_path):
                sub_folders[:] = [d for d in sub_folders if d not in EXCLUDE_DIR_LIST]
                depth = folder_path.replace(disk_path, "").count(os.sep)
                current_folder_name = os.path.basename(folder_path) or "硬盘根目录"
                f.write(f"{'  ' * depth}- 📂 **{current_folder_name}**\n")

                for file_name in file_list:
                    if file_name in EXCLUDE_DIR_LIST:
                        continue
                    file_full_path = os.path.join(folder_path, file_name)
                    try:
                        file_size = os.path.getsize(file_full_path)
                        modify_time = os.path.getmtime(file_full_path)
                        modify_time_str = datetime.fromtimestamp(modify_time).strftime("%Y-%m-%d %H:%M")
                        f.write(f"{'  ' * (depth + 1)}- 📄 {file_name} | {format_file_size(file_size)} | {modify_time_str}\n")
                        total_file_count += 1
                    except Exception:
                        continue

            cost_time = round(time.time() - start_time, 2)
            f.write(f"\n---\n")
            f.write(f"📊 总计文件: {total_file_count} 个 | 扫描耗时: {cost_time} 秒")
        print(f"✅ 更新MD: {disk_name}")
    except Exception as e:
        print(f"⚠️ 扫描异常: {str(e)}")


def unmount_monitor_task():
    """监控U盘/硬盘拔出，弹出前询问扫描"""
    global last_disk_list
    while True:
        current_list = get_win_disks()
        current_path_set = {item[0] for item in current_list}
        last_path_set = {item[0] for item in last_disk_list}

        # 检测被移除的磁盘
        remove_paths = last_path_set - current_path_set

        for disk_path in remove_paths:
            name = ""
            for p, n in last_disk_list:
                if p == disk_path:
                    name = n
                    break
            if name:
                print(f"\n🚨 【{name}】 已触发弹出/拔出")
                choice = input("👉 是否最后扫描一次并更新MD？(y/n，默认n)：").strip().lower()
                if choice in ["y", "yes"]:
                    print(f"🔍 正在最终归档扫描：{name}")
                    scan_disk_and_save_md(disk_path, name)
                    print(f"✅ {name} 目录已最新，可安全拔出\n")
                else:
                    print(f"⏭️ 跳过最终扫描\n")

        last_disk_list = current_list
        time.sleep(CHECK_UNMOUNT_INTERVAL)


def background_scan_task():
    """定时后台全盘扫描"""
    global scanned_disk_set
    print("========================================")
    print("🚀 Windows 硬盘自动扫描程序已启动")
    print(f"📂 MD保存目录: {os.path.abspath(SAVE_FOLDER)}")
    print(f"⏱️ 定时刷新间隔: {SCAN_INTERVAL // 60} 分钟")
    print("🛡️ 已开启【弹出前询问扫描】")
    print("========================================")

    while True:
        current_disks = get_win_disks()
        current_disk_paths = set()

        for path, name in current_disks:
            current_disk_paths.add(path)
            if path not in scanned_disk_set:
                print(f"\n🔌 检测到新磁盘接入: {name}")
                scanned_disk_set.add(path)
            scan_disk_and_save_md(path, name)

        scanned_disk_set.intersection_update(current_disk_paths)
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    # 双线程独立运行
    unmount_thread = threading.Thread(target=unmount_monitor_task, daemon=True)
    unmount_thread.start()

    scan_thread = threading.Thread(target=background_scan_task, daemon=True)
    scan_thread.start()

    # 主线程保活
    while True:
        time.sleep(1)