import C_file
import zstd
import os
import json
import patch.ptutils as ptutils

# ===== 修改以下变量 =====
FILE_LIST_RAW = "C:/Users/lfk90/Downloads/ext_packer_skin_voice_1_file_list"  # 未解密的 file_list 路径
OUTPUT_DIR = "E:/editor_unlocker/extracted_all"                               # 输出目录
# ===========================

def extract_from_file_list_raw():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("解密解压 file_list: " + FILE_LIST_RAW)
    data = ptutils.load_compressed_bin_file(FILE_LIST_RAW)
    entries = json.loads(data)
    total = len(entries)
    print("共 " + str(total) + " 个文件")

    success = 0
    for entry in entries:
        file_path = entry.get('file_name')
        if not file_path:
            continue

        file_path = file_path.replace('\\', '/')

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
                print("已提取: " + str(success) + " / " + str(total))
        except:
            pass

    print("========== 完成 ==========")
    print("成功: " + str(success) + " / " + str(total))

if __name__ == "__main__":
    extract_from_file_list_raw()