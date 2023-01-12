# OSBot

基于Nonebot的一体化机器人，要求`python>=3.8`

注意，本项目仍在开发测试中，未来将支持在线文档。

## 功能

- 运行状态检查（断线通知、系统状态等）
- 支持推送消息 推特、B站动态、B站直播、邮件
- 烤推功能 支持便捷的选项 logo、覆盖等，支持烤制 回复、投票、引用、图片
- 多引擎机器翻译（支持流式翻译，即发一句翻译一句）
- 反馈
- 状态测试（在吗、ping等指令）

## 运行项目

### 配置

复制`.env.example`为`.env.prod`并修改其中配置

将`.env`文件中的`ENVIRONMENT=dev`改为`ENVIRONMENT=prod`

### 使用

```shell
pip install -r requirements.txt
playwright install
playwright install-deps
```

可能需要的依赖(ubuntu)

```shell
apt-get update
apt-get -y install python3.8 python3-pip python3.8-dev build-essential libssl-dev libffi-dev libxml2 libxml2-dev libxslt1-dev zlib1g-dev
python3.8 -m pip install --upgrade pip
```

### 启动

```SHELL
nb run
```
