#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络搜索工具 - 基于LangChain的DuckDuckGo搜索
"""

from typing import Optional, List, Dict
import time

try:
    from langchain_community.tools import DuckDuckGoSearchRun
    from langchain_community.tools import DuckDuckGoSearchResults
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("⚠️ LangChain未安装，将使用备用搜索方法")

class SearchTool:
    """网络搜索工具类"""
    
    def __init__(self):
        if LANGCHAIN_AVAILABLE:
            # 使用LangChain的DuckDuckGo搜索工具
            self.search_tool = DuckDuckGoSearchRun()
            self.search_results_tool = DuckDuckGoSearchResults(num_results=5)
        else:
            # 备用搜索方法
            self.search_tool = None
            self.search_results_tool = None
    
    def set_search_engine(self, engine: str):
        """设置搜索引擎"""
        self.current_engine = engine
    
    def search(self, query: str, max_results: int = 5, search_engine: str = "DuckDuckGo") -> str:
        """
        进行网络搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数量
            search_engine: 搜索引擎选择
            
        Returns:
            搜索结果文本
        """
        try:
            # 只支持DuckDuckGo搜索引擎
            return self._search_duckduckgo(query, max_results)
                
        except Exception as e:
            print(f"搜索出错: {e}")
            return self._get_intelligent_fallback(query)
    
    def _search_duckduckgo(self, query: str, max_results: int = 5) -> str:
        """
        使用DuckDuckGo进行搜索
        """
        try:
            # 首先尝试真正的网络搜索
            print(f"🔍 使用DuckDuckGo搜索: {query}")
            
            # 尝试真正的网络搜索
            network_result = self._fallback_search(query, max_results)
            if network_result and not network_result.startswith("搜索查询:") and len(network_result) > 100:
                # 如果获得了真正的网络搜索结果
                print(f"✅ 获得真正的网络搜索结果，长度: {len(network_result)}")
                return network_result
            else:
                print(f"⚠️ 网络搜索结果不理想，长度: {len(network_result) if network_result else 0}")
            
            # 如果备用搜索失败，尝试LangChain搜索
            if LANGCHAIN_AVAILABLE and self.search_tool:
                print(f"🔍 尝试LangChain DuckDuckGo搜索: {query}")
                
                # 首先尝试使用搜索结果工具获取结构化结果
                try:
                    results = self.search_results_tool.run(query)
                    if results and len(results) > 0:
                        # 处理结构化结果
                        formatted_results = []
                        for i, result in enumerate(results[:max_results], 1):
                            if isinstance(result, dict):
                                title = result.get('title', '')
                                snippet = result.get('body', '')
                                link = result.get('href', '')
                                formatted_results.append(f"{i}. {title}\n   {snippet}\n   链接: {link}")
                            else:
                                formatted_results.append(f"{i}. {result}")
                        
                        if formatted_results:
                            search_result = "\n\n".join(formatted_results)
                            # 添加来源信息
                            source_info = f"\n\n信息来源: DuckDuckGo搜索 (https://duckduckgo.com/?q={query.replace(' ', '+')})"
                            return f"搜索查询: {query}\n\n搜索结果:\n{search_result}{source_info}"
                except Exception as e:
                    print(f"LangChain结构化搜索失败: {e}")
                
                # 如果结构化搜索失败，使用简单搜索
                try:
                    result = self.search_tool.run(query)
                    if result and len(result) > 50:
                        # 添加来源信息
                        source_info = f"\n\n信息来源: DuckDuckGo搜索 (https://duckduckgo.com/?q={query.replace(' ', '+')})"
                        return f"搜索查询: {query}\n\n搜索结果:\n{result}{source_info}"
                except Exception as e:
                    print(f"LangChain简单搜索也失败: {e}")
            
            # 如果所有搜索都失败，返回搜索失败信息
            if network_result:
                print(f"⚠️ 使用网络搜索结果（可能不完整），长度: {len(network_result)}")
                return network_result
            else:
                print("⚠️ 所有搜索方法都失败")
                return f"搜索查询: {query}\n\n搜索服务暂时不可用，请稍后重试。"
                
        except Exception as e:
            print(f"搜索出错: {e}")
            return f"搜索查询: {query}\n\n搜索失败: {str(e)}"
    
    def _fallback_search(self, query: str, max_results: int) -> str:
        """
        备用搜索方法 - 使用多个搜索源
        """
        try:
            import requests
            
            # 首先测试网络连接
            try:
                test_response = requests.get("https://www.baidu.com", timeout=5)
                if test_response.status_code != 200:
                    print("⚠️ 网络连接测试失败")
                    return f"搜索查询: {query}\n\n网络连接不可用，请检查网络设置。"
            except Exception as e:
                print(f"⚠️ 网络连接测试失败: {e}")
                return f"搜索查询: {query}\n\n网络连接不可用，请检查网络设置。"
            
            # 尝试多个搜索源
            search_sources = [
                {
                    'name': 'DuckDuckGo API',
                    'url': 'https://api.duckduckgo.com/',
                    'params': {
                        'q': query,
                        'format': 'json',
                        'no_html': '1',
                        'skip_disambig': '1'
                    }
                }
            ]
            
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache'
            })
            
            # 设置连接池和超时
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            for source in search_sources:
                try:
                    print(f"🔍 尝试搜索源: {source['name']}")
                    print(f"🔍 搜索URL: {source['url']}")
                    print(f"🔍 搜索参数: {source['params']}")
                    # 直接尝试搜索，不重试
                    try:
                        response = session.get(source['url'], params=source['params'], timeout=8)  # 减少超时时间
                        response.raise_for_status()
                        print(f"✅ 搜索请求成功，状态码: {response.status_code}")
                        
                        # 处理DuckDuckGo API响应
                        data = response.json()
                        results = []
                        
                        # 添加摘要信息
                        if data.get('Abstract'):
                            results.append(f"摘要: {data['Abstract']}")
                        
                        # 添加定义信息
                        if data.get('Definition'):
                            results.append(f"定义: {data['Definition']}")
                        
                        # 添加相关主题
                        if data.get('RelatedTopics'):
                            for topic in data['RelatedTopics'][:max_results]:
                                if isinstance(topic, dict) and topic.get('Text'):
                                    results.append(f"相关: {topic['Text']}")
                                elif isinstance(topic, str):
                                    results.append(f"相关: {topic}")
                        
                        # 添加答案
                        if data.get('Answer'):
                            results.append(f"答案: {data['Answer']}")
                        
                        # 如果找到结果，返回
                        if results:
                            search_result = "\n\n".join(results)
                            source_info = f"\n\n信息来源: DuckDuckGo搜索 (https://duckduckgo.com/?q={query.replace(' ', '+')})"
                            print(f"✅ 找到 {len(results)} 个搜索结果")
                            print(f"📊 搜索结果长度: {len(search_result)}")
                            return f"搜索查询: {query}\n\n搜索结果:\n{search_result}{source_info}"
                        else:
                            print("⚠️ 搜索源返回空结果")
                            
                    except Exception as e:
                        print(f"搜索源 {source['name']} 请求失败: {e}")
                        continue
                        
                except Exception as e:
                    print(f"搜索源 {source['name']} 失败: {e}")
                    continue
            
            # 如果所有搜索源都失败，返回搜索失败信息
            print("⚠️ 所有网络搜索源都失败")
            return f"搜索查询: {query}\n\n搜索服务暂时不可用，请稍后重试。"
                
        except Exception as e:
            print(f"备用搜索完全失败: {e}")
            return f"搜索查询: {query}\n\n搜索失败: {str(e)}"
    

# 创建全局搜索工具实例
search_tool = SearchTool()

def search_web(query: str, max_results: int = 5, search_engine: str = "DuckDuckGo") -> str:
    """
    网络搜索函数 - 供外部调用
    
    Args:
        query: 搜索查询
        max_results: 最大结果数量
        search_engine: 搜索引擎选择
        
    Returns:
        搜索结果文本
    """
    return search_tool.search(query, max_results, search_engine)

if __name__ == "__main__":
    # 测试搜索功能
    test_query = "Python编程教程"
    result = search_web(test_query)
    print("搜索结果:")
    print(result)
