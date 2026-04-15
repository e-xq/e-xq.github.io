import os
import sys
import time
import mmap
import zstandard as zstd
import hashlib
import traceback
import shutil
from pathlib import Path
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

FAST_MODE = True
MAX_THREADS = 8
TGA_TAIL_MAGIC = b'TRUEVISION-XFILE.\x00'
TIME_FILE = "__extract_time.txt"

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"

def format_size(n):
    if n < 1024 * 1024:
        return f"{n/1024:.2f}KB"
    elif n < 1024 * 1024 * 1024:
        return f"{n/1024/1024:.2f}MB"
    else:
        return f"{n/1024/1024/1024:.2f}GB"

def detect_ext(data):
    if not data:
        return "UNK"
    if len(data) >= 4 and data[:4] == b'\x34\x80\xc8\xbb':
        return "MESH"
    if len(data) >= 4 and data[:4] == b'\x89PNG':
        return "PNG"
    if len(data) >= 8 and data[:8] == b'\xABKTX 11\xBB':
        return "KTX"
    if len(data) >= 3 and data[:3] == b'DDS':
        return "DDS"
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        return "WEM"
    if len(data) >= 4 and data[:4] == b'BKHD':
        return "BNK"
    if len(data) >= 4 and data[:4] == b'AKPK':
        return "NPK"
    if len(data) >= 4 and data[:4] == b'\x28\xb5\x2f\xfd':
        return "ZST"
    if len(data) >= len(TGA_TAIL_MAGIC) and data[-len(TGA_TAIL_MAGIC):] == TGA_TAIL_MAGIC:
        return "TGA"
    return "UNK"

def check_output_dir(out_root):
    time_file = os.path.join(out_root, TIME_FILE)
    if os.path.exists(time_file):
        with open(time_file, "r") as f:
            last_time = f.read().strip()
        print(f"检测到上次解包时间: {last_time}")
        ans = input("输出文件夹内发现剩余文件，是否覆盖？(Y/N): ").strip().upper()
        if ans == "Y":
            files = os.listdir(out_root)
            print("正在清理输出目录...")
            for fname in tqdm(files, desc="删除进度"):
                fpath = os.path.join(out_root, fname)
                if os.path.isdir(fpath):
                    shutil.rmtree(fpath)
                else:
                    os.remove(fpath)
            print("清理完成。")
        else:
            print("用户选择不覆盖，停止解包。")
            sys.exit(0)
    with open(time_file, "w") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S"))

def extract_frame(mm, start, end, idx, total, out_root, err_path, hash_set, lock, type_count):
    try:
        dctx = zstd.ZstdDecompressor()
        chunk = mm[start:end]
        decompressed = dctx.decompress(chunk)
        h = hashlib.md5(decompressed).hexdigest()
        with lock:
            if h in hash_set:
                return f"正在处理 [{idx:05d}/{total}] @ {start:08X} | SKIP | 重复文件"
            hash_set.add(h)
        ext = detect_ext(decompressed)
        folder = ext
        Path(os.path.join(out_root, folder)).mkdir(parents=True, exist_ok=True)
        if ext == "UNK":
            name = f"extracted_frame_{idx}"
        else:
            name = f"extracted_frame_{idx}.{ext.lower()}"
        with open(os.path.join(out_root, folder, name), "wb") as f:
            f.write(decompressed)
        with lock:
            type_count[ext] = type_count.get(ext, 0) + 1
        color = YELLOW if ext == "UNK" else GREEN
        return f"{color}正在处理 [{idx:05d}/{total}] @ {start:08X} | {ext:<4} | {format_size(len(decompressed))}{RESET}"
    except:
        fail_dir = os.path.join(out_root, "FAIL")
        Path(fail_dir).mkdir(parents=True, exist_ok=True)
        with open(os.path.join(fail_dir, f"extracted_frame_{idx}.zst"), "wb") as f:
            f.write(mm[start:end])
        with open(err_path, "a", encoding="utf-8") as ef:
            ef.write(f"{start:08X}:\n")
            ef.write(traceback.format_exc())
            ef.write("--------------------------------------------------\n")
        return f"{RED}正在处理 [{idx:05d}/{total}] @ {start:08X} | ERR  | 解压失败{RESET}"

def extract_zstd_container(path, out_root):
    t0 = time.time()
    print("--------------------------------------------------")
    print("NPK File Unlocker v.1.4.3 Optimized by XQ")
    print("--------------------------------------------------")
    size = os.path.getsize(path)
    print(f"文件: {os.path.basename(path)}")
    print(f"大小: {format_size(size)}")
    print("正在扫描Zstd帧位置...")
    print("--------------------------------------------------")
    with open(path, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        magic = b"\x28\xb5\x2f\xfd"
        pos = 0
        positions = []
        while True:
            pos = mm.find(magic, pos)
            if pos == -1:
                break
            positions.append(pos)
            pos += 4
    total = len(positions)
    print(f"总共找到 {total} 个Zstd帧，开始解包...")
    print("--------------------------------------------------")
    err_path = os.path.join(out_root, "ERROR.txt")
    if os.path.exists(err_path):
        os.remove(err_path)
    hash_set = set()
    lock = Lock()
    type_count = {}
    t_scan = time.time() - t0
    t1 = time.time()
    try:
        if FAST_MODE:
            with ThreadPoolExecutor(max_workers=MAX_THREADS) as ex:
                futures = []
                for i in range(total):
                    start = positions[i]
                    end = positions[i+1] if i+1 < total else size
                    futures.append(ex.submit(extract_frame, mm, start, end, i+1, total, out_root, err_path, hash_set, lock, type_count))
                for f in as_completed(futures):
                    print(f.result(), flush=True)
        else:
            for i in range(total):
                start = positions[i]
                end = positions[i+1] if i+1 < total else size
                print(extract_frame(mm, start, end, i+1, total, out_root, err_path, hash_set, lock, type_count), flush=True)
    except KeyboardInterrupt:
        print("\n正在停止解包...")
    t_extract = time.time() - t1
    t_total = time.time() - t0
    print("--------------------------------------------------")
    print(f"提取完成! 共提取 {len(hash_set)} 个不重复文件\n")
    print("总体耗时:")
    print(f"扫描帧位置: {int(t_scan)} 秒")
    print(f"解压: {int(t_extract//60)} 分 {int(t_extract%60)} 秒")
    print(f"总耗时: {int(t_total//60)} 分 {int(t_total%60)} 秒")
    print("--------------------------------------------------")
    print("解包过程总览:")
    print(f"总共提取文件数: {len(hash_set)}")
    fail_count = len(os.listdir(os.path.join(out_root, 'FAIL'))) if os.path.exists(os.path.join(out_root, 'FAIL')) else 0
    print(f"处理失败文件数: {fail_count}")
    print("文件类型统计:")
    for k, v in type_count.items():
        print(f"{k}: {v}")
    print("--------------------------------------------------")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python NpkUnlocker1.4.3.py 输入文件 输出目录")
        sys.exit(1)
    inp = sys.argv[1]
    outp = sys.argv[2]
    Path(outp).mkdir(exist_ok=True)
    check_output_dir(outp)
    extract_zstd_container(inp, outp)
