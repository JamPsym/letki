import ctypes
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from general_link import *
from general_program import compile_show


def fill(level=70,duration=1000):
    return compile_show(dict(duration_ms=duration,tracks=[dict(type='fill',levels=[level,level])]))

class GeneralTest(unittest.TestCase):
    def setUp(self):
        self.sim=Simulation();self.driver=Driver(self.sim)
    def tearDown(self): self.sim.close()
    def load_one(self,program,mode=1,policy=0):
        d=self.driver
        d.request(0,BEGIN,struct.pack('<BBHH',mode,policy,len(program),crc(program)))
        for at in range(0,len(program),46):d.request(0,WRITE,struct.pack('<H',at)+program[at:at+46])
        d.request(0,COMMIT)
    def test_wire_golden_crc_and_binary(self):
        self.assertEqual(crc(b'123456789'),0x29b1)
        self.assertEqual(packet(3,1,0x1234,0x5678,b'\0\xff').hex(),'09010103341278560204ff3c9900')
        for count in range(49):
            payload=bytes(range(count));wire=packet(4,5,22,31,payload)
            self.assertEqual(unpack(wire),(4,5,22,31,payload))
            array=ctypes.create_string_buffer(wire,60)
            used=self.sim.lib.lg_decode(array,len(wire)-1)
            self.assertTrue(used)
            out=ctypes.create_string_buffer(60)
            encoded=self.sim.lib.lg_encode(out,array,used)
            self.assertEqual(out.raw[:encoded],wire)
    def test_corruption_retries_missing_and_duplicates(self):
        self.sim.corrupt_once=True;self.driver.request(2,TIME)
        self.sim.drop_reply_once=True;self.driver.request(2,BRIGHTNESS,b'\x35')
        self.assertEqual(self.driver.info(2)['brightness'],53)
        self.sim.missing.add(3)
        with self.assertRaisesRegex(RuntimeError,'did not consume'):self.driver.request(3,TIME)
        wire=packet(0,BRIGHTNESS,self.driver.session,self.driver.sequences[0]+1,b'\x44')
        first=self.sim.exchange([wire]);second=self.sim.exchange([wire]);self.assertEqual(first,second)
        different=packet(0,BRIGHTNESS,self.driver.session,self.driver.sequences[0]+1,b'\x45')
        self.assertEqual(unpack(self.sim.exchange([different])[0])[-1][0],9)
    def test_ram_load_play_seek_pause_reconnect(self):
        program=compile_show(ROOT/'config/general/demo.json');self.driver.load(program)
        self.assertEqual(self.driver.read(2),program)
        self.driver.play(lead=250)
        self.assertFalse(any(map(any,self.sim.pixels())))
        a=self.sim.advance(1250)
        self.assertTrue(any(map(any,a)))
        self.driver.all(PAUSE);self.assertEqual(a,self.sim.advance(10000))
        other=Driver(self.sim);self.assertTrue(other.info(0)['paused'])
        other.seek(9000);b=self.sim.advance(20);self.assertNotEqual(a,b)
        other.play(position=1000,lead=0);self.assertEqual(a,self.sim.advance(20))
    def test_memory_reclaim_and_exact_fit(self):
        self.driver.all(QUEUE,b'\0')
        self.assertEqual(self.driver.info(0)['ram'],752)
        program=fill()+bytes(752-48)
        program=program[:4]+struct.pack('<H',752)+program[6:]
        self.driver.load(program)
        self.assertEqual(self.driver.read(0),program)
        with self.assertRaises(ProtocolError):self.driver.request(0,QUEUE,b'\x01')
        with self.assertRaises(ProtocolError):self.driver.request(0,BEGIN,struct.pack('<BBHH',0,0,48,0))
        self.driver.load(fill(20),replace='capacity');self.assertEqual(self.driver.info(0)['program_bytes'],48)
    def test_invalid_program_and_upload_preserve_current(self):
        old=fill();self.driver.load(old)
        invalid=bytearray(fill(40));invalid[16]=99
        self.driver.request(0,BEGIN,struct.pack('<BBHH',0,0,len(invalid),crc(invalid)))
        with self.assertRaises(ProtocolError):self.driver.request(0,WRITE,struct.pack('<H',5)+b'wrong')
        for at in range(0,len(invalid),46):self.driver.request(0,WRITE,struct.pack('<H',at)+invalid[at:at+46])
        with self.assertRaises(ProtocolError):self.driver.request(0,COMMIT)
        self.assertEqual(self.driver.read(0),old);self.driver.request(0,ABORT)
    def test_frames_formats_time_order_queue_backpressure_and_wrap(self):
        self.sim.now=0xfffffff0
        self.driver.synchronize()
        for fmt in ('mono1','gray4','level8'):
            self.driver.all(FLUSH)
            pixels=[bytes((i*17)%101 for i in range(64)) for _ in range(5)]
            before=self.sim.pixels()
            gen=self.driver.frame(pixels,self.sim.now+60,fmt)
            self.assertEqual(before,self.sim.advance(40))
            shown=self.sim.advance(20)
            expected=[100 if v else 0 for v in pixels[0]] if fmt=='mono1' else [((v*15+50)//100)*100//15 for v in pixels[0]] if fmt=='gray4' else pixels[0]
            self.assertEqual(shown[0],bytes(expected));self.assertEqual(self.driver.info(0)['presented'],gen)
        self.driver.frame(pixels,self.sim.now+100)
        self.driver.frame(pixels,self.sim.now+200)
        with self.assertRaises(ProtocolError):self.driver.frame(pixels,self.sim.now+300)
        self.assertEqual(self.driver.info(0)['queued'],2)
    def test_frame_partial_commit_and_invalid_level(self):
        gen=struct.pack('<H',99)
        self.driver.request(0,FRAME_BEGIN,gen+struct.pack('<IB',100,2))
        with self.assertRaises(ProtocolError):self.driver.request(0,FRAME_COMMIT,gen)
        with self.assertRaises(ProtocolError):self.driver.request(0,FRAME_DATA,gen+b'\0\xff')
        self.driver.request(0,FRAME_DATA,gen+b'\0'+bytes([20])*45)
        self.driver.request(0,FRAME_DATA,gen+bytes([45])+bytes([20])*19)
        self.driver.request(0,FRAME_COMMIT,gen)
        self.assertEqual(self.sim.advance(100)[0],bytes([20])*64)
    def test_persistent_boot_dual_slot_and_capacity(self):
        self.driver.load(fill(30),storage='flash')
        self.driver.load(fill(80),storage='flash')
        self.sim.reboot();self.driver=Driver(self.sim)
        self.assertEqual(self.sim.advance(40)[0],bytes([80])*64)
        self.assertEqual(self.driver.read(0),fill(80))
        self.driver.load(fill(50),storage='flash',replace='capacity')
        self.sim.reboot();self.driver=Driver(self.sim)
        self.assertEqual(self.sim.advance(40)[0],bytes([50])*64)
        with self.assertRaises(ProtocolError):self.driver.load(fill(60),storage='flash')
    def test_flash_power_loss_each_erase_and_program_byte(self):
        old,new=fill(30),fill(80)
        # 32 erase pages + 64 data bytes + 64 manifest bytes. Every interruption
        # point, including every byte of the validity manifest, is exercised.
        for cut in range(161):
            with self.subTest(cut=cut):
                self.sim.close();self.sim=Simulation();self.driver=Driver(self.sim)
                self.load_one(old)
                self.sim.fault(cut)
                try:self.load_one(new)
                except ProtocolError:pass
                self.sim.reboot();self.driver=Driver(self.sim)
                self.assertIn(self.driver.read(0),(old,new))
                self.assertIn(self.sim.advance(40)[0],(bytes([30])*64,bytes([80])*64))
    def test_long_loaded_show_and_independent_simulators(self):
        program=fill(40,duration=3600000);self.driver.load(program);self.driver.play(lead=0)
        second=Simulation();other=Driver(second);other.load(fill(80));other.play(lead=0)
        try:
            for tick in range(0,3600000,10000):
                self.sim.now=tick
                self.assertEqual(self.sim.pixels()[0],bytes([40])*64)
                self.assertEqual(second.pixels()[0],bytes([80])*64)
        finally:second.close()
    def test_fuzz_every_packet_bit_preserves_brightness(self):
        valid=packet(0,BRIGHTNESS,self.driver.session,self.driver.sequences[0]+1,b'\x01')
        for i in range(len(valid)-1):
            for bit in range(8):
                bad=bytearray(valid);bad[i]^=1<<bit
                self.sim.exchange([bytes(bad)])
        self.assertEqual(self.driver.info(0)['brightness'],100)

if __name__=='__main__':unittest.main()
