#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索查询提取Agent
负责从用户输入中提取合适的搜索关键词
"""

import re
import json
from typing import Optional
import openai

class SearchQueryExtractor:
    """搜索查询提取器"""
    
    def __init__(self, config=None):
        self.config = config or {}
        # 需要移除的常见词汇
        self.remove_words = [
            "介绍一下", "介绍", "帮我", "帮我介绍", "请介绍", "请帮我",
            "告诉我", "我想知道", "我想了解", "请问", "能否", "可以",
            "怎么样", "如何", "什么", "为什么", "怎么", "怎样",
            "的", "了", "吗", "呢", "吧", "啊", "呀", "哦"
        ]
        
        # 搜索意图关键词
        self.search_intent_keywords = [
            "介绍", "了解", "知道", "查询", "搜索", "查找", "找",
            "是什么", "怎么样", "如何", "怎么", "为什么", "什么是",
            "最新", "新闻", "资讯", "信息", "详细", "具体", "情况"
        ]
    
    def extract_search_query(self, user_input: str) -> Optional[str]:
        """
        从用户输入中提取搜索查询
        
        Args:
            user_input: 用户输入
            
        Returns:
            提取的搜索查询，如果无法提取则返回None
        """
        if not user_input or not user_input.strip():
            return None
        
        # 清理输入
        query = user_input.strip()
        
        # 检查是否包含搜索意图
        if not self._has_search_intent(query):
            return None
        
        # 优先使用AI智能提取
        if self.config.get("use_ai_query_extraction", False):
            try:
                ai_extracted = self._ai_extract_keywords(query)
                if ai_extracted and self._is_valid_query(ai_extracted):
                    print(f"✅ AI提取搜索查询: {ai_extracted}")
                    return ai_extracted
            except Exception as e:
                print(f"⚠️ AI提取失败，使用规则提取: {e}")
        
        # 回退到规则提取
        extracted_query = self._extract_core_keywords(query)
        
        # 验证提取结果
        if self._is_valid_query(extracted_query):
            print(f"📝 规则提取搜索查询: {extracted_query}")
            return extracted_query
        
        return None
    
    def _has_search_intent(self, text: str) -> bool:
        """检查是否包含搜索意图"""
        text_lower = text.lower()
        
        # 检查搜索意图关键词
        for keyword in self.search_intent_keywords:
            if keyword in text_lower:
                return True
        
        # 检查问号
        if "?" in text or "？" in text:
            return True
        
        # 检查疑问词
        question_words = ["什么", "怎么", "如何", "为什么", "哪里", "哪个", "谁", "何时"]
        for word in question_words:
            if word in text:
                return True
        
        return False
    
    def _extract_core_keywords(self, text: str) -> str:
        """提取核心关键词"""
        # 移除常见的无意义词汇
        cleaned_text = text
        
        # 按优先级移除词汇
        for word in self.remove_words:
            # 使用正则表达式确保完整匹配
            pattern = r'\b' + re.escape(word) + r'\b'
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
        
        # 清理多余的空格和标点
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        cleaned_text = re.sub(r'^[，。！？,\.!?]+|[，。！？,\.!?]+$', '', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        return cleaned_text
    
    def _ai_extract_keywords(self, user_input: str) -> Optional[str]:
        """使用AI提取搜索关键词"""
        try:
            # 获取API配置
            ai_model = self.config.get("ai_query_extraction_model", "deepseek-chat")
            
            # 根据模型选择API密钥
            if "deepseek" in ai_model:
                api_key = self.config.get("deepseek_key", "")
            else:
                api_key = self.config.get("openai_key", "")
            
            if not api_key:
                print("⚠️ 未配置API密钥，无法使用AI提取")
                return None
            
            # 构建AI提示词
            system_prompt = """你是一个专业的搜索查询提取助手。你的任务是从用户的自然语言输入中提取出最适合网络搜索的关键词。

规则：
1. 移除礼貌用语、语气词、无意义的连接词
2. 保留核心的搜索关键词
3. 保持关键词的完整性和准确性
4. 如果输入不是搜索请求，返回"NOT_SEARCH"
5. 只返回提取的关键词，不要添加任何解释

示例：
输入："介绍一下2025年的93阅兵"
输出："2025年的93阅兵"

输入："帮我查询今天的天气"
输出："今天天气"

输入："打开百度"
输出："NOT_SEARCH"

输入："什么是机器学习"
输出："机器学习" """

            user_prompt = f"请从以下用户输入中提取搜索关键词：\n{user_input}"
            
            # 调用AI模型
            if "deepseek" in ai_model:
                client = openai.OpenAI(
                    api_key=api_key,
                    base_url="https://api.deepseek.com/v1"
                )
            else:
                client = openai.OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model=ai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            extracted = response.choices[0].message.content.strip()
            
            # 检查是否是无效搜索
            if extracted == "NOT_SEARCH" or not extracted:
                return None
            
            return extracted
            
        except Exception as e:
            print(f"⚠️ AI提取关键词失败: {e}")
            return None
    
    def _is_valid_query(self, query: str) -> bool:
        """验证查询是否有效"""
        if not query or len(query.strip()) < 2:
            return False
        
        # 检查是否只包含标点符号
        if re.match(r'^[，。！？,\.!?\s]+$', query):
            return False
        
        # 检查是否包含实际内容
        if len(query.strip()) < 3:
            return False
        
        return True

# 全局实例（延迟初始化）
_search_query_extractor = None

def extract_search_query(user_input: str, config: dict = None) -> Optional[str]:
    """
    提取搜索查询的全局函数
    
    Args:
        user_input: 用户输入
        config: 配置字典
        
    Returns:
        提取的搜索查询
    """
    global _search_query_extractor
    
    # 如果配置发生变化，重新创建实例
    if _search_query_extractor is None or config is not None:
        _search_query_extractor = SearchQueryExtractor(config or {})
    
    return _search_query_extractor.extract_search_query(user_input)

if __name__ == "__main__":
    # 测试搜索查询提取
    test_cases = [
        "介绍一下2025年的93阅兵",
        "帮我查询今天的天气",
        "我想了解AI的最新发展",
        "什么是机器学习",
        "如何学习Python编程",
        "打开百度",
        "创建文件",
        "计算1+1"
    ]
    
    print("🔍 测试搜索查询提取...")
    for test_input in test_cases:
        extracted = extract_search_query(test_input)
        print(f"输入: {test_input}")
        print(f"提取: {extracted}")
        print("-" * 50)
