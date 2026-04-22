# BNK-WEM-Renamer

BNK/WEM 批量重命名脚本，根据音频配置表将原始文件名重命名为中文。

## 功能

- 根据 JSON 配置表将 `bgm_s30_lobby_03.bnk` 重命名为 `[13103]S30主城BGM2.bnk`
- 自动识别索引 BNK，调用 wwiser 解析 WEM ID 并重命名对应 WEM 文件
- 自动删除索引 BNK，仅保留内嵌 BNK 和有效 WEM
- 支持增量更新，记录已处理文件，游戏更新后仅处理新增内容
- XML 缓存机制，避免重复解析

## 使用方法

1. 从游戏导出音频配置表 `bgm_full.json`
2. 将提取的 BNK 文件放入 `wwise` 目录
3. 修改脚本开头的路径配置：
   - `JSON_PATH`：配置表路径
   - `SOURCE_DIR`：BNK 源目录
   - `OUTPUT_DIR`：输出目录
   - `WWISER_PATH`：wwiser.pyz 路径
4. 运行 `python rename_audio.py`

## 依赖

- Python 3.x
- wwiser.pyz

## 说明

仅供学习交流，请勿用于商业用途。
