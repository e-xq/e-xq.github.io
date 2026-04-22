import json
import os
import re
import shutil
import subprocess
from pathlib import Path

# ========== 配置 ==========
JSON_PATH = 'E:/bgm_full.json'
SOURCE_DIR = Path('F:/extracted_all/wwise')
OUTPUT_DIR = Path('F:/extracted_all/rename_audio')
WWISER_PATH = r'C:\Users\lfk90\Downloads\wwiser.pyz'
XML_CACHE_DIR = Path('F:/extracted_all/xml_cache')
PROCESSED_LOG = OUTPUT_DIR / 'processed.txt'  # 记录已处理的原始文件名

# ========== 清理非法字符 ==========
def clean_filename(name):
    illegal_chars = r'[\\/:*?"<>|\n\r\t]'
    name = re.sub(illegal_chars, '_', name)
    name = name.strip(' .')
    return name

# ========== 提取文件名中的序号 ==========
def extract_suffix(filename):
    stem = filename.replace('.bnk', '')
    match = re.search(r'_(\d+)$', stem)
    if match:
        return '_' + match.group(1)
    match = re.search(r'(\d+)$', stem)
    if match:
        return '_' + match.group(1)
    return ''

# ========== 加载已处理记录 ==========
def load_processed():
    if PROCESSED_LOG.exists():
        with open(PROCESSED_LOG, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed(processed_set):
    with open(PROCESSED_LOG, 'w', encoding='utf-8') as f:
        for name in sorted(processed_set):
            f.write(name + '\n')

# ========== 加载 JSON ==========
print('加载 JSON...')
with open(JSON_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

bank_to_info = {}
for key, value in data.items():
    bank_path = value.get('bank', '')
    chinese_name = value.get('name', '')
    if bank_path and chinese_name:
        bank_filename = Path(bank_path).name
        safe_name = clean_filename(chinese_name)
        bank_to_info[bank_filename] = (key, safe_name)

print(f'加载 {len(bank_to_info)} 条 JSON 映射')

# ========== 扫描源目录所有 BNK ==========
print('\n扫描源目录...')
all_bnks = {}
for root, dirs, files in os.walk(SOURCE_DIR):
    for file in files:
        if file.endswith('.bnk') and '_md' not in file.lower():
            all_bnks[file] = Path(root) / file

print(f'找到 {len(all_bnks)} 个 BNK 文件')

# ========== 加载已处理记录 ==========
processed_files = load_processed()
print(f'已处理 {len(processed_files)} 个文件')

# ========== 筛选新文件 ==========
new_bnks = {}
for filename, path in all_bnks.items():
    if filename not in processed_files:
        new_bnks[filename] = path

print(f'新文件: {len(new_bnks)} 个')

if len(new_bnks) == 0:
    print('\n没有新文件需要处理！')
    exit()

# ========== 创建目录 ==========
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
XML_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ========== 第一步：复制并重命名 BNK（只处理新文件）==========
print('\n第一步：复制并重命名 BNK（新文件）...')

bnk_copied = 0
index_bnks = []
total_new = len(new_bnks)
processed = 0

for bnk_filename, src_path in new_bnks.items():
    if bnk_filename not in bank_to_info:
        continue
    
    key, base_name = bank_to_info[bnk_filename]
    suffix = extract_suffix(bnk_filename)
    new_name = f'[{key}]{base_name}{suffix}.bnk'
    dst_path = OUTPUT_DIR / new_name
    
    shutil.copy2(src_path, dst_path)
    bnk_copied += 1
    processed_files.add(bnk_filename)  # 标记为已处理
    
    # 检查是否是索引 BNK
    try:
        with open(src_path, 'rb') as f:
            content = f.read(1024 * 1024)
            if b'RIFF' not in content:
                index_bnks.append((dst_path, new_name.replace('.bnk', ''), bnk_filename))
    except:
        pass
    
    processed += 1
    if processed % 50 == 0:
        print(f'  复制进度: {processed}/{total_new}')

print(f'复制了 {bnk_copied} 个新 BNK，其中 {len(index_bnks)} 个是索引 BNK')

# 保存已处理记录
save_processed(processed_files)

# ========== 第二步：解析索引 BNK（使用缓存）==========
print('\n第二步：解析索引 BNK，获取 WEM ID...')

def get_xml_for_bnk(bnk_filename, bnk_path):
    cache_xml = XML_CACHE_DIR / f'{bnk_filename}.xml'
    
    if cache_xml.exists():
        content = cache_xml.read_text(encoding='utf-8', errors='ignore')
        return content
    
    default_xml = bnk_path.with_suffix('.bnk.xml')
    
    if default_xml.exists():
        shutil.copy2(str(default_xml), str(cache_xml))
        content = cache_xml.read_text(encoding='utf-8', errors='ignore')
        return content
    
    print(f'    正在生成 XML: {bnk_filename}')
    subprocess.run(
        ['python', WWISER_PATH, str(bnk_path)],
        cwd=str(bnk_path.parent),
        capture_output=True,
        timeout=30
    )
    
    if default_xml.exists():
        shutil.move(str(default_xml), str(cache_xml))
        content = cache_xml.read_text(encoding='utf-8', errors='ignore')
        return content
    
    return None

bnk_to_wem_ids = {}
total_index = len(index_bnks)

for i, (bnk_path, bnk_name, original_filename) in enumerate(index_bnks):
    xml_content = get_xml_for_bnk(original_filename, bnk_path)
    if xml_content:
        wem_ids = re.findall(r'<fld ty="tid" na="sourceID" va="(\d+)"', xml_content)
        if wem_ids:
            bnk_to_wem_ids[bnk_name] = (bnk_path, wem_ids)
    
    if (i + 1) % 10 == 0 or (i + 1) == total_index:
        print(f'  解析进度: {i+1}/{total_index}')

print(f'解析完成，{len(bnk_to_wem_ids)} 个索引 BNK 包含 WEM ID')

# ========== 第三步：扫描 WEM 文件 ==========
print('\n第三步：扫描 WEM 文件...')
wem_map = {}
wem_count = 0
for root, dirs, files in os.walk(SOURCE_DIR):
    for file in files:
        if file.endswith('.wem'):
            nums = re.findall(r'\d+', file)
            if nums:
                wem_map[nums[-1]] = Path(root) / file
            wem_count += 1
            if wem_count % 200 == 0:
                print(f'  扫描进度: {wem_count} 个 WEM')

print(f'找到 {len(wem_map)} 个 .wem 文件')

# ========== 第四步：复制并重命名 WEM ==========
print('\n第四步：复制并重命名 WEM 文件...')
wem_copied = 0
total_wem_tasks = sum(len(ids) for _, ids in bnk_to_wem_ids.values())
processed_wem = 0

for bnk_name, (bnk_path, wem_ids) in bnk_to_wem_ids.items():
    for wem_id in wem_ids:
        if wem_id in wem_map:
            src = wem_map[wem_id]
            dst = OUTPUT_DIR / f'{bnk_name}.wem'
            if not dst.exists():  # 跳过已存在的
                try:
                    shutil.copy2(src, dst)
                    wem_copied += 1
                except Exception as e:
                    print(f'  复制失败: {src.name} -> {e}')
        
        processed_wem += 1
        if processed_wem % 100 == 0:
            print(f'  WEM进度: {processed_wem}/{total_wem_tasks}')

print(f'复制了 {wem_copied} 个新 WEM 文件')

# ========== 第五步：删除索引 BNK ==========
print('\n第五步：删除索引 BNK...')
deleted = 0
total_to_delete = len(bnk_to_wem_ids)

for i, (bnk_name, (bnk_path, _)) in enumerate(bnk_to_wem_ids.items()):
    try:
        bnk_path.unlink()
        deleted += 1
    except Exception as e:
        print(f'  删除失败: {bnk_name}.bnk -> {e}')
    
    if (i + 1) % 50 == 0:
        print(f'  删除进度: {i+1}/{total_to_delete}')

print(f'删除了 {deleted} 个索引 BNK')

# ========== 统计 ==========
remaining_bnks = list(OUTPUT_DIR.glob('*.bnk'))
remaining_wems = list(OUTPUT_DIR.glob('*.wem'))

print('\n' + '=' * 60)
print(f'完成！')
print(f'  本次新增 BNK: {bnk_copied} 个')
print(f'  本次新增 WEM: {wem_copied} 个')
print(f'  输出目录总计: {len(remaining_bnks)} 个 BNK, {len(remaining_wems)} 个 WEM')
print(f'  已处理记录: {PROCESSED_LOG}')
print('=' * 60)