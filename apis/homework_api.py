#!/usr/bin/python
# -*- coding:utf-8 -*-
import io
import string
import random
import time
from io import BytesIO
from zhixuewang.teacher.teacher import TeacherAccount
from zhixuewang.account import get_session
from models.model import StudentStatus


def get_homework_header():
    header = {
        "Referer": "https://www.zhixue.com/middlehomework/web-teacher/views/",
        "Host": "www.zhixue.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/110.0.0.0 Safari/537.36",
        "sucClientType": "pc-web",
        "sucAccessDeviceId": "877C6188-51E8-460B-9A58-151350BCC329",
        "sucOriginAppKey": "pc_web",
    }
    return header


def generate_random_string():
    # 生成数字、字母和大小写字母的所有可能字符
    chars = string.digits + string.ascii_letters

    # 随机选择16个字符
    random_chars = random.choices(chars, k=16)

    # 将字符拼接成字符串并返回
    return ''.join(random_chars)


class HomeworkTeacherAccount(TeacherAccount):
    def __init__(self, *args):
        super(HomeworkTeacherAccount, self).__init__(*args)
        self.contains = {
            # "homework_id": ["class_id1", "class_id2"]
        }

    def add_homework_listen(self, homework_id: str, class_ids: list):
        self.contains[homework_id] = class_ids

    def get_homework_token(self):
        self.update_login_status()
        url = "https://www.zhixue.com/middleweb/newToken"
        res = self._session.get(url, headers=get_homework_header()).json()
        token = res["result"]["token"]
        return token

    def refresh_header(self):
        token = self.get_homework_token()
        header = get_homework_header()
        header["appName"] = "com.iflytek.zxzy.web.zx.tea"
        header["Authorization"] = token
        header["sucUserToken"] = token
        return header

    def _get_student_learning_status(self, hw_id, class_id):
        header = self.refresh_header()

        url = "https://mhw.zhixue.com/hwreport/learning/learningRecordList"

        data = {"base": {"appId": "OAXI57PG",
                         "appVersion": "",
                         "sysVersion": "v1001",
                         "sysType": "web",
                         "packageName": "com.iflytek.edu.hw",
                         "udid": "9190943208000048659", "expand": {}},
                "params": {"hwId": hw_id,
                           "hwType": 107,
                           "classId": class_id}}

        res_json = self._session.post(url, json=data, headers=header).json()
        return res_json

    def get_student_learning_status(self):
        res_status_list = []

        for homework_id in self.contains.keys():
            class_ids = self.contains[homework_id]

            for class_id in class_ids:
                res_json = self._get_student_learning_status(homework_id, class_id)

                for student in res_json["result"]["learningRecordList"]:
                    question = student["answerResults"]
                    if not question:
                        question = ""
                    else:
                        question = question[0]["description"]

                    status = StudentStatus(
                        student_id=student["studentId"],
                        class_id=class_id,
                        student_name=student["studentName"],
                        student_hw_id=student["stuHwId"],
                        has_answer=student["status"] == 2,
                        has_feedback=student["feedbackStatus"] != 0,
                        question=question,
                        clock_record_id=student["clockRecordId"],
                        homework_id=homework_id
                    )

                    res_status_list.append(status)
        return res_status_list

    def comment_homework(self, student: StudentStatus, comment):
        header = self.refresh_header()

        url = "https://mhw.zhixue.com/hw/clock/comment/add"

        data = {"base": {"appId": "OAXI57PG",
                         "appVersion": "",
                         "sysVersion": "v1001",
                         "sysType": "web",
                         "packageName": "com.iflytek.edu.hw",
                         "udid": "9190943208000048659",
                         "expand": {}},
                "params": {"hwId": student.homework_id,
                           "clockRecordId": student.clock_record_id,
                           "commentType": 2,
                           "classId": student.class_id,
                           "stuHwId": student.student_hw_id,
                           "attachment": [{"fileType": 5, "description": comment, "path": None, "sort": 1}]}}

        res = self._session.post(url, json=data, headers=header)
        print(res.json())
        return res.json()["code"] == "000000"

    def comment_delete(self, student: StudentStatus):
        header = self.refresh_header()

        url = "https://mhw.zhixue.com/hw/clock/comment/delete"

        data = {"base": {"appId": "OAXI57PG",
                         "appVersion": "",
                         "sysVersion": "v1001",
                         "sysType": "web",
                         "packageName": "com.iflytek.edu.hw",
                         "udid": "9190943208000048659",
                         "expand": {}},
                "params": {"hwId": student.homework_id,
                           "clockRecordId": student.clock_record_id, "commentType": 2,
                           "stuHwId": student.student_hw_id,
                           "attachmentIds": ["3a01666b3a7f4e55b88ec7a3c4f9f7d1"], "classId": "1500000100075734896"}}
        raise NotImplemented

    def redo_homework(self, student: StudentStatus, redo_reason):
        header = self.refresh_header()

        url = "https://mhw.zhixue.com/hw/clock/comment/redo"

        data = {"base": {"appId": "OAXI57PG",
                         "appVersion": "",
                         "sysVersion": "v1001",
                         "sysType": "web",
                         "packageName": "com.iflytek.edu.hw",
                         "udid": "9190943208000048659",
                         "expand": {}},
                "params": {"hwId": student.homework_id,
                           "stuHwId": student.student_hw_id,
                           "clockRecordId": student.clock_record_id,
                           "redoReason": redo_reason,
                           "classId": student.class_id}}

        res = self._session.post(url, json=data, headers=header)
        print("打回:", res.json())

    def upload_mp3_file(self, bytes_io: BytesIO):
        boundary = generate_random_string()
        timestamp = int(time.time() * 1000)

        data_start = f"------WebKitFormBoundary{boundary}\r\n".encode()
        data_info = f'Content-Disposition: form-data; name="file"; filename="{timestamp}.mp3"\r\nContent-Type: ' \
                    'application/octet-stream\r\n\r\n'.encode()
        data_end = f"\r\n------WebKitFormBoundary{boundary}--\r\n".encode()

        data_content = bytes_io.getvalue()

        url = "https://www.zhixue.com/middleweb/homework_middle_service/teaapp/newUploadToAliyun"
        data = data_start + data_info + data_content + data_end
        # print(data_start + data_info + data_end)
        # print(data)
        header = self.refresh_header()
        header["Referer"] = "https://www.zhixue.com/middlehomework/web-teacher/views/"
        header['Content-Type'] = f'multipart/form-data; boundary=----WebKitFormBoundary{boundary}'

        res = self._session.post(url, data=data, headers=header)
        print(res.json())
        return res.json()["result"]

    def upload_pic_file(self, bytes_io: BytesIO):
        boundary = generate_random_string()
        timestamp = int(time.time() * 1000)

        data_start = f"------WebKitFormBoundary{boundary}\r\n".encode()
        data_info = f'Content-Disposition: form-data; name="file"; filename="{timestamp}.png"\r\nContent-Type: ' \
                    'image/png\r\n\r\n'.encode()
        data_end = f"\r\n------WebKitFormBoundary{boundary}--\r\n".encode()

        data_content = bytes_io.getvalue()

        url = "https://www.zhixue.com/middleweb/homework_middle_service/teaapp/newUploadToAliyun"
        data = data_start + data_info + data_content + data_end
        # print(data_start + data_info + data_end)
        # print(data)
        header = self.refresh_header()
        header["Referer"] = "https://www.zhixue.com/middlehomework/web-teacher/views/"
        header['Content-Type'] = f'multipart/form-data; boundary=----WebKitFormBoundary{boundary}'

        res = self._session.post(url, data=data, headers=header)
        print(res.json())
        return res.json()["result"]

    def upload_mp4_file(self, bytes_io: BytesIO):
        boundary = generate_random_string()
        timestamp = int(time.time() * 1000)

        data_start = f"------WebKitFormBoundary{boundary}\r\n".encode()
        data_info = f'Content-Disposition: form-data; name="file"; filename="{timestamp}.png"\r\nContent-Type: ' \
                    'video/mp4\r\n\r\n'.encode()
        data_end = f"\r\n------WebKitFormBoundary{boundary}--\r\n".encode()

        data_content = bytes_io.getvalue()

        url = "https://www.zhixue.com/middleweb/homework_middle_service/teaapp/newUploadToAliyun"
        data = data_start + data_info + data_content + data_end
        # print(data_start + data_info + data_end)
        # print(data)
        header = self.refresh_header()
        header["Referer"] = "https://www.zhixue.com/middlehomework/web-teacher/views/"
        header['Content-Type'] = f'multipart/form-data; boundary=----WebKitFormBoundary{boundary}'

        res = self._session.post(url, data=data, headers=header)
        print(res.json())
        return res.json()["result"]


def login_teacher(username: str, password: str) -> HomeworkTeacherAccount:
    """通过用户名和密码登录老师账号

    Args:
        username (str): 用户名, 可以为准考证号, 手机号
        password (str): 密码(包括加密后的密码)

    Raises:
        UserOrPassError: 用户名或密码错误
        UserNotFoundError: 未找到用户
        LoginError: 登录错误

    Returns:
        TeacherAccount
    """
    session = get_session(username, password)
    teacher = HomeworkTeacherAccount(session)
    return teacher.set_base_info()


if __name__ == '__main__':
    pass
