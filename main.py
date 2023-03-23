#!/usr/bin/python
# -*- coding:utf-8 -*-
import json
import pickle
import sys
import time
from pathlib import Path
from queue import Queue

from apis.homework_api import login_teacher
from models.handler import Handler
from models.history import History
from models.model import StudentStatus


class GPT2ZhiXue:
    DATA_PATH = Path(r"data")
    HISTORY_PATH = DATA_PATH / "history.pickle"
    STUDENT_JSON_PATH = DATA_PATH / "student_data.json"

    CONFIG_FILE = Path(r"config.toml")

    def __init__(self):
        # self.config = toml.loads(self.CONFIG_FILE.read_text(encoding="utf-8"))
        self.wait_queue = Queue()

        self.announcement = None
        self.is_maintain = False
        self.warning_list = []

        self._init_auth()
        self._init_history()
        self._init_student_json()

        self._init_gpt_handler()
        self._init_zhixue_listen()
        self._init_command_handler()

        self.gpt_handler_start()

    def _init_command_handler(self):
        self.command_handler = CommandHandler(self)

    def _init_auth(self):
        self.admin_list = []
        self.super_admin = ""

    def _init_zhixue_listen(self):
        self.teachers = []
        self.homework_teacher_map = {}
        self.teachers_data = {
            "teacher1": {
                "login": ("account", "password"),
                "homework": {
                    # "homework_id": ["class_id1", "class_id2"]
                }
            }
        }
        for teacher_data in self.teachers_data.values():
            account = teacher_data["login"]
            listen_homework = teacher_data["homework"]

            teacher = login_teacher(*account)
            for item in listen_homework.items():
                teacher.add_homework_listen(*item)
                self.homework_teacher_map[item[0]] = teacher
            self.teachers.append(teacher)

    def _init_gpt_handler(self):
        self.api_keys = ["GPT api_keys1",
                         "GPT api_keys2"]
        self.gpt_handlers = []
        for api_key in self.api_keys:
            self.gpt_handlers.append(Handler(self.wait_queue, api_key, self.response_signal_func))

    def _init_history(self):
        self.history = History()
        if self.HISTORY_PATH.exists():
            self.history = pickle.loads(self.HISTORY_PATH.read_bytes())

    def _init_student_json(self):
        if self.STUDENT_JSON_PATH.exists():
            self.student_json = json.load(self.STUDENT_JSON_PATH.open(encoding="utf-8"))
        else:
            self.student_json = {}

    def gpt_handler_start(self):
        for gpt_handler in self.gpt_handlers:
            gpt_handler.start_thread()

    def save_json(self):
        self.STUDENT_JSON_PATH.write_text(json.dumps(self.student_json, indent=4, ensure_ascii=False),
                                          encoding="utf-8")

    def save_history(self):
        pickle.dump(self.history, self.HISTORY_PATH.open("wb"))

    def response_signal_func(self, student: StudentStatus, response: str):
        teacher = self.homework_teacher_map[student.homework_id]
        status = teacher.comment_homework(student, response)
        if not status:
            teacher.comment_homework(student, "回复过长或未知原因导致 智学网无法显示")
        if not response.startswith("revGPTError: "):
            self.history.add_history(student.student_name, student.question, response)

    def process_pre(self, student: StudentStatus, last_status):
        teacher = self.homework_teacher_map[student.homework_id]
        if not last_status["enable"]:
            teacher.comment_homework(student, "你已经被管理员封禁，请联系管理员解封")
            return True
        if self.is_maintain and student.student_id != self.super_admin:
            teacher.comment_homework(student, "当前正在维护，请稍后再试")
            return True
        if student.student_name in self.warning_list:
            self.warning_list.remove(student.student_name)
            teacher.comment_homework(student, "你的本次请求被截断\n你已被警告，请注意问题要求。")
            return True
        return False

    def process_question(self, student: StudentStatus):
        self.student_json[student.student_name]["questions"].append(student.question)
        self.wait_queue.put(student)

    def process_command(self, student: StudentStatus):
        teacher = self.homework_teacher_map[student.homework_id]
        try:
            res_show = self.command_handler.process_command(student.question, student.student_id)
        except CommandError as e:
            res_show = "processError:" + str(e)
        status = teacher.comment_homework(student, res_show)
        if not status:
            teacher.comment_homework(student, "回复过长或未知原因导致 智学网无法显示")

    def main(self):
        sleep_time = 5

        while True:
            time.sleep(sleep_time)
            print("开始检查智学网作业状况")
            for teacher in self.teachers:
                student_status_list = teacher.get_student_learning_status()
                for student in student_status_list:
                    last_status = self.student_json.get(student.student_name)

                    if not last_status:
                        last_status = {
                            "enable": True,
                            "class_id": student.class_id,
                            "student_id": student.student_id,
                            "homework_id": student.homework_id,
                            "student_hw_id": student.student_hw_id,
                            "clock_record_id": student.clock_record_id,
                            "has_answer": False,
                            "has_feedback": False,
                            "questions": []
                        }
                        self.student_json[student.student_name] = last_status
                        self.save_json()

                    if not student.has_answer:
                        self.student_json[student.student_name]["has_answer"] = False
                        continue

                    if student.has_feedback or not student.question:
                        self.student_json[student.student_name]["has_answer"] = False
                        teacher = self.homework_teacher_map[student.homework_id]
                        teacher.redo_homework(student, "请输入你的问题")
                        continue

                    if not last_status["has_answer"]:
                        self.student_json[student.student_name]["has_answer"] = True

                        if self.process_pre(student, last_status):
                            continue

                        if student.question[0] == '/':
                            self.process_command(student)
                        else:
                            self.process_question(student)
                self.save_json()
                self.save_history()
            print("检查作业状况完毕")

    def stop_gpt_handler(self):
        for gpt_handler in self.gpt_handlers:
            gpt_handler.is_running = False
            gpt_handler.event.set()


