# bili-spyder-example

Bilibili 直播小心心获取示例

## 使用方法

**已安装了 python 3.6+**

1. clone 或下载

2. 安装依赖 `pip3 install -r requirements.txt`

3. 用以下方法之一配置好 conf/user.toml

    1. 复制 user.sample.toml 为 user.toml, 然后填上 cookie（必须）和用户名（可选、随意）
    2. 把 bili2.0 的 user.toml 直接复制过来用
    3. 用 ln 链接 bili2.0 的 user.toml 文件

4. 运行 `python3 run.py`

    加上 `--debug` 选项可显示调试日志 `python3 run.py --debug`

## 示例截图

![1_2020-08-29_095807](https://user-images.githubusercontent.com/33854576/91628943-4d390d80-e9f7-11ea-916a-9064beebc16e.png)
![2_2020-08-29_100204](https://user-images.githubusercontent.com/33854576/91628950-62ae3780-e9f7-11ea-88a4-ab6879decd7b.png)
![3_2020-08-29_101616](https://user-images.githubusercontent.com/33854576/91628954-693caf00-e9f7-11ea-9ff8-df84738b2a06.png)
