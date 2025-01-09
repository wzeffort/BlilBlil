import time

import requests
from bs4 import BeautifulSoup
import os
from pprint import pprint

# 音频和视频都是m4s格式，只是音频的码率比视频的低
# 电视剧或者连续剧的用这个方法
# url = "https://upos-sz-mirrorcos.bilivideo.com/upgcxcode/30/10/93001030/93001030_da8-1-100023.m4s?e=ig8euxZM2rNcNbdlhoNvNC8BqJIzNbfqXBvEqxTEto8BTrNvN0GvT90W5JZMkX_YN0MvXg8gNEV4NC8xNEV4N03eN0B5tZlqNxTEto8BTrNvNeZVuJ10Kj_g2UB02J0mN0B5tZlqNCNEto8BTrNvNC7MTX502C8f2jmMQJ6mqF2fka1mqx6gqj0eN0B599M=&uipk=5&nbs=1&deadline=1701076433&gen=playurlv2&os=cosbv&oi=0&trid=1ef0a6d5adc1463cbbbcf5ce46a1a8dap&mid=3461572699621478&platform=pc&upsig=6731423ff4a303898f70e89096fd6826&uparams=e,uipk,nbs,deadline,gen,os,oi,trid,mid,platform&bvc=vod&nettype=0&orderid=0,3&buvid=236DB2EC-B01A-89DD-76B2-3D1960B4746482627infoc&build=0&f=p_0_0&agrr=1&bw=16700&logo=80000000"
# url2 = "https://upos-sz-mirror08c.bilivideo.com/upgcxcode/30/10/93001030/93001030_da8-1-30216.m4s?e=ig8euxZM2rNcNbdlhoNvNC8BqJIzNbfqXBvEqxTEto8BTrNvN0GvT90W5JZMkX_YN0MvXg8gNEV4NC8xNEV4N03eN0B5tZlqNxTEto8BTrNvNeZVuJ10Kj_g2UB02J0mN0B5tZlqNCNEto8BTrNvNC7MTX502C8f2jmMQJ6mqF2fka1mqx6gqj0eN0B599M=&uipk=5&nbs=1&deadline=1701076433&gen=playurlv2&os=08cbv&oi=0&trid=1ef0a6d5adc1463cbbbcf5ce46a1a8dap&mid=3461572699621478&platform=pc&upsig=b84ea7550d34d9da6798ab404f3fdf21&uparams=e,uipk,nbs,deadline,gen,os,oi,trid,mid,platform&bvc=vod&nettype=0&orderid=0,3&buvid=236DB2EC-B01A-89DD-76B2-3D1960B4746482627infoc&build=0&f=p_0_0&agrr=1&bw=8409&logo=80000000"
# headers = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
#     'Accept-Encoding': 'gzip, deflate',
#     "Referer": "https://www.bilibili.com/bangumi/play/ep261820?spm_id_from=333.337.search-card.all.click",
#     ##每次都要改变
# }
#
# res = requests.get(url, headers=headers)
#
# res2 = requests.get(url2, headers=headers)
# print(res.status_code)
# soup = BeautifulSoup(res.content, 'html.parser')
# soup2 = BeautifulSoup(res2.content, 'html.parser')
# # print(soup.text)
# with open("D:\\b站视频\\74\\77474\\1.mp4", "wb") as f:  # 视频下载
#     f.write(res.content)
# with open("D:\\b站视频\\74\\77474\\2.mp4", "wb") as f:  # 音频下载
#     f.write(res2.content)
# com = f'D:/FFmpeg/bin/ffmpeg.exe -i "D:\\b站视频\\74\\77474\\1.mp4" -i "D:\\b站视频\\74\\77474\\2.mp4" -acodec copy -vcodec ' \
#       f'copy "D:\\b站视频\\74\\77474\\第六话第一国际风云.mp4" '
# os.system(com)
# os.remove(f"D:\\b站视频\\74\\77474\\1.mp4")
# os.remove(f"D:\\b站视频\\74\\77474\\2.mp4")
import time
import requests
from bs4 import BeautifulSoup
import os
import json
from pprint import pprint
import tkinter
import tkinter as tk
from tkinter import messagebox
import re
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ",
    "Referer": "https://www.bilibili.com"
}
root = tk.Tk()
root.title('下载窗口')
width, height = root.maxsize()
root.maxsize(width, height)
root.geometry("600x500+590+400")
root.resizable(width=True, height=True)
l_name = tkinter.Label(root, text='视频地址', font=('宋体', 25))


l_name.place(x=60, y=250)
e_names = tkinter.Entry(root, width=16, font=('宋体', 25))
e_names.place(x=200, y=250)

def sanitize_title(title):
    # 用下划线替换所有不规范的字符
    return re.sub(r'[^\w\-_\. ]', '_', title)

def get_video_info(url):
    res1 = requests.get(url, headers=headers, stream=True)
    soup1 = BeautifulSoup(res1.text, 'html.parser')

    scripts = soup1.find_all('script')
    for script in scripts:
        if 'window.__playinfo__' in script.text:
            json_str = script.text.split('=', 1)[1].strip()
            json_str = json_str.rsplit(';', 1)[0]
            data1 = json.loads(json_str)
            audio_url = data1['data']['dash']['audio'][0]['base_url']
            video_url = data1['data']['dash']['video'][0]['base_url']
            print(audio_url)
            print(video_url)
            return audio_url, video_url


#
def download_and_process_video(audio_url, video_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ",
        "Referer": "https://www.bilibili.com"
    }

    # 下载音频和视频
    audio_res = requests.get(audio_url, headers=headers)
    video_res = requests.get(video_url, headers=headers)
    res1 = requests.get(e_names.get(), headers=headers, stream=True)
    # 解析视频页面，获取视频标题
    soup = BeautifulSoup(res1.text, 'html.parser')
    title = soup.find('h1', class_='video-title').text
    # 保存音频和视频文件
    with open("D:\\b站视频\\74\\77474\\1.mp4", "wb") as f:
        f.write(audio_res.content)
    with open("D:\\b站视频\\74\\77474\\2.mp4", "wb") as f:
        f.write(video_res.content)
    title = soup.find('h1', class_='video-title').text
    title = sanitize_title(title)
    # 使用ffmpeg命令合并音频和视频文件
    command = f'D:/FFmpeg/bin/ffmpeg.exe -i "D:\\b站视频\\74\\77474\\1.mp4" -i "D:\\b站视频\\74\\77474\\2.mp4" -acodec copy -vcodec ' \
              f'copy "D:\\b站视频\\74\\77474\\{title}.mp4" '
    os.system(command)

    # 删除下载的音频和视频文件
    os.remove("D:\\b站视频\\74\\77474\\1.mp4")
    os.remove("D:\\b站视频\\74\\77474\\2.mp4")
    tkinter.messagebox.showinfo("提示", "下载完成")

    # 关闭窗口
    root.destroy()


def on_button_click():
    url = e_names.get()# 获取输入框的内容
    audio_url, video_url = get_video_info(url)
    download_and_process_video(audio_url, video_url)


b1 = tkinter.Button(root, text='下载', width=30, height=2, command=on_button_click)
b1.place(x=200, y=450)
root.mainloop()  # 启动事件循环
