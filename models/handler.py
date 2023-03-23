#!/usr/bin/python
# -*- coding:utf-8 -*-
import time

from revChatGPT.V3 import Chatbot
from queue import Queue
from typing import Callable
from models.model import StudentStatus
import threading


class MyGPT:
    def __init__(self, api_key):
        self.config = {
            "api_key": api_key,
            "proxy": "127.0.0.1:10889"  # your proxy
        }
        print("开始构建chatGPT连接")
        self.chatbot = Chatbot(**self.config)
        print("连接成功")

    def rebuild(self):
        print("开始构建chatGPT连接")
        self.chatbot = Chatbot(**self.config)
        print("连接成功")

    def get_response(self, prompt):
        try:
            response = ""
            for data in self.chatbot.ask(prompt):
                response += data
        except Exception as e:
            self.rebuild()
            return "revGPTError: " + str(e)
        return response


class Handler:
    RESPONSE_TIME_GAP = 3
    TIMES_REFRESH = 5

    def __init__(self, queue: Queue, api_key: str, response_signal_func: Callable[[StudentStatus, str], None]):
        self.response_signal_func = response_signal_func
        self.chatGPT = MyGPT(api_key)
        self.queue = queue
        self.times = 0

        self.event = threading.Event()
        self.is_running = True

    def start_thread(self):
        thread = threading.Thread(target=self.working_func)
        thread.start()

    def working_func(self):
        while self.is_running:
            while self.queue.empty() and self.is_running:
                self.event.wait(1)

            request_student = self.queue.get()
            question = request_student.question
            print(f"学生{request_student.student_name}出队, 开始解答问题")
            response = self.chatGPT.get_response(question)
            self.response_signal_func(request_student, response)
            print(f"已回答{request_student.student_name}")

            self.times += 1
            if self.times >= self.TIMES_REFRESH:
                self.times = 0
                self.chatGPT.rebuild()

            self.event.wait(self.RESPONSE_TIME_GAP)
