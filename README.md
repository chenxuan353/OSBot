# OSBot

基于Nonebot的一体化机器人，要求`python>=3.8`

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
