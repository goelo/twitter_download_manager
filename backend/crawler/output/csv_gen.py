import csv
import os
import sqlite3
import time
from datetime import datetime

# task_items_realtime 统一 schema:
# [tweet_date, display_name, user_name, tweet_url, media_type, media_url,
#  saved_filename, tweet_content, favorite_count, retweet_count, reply_count]
REALTIME_COLUMNS = 11


class RealtimeWriter:
    """把采集行双写到 web 端 sqlite 的 task_items_realtime 表，供实时数据展示。

    由 web 端启动子进程时注入 TW_TASK_ID / TW_REALTIME_DB_PATH；
    环境变量缺失（如 CLI 直接运行）时退化为 no-op。写入失败只告警，不影响采集主流程。
    """

    FLUSH_THRESHOLD = 20

    def __init__(self):
        self.task_id = os.environ.get('TW_TASK_ID')
        self.db_path = os.environ.get('TW_REALTIME_DB_PATH')
        self.enabled = bool(self.task_id and self.db_path)
        self.buffer = []

    def add(self, row):
        if not self.enabled:
            return
        row = (list(row) + [''] * REALTIME_COLUMNS)[:REALTIME_COLUMNS]
        self.buffer.append(row)
        if len(self.buffer) >= self.FLUSH_THRESHOLD:
            self.flush()

    def flush(self):
        if not self.enabled or not self.buffer:
            return
        rows, self.buffer = self.buffer, []
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            try:
                conn.executemany(
                    '''
                    insert or ignore into task_items_realtime (
                        task_id, tweet_date, display_name, user_name, tweet_url,
                        media_type, media_url, saved_filename, tweet_content,
                        favorite_count, retweet_count, reply_count, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    [tuple([int(self.task_id)] + r + [created_at]) for r in rows],
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f'[realtime] 实时数据写入失败(不影响采集): {e}')


class csv_gen():
    def __init__(self, save_path:str, user_name, screen_name, tweet_range) -> None:
        self.f = open(f'{save_path}/{screen_name}-{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.csv', 'w', encoding='utf-8-sig', newline='')
        self.writer = csv.writer(self.f)
        self.realtime = RealtimeWriter()

        #初始化
        self.writer.writerow([user_name, screen_name])
        self.writer.writerow(['Tweet Range : ' + tweet_range])
        self.writer.writerow(['Save Path : ' + save_path])
        main_par = ['Tweet Date', 'Display Name', 'User Name', 'Tweet URL', 'Media Type', 'Media URL', 'Saved Filename', 'Tweet Content', 'Favorite Count',
                    'Retweet Count', 'Reply Count']
        self.writer.writerow(main_par)

    def csv_close(self):
        self.realtime.flush()
        self.f.close()

    def stamp2time(self, msecs_stamp:int) -> str:
        timeArray = time.localtime(msecs_stamp/1000)
        otherStyleTime = time.strftime("%Y-%m-%d %H:%M", timeArray)
        return otherStyleTime

    def data_input(self, main_par_info:list) -> None:   #数据格式参见 main_par
        main_par_info[0] = self.stamp2time(main_par_info[0])    #传进来的是 int 时间戳, 故转换一下
        self.writer.writerow(main_par_info)
        self.realtime.add(main_par_info)