class CommandError(Exception):
    """指令错误"""


class CommandHandler:
    def __init__(self, parent: GPT2ZhiXue):
        self._parent = parent

        self._command_list = [attr for attr in dir(self) if not attr.startswith("_")]
        self._command_list.remove("process_command")

        self._auth_command = {
            "check": 0,
            "ban": 1,
            "unban": 2,
            "clear": 1,
            "history": 0,
            "rebuild": 1,
            "blacklist": 0,
            "stop": 1,
            "start": 1,
            "warn": 1,
            "ad": 2,
            "kill": 2,
            "peek": 0,
            "clean": 2
        }

    def _get_auth(self, student_id):
        auth = 0
        if student_id in self._parent.admin_list:
            auth = 1
        if student_id == self._parent.super_admin:
            auth = 3
        return auth

    def process_command(self, raw_command: str, student_id):
        auth = self._get_auth(student_id)

        raw_command = raw_command[1:]
        if not raw_command:
            raise CommandError("指令内容为空")

        split_com = raw_command.split()
        command = split_com[0]
        args = split_com[1:]

        if command not in self._command_list:
            raise CommandError("没有这条指令，请检查是否正确")

        if auth < self._auth_command[command]:
            raise CommandError(f"权限不足，无法使用/{command}")

        try:
            func = getattr(self, command)
            res_show = func(*args)
            return res_show
        except CommandError as e:
            raise e
        except (ValueError, TypeError):
            raise CommandError("参数个数有误")

    def ad(self, content):
        if content == "None":
            self._parent.announcement = None
            return "已经去除公告"
        self._parent.announcement = content
        return "已经添加公告"

    def stop(self):
        self._parent.is_maintain = True
        return "已经关闭服务"

    def start(self):
        self._parent.is_maintain = False
        return "已经开启服务"

    def check(self, target_name, num=40):
        student = self._student_json.get(target_name)
        if not student:
            return f"找不到学生 {target_name}"

        questions = student["questions"]
        res_show = f"这是 学生{target_name} 的问题记录:(最近{int(num)}条)"
        for question in questions[-int(num):]:
            res_show += "\n" + question
        return res_show

    def ban(self, *args):
        res_show = ""
        for stu in args:
            student = self._student_json.get(stu)
            if not student:
                res_show += f"找不到学生 {stu}\n"
            elif student["student_id"] == self._parent.super_admin:
                res_show += f"你无权封禁"
            else:
                student["enable"] = False
                res_show += f"已封禁 学生{stu}\n"

                self._parent.history.add_history("⚠️通报⚠️", f"{stu}被封禁", "")
        return res_show

    def unban(self, *args):
        res_show = ""
        for stu in args:
            student = self._student_json.get(stu)
            if not student:
                res_show += f"找不到学生 {stu}\n"
            else:
                student["enable"] = True
                res_show += f"已解封 学生{stu}\n"
        return res_show

    def clear(self, *args):
        res_show = ""
        for stu in args:
            student = self._student_json.get(stu)
            if not student:
                res_show += f"找不到学生 {stu}\n"
            else:
                student["questions"] = []
                res_show += f"已清除 学生{stu} 的问题记录\n"
        return res_show

    def history(self, num=30):
        res_show = ""

        if self._parent.announcement:
            ad_ = f"公告:\n{self._parent.announcement}\n"
            res_show = ad_ + res_show

        res_show += "\n" + self._parent.history.to_text(int(num))
        return res_show

    def blacklist(self):
        res_show = f"被封禁人员为以下：\n"
        black_list = [stu for stu, item in self._student_json.items() if item["enable"] is False]
        return res_show + ", ".join(black_list)

    def warn(self, *args):
        res_show = ""
        for stu in args:
            if self._student_json.get(stu):
                res_show += f"已警告{stu}\n"
                self._parent.warning_list.append(stu)
                self._parent.history.add_history("⚠️通报⚠️", f"{stu}被警告", "")
            else:
                res_show += f"找不到{stu}\n"
        return res_show

    def kill(self):
        self._parent.save_json()
        self._parent.save_history()
        self._parent.stop_gpt_handler()
        sys.exit(0)

    def peek(self, name, num):
        try:
            con = self._parent.history.get_sb_history(name, int(num))
            return f"{con.name}问了：\n{con.question}\n回复：{con.reply}"
        except TypeError:
            return f"不存在{name}或者没有对应历史记录"

    def clean(self, name, num):
        if name == "history":
            self._parent.history.clean_nm_history(int(num))
            return "已清除"

        if name not in self._student_json:
            return f"不存在{name}或者没有对应历史记录"

        self._parent.history.clean_sb_history(name, int(num))
        return "已清除"

    @property
    def _student_json(self):
        return self._parent.student_json

    def _save_json(self):
        self._parent.save_json()


if __name__ == '__main__':
    main = GPT2ZhiXue()
    main.main()
