import os
from pathlib import Path
import pty
import sys
import subprocess
import termios
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import uart_chain


class ChainTests(unittest.TestCase):
    def test_python_requests_cross_two_real_c_nodes(self):
        fixture=Path(__file__).resolve().parents[1]/'build/tests/uart_chain_relay'
        if not fixture.exists(): self.fail('Run make test to build the real C relay fixture')
        requests=[(n,(0x12340000+n)&0xffffffff) for n in [0,1,42,255,256,0xa55a,0xffff]]
        traffic=''.join(uart_chain.encode(n,token)+'\r\n' for n,token in requests)
        result=subprocess.run([str(fixture)],input=traffic,text=True,capture_output=True,check=True)
        replies=result.stdout.splitlines()
        self.assertEqual(len(replies),len(requests))
        for line,(n,token) in zip(replies,requests):
            self.assertEqual(uart_chain.decode(line),dict(counter=n,token=token,hops=2,errors=0))

    def test_codec_and_crc(self):
        wire=uart_chain.encode(65535,0x1234abcd,2,0)
        self.assertEqual(len(wire),29)
        self.assertEqual(uart_chain.decode(wire),dict(counter=65535,token=0x1234abcd,hops=2,errors=0))
        for i in range(1,29):
            changed=wire[:i]+('0' if wire[i]!='0' else '1')+wire[i+1:]
            with self.assertRaises(ValueError): uart_chain.decode(changed)

    def exchange(self, mutate=None):
        master,slave=pty.openpty()
        before=termios.tcgetattr(slave)
        link=uart_chain.SerialLink(os.ttyname(slave),timeout=0.3)
        def relay():
            data=bytearray()
            while b'\n' not in data: data.extend(os.read(master,128))
            p=uart_chain.decode(data.decode().strip())
            p['hops']=2
            if mutate: mutate(p)
            response=uart_chain.encode(**p).encode()+b'\r\n'
            os.write(master,response[:8]); os.write(master,response[8:])
        worker=threading.Thread(target=relay); worker.start()
        try:
            return uart_chain.run_test(link,2,1,on_reply=lambda s:None)
        finally:
            link.close(); worker.join(timeout=1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(termios.tcgetattr(slave),before)
            os.close(master); os.close(slave)

    def test_real_tty_fragmentation_and_cleanup(self):
        self.assertEqual(self.exchange()['result'],'PASS')

    def test_stale_payload_wrong_hops_and_diagnostics_fail(self):
        for mutate in [lambda p:p.update(token=p['token']^1),
                       lambda p:p.update(counter=p['counter']^1),
                       lambda p:p.update(hops=1),lambda p:p.update(errors=1)]:
            with self.assertRaises(RuntimeError): self.exchange(mutate)

    def test_missing_response_fails(self):
        master,slave=pty.openpty(); link=uart_chain.SerialLink(os.ttyname(slave),timeout=0.05)
        try:
            with self.assertRaises(TimeoutError): uart_chain.run_test(link,2,1,on_reply=lambda s:None)
        finally:
            link.close(); os.close(master); os.close(slave)


if __name__=='__main__': unittest.main()
