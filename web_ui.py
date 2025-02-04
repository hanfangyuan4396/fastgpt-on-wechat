# Web UI模块：提供基于Gradio的Web管理界面
# 主要功能：
# 1. 管理员登录验证
# 2. 显示微信登录二维码
# 3. 系统重启功能
# 4. 二维码刷新功能

import os
import sys
import time
import json
import gradio as gr
import logging
import threading
from multiprocessing import Process
import signal
import re

from common import const
from config import conf, load_config
from common.log import logger
from common.tmp_dir import get_appdata_dir
from channel import channel_factory
from plugins import *

# 全局进程实例
current_process_instance = None

def start_channel(channel_name: str):
    """
    启动指定的通道
    Args:
        channel_name: 通道名称
    """
    channel = channel_factory.create_channel(channel_name)
    available_channels = [
        "wx",
        "terminal",
        "wechatmp",
        "wechatmp_service",
        "wechatcom_app",
        "wework",
        "wechatcom_service",
        const.FEISHU,
        const.DINGTALK,
        "gewechat"  # 添加 gewechat 支持
    ]
    if channel_name in available_channels:
        PluginManager().load_plugins()
    channel.startup()

def run():
    """
    主运行函数：加载配置并启动通道
    """
    try:
        load_config()
        channel_name = conf().get("channel_type", "wx")
        logging.info(f"正在启动通道: {channel_name}")
        start_channel(channel_name)
    except Exception as e:
        logging.error("应用启动失败!")
        logging.exception(e)
        raise

def start_run():
    """
    启动或重启进程
    Returns:
        str: 重启状态信息
    """
    global current_process_instance

    try:
        if current_process_instance is not None and current_process_instance.is_alive():
            logging.info("正在终止当前进程...")
            os.kill(current_process_instance.pid, signal.SIGTERM)
            current_process_instance.join()

        current_process_instance = Process(target=run)
        current_process_instance.start()
        time.sleep(10)  # 等待进程启动
        logging.info("进程重启成功")
        return "重启成功!!"
    except Exception as e:
        logging.error("重启失败")
        logging.exception(e)
        return f"重启失败: {str(e)}"

def refresh_qrcode():
    """
    强制刷新二维码
    Returns:
        str: 二维码图片路径或None
    """
    try:
        # 获取当前的 channel
        channel_name = conf().get("channel_type", "wx")
        if channel_name == "gewechat":
            from channel.gewechat.gewechat_channel import GeWeChatChannel
            channel = GeWeChatChannel()
            # 重新初始化客户端并获取二维码
            channel.startup()
        else:
            # 对于微信，先删除旧的二维码文件，强制重新生成
            image_path = os.path.join(get_appdata_dir(), 'wx_qrcode.png')
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                    logging.info(f"已删除旧的二维码文件: {image_path}")
                except Exception as e:
                    logging.error(f"删除旧二维码文件失败: {e}")

        return get_qrcode_image()
    except Exception as e:
        logging.error(f"刷新二维码失败: {e}")
        return None

def get_qrcode_image():
    """
    获取微信登录二维码图片
    Returns:
        str: 二维码图片路径或None
    """
    # 使用 appdata 目录下的二维码图片
    image_path = os.path.join(get_appdata_dir(), 'wx_qrcode.png')
    if os.path.exists(image_path):
        logging.info(f"找到二维码图片: {image_path}")
        return image_path
    return None

def verify_login(username, password):
    """
    验证登录凭据
    Args:
        username: 用户名
        password: 密码
    Returns:
        bool: 验证是否成功
    """
    correct_username = conf().get("web_ui_username", "dow")
    correct_password = conf().get("web_ui_password", "dify-on-wechat")
    return username == correct_username and password == correct_password

def login(username, password):
    """
    处理登录请求
    Args:
        username: 用户名
        password: 密码
    Returns:
        tuple: Gradio界面更新信息
    """
    if verify_login(username, password):
        logging.info("登录成功")
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False)
        )
    logging.warning(f"登录失败: 用户名={username}")
    return (
        "用户名或密码错误",
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=True),
        gr.update(visible=True),
        gr.update(visible=True)
    )

def mask_sensitive_data(text):
    """
    对日志中的敏感信息进行屏蔽
    """
    # 屏蔽 API Key
    text = re.sub(r'(sk-|ak-|api-|openapi-)[a-zA-Z0-9]{5,}', r'\1***', text)
    
    # 屏蔽 URL 中的敏感信息
    text = re.sub(r'(https?://)[^/\s:]+', r'\1***', text)
    
    # 屏蔽 IP 地址
    text = re.sub(r'(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})', r'\1.***.\3.***', text)
    
    return text

def run_log():
    """获取最近20条日志"""
    try:
        log_path = os.path.join(get_appdata_dir(), 'run.log')
        if not os.path.exists(log_path):
            return "暂无日志"
        
        with open(log_path, 'r', encoding='utf-8') as file:
            # 读取最后20行
            lines = file.readlines()[-20:]
            # 对每行进行脱敏处理
            filtered_lines = [mask_sensitive_data(line) for line in lines]
            return ''.join(filtered_lines)
    except Exception as e:
        logging.error(f"读取日志失败: {str(e)}")
        return "读取日志失败"

# 创建Gradio界面
with gr.Blocks() as demo:
    username_input = gr.Textbox(label="用户名")
    password_input = gr.Textbox(label="密码", type="password")
    login_button = gr.Button("登录")
    login_status = gr.Textbox(label="登录状态", value="", interactive=False)

    qrcode_image = gr.Image(value=get_qrcode_image(), label="微信二维码", width=400, height=400, visible=False)
    restart_status = gr.Textbox(label="状态", value="启动成功", visible=False)
    
    with gr.Row():
        restart_button = gr.Button("异常退出后请点击此按钮重启", visible=False)
        refresh_button = gr.Button("点击刷新二维码", visible=False)
    
    # 添加日志显示区域
    log_textbox = gr.Textbox(value=run_log(), label="运行日志（最近20条）", lines=10, interactive=False)
    refresh_log_button = gr.Button("刷新日志")
    
    # 绑定登录按钮事件
    login_button.click(
        login, 
        inputs=[username_input, password_input], 
        outputs=[
            login_status, 
            qrcode_image, 
            restart_button, 
            refresh_button,
            restart_status,
            username_input, 
            password_input, 
            login_button
        ]
    )

    # 绑定重启按钮事件
    restart_button.click(start_run, outputs=restart_status)

    # 绑定刷新二维码按钮事件
    refresh_button.click(refresh_qrcode, outputs=qrcode_image)

    # 绑定刷新日志按钮事件
    refresh_log_button.click(run_log, outputs=log_textbox)

if __name__ == "__main__":
    start_run()
    load_config()
    demo.launch(server_name="0.0.0.0", server_port=conf().get("web_ui_port", 7860))
