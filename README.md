# bili-spyder-example

Bilibili 直播小心心获取示例

**现在只支持 64 位类 Unix 系统，Window 可用 WSL。** 详见：https://github.com/acgnhiki/bili-spyder
本项目用到的 `wasmer` 是自己编译的，只支持 python 3.8。

## 使用方法

1. clone 或下载

2. 安装依赖 `pip3 install -r requirements.txt`

3. 用以下方法之一配置好 conf/user.toml

    1. 复制 user.sample.toml 为 user.toml, 然后填上 cookie（必须）和用户名（可选、随意）
    2. 把 bili2.0 的 user.toml 直接复制过来用
    3. 用 ln 链接 bili2.0 的 user.toml 文件

4. 运行 `python3 run.py`

    加上 `--debug` 选项可显示调试日志 `python3 run.py --debug`
