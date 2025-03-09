# FastGPT on WeChat

本项目是 [dify-on-wechat](https://github.com/hanfangyuan4396/dify-on-wechat) 的下游项目，专门适配了 [FastGPT](https://github.com/labring/FastGPT) 平台，让您可以轻松地将FastGPT接入到微信生态中。

本项目专注于把FastGPT对接到微信生态中，贡献给 [小x宝](https://github.com/pancrePal-xiaoyibao/pancrePal-xiaoyibao) 公益项目使用

## 项目特点

- 🚀 完全兼容dify-on-wechat的所有功能
- 🖼️ 支持图片解析功能，可以识别和处理图片消息
- ☁️ 灵活的存储方案：
  - 支持OSS对象存储配置
  - 支持Base64图片编码传输
- 💬 支持群聊和私聊场景
- 🔄 支持FastGPT知识库和对话功能

## 快速开始

请参考 [Dify-on-wechat项目文档](https://github.com/hanfangyuan4396/dify-on-wechat) 进行基础配置。

### 新增图片处理流程

图片处理流程如下：

1. 接收图片消息时，系统自动下载并保存
2. 根据配置将图片上传至OSS或转换为Base64格式
3. 调用FastGPT API进行图片分析
4. 返回分析结果到微信对话中

详细流程请参考 [处理流程文档](./流程应该是这样.md)。

### 配置说明

#### 1. 配置文件

项目使用两个主要配置文件：
- `config.json`：主配置文件，包含所有运行时配置
- `config.py`：Python配置模块，包含系统级配置

#### 2. 重要配置参数

##### FastGPT 配置
```json
{
    "fastgpt_api_base": "https://fastgpt.run/api/v1",    // FastGPT应用 API基础URL
    "fastgpt_api_key": "fk-xxx",                         // FastGPT应用 API密钥
    "model": "gpt-3.5-turbo",                           // 调用fastgpt api这个参数会被忽略，以fastgpt配置工作流中的model为准
    "temperature": 0.7,                                 // 温度参数，控制回答的随机性
    "max_tokens": 2000                                 // 最大token数量
}
```

##### OSS 存储配置
```json
{
    "oss_base_url": "你的OSS基础URL",        // 例如：https://your-bucket.oss-cn-beijing.aliyuncs.com
    "oss_access_key": "你的OSS访问密钥",     // OSS AccessKey ID
    "oss_secret_key": "你的OSS密钥",        // OSS AccessKey Secret
    "oss_bucket_name": "你的OSS存储桶名称",  // Bucket名称
    "oss_endpoint": "oss-cn-beijing.aliyuncs.com"  // OSS访问域名
}
```

##### 图片处理配置
```json
{
    "image_store_type": "oss",              // 图片存储类型：oss或base64
    "image_base64_encode": true,           // 是否启用base64编码
    "image_max_size": 10485760            // 最大图片大小（字节）
}
```

更多配置说明请参考 [Dify-on-wechat配置文档](./Dify-on-wechat-README.md)。

## 启动前重要提示

### 1. 部署gewechat服务

首先需要部署gewechat服务，具体步骤如下：

```bash
# 从阿里云镜像仓库拉取(国内)
docker pull registry.cn-chengdu.aliyuncs.com/tu1h/wechotd:alpine
docker tag registry.cn-chengdu.aliyuncs.com/tu1h/wechotd:alpine gewe

# 创建数据目录并启动服务
mkdir -p gewechat/data  
docker run -itd -v ./gewechat/data:/root/temp -p 2531:2531 -p 2532:2532 --restart=always --name=gewe gewe
```

### 2. 关闭代理服务

在启动服务之前，请确保关闭所有代理服务（VPN、梯子等），否则可能会导致连接错误。如果开启VPN会导致服务无法正常工作。

### 3. 地理位置要求

gewechat服务对地理位置有严格要求：
- gewechat服务器必须与扫码登录的微信在同一省份
- 建议将服务部署在本地电脑或同省的服务器上
- 如果服务器与微信不在同一省份，可能会导致登录失败或服务不稳定

- docker compose.yml文件后面增加extra_hosts, 在mac/windows电脑上会出现callback的问题
```
version: '3'
services:
  gewechat:
    image: gewe
    container_name: gewe
    volumes:
      - ./gewechat/data:/root/temp
    ports:
      - "2531:2531"
      - "2532:2532"
    restart: always
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### 4. 配置说明

gewechat相关配置示例：

```json
{
    "channel_type": "gewechat",  // 通道类型设置为gewechat    
    "gewechat_token": "",        // 首次登录可留空,自动获取
    "gewechat_app_id": "",       // 首次登录可留空,自动获取
    "gewechat_base_url": "http://本机ip:2531/v2/api",  // gewechat服务API地址
    "gewechat_callback_url": "http://本机ip:9919/v2/api/callback/collect", // 回调地址
    "gewechat_download_url": "http://本机ip:2532/download" // 文件下载地址 
}
```
mac本机配置
```
    "gewechat_app_id": "wx_xx",
    "gewechat_base_url": "http://192.168.1.159:2531/v2/api",
    "gewechat_callback_url": "http://host.docker.internal:9919/v2/api/callback/collect",
    "gewechat_download_url": "http://192.168.1.159:2532/download",
```

注意事项：
- 本机ip是指**局域网ip**或**公网ip**，可通过`ipconfig`或`ifconfig`命令查看
- gewechat_callback_url中的ip不能使用`127.0.0.1`或`localhost`
- 如果使用docker启动服务，请确保`9919`端口已映射到宿主机

对于 Mac/Windows 使用 Docker Desktop 部署的用户，base_url 请填写为 **http://host.docker.internal:2531**。并且回调地址端口不要修改。

如果还不行，请通过 docker inspect gewe 查看 gewechat 容器网络的 IP 地址，然后 http://ip地址:2531。

对于 Linux 使用 Docker 部署的用户，请通过 docker inspect gewe 查看 gewechat 容器网络的 IP 地址，然后 http://ip地址:2531。如果有 公网ip，也可以是公网 ip，但是需要放行 2531 端口。

![image](https://astrbot.app/assets/image-1.DRlMtAyX.png)
通用方法：

填写宿主机 ip（局域网 ip或者公网地址）或者 Docker Bridge 网络网关 IP（请先在面板上更新 astrbot 到 928245cd0c50c5518c8d68358aa987ef686ef4be 这一个commit）
对于 linux：

将gewechat 的网络模式设置为 host。即在启动参数加 --network=host
对于 Docker Desktop（Windows 和 macOS）:

尝试host改成 host.docker.internal

## 环境配置

### Conda环境配置

推荐使用Conda创建独立的Python环境：

```bash
# 创建Python 3.10环境
conda create -n fow-xiaoyibao python==3.10

# 激活环境
conda activate fow-xiaoyibao
```

### 依赖安装

项目新增了以下重要依赖包：

```bash
# OSS对象存储支持
minio

# Web UI及API支持
gradio==4.44.1
fastapi>=0.100.0
pydantic>=2.5.0,<3.0.0
typing-extensions>=4.5.0
python-multipart>=0.0.5
starlette>=0.27.0
```

您可以通过以下命令安装所需依赖：

```bash
pip install -r requirements.txt
```

## 社区支持

欢迎加入小x宝开源社区！

- 🌟 [小x宝开源社区](https://github.com/pancrePal-xiaoyibao/pancrePal-xiaoyibao)
- 💡 小X宝社区：专注于AI在癌症患者公益助手方面应用开发和创新，应用AI技术提供公益服务，帮助癌症患者家属减少信息差，获得科学循证治疗和更好的依从效果。
- 🤝 社区特色：
  - 活跃的开发者社区
  - 丰富的AI应用实践经验
  - 及时的技术支持
  - 开放的技术交流氛围
- 📢 欢迎加入社区讨论，分享使用经验和建议

## 参与贡献

欢迎提交Pull Request来改进项目！无论是修复bug、新功能开发还是文档改进，我们都非常感谢您的贡献。

## 依赖说明

项目新增了以下重要依赖包：

```bash
# OSS对象存储支持
minio

# Web UI及API支持
gradio==4.44.1
fastapi>=0.100.0
pydantic>=2.5.0,<3.0.0
typing-extensions>=4.5.0
python-multipart>=0.0.5
starlette>=0.27.0
```

您可以通过以下命令安装所需依赖：

```bash
pip install -r requirements.txt
```




## Web UI 功能

项目提供了基于Gradio的Web管理界面，主要功能包括：

1. 扫码登录配置
   - 支持在Web界面显示gewechat的登录二维码
   - 提供二维码刷新功能
   - 可在`config.json`中配置访问密码：
     ```json
     {
       "web_ui_username": "your_username",  // Web界面用户名
       "web_ui_password": "your_password",  // Web界面密码
       "web_ui_port": 7860                  // Web界面端口号
     }
     ```

2. 日志查看
   - 实时显示最近30条运行日志
   - 日志文件位置：`appdata/run.log`
   - 可以在`web_ui.py`的`run_log()`函数中修改显示的日志条数：
     ```python
     def run_log():
         # ...
         lines = file.readlines()[-30:]  # 修改这里的数字来调整显示的日志条数
         # ...
     ```

3. 系统管理
   - 支持在线重启系统
   - 提供二维码强制刷新功能

4. 自定义扩展
   - Web UI基于Gradio框架开发，可以根据需要自行修改`web_ui.py`添加新功能
   - 支持添加自定义页面和功能模块
   - 可以根据实际需求调整界面布局和样式

## 致谢

特别感谢以下项目和社区的贡献：

- [cow](https://github.com/zhayujie/chatgpt-on-wechat) - 基础微信项目框架
- [dow](https://github.com/hanfangyuan4396/dify-on-wechat) - Dify对接实现
- [FastGPT](https://github.com/labring/FastGPT) - 强大的FastGPT平台
- [小胰宝/小x宝社区](https://github.com/pancrePal-xiaoyibao/pancrePal-xiaoyibao) - 公益服务多癌种的AI患者助手社区

持续的支持和反馈

## 免责声明

请遵守相关法律法规，不得用于任何商业或非法用途。详细声明请参考 [Dify-on-wechat免责声明](./Dify-on-wechat-README.md#免责声明必读)。
