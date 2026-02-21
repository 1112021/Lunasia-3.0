# -*- coding: utf-8 -*-
"""
异步资源管理器
用于正确清理所有异步资源，避免退出时的警告信息
"""

import asyncio
import warnings
from typing import List, Optional


class AsyncResourceManager:
    """异步资源管理器 - 统一管理所有异步资源的生命周期"""
    
    def __init__(self):
        self.resources: List = []
        self.event_loops: List[asyncio.AbstractEventLoop] = []
        self._cleanup_in_progress = False
        
        # 抑制资源警告
        warnings.filterwarnings("ignore", category=ResourceWarning)
        warnings.filterwarnings("ignore", message=".*unclosed.*")
    
    def register_resource(self, resource):
        """注册需要清理的资源"""
        if resource not in self.resources:
            self.resources.append(resource)
    
    def register_event_loop(self, loop: asyncio.AbstractEventLoop):
        """注册事件循环"""
        if loop not in self.event_loops:
            self.event_loops.append(loop)
    
    def cleanup_all(self):
        """清理所有资源"""
        if self._cleanup_in_progress:
            return
        
        self._cleanup_in_progress = True
        
        try:
            # 不打印开始信息，保持静默
            
            # 1. 清理所有注册的资源
            for resource in self.resources:
                try:
                    if hasattr(resource, 'close_sync') and callable(resource.close_sync):
                        # 优先使用同步关闭方法
                        resource.close_sync()
                    elif hasattr(resource, 'close') and callable(resource.close):
                        if asyncio.iscoroutinefunction(resource.close):
                            # 异步close方法
                            try:
                                # 尝试获取运行中的事件循环
                                try:
                                    loop = asyncio.get_running_loop()
                                except RuntimeError:
                                    loop = None
                                
                                if loop and not loop.is_closed():
                                    # 在运行中的循环创建任务
                                    asyncio.create_task(resource.close())
                                else:
                                    # 创建新循环执行清理
                                    new_loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(new_loop)
                                    try:
                                        new_loop.run_until_complete(resource.close())
                                    finally:
                                        new_loop.close()
                            except:
                                pass
                        else:
                            # 同步close方法
                            resource.close()
                except Exception:
                    # 静默处理清理错误
                    pass
            
            # 2. 清理所有事件循环
            for loop in self.event_loops:
                try:
                    if loop and not loop.is_closed():
                        # 取消所有待处理的任务
                        self._cancel_all_tasks(loop)
                        
                        # 给予短暂时间让任务完成清理
                        try:
                            loop.run_until_complete(asyncio.sleep(0.05))
                        except:
                            pass
                        
                        # 关闭事件循环
                        loop.close()
                except Exception:
                    # 静默处理
                    pass
            
            # 静默完成，不打印
            
        except Exception:
            # 静默处理任何清理错误
            pass
        finally:
            self._cleanup_in_progress = False
    
    def _cancel_all_tasks(self, loop: asyncio.AbstractEventLoop):
        """取消事件循环中的所有任务"""
        try:
            # 获取所有待处理的任务
            if hasattr(asyncio, 'all_tasks'):
                pending = asyncio.all_tasks(loop)
            else:
                pending = asyncio.Task.all_tasks(loop)
            
            # 取消所有任务
            for task in pending:
                try:
                    task.cancel()
                except:
                    pass
            
            # 等待所有任务完成取消
            if pending:
                try:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except:
                    pass
                    
        except Exception as e:
            # 静默处理
            pass
    
    def __del__(self):
        """析构时确保清理"""
        if not self._cleanup_in_progress:
            self.cleanup_all()


# 全局资源管理器实例
_global_resource_manager: Optional[AsyncResourceManager] = None


def get_resource_manager() -> AsyncResourceManager:
    """获取全局资源管理器"""
    global _global_resource_manager
    if _global_resource_manager is None:
        _global_resource_manager = AsyncResourceManager()
    return _global_resource_manager


def cleanup_on_exit():
    """程序退出时的清理函数"""
    global _global_resource_manager
    if _global_resource_manager:
        _global_resource_manager.cleanup_all()
        _global_resource_manager = None

