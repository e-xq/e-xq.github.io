import C_file
import zstd
import os

# ===== 修改以下变量 =====
MAP_FILE = "E:/editor_unlocker/assets_raw.txt"     # 解出来的 map 文本文件路径
OUTPUT_DIR = "E:/editor_unlocker/extracted_all"     # 输出目录
# ===========================

def extract_from_map_full():
    if not os.path.exists(MAP_FILE):
        print("错误：找不到 map 文件: " + MAP_FILE)
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    total = 0
    success = 0
    failed = 0

    with open(MAP_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            total += 1

            # 提取文件路径（第一个字段，按 tab 分割）
            parts = line.split('\t')
            if not parts:
                continue
            file_path = parts[0].strip().replace('\\', '/')

            # 构建输出路径
            out_path = os.path.join(OUTPUT_DIR, file_path)
            out_dir = os.path.dirname(out_path)
            if not os.path.exists(out_dir):
                try:
                    os.makedirs(out_dir)
                except:
                    pass

            # 从引擎读取文件
            try:
                data = C_file.get_res_file(file_path, '')
                if data is None:
                    failed += 1
                    continue
            except:
                failed += 1
                continue

            # 尝试 zstd 解压
            try:
                data = zstd.decompress(data)
            except:
                pass

            # 写入文件
            try:
                with open(out_path, 'wb') as out:
                    out.write(data)
                success += 1
                if success % 100 == 0:
                    print("已提取: " + str(success) + " / " + str(total))
            except:
                failed += 1

    print("========== 完成 ==========")
    print