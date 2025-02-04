# encoding:utf-8

from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ContextType(Enum):
    TEXT = 1  # 文本消息
    VOICE = 2  # 音频消息
    IMAGE = 3  # 图片消息
    FILE = 4  # 文件信息
    VIDEO = 5  # 视频信息
    SHARING = 6  # 分享信息

    IMAGE_CREATE = 10  # 创建图片命令
    ACCEPT_FRIEND = 19 # 同意好友请求
    JOIN_GROUP = 20  # 加入群聊
    PATPAT = 21  # 拍了拍
    FUNCTION = 22  # 函数调用
    EXIT_GROUP = 23 #退出

    NON_USER_MSG = 30  # 来自公众号、腾讯游戏、微信团队等非用户账号的消息
    STATUS_SYNC  = 51   # 微信客户端的状态同步消息，可以忽略 eggs: 打开/退出某个聊天窗口


    def __str__(self):
        return self.name


class Context(dict):
    """
    上下文信息，具有 dict 的所有特性
    """
    _last_image_context = None

    def __init__(self, type: ContextType = None, content=None, **kwargs):
        """初始化上下文
        
        Args:
            type (ContextType, optional): 消息类型. Defaults to None.
            content (Any, optional): 消息内容. Defaults to None.
            **kwargs: 其他参数
        """
        super().__init__()
        super().__setitem__('type', type or ContextType.TEXT)
        super().__setitem__('content', content)
        self.update(kwargs)
        
        # 如果是图片类型，更新最后的图片上下文
        if super().__getitem__('type') == ContextType.IMAGE:
            logger.info(f"[Context] 更新图片上下文，路径：{super().__getitem__('content')}")
            Context._last_image_context = self
            logger.debug("[Context] 图片上下文更新完成")

    def get_last_image(self):
        """获取最近的图片上下文"""
        if Context._last_image_context and super(Context._last_image_context, dict).__getitem__('type') == ContextType.IMAGE:
            return Context._last_image_context
        return None

    def __getattr__(self, name):
        """支持通过属性访问字典值
        
        Args:
            name (str): 属性名
            
        Returns:
            Any: 属性值
        """
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'Context' object has no attribute '{name}'")

    def __str__(self):
        return f"Context(type={super().__getitem__('type')}, content={super().__getitem__('content')}, kwargs={dict(self)})"

    def __contains__(self, key):
        if key == "type":
            return super().__contains__('type')
        elif key == "content":
            return super().__contains__('content')
        else:
            return super().__contains__(key)

    def __setitem__(self, key, value):
        if key == "type":
            super().__setitem__('type', value)
        elif key == "content":
            super().__setitem__('content', value)
        else:
            super().__setitem__(key, value)

    def __delitem__(self, key):
        if key == "type":
            super().__setitem__('type', None)
        elif key == "content":
            super().__setitem__('content', None)
        else:
            super().__delitem__(key)
