# -*- coding: utf-8 -*-
import time
import select
import socket
import argparse
import importlib
from enum import Enum
from subprocess import Popen, CREATE_NEW_CONSOLE

import cv2

import majsoul_wrapper as sdk
from majsoul_wrapper import all_tiles, Operation
from majsoul_wrapper.action.action import GUIInterface
from wrapper import TenHouAIWrapper, MahjongAIWrapper


class AIInput(Enum):
    TenHou = 0
    Mahjong = 1


def MainLoop(isRemoteMode=False, remoteIP: str = None, input_=AIInput.TenHou, level=None, match=0):
    # 循环进行段位场对局，level=0~4表示铜/银/金/玉/王之间，None需手动开始游戏
    # calibrate browser position
    wrappers = {
        AIInput.TenHou: TenHouAIWrapper(),
        AIInput.Mahjong: MahjongAIWrapper(),
    }
    aiWrapper = wrappers[input_]
    print('waiting to calibrate the browser location')
    while not aiWrapper.calibrateMenu():
        print('  majsoul menu not found, calibrate again')
        time.sleep(3)

    while True:
        # create AI
        if isRemoteMode == False:
            print('create AI subprocess locally')
            AI = Popen('python main.py --fake', cwd='JianYangAI', creationflags=CREATE_NEW_CONSOLE)
            # create server
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_address = ('127.0.0.1', 7479)
            print('starting up on %s port %s' % server_address)
            server.bind(server_address)
            server.listen(1)
            print('waiting for the AI')
            connection, client_address = server.accept()
            print('AI connection: ', type(connection), connection, client_address)

        else:
            print('call remote AI')
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            port = importlib.import_module('remote').REMOTE_PORT
            connection.connect((remoteIP, port))
            ACK = connection.recv(3)
            assert(ACK == b'ACK')
            print('remote AI connection: ', connection, remoteIP)

        aiWrapper.init(connection)
        inputs = [connection]
        outputs = []

        if level != None:
            if level != -1:
                aiWrapper.actionBeginGame(level, match)
            else:
                aiWrapper.actionBeginAlternativeGame(match)

        print('waiting for the game to start')
        while not aiWrapper.isPlaying():
            time.sleep(3)

        while True:
            readable, writable, exceptional = select.select(inputs, outputs, inputs, 0.1)
            for s in readable:
                data = s.recv(1024)
                if data:
                    # A readable client socket has data
                    aiWrapper.recv(data)
                else:
                    # Interpret empty result as closed connection
                    print('closing server after reading no data')
                    return
            # Handle "exceptional conditions"
            for s in exceptional:
                print('handling exceptional condition for', s.getpeername())
                break
            aiWrapper.recvFromMajsoul()
            if aiWrapper.isEnd:
                aiWrapper.isEnd = False
                connection.close()
                if isRemoteMode == False:
                    AI.wait()
                aiWrapper.actionReturnToMenu()
                break


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="MajsoulAI")
    parser.add_argument('-r', '--remote_ip', default='')
    parser.add_argument('-i', '--input', default=1)
    parser.add_argument('-l', '--level', default=None)
    parser.add_argument('-m', '--match', default=0)
    args = parser.parse_args()
    input_ = AIInput(int(args.input))
    level = None if args.level == None else int(args.level)
    match = int(args.match)
    assert(input_ == AIInput.TenHou and match in range(0, 2) or input_ == AIInput.Mahjong)

    if args.remote_ip == '':
        # 本地AI模式
        MainLoop(input_=input_, level=level, match=match)
    else:
        # 远程AI模式
        MainLoop(isRemoteMode=True, remoteIP=args.remote_ip, input_=input_, level=level, match=match)