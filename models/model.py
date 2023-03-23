#!/usr/bin/python
# -*- coding:utf-8 -*-
from collections import namedtuple

Conversation = namedtuple("Conversation", ["name", "question", "reply"])

StudentStatus = namedtuple("StudentStatus",
                           ["class_id", "homework_id", "student_id", "student_hw_id", "clock_record_id", "student_name",
                            "question", "has_feedback", "has_answer"])
