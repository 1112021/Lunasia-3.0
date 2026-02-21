# -*- coding: utf-8 -*-
"""
配置管理模块
处理应用程序的配置加载、保存和默认配置
"""

import json
import os

# 配置文件路径
CONFIG_FILE = "ai_agent_config.json"

def load_config():
    """加载配置"""
    default_config = {
        "openai_key": "",
        "deepseek_key": "",
        "qwen3vl_plus_key": "",  # Qwen3VL-Plus API密钥（用于图片分析）
        "dashscope_key": "",  # 阿里 DashScope API 密钥（用于语音识别 Paraformer 8k-v2）
        "voice_auto_send": False,  # 语音识别结束后是否自动发送消息
        "weather_key": "",
        "heweather_key": "",
        "amap_key": "",  # 用户需要在设置中配置自己的API密钥
        "weather_source": "高德地图API",
        "default_browser": "",  # 默认浏览器
        "default_search_engine": "baidu",  # 默认搜索引擎
        "selected_model": "deepseek-reasoner",
        "memory_summary_model": "deepseek-reasoner",  # 识底深湖总结使用的模型
        "max_tokens": 1000,  # AI最大token数，0表示无限制
        "window_transparency": 100,  # 窗口透明度，100表示完全不透明
        "show_remember_details": True,  # 是否显示"记住这个时刻"的详细信息
        "note_filename_format": "timestamp",  # 笔记文件名格式：timestamp(时间戳格式) 或 simple(简单格式)
        "max_memory_recall": 12,  # 智能回忆最大加载轮数（必须是3的倍数）
        # TTS设置
        "tts_enabled": False,  # 是否启用TTS
        "azure_tts_key": "",  # Azure TTS API密钥
        "azure_region": "eastasia",  # Azure区域
        "tts_voice": "zh-CN-XiaoxiaoNeural",  # TTS语音
        "tts_speaking_rate": 1.0,  # TTS语速
        "ai_fallback_enabled": True,  # 是否启用AI智能创建的后备机制（关键词识别）
        # 快捷键设置
        "send_key_sequence": "ctrl+enter",  # 发送消息快捷键（keyboard库格式，如 "ctrl+enter", "enter"）
        "show_window_key_sequence": "ctrl+shift+l",  # 窗口呼出快捷键（keyboard库格式）
        "voice_input_key_sequence": "",  # 语音输入快捷键（按住说话，松开结束；留空则禁用）
        "website_map": {
            "哔哩哔哩": "https://www.bilibili.com",
            "b站": "https://www.bilibili.com",
            "百度": "https://www.baidu.com",
            "谷歌": "https://www.google.com",
            "知乎": "https://www.zhihu.com",
            "github": "https://github.com",
            "youtube": "https://www.youtube.com"
        },
        "app_map": {},
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 向后兼容：如果配置中没有 send_key_sequence，从 send_key_mode 推断
                if "send_key_sequence" not in config and "send_key_mode" in config:
                    send_key_mode = config.get("send_key_mode", "Ctrl+Enter")
                    if send_key_mode == "Enter":
                        config["send_key_sequence"] = "enter"
                    else:
                        config["send_key_sequence"] = "ctrl+enter"
                # 向后兼容：如果配置中没有 show_window_key_sequence，使用默认值
                if "show_window_key_sequence" not in config:
                    config["show_window_key_sequence"] = "ctrl+shift+l"
                return config
        except:
            return default_config
    return default_config

def save_config(config):
    """保存配置"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
