import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import termios
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from general_link import Simulation,Serial,Driver,TIME,BRIGHTNESS,STATUS,packet

class SerialBurstTest(unittest.TestCase):
    def link(self):
        link=object.__new__(Serial)
        link.raw=SimpleNamespace(fd=-1,_write=lambda data: None)
        link.buffer=bytearray();link.discard=False
        link.diagnostics=dict(exchanges=0,timeouts=0,invalid_replies=0)
        return link
    def test_coalesced_maximum_replies_and_partial_tail(self):
        requests=[packet(i,STATUS,123,1) for i in range(5)]
        replies=[packet(i,STATUS|128,123,1,b'\0'*48) for i in range(5)]
        self.assertTrue(all(len(reply)==60 for reply in replies))
        burst=b''.join(replies)
        with patch('general_link.select.select',return_value=([-1],[],[])), patch('general_link.os.read',side_effect=[burst[:256],burst[256:]]):
            self.assertEqual(self.link().exchange(requests),replies)
    def test_overlong_tail_discards_through_delimiter(self):
        request=packet(0,STATUS,123,1)
        reply=packet(0,STATUS|128,123,1,b'\0'*48)
        # The first reply is the suffix of an overlong frame, not a valid one.
        chunks=[b'x'*100,reply,reply]
        with patch('general_link.select.select',return_value=([-1],[],[])), patch('general_link.os.read',side_effect=chunks) as read:
            self.assertEqual(self.link().exchange([request]),[reply])
            self.assertEqual(read.call_count,3)

class SerialTest(unittest.TestCase):
    def setUp(self):
        self.master,self.slave=pty.openpty();self.port=os.ttyname(self.slave)
        self.original=termios.tcgetattr(self.slave);self.stop=threading.Event()
        self.sim=Simulation();self.drop=False;self.buffer=bytearray();self.clock=time.monotonic()
        self.thread=threading.Thread(target=self.run_board,daemon=True);self.thread.start()
        self.fuser=patch('general_link.subprocess.run',return_value=subprocess.CompletedProcess([],1,b'',b''));self.fuser.start()
    def tearDown(self):
        self.stop.set();self.thread.join(2);self.fuser.stop();os.close(self.master);os.close(self.slave);self.sim.close()
    def run_board(self):
        while not self.stop.is_set():
            if not select.select([self.master],[],[],.02)[0]:continue
            try:data=os.read(self.master,4096)
            except OSError:return
            self.buffer.extend(data)
            while 0 in self.buffer:
                packet,_,rest=self.buffer.partition(b'\0');self.buffer=bytearray(rest)
                if not packet:continue
                self.sim.now=round((time.monotonic()-self.clock)*1000)
                replies=self.sim.exchange([bytes(packet)+b'\0'])
                if self.drop:self.drop=False;continue
                for reply in replies:
                    # Fragmented USB reads, arbitrary embedded zero payloads,
                    # an old duplicate response and frame-boundary recovery.
                    os.write(self.master,reply[:3]);os.write(self.master,reply[3:])
    def test_real_serial_driver_cleanup_binary_and_retries(self):
        link=Serial(self.port)
        try:
            driver=Driver(link)
            driver.all(BRIGHTNESS,b'\0')
            self.assertTrue(all(driver.info(i)['brightness']==0 for i in range(5)))
            self.drop=True
            self.assertTrue(driver.request(3,TIME,timeout=.08))
            self.assertEqual(len(driver.batch([(i,STATUS,b'') for i in range(5)])),5)
        finally:link.close()
        self.assertEqual(termios.tcgetattr(self.slave),self.original)
    def test_device_errors_do_not_leak_exclusive_connection(self):
        link=Serial(self.port)
        try:
            driver=Driver(link)
            from general_link import ProtocolError
            with self.assertRaises(ProtocolError):driver.request(0,BRIGHTNESS,b'\xff')
        finally:link.close()
        another=Serial(self.port);another.close()
        self.assertEqual(termios.tcgetattr(self.slave),self.original)
    def test_busy_terminal_is_reported_without_touching_it(self):
        self.fuser.stop()
        with self.assertRaisesRegex(RuntimeError,'Close picocom'):Serial(self.port)
        self.fuser.start()
        self.assertEqual(termios.tcgetattr(self.slave),self.original)

if __name__=='__main__':unittest.main()
