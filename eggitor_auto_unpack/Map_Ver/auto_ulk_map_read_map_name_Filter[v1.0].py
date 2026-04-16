import C_file
import zstd
import os
import patch.ptutils as ptutils

# ===== 修改以下变量 =====
MAP_RAW = "E:/editor_unlocker/Documents/assets.ppk.map"   # 未解密的 map 文件路径
OUTPUT_DIR = "E:/editor_unlocker/extracted_str"          # 输出目录
FILTER_STRING = "s30"                                    # 只提取包含这个字符串的文件
# ===========================

def extract_from_map_str():
    print("加载 map 文件: " + MAP_RAW)
    data = ptutils.load_compressed_bin_file(MAP_RAW)
    
    if isinstance(data, bytes):
        content = data.decode('utf-8', errors='replace')
    else:
        content = data
    
    lines = content.split('\n')
    print("解析到 " + str(len(lines)) + " 行")

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    total = 0
    success = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        total += 1
        parts = line.split('\t')
        if not parts:
            continue
        
        file_path = parts[0].strip().replace('\\', '/')
        
        if FILTER_STRING not in file_path:
            continue
        
        out_path = os.path.join(OUTPUT_DIR, file_path)
        out_dir = os.path.dirname(out_path)
        
        if not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir)
            except:
                pass

        try:
            data = C_file.get_res_file(file_path, '')
            if data is None:
                continue
        except:
            continue

        try:
            data = zstd.decompress(data)
        except:
            pass

        try:
            with open(out_path, 'wb') as out:
                out.write(data)
            success += 1
            if success % 100 == 0:
                print("已提取: " + str(success))
        except:
            pass

    print("========== 完成 ==========")
    print("成功: " + str(success))

if __name__ == "__main__":
    extract_from_map_str()
