#!/usr/bin/python
# -*- coding:utf-8 -*-
from typing import List
from models.model import Conversation


class History:
    def __init__(self):
        self.history_list: List[Conversation] = []
        self.anonymity_dict = {
            # "ori_name": "anonymity"
        }

    def __getstate__(self):
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def add_anonymity(self, name, anonymity):
        self.anonymity_dict[name] = anonymity

    def anonymity_name(self, name):
        return self.anonymity_dict.get(name)

    def add_history(self, name, question, reply):
        con = Conversation(name, question, reply)
        self.history_list.append(con)

    def clean_sb_history(self, name, num):
        for index in range(len(self.history_list) - 1, -1, -1):
            if self.history_list[index].name == name:
                self.history_list.pop(index)
                num -= 1
            if num == 0:
                break

    def clean_nm_history(self, num):
        if num > len(self.history_list):
            self.history_list.clear()
        else:
            del self.history_list[-num:]

    def get_sb_history(self, name, num) -> Conversation:
        for index in range(len(self.history_list) - 1, -1, -1):
            if self.history_list[index].name == name:
                num -= 1
            if num == 0:
                return self.history_list[index]
        raise TypeError

    def to_dict(self):
        ...

    def to_text(self, num):
        res_lines = [f"历史记录如下(最近{num}条):"]

        for con in self.history_list[-num:]:
            name = self.anonymity_name(con.name) or con.name
            name = "{:　^{}}".format(name, 4)
            question: str = con.question

            line_list = ["\n\u3000\u3000\u3000\u3000\u3000".join([chunk[i:i + 37] for i in range(0, len(chunk), 37)])
                         for chunk in question.split("\n")]
            question = "\n\u3000\u3000\u3000\u3000\u3000".join(line_list)

            show_line = f"{name}：{question}"
            res_lines.append(show_line)

        return "\n".join(res_lines)


if __name__ == "__main__":
    import pickle
    from pathlib import Path
    his = Path(r"../data/history.pickle")

    history = pickle.loads(his.read_bytes())

    print(history.history_list)
