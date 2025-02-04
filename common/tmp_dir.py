import os
import pathlib

from config import conf


class TmpDir(object):
    """A temporary directory that is deleted when the object is destroyed."""

    def __init__(self):
        # 获取项目根目录的绝对路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 使用项目根目录下的 tmp 目录
        self.tmpFilePath = os.path.join(project_root, "tmp")
        if not os.path.exists(self.tmpFilePath):
            os.makedirs(self.tmpFilePath, mode=0o777)  # 设置目录权限为777
            os.chmod(self.tmpFilePath, 0o777)  # 确保目录权限正确
        else:
            # 如果目录已存在，也确保权限正确
            os.chmod(self.tmpFilePath, 0o777)

    def path(self):
        """返回临时目录的绝对路径"""
        return self.tmpFilePath + os.path.sep


def get_appdata_dir():
    """
    获取应用数据目录
    Returns:
        str: 应用数据目录的绝对路径
    """
    # 获取项目根目录的绝对路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 使用项目根目录下的 appdata 目录
    appdata_path = os.path.join(project_root, "appdata")
    if not os.path.exists(appdata_path):
        os.makedirs(appdata_path, mode=0o777)  # 设置目录权限为777
        os.chmod(appdata_path, 0o777)  # 确保目录权限正确
    else:
        # 如果目录已存在，也确保权限正确
        os.chmod(appdata_path, 0o777)
    return appdata_path
