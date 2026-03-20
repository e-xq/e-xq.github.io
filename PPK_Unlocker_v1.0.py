import os
import sys
import zstandard as zstd
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil

MAX_THREADS = 3
MAX_BLOCK_SIZE = 20 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

DEFAULT_OUTPUT_DIR = None

FILE_CATEGORY_MAP = {
    ".wem": "音频文件",
    ".bnk": "音频文件",
    ".png": "图片纹理",
    ".dds": "图片纹理",
    ".ktx": "图片纹理",
    ".tga": "图片纹理",
    ".mesh": "模型文件",
    ".npk": "数据包文件",
    ".zst": "压缩文件",
    "": "未知文件"
}

TGA_TAIL_MAGIC = b'TRUEVISION-XFILE.\x00'

def detect_file_extension(data):
    if not data:
        return ""
    
    MESH_MAGIC = b'\x34\x80\xc8\xbb'
    if len(data) >= 4 and data[:4] == MESH_MAGIC:
        return ".mesh"
    
    PNG_MAGIC = b'\x89PNG'
    if len(data) >= 4 and data[:4] == PNG_MAGIC:
        return ".png"
    
    KTX_MAGIC = b'\xABKTX 11\xBB'
    if len(data) >= 8 and data[:8] == KTX_MAGIC:
        return ".ktx"
    
    if len(data) >= 3 and data[:3] == b'DDS':
        return ".dds"
    
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        return ".wem"
    
    if len(data) >= 4 and data[:4] == b'BKHD':
        return ".bnk"
    
    if len(data) >= 4 and data[:4] == b'AKPK':
        return ".npk"
    
    if len(data) >= 4 and data[:4] == b'\x28\xb5\x2f\xfd':
        return ".zst"
    
    if len(data) >= len(TGA_TAIL_MAGIC):
        if data[-len(TGA_TAIL_MAGIC):] == TGA_TAIL_MAGIC:
            return ".tga"
    
    return ""

DUPLICATE_MD5 = set()

def process_ppk_file(file_path, output_root):
    file_name = Path(file_path).name
    processed_blocks = 0
    extracted_blocks = 0
    
    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
        
        ZSTD_MAGIC = b"\x28\xB5\x2F\xFD"
        offset = 0
        block_idx = 0
        
        while offset < len(file_data):
            magic_pos = file_data.find(ZSTD_MAGIC, offset)
            if magic_pos == -1:
                break
            
            next_magic_pos = file_data.find(ZSTD_MAGIC, magic_pos + 4)
            block_end = min(
                next_magic_pos if next_magic_pos != -1 else len(file_data),
                magic_pos + MAX_BLOCK_SIZE
            )
            
            zstd_data = file_data[magic_pos:block_end]
            processed_blocks += 1
            
            if len(zstd_data) < 1024:
                offset = block_end
                continue
            
            block_md5 = hashlib.md5(zstd_data).hexdigest()
            if block_md5 in DUPLICATE_MD5:
                offset = block_end
                continue
            DUPLICATE_MD5.add(block_md5)
            
            try:
                dctx = zstd.ZstdDecompressor()
                decompressed = dctx.decompress(zstd_data)
            except Exception as e:
                offset = block_end
                continue
            
            file_ext = detect_file_extension(decompressed)
            category = FILE_CATEGORY_MAP.get(file_ext, "未知文件")
            
            category_dir = output_root / category
            category_dir.mkdir(exist_ok=True, parents=True)
            
            save_name = f"{file_name}_block{block_idx}{file_ext}"
            save_path = category_dir / save_name
            
            with open(save_path, "wb") as f:
                f.write(decompressed)
            
            extracted_blocks += 1
            block_idx += 1
            offset = block_end
        
        return {
            "file": file_name,
            "processed": processed_blocks,
            "extracted": extracted_blocks,
            "status": "success"
        }
    
    except Exception as e:
        return {
            "file": file_name,
            "error": str(e)[:100],
            "status": "failed"
        }

def main():
    def print_help():
        print("="*60)
        print("PPK文件解析工具 - 支持自定义输出目录")
        print("="*60)
        print("用法1（使用默认输出路径）：")
        print("  python 脚本.py <PPK文件所在目录>")
        print("  示例：python ppk_extract.py D:/ppk_files")
        print("  输出路径：PPK目录/Output")
        print("\n用法2（自定义输出路径）：")
        print("  python 脚本.py <PPK文件所在目录> <自定义输出目录>")
        print("  示例：python ppk_extract.py D:/ppk_files E:/ppk_output")
        print("="*60)
    
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print_help()
        sys.exit(1)
    
    ppk_dir = Path(sys.argv[1])
    if not ppk_dir.exists() or not ppk_dir.is_dir():
        print(f"❌ 错误：目录 {ppk_dir} 不存在或不是有效目录")
        sys.exit(1)
    
    if len(sys.argv) == 3:
        output_root = Path(sys.argv[2])
    elif DEFAULT_OUTPUT_DIR is not None:
        output_root = Path(DEFAULT_OUTPUT_DIR)
    else:
        output_root = ppk_dir / "Output"
    
    output_root.mkdir(parents=True, exist_ok=True)
    print(f"📂 输出目录已确定：{output_root.absolute()}")
    
    ppk_files = []
    for file in ppk_dir.iterdir():
        if file.is_file():
            ppk_files.append(file)
    
    if not ppk_files:
        print(f"⚠️ 在目录 {ppk_dir} 中未找到任何文件")
        sys.exit(0)
    
    print(f"🚀 找到 {len(ppk_files)} 个文件，使用 {MAX_THREADS} 线程处理...")
    results = []
    
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_file = {
            executor.submit(process_ppk_file, str(file), output_root): file 
            for file in ppk_files
        }
        
        for future in as_completed(future_to_file):
            file = future_to_file[future]
            try:
                result = future.result()
                results.append(result)
                if result["status"] == "success":
                    print(f"✅ {result['file']} - 处理块数：{result['processed']} - 提取块数：{result['extracted']}")
                else:
                    print(f"❌ {result['file']} - 错误：{result['error']}")
            except Exception as e:
                print(f"❌ {file.name} - 任务异常：{str(e)[:100]}")
    
    total_processed = 0
    total_extracted = 0
    failed_files = 0
    
    for res in results:
        if res["status"] == "success":
            total_processed += res["processed"]
            total_extracted += res["extracted"]
        else:
            failed_files += 1
    
    print("\n" + "="*60)
    print("📊 处理完成统计：")
    print(f"   📁 总文件数：{len(ppk_files)}")
    print(f"   ❌ 处理失败文件数：{failed_files}")
    print(f"   🔍 总扫描Zstd块数：{total_processed}")
    print(f"   ✅ 去重后提取块数：{total_extracted}")
    print(f"   📂 最终输出目录：{output_root.absolute()}")
    print("="*60)

if __name__ == "__main__":
    try:
        import zstandard
    except ImportError:
        print("📦 正在安装依赖包 zstandard...")
        os.system("pip install zstandard -q")
        import zstandard
    
    main()